import argparse
import json
import logging
import math
import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from services.strategy.conviction_engine import ConvictionConfig, ConvictionEngine
from services.strategy.prices import SyntheticPriceProvider, default_price_provider

logger = logging.getLogger(__name__)


def _to_date(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def _load_symbol_map(path: Optional[str]) -> Dict[str, str]:
    """Load a mapping of internal symbols (often CUSIP) -> ticker for pricing.

    This is optional and opt-in. If not provided, the backtest uses the symbols
    produced by the conviction engine as-is.
    """
    if not path:
        return {}
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"symbol map file not found: {path}")
    data = json.loads(p.read_text())
    if not isinstance(data, dict):
        raise ValueError("symbol map JSON must be an object/dict")
    out: Dict[str, str] = {}
    for k, v in data.items():
        if not k or not v:
            continue
        out[str(k)] = str(v)
    return out


def _apply_symbol_map(symbols: List[str], symbol_map: Dict[str, str]) -> List[str]:
    if not symbol_map:
        return symbols
    return [symbol_map.get(s, s) for s in symbols]


def _next_business_day(d: date) -> date:
    # very small helper; doesn't handle holidays
    while d.weekday() >= 5:
        d = d + timedelta(days=1)
    return d


def _portfolio_value(positions: Dict[str, float], cash: float, prices: pd.Series) -> float:
    v = float(cash)
    for t, sh in positions.items():
        if t in prices.index and pd.notna(prices[t]):
            v += float(sh) * float(prices[t])
    return v


def _compute_trades(
    current_positions: Dict[str, float],
    target_weights: Dict[str, float],
    total_value: float,
    prices: pd.Series,
    txn_cost_bps: float,
) -> Tuple[Dict[str, float], float, List[Dict]]:
    """Rebalance to target weights at given prices.

    Returns (new_positions, new_cash, trades)
    """

    txn_cost = float(txn_cost_bps) / 10_000.0

    # Target dollar value per ticker.
    targets_value = {t: float(w) * float(total_value) for t, w in target_weights.items()}

    # Compute current dollar values.
    current_value = {}
    for t, sh in current_positions.items():
        if t in prices.index and pd.notna(prices[t]):
            current_value[t] = float(sh) * float(prices[t])

    # Sell tickers not in target.
    positions = dict(current_positions)
    cash_delta = 0.0
    trades: List[Dict] = []

    for t in list(positions.keys()):
        if t not in targets_value:
            if t not in prices.index or pd.isna(prices[t]):
                continue
            px = float(prices[t])
            sh = float(positions.pop(t))
            proceeds = sh * px
            cost = proceeds * txn_cost
            cash_delta += proceeds - cost
            trades.append({"ticker": t, "shares": -sh, "price": px, "notional": proceeds, "fee": cost})

    # Recompute total value after sells (cash increases).
    cash = cash_delta

    # Compute trades for tickers in target.
    for t, tgt_val in targets_value.items():
        if t not in prices.index or pd.isna(prices[t]):
            continue
        px = float(prices[t])
        cur_val = current_value.get(t, 0.0)
        delta = float(tgt_val) - float(cur_val)
        if abs(delta) < 1.0:
            continue

        sh = delta / px
        if sh > 0:
            # buy
            notional = sh * px
            fee = notional * txn_cost
            cash -= notional + fee
            positions[t] = float(positions.get(t, 0.0)) + sh
            trades.append({"ticker": t, "shares": sh, "price": px, "notional": notional, "fee": fee})
        else:
            # sell
            sh = abs(sh)
            have = float(positions.get(t, 0.0))
            sh = min(sh, have)
            if sh <= 0:
                continue
            notional = sh * px
            fee = notional * txn_cost
            cash += notional - fee
            new_sh = have - sh
            if new_sh <= 1e-9:
                positions.pop(t, None)
            else:
                positions[t] = new_sh
            trades.append({"ticker": t, "shares": -sh, "price": px, "notional": notional, "fee": fee})

    return positions, cash, trades


