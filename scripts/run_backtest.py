#!/usr/bin/env python3
"""
Run walk-forward portfolio backtest against historical data.

Usage:
    python scripts/run_backtest.py [--years N] [--capital N]
    python scripts/run_backtest.py --per-strategy [--years N] [--capital N]

Outputs results to console and saves to artifacts/backtest/
"""
import argparse
import json
import logging
import os
import sys
from pathlib import Path

# Project root
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd

from src.integration.portfolio_backtester import PortfolioBacktester
from src.strategies.strategy_earnings_drift import EarningsDriftStrategy
from src.strategies.strategy_factor_momentum import FactorMomentumStrategy
from src.strategies.strategy_ma_crossover import MACrossoverStrategy
from src.strategies.strategy_ml_momentum import MLMomentumStrategy
from src.strategies.strategy_news_sentiment import NewsSentimentStrategy
from src.strategies.strategy_rsi_mean_reversion import RSIMeanReversionStrategy
from src.strategies.strategy_sector_rotation import SectorRotationStrategy
from src.strategies.strategy_volatility_breakout import VolatilityBreakoutStrategy

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def load_market_data(data_path: str = "data/training_data.csv") -> pd.DataFrame:
    """Load and prepare market data."""
    print(f"Loading market data from {data_path}...")
    df = pd.read_csv(data_path, index_col=0)
    df.index = pd.to_datetime(df.index)
    df.sort_index(inplace=True)

    print(f"  Symbols: {df['symbol'].nunique()}")
    print(f"  Date range: {df.index.min().date()} to {df.index.max().date()}")
    print(f"  Rows: {len(df):,}")
    return df


