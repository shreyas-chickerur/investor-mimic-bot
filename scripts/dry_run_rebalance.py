#!/usr/bin/env python3

import argparse
import json
import os
import sys
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Dict, Optional

from dotenv import load_dotenv

# Allow running as a script from repo root
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from services.strategy.allocation import weights_to_dollars_and_shares
from services.strategy.conviction_engine import ConvictionConfig, ConvictionEngine
from services.strategy.risk import RiskConstraints, apply_risk_constraints


def _to_date(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def _normalize_db_url(db_url: str) -> str:
    if db_url.startswith("postgresql+asyncpg://"):
        return db_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    return db_url


def _load_symbol_map(path: Optional[str]) -> Dict[str, str]:
    if not path:
        return {}
    p = Path(path)
    data = json.loads(p.read_text())
    if not isinstance(data, dict):
        return {}
    out: Dict[str, str] = {}
    for k, v in data.items():
        if not k or not v:
            continue
        out[str(k)] = str(v)
    return out


def _as_decimal(v) -> Decimal:
    return Decimal(str(v))


def _alpaca_clients(paper: bool):
    api_key = os.getenv("ALPACA_API_KEY")
    secret_key = os.getenv("ALPACA_SECRET_KEY")
    if not api_key or not secret_key:
        raise RuntimeError("Missing ALPACA_API_KEY/ALPACA_SECRET_KEY")

    from alpaca.trading.client import TradingClient

    trading = TradingClient(api_key, secret_key, paper=paper)

    data = None
    try:
        from alpaca.data.historical import StockHistoricalDataClient

        data = StockHistoricalDataClient(api_key, secret_key)
    except Exception:
        data = None

    return trading, data


def _submit_market_order(
    trading_client, *, symbol: str, side: str, qty: Optional[Decimal], notional: Optional[Decimal]
):
    from alpaca.trading.enums import OrderSide, TimeInForce
    from alpaca.trading.requests import MarketOrderRequest

    if side not in {"buy", "sell"}:
        raise ValueError(f"Invalid side: {side}")

    order = MarketOrderRequest(
        symbol=symbol,
        side=OrderSide.BUY if side == "buy" else OrderSide.SELL,
        time_in_force=TimeInForce.DAY,
        qty=float(qty) if qty is not None else None,
        notional=float(notional) if notional is not None else None,
    )
    return trading_client.submit_order(order_data=order)


def _latest_prices(data_client, symbols) -> Dict[str, Decimal]:
    if data_client is None:
        return {}

    symbols = [s for s in symbols if s and s.isalpha() and len(s) <= 5]
    if not symbols:
        return {}

    prices: Dict[str, Decimal] = {}

    try:
        from alpaca.data.requests import StockLatestTradeRequest

        resp = data_client.get_stock_latest_trade(StockLatestTradeRequest(symbol_or_symbols=symbols))
        for sym, trade in resp.items():
            px = getattr(trade, "price", None)
            if px is not None:
                prices[str(sym)] = _as_decimal(px)
    except Exception:
        pass

    if prices:
        return prices

    try:
        from alpaca.data.requests import StockLatestBarRequest

        resp = data_client.get_stock_latest_bar(StockLatestBarRequest(symbol_or_symbols=symbols))
        for sym, bar in resp.items():
            px = getattr(bar, "close", None)
            if px is not None:
                prices[str(sym)] = _as_decimal(px)
    except Exception:
        pass

    return prices


def _positions_by_symbol(trading_client) -> Dict[str, Decimal]:
    out: Dict[str, Decimal] = {}
    for p in trading_client.get_all_positions():
        sym = getattr(p, "symbol", None)
        qty = getattr(p, "qty", None)
        if sym is None or qty is None:
            continue
        out[str(sym)] = _as_decimal(qty)
    return out


def main() -> int:
    load_dotenv()

    parser = argparse.ArgumentParser(description="Dry-run rebalance: strategy -> target orders (no trades)")
    parser.add_argument("--as-of", default=date.today().isoformat())
    parser.add_argument("--lookback-days", type=int, default=365)
    parser.add_argument("--half-life-days", type=int, default=90)
    parser.add_argument("--max-positions", type=int, default=20)

    parser.add_argument("--max-position", type=float, default=0.10)
    parser.add_argument("--max-sector", type=float, default=0.30)
    parser.add_argument("--cash-buffer", type=float, default=0.10)

    parser.add_argument("--min-trade-dollars", type=str, default="10.00")
    parser.add_argument("--share-increment", type=str, default="0.0001")

    parser.add_argument("--symbol-map", default="data/ticker_cache/openfigi_cusip_to_ticker.json")
    parser.add_argument(
        "--db-url",
        default=os.getenv("DATABASE_URL", "postgresql://postgres@localhost:5432/investorbot"),
    )
    parser.add_argument("--paper", action="store_true")
    parser.add_argument("--use-buying-power", action="store_true")

    # Execution (opt-in)
    parser.add_argument("--execute", action="store_true", help="Place orders (paper only by default)")
    parser.add_argument(
        "--confirm",
        default="",
        help="Required confirmation token to execute. Use: --confirm EXECUTE_PAPER",
    )
    parser.add_argument("--max-orders", type=int, default=30)
    parser.add_argument("--max-total-notional", type=str, default="25000")
    parser.add_argument("--max-order-notional", type=str, default="5000")
    parser.add_argument(
        "--allowlist",
        type=str,
        default="",
        help="Comma-separated list of symbols allowed to trade (optional)",
    )
    parser.add_argument(
        "--allow-live",
        action="store_true",
        help="Allow execution when PAPER_TRADING is false (still requires --confirm EXECUTE_LIVE)",
    )

    args = parser.parse_args()

    paper = bool(args.paper) or str(os.getenv("PAPER_TRADING", "true")).lower() in {
        "1",
        "true",
        "yes",
        "y",
        "on",
    }

    trading, data = _alpaca_clients(paper)
    account = trading.get_account()

    if getattr(account, "trading_blocked", False):
        raise RuntimeError("Alpaca account is trading_blocked=true")

    cash = _as_decimal(getattr(account, "cash", "0"))
    buying_power = _as_decimal(getattr(account, "buying_power", cash))
    capital = buying_power if args.use_buying_power else cash

    engine = ConvictionEngine(db_url=_normalize_db_url(args.db_url))
    alloc = engine.allocations(
        as_of=_to_date(args.as_of),
        lookback_days=int(args.lookback_days),
        cfg=ConvictionConfig(recency_half_life_days=int(args.half_life_days), max_positions=int(args.max_positions)),
    )

    symbol_map = _load_symbol_map(args.symbol_map)
    if not alloc.empty:
        alloc["ticker"] = alloc["ticker"].apply(lambda s: symbol_map.get(str(s), str(s)))

    constrained = apply_risk_constraints(
        alloc,
        constraints=RiskConstraints(
            max_position_weight=float(args.max_position),
            max_sector_weight=float(args.max_sector),
            cash_buffer_weight=float(args.cash_buffer),
        ),
    )

    target_symbols = [s for s in constrained["ticker"].tolist() if s and s != "CASH"]
    prices = _latest_prices(data, target_symbols)

    orders = weights_to_dollars_and_shares(
        constrained.rename(columns={"normalized_weight": "normalized_weight"}),
        available_capital=capital,
        prices=prices,
        allow_fractional=True,
        share_increment=Decimal(args.share_increment),
        min_trade_dollars=Decimal(args.min_trade_dollars),
    )

    current = _positions_by_symbol(trading)

    proposed = []
    for _, row in orders.iterrows():
        sym = row["ticker"]
        if sym == "CASH":
            continue
        tgt_sh = row["shares"]
        px = row["price"]
        if tgt_sh is None or px is None:
            continue
        tgt_sh = _as_decimal(tgt_sh)
        cur_sh = current.get(sym, Decimal("0"))
        delta = tgt_sh - cur_sh
        if delta.copy_abs() <= Decimal(args.share_increment):
            continue
        side = "buy" if delta > 0 else "sell"
        qty = delta.copy_abs()
        notional = (qty * _as_decimal(px)).quantize(Decimal("0.01"))
        if notional < Decimal(args.min_trade_dollars):
            continue
        proposed.append(
            {
                "symbol": sym,
                "side": side,
                "qty": str(qty),
                "est_price": str(px).strip(),
                "est_notional": str(notional),
                "current_qty": str(cur_sh),
                "target_qty": str(tgt_sh),
            }
        )

    print("DRY RUN (no trades placed)")
    print(f"paper={paper}")
    print(f"cash={cash} buying_power={buying_power} capital_used={capital}")
    print(f"as_of={args.as_of} lookback_days={args.lookback_days} max_positions={args.max_positions}")
    print(f"tickers_with_prices={len(prices)}/{len(set(target_symbols))}")
    print("--- Proposed Orders ---")
    if not proposed:
        print("No orders (already close to target or missing prices)")
        return 0

    for o in proposed:
        print(json.dumps(o))

    if not args.execute:
        return 0

    # ---- Execution guardrails ----
    allowlist = {s.strip().upper() for s in (args.allowlist.split(",") if args.allowlist else []) if s.strip()}
    filtered = []
    for o in proposed:
        if allowlist and o["symbol"].upper() not in allowlist:
            continue
        filtered.append(o)

    if not filtered:
        print("No orders remain after allowlist filter")
        return 0

    max_total = Decimal(args.max_total_notional)
    max_one = Decimal(args.max_order_notional)
    total_notional = sum(Decimal(o["est_notional"]) for o in filtered)

    if len(filtered) > int(args.max_orders):
        raise RuntimeError(f"Refusing to execute: {len(filtered)} orders exceeds --max-orders={args.max_orders}")
    if total_notional > max_total:
        raise RuntimeError(
            f"Refusing to execute: total notional {total_notional} exceeds --max-total-notional={max_total}"
        )
    if any(Decimal(o["est_notional"]) > max_one for o in filtered):
        raise RuntimeError(f"Refusing to execute: an order exceeds --max-order-notional={max_one}")

    # Confirm token check
    if paper:
        required = "EXECUTE_PAPER"
    else:
        if not args.allow_live:
            raise RuntimeError("Refusing to execute in live mode without --allow-live")
        required = "EXECUTE_LIVE"

    if str(args.confirm).strip() != required:
        raise RuntimeError(f"Missing/incorrect confirmation token. Required: --confirm {required}")

    print("--- EXECUTING ORDERS ---")
    submitted = []
    for o in filtered:
        sym = o["symbol"]
        side = o["side"]
        qty = Decimal(o["qty"])
        notional = Decimal(o["est_notional"])

        # Alpaca supports fractional. For BUY, using notional is typically more reliable; for SELL, use qty.
        submit_qty: Optional[Decimal] = None
        submit_notional: Optional[Decimal] = None
        if side == "buy":
            submit_notional = notional
        else:
            submit_qty = qty

        resp = _submit_market_order(
            trading,
            symbol=sym,
            side=side,
            qty=submit_qty,
            notional=submit_notional,
        )
        submitted.append({"symbol": sym, "side": side, "id": str(getattr(resp, "id", ""))})

    print("Submitted orders:")
    for s in submitted:
        print(json.dumps(s))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