def run_backtest(
    *,
    engine: ConvictionEngine,
    start: date,
    end: date,
    rebalance_days: int,
    lookback_days: int,
    half_life_days: int,
    max_positions: int,
    initial_capital: float,
    txn_cost_bps: float,
    use_synthetic_prices: bool,
    symbol_map: Optional[Dict[str, str]],
    results_dir: Path,
) -> Dict:
    results_dir.mkdir(parents=True, exist_ok=True)

    # Prepare rebalance schedule.
    rebal_dates: List[date] = []
    d = start
    while d <= end:
        rebal_dates.append(_next_business_day(d))
        d = d + timedelta(days=int(rebalance_days))

    cfg = ConvictionConfig(recency_half_life_days=int(half_life_days), max_positions=int(max_positions))

    # We'll fetch prices over full interval for all tickers encountered.
    # First pass: get tickers per rebalance.
    allocations_by_date: Dict[str, pd.DataFrame] = {}
    all_tickers: List[str] = []

    for d in rebal_dates:
        alloc = engine.allocations(as_of=d, lookback_days=int(lookback_days), cfg=cfg)
        allocations_by_date[d.isoformat()] = alloc
        if not alloc.empty:
            all_tickers.extend([t for t in alloc["ticker"].tolist() if t])

    all_tickers = sorted(set(all_tickers))

    # Optional mapping for price symbols (e.g., CUSIP -> TICKER)
    symbol_map = symbol_map or {}
    priced_symbols = _apply_symbol_map(all_tickers, symbol_map)

    # Price provider
    provider = SyntheticPriceProvider() if use_synthetic_prices else default_price_provider()

    # If we have no tickers (e.g., DB only has private CUSIPs), still run a cash-only backtest.
    prices = provider.get_prices(priced_symbols, start=start, end=end)

    # If prices empty but tickers exist, fall back to synthetic.
    if priced_symbols and prices.empty and not use_synthetic_prices:
        logger.warning("Price provider returned no data; falling back to synthetic prices")
        provider = SyntheticPriceProvider()
        prices = provider.get_prices(priced_symbols, start=start, end=end)

    positions: Dict[str, float] = {}
    cash: float = float(initial_capital)

    history_rows: List[Dict] = []
    trade_rows: List[Dict] = []

    # We'll evaluate portfolio value daily on business days.
    if prices.empty:
        idx = pd.date_range(start=start, end=end, freq="B")
        prices = pd.DataFrame(index=idx)

    # Run day-by-day, rebalance when date matches.
    rebal_set = set(rebal_dates)

    for ts in prices.index:
        day = ts.date()
        day_prices = prices.loc[ts] if ts in prices.index else pd.Series(dtype=float)

        if day in rebal_set:
            alloc = allocations_by_date.get(day.isoformat())
            if alloc is None or alloc.empty:
                # no target => hold cash
                target_weights = {}
            else:
                target_weights = {}
                for _, r in alloc.iterrows():
                    sym = symbol_map.get(r["ticker"], r["ticker"])
                    # If we have no price for this symbol on this day, skip it (weight implicitly stays in cash).
                    if sym not in day_prices.index or pd.isna(day_prices.get(sym)):
                        continue
                    target_weights[sym] = float(r["normalized_weight"])

            total_val = _portfolio_value(positions, cash, day_prices)
            new_positions, cash_change, trades = _compute_trades(
                positions, target_weights, total_val, day_prices, txn_cost_bps
            )
            positions = new_positions
            cash = cash + cash_change

            for tr in trades:
                tr2 = dict(tr)
                tr2["date"] = day.isoformat()
                trade_rows.append(tr2)

        pv = _portfolio_value(positions, cash, day_prices)
        history_rows.append({"date": day.isoformat(), "value": pv, "cash": cash, "positions": len(positions)})

    history = pd.DataFrame(history_rows)
    trades = pd.DataFrame(trade_rows)

    # Metrics
    history["return"] = history["value"].pct_change().fillna(0.0)
    history["cum_return"] = (1.0 + history["return"]).cumprod() - 1.0

    total_return = float(history["value"].iloc[-1] / history["value"].iloc[0] - 1.0) if len(history) else 0.0
    daily_vol = float(history["return"].std()) if len(history) > 2 else 0.0
    ann_vol = daily_vol * math.sqrt(252.0) if daily_vol > 0 else 0.0

    # naive CAGR
    days = (end - start).days
    years = max(days / 365.25, 1e-9)
    cagr = float((history["value"].iloc[-1] / history["value"].iloc[0]) ** (1.0 / years) - 1.0) if len(history) else 0.0

    # drawdown
    values = history["value"].astype(float)
    running_max = values.cummax()
    dd = values / running_max - 1.0
    max_drawdown = float(dd.min()) if len(dd) else 0.0

    sharpe = float(cagr / ann_vol) if ann_vol > 0 else 0.0

    metrics = {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "initial_capital": float(initial_capital),
        "final_value": float(history["value"].iloc[-1]) if len(history) else float(initial_capital),
        "total_return": total_return,
        "cagr": cagr,
        "annualized_volatility": ann_vol,
        "sharpe": sharpe,
        "max_drawdown": max_drawdown,
        "rebalance_days": int(rebalance_days),
        "lookback_days": int(lookback_days),
        "half_life_days": int(half_life_days),
        "max_positions": int(max_positions),
        "txn_cost_bps": float(txn_cost_bps),
        "used_synthetic_prices": bool(use_synthetic_prices or isinstance(provider, SyntheticPriceProvider)),
        "unique_tickers": int(len(all_tickers)),
        "unique_priced_symbols": int(len(set(priced_symbols))),
        "trades": int(len(trades)),
    }

    # Write outputs
    history.to_csv(results_dir / "history.csv", index=False)
    trades.to_csv(results_dir / "trades.csv", index=False)
    (results_dir / "metrics.json").write_text(json.dumps(metrics, indent=2))

    # Also dump allocations used each rebalance so you can inspect conviction outputs.
    alloc_dump = {}
    for k, df in allocations_by_date.items():
        alloc_dump[k] = df.to_dict(orient="records") if df is not None else []
    (results_dir / "allocations.json").write_text(json.dumps(alloc_dump, indent=2, default=str))

    return {"metrics": metrics, "history": history, "trades": trades}


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    parser = argparse.ArgumentParser(description="Backtest 13F conviction strategy")
    parser.add_argument("--start", default="2024-01-01")
    parser.add_argument("--end", default=date.today().isoformat())
    parser.add_argument("--rebalance-days", type=int, default=30)
    parser.add_argument("--lookback-days", type=int, default=365)
    parser.add_argument("--half-life-days", type=int, default=90)
    parser.add_argument("--max-positions", type=int, default=20)
    parser.add_argument("--initial-capital", type=float, default=1_000_000.0)
    parser.add_argument("--txn-cost-bps", type=float, default=10.0, help="Transaction cost in bps")
    parser.add_argument(
        "--synthetic-prices",
        action="store_true",
        help="Use synthetic prices instead of downloading from Stooq",
    )
    parser.add_argument(
        "--symbol-map",
        default=None,
        help="Optional path to JSON mapping internal symbols (e.g. CUSIP) -> ticker for pricing",
    )
    parser.add_argument("--db-url", default=None)
    parser.add_argument("--results-dir", default="data/backtest/results")

    args = parser.parse_args()

    engine = ConvictionEngine(db_url=args.db_url)

    symbol_map = _load_symbol_map(args.symbol_map)

    res = run_backtest(
        engine=engine,
        start=_to_date(args.start),
        end=_to_date(args.end),
        rebalance_days=args.rebalance_days,
        lookback_days=args.lookback_days,
        half_life_days=args.half_life_days,
        max_positions=args.max_positions,
        initial_capital=args.initial_capital,
        txn_cost_bps=args.txn_cost_bps,
        use_synthetic_prices=bool(args.synthetic_prices),
        symbol_map=symbol_map,
        results_dir=Path(args.results_dir),
    )

    print(json.dumps(res["metrics"], indent=2))


if __name__ == "__main__":
    main()