def main():
    parser = argparse.ArgumentParser(description="Walk-forward portfolio backtest")
    parser.add_argument("--years", type=int, default=5, help="Years of test data (default 5)")
    parser.add_argument(
        "--capital", type=float, default=100000, help="Initial capital (default 100000)"
    )
    parser.add_argument(
        "--train-days",
        type=int,
        default=252,
        help="Training window in trading days (default 252 ~1yr)",
    )
    parser.add_argument(
        "--test-days", type=int, default=63, help="Test window in trading days (default 63 ~3mo)"
    )
    parser.add_argument(
        "--step-days", type=int, default=63, help="Step size in trading days (default 63 ~3mo)"
    )
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    parser.add_argument(
        "--per-strategy",
        action="store_true",
        help="Run each strategy in isolation and compare results side-by-side",
    )
    parser.add_argument(
        "--data",
        default="data/training_data.csv",
        help="Market data CSV (use data/extended_historical_data.csv for the 15yr evidence base)",
    )
    parser.add_argument(
        "--legacy",
        action="store_true",
        help="Use the legacy synthetic gates (0.60 confidence floor, 3 buys/day, "
        "10d cooldown, 5x static stop) instead of production-parity settings",
    )
    parser.add_argument(
        "--set",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="In-memory config override for parameter sweeps, e.g. "
        "--set strategies.rsi_mean_reversion.rsi_threshold=30 (repeatable)",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        metavar="CLASSNAME",
        help="Strategy class name(s) to skip, e.g. --exclude MLMomentumStrategy "
        "(its daily retrain makes 15yr runs take hours; its purged-OOS gate "
        "is evaluated from training warnings instead)",
    )
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.INFO)

    # Apply parameter overrides (plateau sweeps) before any strategy reads config
    from src.utils.config_loader import get_config

    config = get_config()
    for override in args.set:
        key, _, raw = override.partition("=")
        if not key or not raw:
            parser.error(f"--set expects KEY=VALUE, got {override!r}")
        import yaml as _yaml

        config.set_override(key.strip(), _yaml.safe_load(raw))

    # Load data
    df = load_market_data(args.data)

    # Trim to requested years (from end of data). No extra offset — use all available
    # data within the window so training periods can actually fit.
    if args.years:
        cutoff = df.index.max() - pd.DateOffset(years=args.years)
        df = df[df.index >= cutoff]
        print(
            f"  Trimmed to {args.years}yr window: {df.index.min().date()} to {df.index.max().date()}"
        )

    # Every long-only strategy is backtested. Pairs Trading is excluded — the
    # backtester has no short-leg support; it is validated separately by
    # scripts/research/validate_pairs.py. News Sentiment fetches live RSS, so
    # ~0 backtest trades is the expected (and recorded) finding.
    ALL_STRATEGY_CLASSES = [
        RSIMeanReversionStrategy,
        MLMomentumStrategy,
        EarningsDriftStrategy,
        FactorMomentumStrategy,
        MACrossoverStrategy,
        VolatilityBreakoutStrategy,
        NewsSentimentStrategy,
        SectorRotationStrategy,
    ]
    if args.exclude:
        ALL_STRATEGY_CLASSES = [
            c for c in ALL_STRATEGY_CLASSES if c.__name__ not in set(args.exclude)
        ]
        print(f"Excluded: {args.exclude}")
    strategy_classes = ALL_STRATEGY_CLASSES

    os.makedirs("artifacts/backtest", exist_ok=True)

    if args.per_strategy:
        _run_per_strategy_backtest(df, args, ALL_STRATEGY_CLASSES, config)
        return

    print(f"\nStrategies: {[c.__name__ for c in strategy_classes]}")
    print(f"Capital: ${args.capital:,.0f}")
    print(f"Mode: {'LEGACY gates' if args.legacy else 'production parity'}")
    print(
        f"Walk-forward: {args.train_days}d train / {args.test_days}d test / {args.step_days}d step"
    )
    print()

    # Run backtest
    if args.legacy:
        bt = PortfolioBacktester(
            initial_capital=args.capital,
            slippage_bps=5.0,
            commission_per_share=0.0,
            max_portfolio_heat=0.50,
            max_daily_loss_pct=0.05,
            stop_loss_atr_mult=5.0,
            max_positions_per_strategy=5,
        )
    else:
        bt = PortfolioBacktester.from_config(config, initial_capital=args.capital)

    results = bt.run_walk_forward(
        market_data=df,
        strategy_classes=strategy_classes,
        train_days=args.train_days,
        test_days=args.test_days,
        step_days=args.step_days,
    )

    # Print results
    PortfolioBacktester.print_results(results)

    # Save results
    out_path = "artifacts/backtest/walk_forward_results.json"

    # Save summary (exclude DataFrames)
    summary = {
        k: v for k, v in results.items() if not isinstance(v, pd.DataFrame) and k != "windows"
    }
    summary["windows"] = []
    for w in results.get("windows", []):
        summary["windows"].append(
            {
                "window_id": w["window_id"],
                "train_period": w["train_period"],
                "test_period": w["test_period"],
                "final_value": w["final_value"],
                "num_trades": len(w.get("trades", [])),
            }
        )

    with open(out_path, "w") as f:
        json.dump(summary, f, indent=2, default=str)
    print(f"\nResults saved to {out_path}")

    # Save equity curve CSV
    eq_path = "artifacts/backtest/equity_curve.csv"
    if "equity_curve" in results and isinstance(results["equity_curve"], pd.DataFrame):
        results["equity_curve"].to_csv(eq_path, index=False)
        print(f"Equity curve saved to {eq_path}")

    # Save trades CSV
    trades_path = "artifacts/backtest/all_trades.csv"
    if (
        "all_trades" in results
        and isinstance(results["all_trades"], pd.DataFrame)
        and len(results["all_trades"]) > 0
    ):
        results["all_trades"].to_csv(trades_path, index=False)
        print(f"Trades saved to {trades_path}")


