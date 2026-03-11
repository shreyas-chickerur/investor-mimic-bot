#!/usr/bin/env python3
"""
Run walk-forward portfolio backtest against historical data.

Usage:
    python scripts/run_backtest.py [--years N] [--capital N]

Outputs results to console and saves to artifacts/backtest/
"""
import sys
import os
import argparse
import logging
from pathlib import Path

# Project root
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd

from src.integration.portfolio_backtester import PortfolioBacktester
from src.strategies.strategy_rsi_mean_reversion import RSIMeanReversionStrategy
from src.strategies.strategy_ml_momentum import MLMomentumStrategy
from src.strategies.strategy_earnings_drift import EarningsDriftStrategy
from src.strategies.strategy_factor_momentum import FactorMomentumStrategy

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
    parser.add_argument("--capital", type=float, default=100000, help="Initial capital (default 100000)")
    parser.add_argument("--train-days", type=int, default=504, help="Training window in trading days (default 504 ~2yr)")
    parser.add_argument("--test-days", type=int, default=126, help="Test window in trading days (default 126 ~6mo)")
    parser.add_argument("--step-days", type=int, default=126, help="Step size in trading days (default 126 ~6mo)")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.INFO)

    # Load data
    df = load_market_data()

    # Trim to requested years (from end of data)
    if args.years:
        cutoff = df.index.max() - pd.DateOffset(years=args.years + 2)  # +2 for training window
        df = df[df.index >= cutoff]
        print(f"  Trimmed to {args.years}+2yr window: {df.index.min().date()} to {df.index.max().date()}")

    # Strategy classes to test
    # New mix: drop NewsSentiment (no API key) and MACrossover (weakest signal)
    # Add EarningsDrift (PEAD anomaly) and FactorMomentum (cross-sectional ranking)
    strategy_classes = [
        RSIMeanReversionStrategy,
        MLMomentumStrategy,
        EarningsDriftStrategy,
        FactorMomentumStrategy,
    ]

    print(f"\nStrategies: {[c.__name__ for c in strategy_classes]}")
    print(f"Capital: ${args.capital:,.0f}")
    print(f"Walk-forward: {args.train_days}d train / {args.test_days}d test / {args.step_days}d step")
    print()

    # Run backtest
    bt = PortfolioBacktester(
        initial_capital=args.capital,
        slippage_bps=5.0,
        commission_per_share=0.0,
        max_portfolio_heat=0.50,
        max_daily_loss_pct=0.05,
        stop_loss_atr_mult=5.0,
        max_positions_per_strategy=5,
    )

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
    os.makedirs("artifacts/backtest", exist_ok=True)
    out_path = "artifacts/backtest/walk_forward_results.json"

    # Save summary (exclude DataFrames)
    summary = {k: v for k, v in results.items() if not isinstance(v, pd.DataFrame) and k != 'windows'}
    summary['windows'] = []
    for w in results.get('windows', []):
        summary['windows'].append({
            'window_id': w['window_id'],
            'train_period': w['train_period'],
            'test_period': w['test_period'],
            'final_value': w['final_value'],
            'num_trades': len(w.get('trades', [])),
        })

    import json
    with open(out_path, 'w') as f:
        json.dump(summary, f, indent=2, default=str)
    print(f"\nResults saved to {out_path}")

    # Save equity curve CSV
    eq_path = "artifacts/backtest/equity_curve.csv"
    if 'equity_curve' in results and isinstance(results['equity_curve'], pd.DataFrame):
        results['equity_curve'].to_csv(eq_path, index=False)
        print(f"Equity curve saved to {eq_path}")

    # Save trades CSV
    trades_path = "artifacts/backtest/all_trades.csv"
    if 'all_trades' in results and isinstance(results['all_trades'], pd.DataFrame) and len(results['all_trades']) > 0:
        results['all_trades'].to_csv(trades_path, index=False)
        print(f"Trades saved to {trades_path}")


if __name__ == "__main__":
    main()
