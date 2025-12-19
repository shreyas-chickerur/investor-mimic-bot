#!/usr/bin/env python3

# Standard library imports
import argparse
import json
import os
import re
import sys
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Dict

# Third-party imports
from dotenv import load_dotenv

# Add project root to path
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# Third-party imports (after path setup)
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockLatestTradeRequest
from alpaca.trading.client import TradingClient

# Local application imports
from services.execution.planner import TradePlanner, TradePlannerConfig
from services.strategy.conviction_engine import ConvictionConfig, ConvictionEngine
from services.strategy.risk import RiskConstraints, apply_risk_constraints


def _bool_env(name: str, default: bool) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return v.strip().lower() in {"1", "true", "yes", "y", "on"}


def _to_date(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def _as_decimal(v) -> Decimal:
    return Decimal(str(v))


def _latest_prices(data_client, symbols) -> Dict[str, Decimal]:
    if not symbols:
        return {}

    valid_re = re.compile(r"^[A-Z]{1,5}$")
    valid = [str(s).upper() for s in symbols if s and valid_re.match(str(s).upper())]
    if not valid:
        return {}

    out: Dict[str, Decimal] = {}

    try:
        req = StockLatestTradeRequest(symbol_or_symbols=valid)
        resp = data_client.get_stock_latest_trade(req)
        for sym, trade in resp.items():
            px = getattr(trade, "price", None)
            if px is not None:
                out[str(sym)] = _as_decimal(px)
        return out
    except Exception:
        # Fallback: request per symbol to skip any remaining invalid symbols.
        for sym in valid:
            try:
                req = StockLatestTradeRequest(symbol_or_symbols=sym)
                resp = data_client.get_stock_latest_trade(req)
                trade = resp.get(sym)
                if trade is None:
                    continue
                px = getattr(trade, "price", None)
                if px is not None:
                    out[sym] = _as_decimal(px)
            except Exception:
                continue
        return out


def _symbol_map(path: str) -> Dict[str, str]:
    if not path:
        return {}
    data = json.loads(Path(path).read_text())
    if not isinstance(data, dict):
        return {}
    return {str(k): str(v) for k, v in data.items() if k and v}


def main() -> int:
    load_dotenv()

    parser = argparse.ArgumentParser()
    parser.add_argument("--as-of", default=date.today().isoformat())
    parser.add_argument(
        "--db-url",
        default=os.getenv("DATABASE_URL", "postgresql://postgres@localhost:5432/investorbot"),
    )
    parser.add_argument("--symbol-map", default="data/ticker_cache/openfigi_cusip_to_ticker.json")
    parser.add_argument("--paper", action="store_true")
    parser.add_argument("--use-buying-power", action="store_true")

    parser.add_argument("--lookback-days", type=int, default=365)
    parser.add_argument("--half-life-days", type=int, default=90)
    parser.add_argument("--max-positions", type=int, default=20)

    parser.add_argument("--max-position", type=float, default=0.10)
    parser.add_argument("--max-sector", type=float, default=0.30)
    parser.add_argument("--cash-buffer", type=float, default=0.10)

    parser.add_argument("--limit-offset-bps", type=int, default=10)
    parser.add_argument("--min-trade-notional", type=str, default="10")
    parser.add_argument("--share-increment", type=str, default="0.0001")

    args = parser.parse_args()

    paper = bool(args.paper) or _bool_env("PAPER_TRADING", True)

    api_key = os.getenv("ALPACA_API_KEY")
    secret_key = os.getenv("ALPACA_SECRET_KEY")
    if not api_key or not secret_key:
        raise RuntimeError("Missing ALPACA_API_KEY/ALPACA_SECRET_KEY")

    trading = TradingClient(api_key, secret_key, paper=paper)
    data = StockHistoricalDataClient(api_key, secret_key)

    acct = trading.get_account()
    cash = _as_decimal(getattr(acct, "cash", "0"))
    buying_power = _as_decimal(getattr(acct, "buying_power", cash))
    total_equity = buying_power if args.use_buying_power else cash

    engine = ConvictionEngine(
        db_url=str(args.db_url).replace("postgresql+asyncpg://", "postgresql://", 1)
    )
    alloc = engine.allocations(
        as_of=_to_date(args.as_of),
        lookback_days=int(args.lookback_days),
        cfg=ConvictionConfig(
            recency_half_life_days=int(args.half_life_days), max_positions=int(args.max_positions)
        ),
    )

    m = _symbol_map(args.symbol_map)
    if not alloc.empty:
        alloc["ticker"] = alloc["ticker"].apply(lambda s: m.get(str(s), str(s)))

    constrained = apply_risk_constraints(
        alloc,
        constraints=RiskConstraints(
            max_position_weight=float(args.max_position),
            max_sector_weight=float(args.max_sector),
            cash_buffer_weight=float(args.cash_buffer),
        ),
    )

    target_weights: Dict[str, Decimal] = {}
    for _, r in constrained.iterrows():
        sym = str(r["ticker"])
        if sym == "CASH":
            continue
        target_weights[sym] = _as_decimal(r["normalized_weight"])

    current_positions = {str(p.symbol): _as_decimal(p.qty) for p in trading.get_all_positions()}

    symbols = sorted(set(target_weights.keys()))
    prices = _latest_prices(data, symbols)

    planner = TradePlanner(
        TradePlannerConfig(
            share_increment=Decimal(args.share_increment),
            min_trade_notional=Decimal(args.min_trade_notional),
        )
    )

    plan = planner.generate_buy_plan(
        target_weights=target_weights,
        prices=prices,
        current_positions=current_positions,
        total_equity=total_equity,
        limit_offset_bps=int(args.limit_offset_bps),
    )

    print(
        json.dumps(
            {
                "paper": paper,
                "total_equity": str(total_equity),
                "orders": len(plan.orders),
                "skipped": len(plan.skipped),
            }
        )
    )
    for o in plan.orders:
        print(
            json.dumps(
                {
                    "symbol": o.symbol,
                    "side": o.side,
                    "qty": str(o.qty),
                    "limit_price": str(o.limit_price),
                    "notional": str(o.notional),
                }
            )
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