def _run_per_strategy_backtest(
    df: pd.DataFrame, args: "argparse.Namespace", strategy_classes: list, config
) -> None:
    """Run each strategy independently and write a comparison report."""
    print("\n" + "=" * 70)
    print("PER-STRATEGY WALK-FORWARD BACKTEST")
    print("=" * 70)
    print(f"Capital per strategy: ${args.capital:,.0f}")
    print(f"Mode: {'LEGACY gates' if args.legacy else 'production parity'}")
    print(
        f"Walk-forward: {args.train_days}d train / {args.test_days}d test / {args.step_days}d step"
    )

    per_strategy_results: list[dict] = []

    for cls in strategy_classes:
        name = cls.__name__
        print(f"\n{'─'*50}")
        print(f"  {name}")
        print(f"{'─'*50}")
        try:
            if args.legacy:
                bt = PortfolioBacktester(
                    initial_capital=args.capital,
                    slippage_bps=5.0,
                    commission_per_share=0.0,
                    max_portfolio_heat=0.80,  # single-strategy: higher heat is fine
                    max_daily_loss_pct=0.10,
                    stop_loss_atr_mult=5.0,
                    max_positions_per_strategy=8,
                )
            else:
                bt = PortfolioBacktester.from_config(config, initial_capital=args.capital)
                # Single-strategy runs measure signal quality, not the shared
                # portfolio gate — relax heat so one strategy isn't capacity-
                # limited by a budget meant for nine. Stop geometry stays parity.
                bt.max_portfolio_heat = 0.80
                bt.max_daily_loss_pct = 0.10
            results = bt.run_walk_forward(
                market_data=df,
                strategy_classes=[cls],
                train_days=args.train_days,
                test_days=args.test_days,
                step_days=args.step_days,
            )
            PortfolioBacktester.print_results(results)

            # Collect summary metrics. NOTE: the backtester's key is
            # max_drawdown_pct (percent units) — reading "max_drawdown" here
            # silently nulled the drawdown acceptance gate for every strategy.
            total_return = (results.get("final_value", args.capital) - args.capital) / args.capital
            all_trades = results.get("all_trades")
            n_trades = len(all_trades) if isinstance(all_trades, pd.DataFrame) else 0

            # Per-window OOS returns: chained from each window's final value
            window_returns: list[float] = []
            prev_value = args.capital
            for w in results.get("windows", []):
                fv = w.get("final_value")
                if fv is not None and prev_value > 0:
                    window_returns.append(round((fv - prev_value) / prev_value * 100, 2))
                    prev_value = fv
            positive_window_pct = (
                round(sum(1 for r in window_returns if r > 0) / len(window_returns) * 100, 1)
                if window_returns
                else None
            )

            entry = {
                "strategy": name,
                "final_value": results.get("final_value", args.capital),
                "total_return_pct": round(total_return * 100, 2),
                "cagr_pct": results.get("cagr_pct"),
                "sharpe": results.get("sharpe_ratio"),
                "sortino": results.get("sortino_ratio"),
                "calmar": results.get("calmar_ratio"),
                "max_drawdown_pct": results.get("max_drawdown_pct"),
                "win_rate_pct": results.get("win_rate_pct"),
                "profit_factor": results.get("profit_factor"),
                "num_trades": n_trades,
                "closed_trades": results.get("sell_trades"),
                "window_returns_pct": window_returns,
                "positive_window_pct": positive_window_pct,
            }
            per_strategy_results.append(entry)

            # Save per-strategy equity curve
            eq = results.get("equity_curve")
            if isinstance(eq, pd.DataFrame):
                eq.to_csv(f"artifacts/backtest/equity_{name}.csv", index=False)

        except Exception as exc:
            print(f"  ⚠️  {name} backtest failed: {exc}")
            per_strategy_results.append({"strategy": name, "error": str(exc)})

    # Print comparison table
    print("\n" + "=" * 70)
    print("COMPARISON SUMMARY")
    print("=" * 70)
    print(f"{'Strategy':<30} {'Return':>10} {'Sharpe':>8} {'Drawdown':>10} {'Trades':>8}")
    print("─" * 70)
    for r in sorted(
        per_strategy_results, key=lambda x: x.get("total_return_pct", -999), reverse=True
    ):
        if "error" in r:
            print(f"{r['strategy']:<30}  ERROR: {r['error']}")
            continue
        sharpe = f"{r['sharpe']:.2f}" if r.get("sharpe") is not None else "—"
        dd = f"{r['max_drawdown_pct']:.1f}%" if r.get("max_drawdown_pct") is not None else "—"
        ret = f"{r['total_return_pct']:+.1f}%"
        print(f"{r['strategy']:<30} {ret:>10} {sharpe:>8} {dd:>10} {r['num_trades']:>8}")

    # Save comparison JSON
    out_path = "artifacts/backtest/per_strategy_results.json"
    with open(out_path, "w") as f:
        json.dump(per_strategy_results, f, indent=2, default=str)
    print(f"\nPer-strategy results saved to {out_path}")


if __name__ == "__main__":
    main()
