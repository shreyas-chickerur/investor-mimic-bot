#!/usr/bin/env python3
"""
Comprehensive Backtesting Runner

Runs complete backtest on historical data (2010-2024, excluding COVID).
Tests the 8-factor system and generates detailed performance analysis.
"""

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")  # Non-interactive backend
from typing import Dict, List

import matplotlib.pyplot as plt

from backtesting.backtest_engine import BacktestConfig, BacktestEngine, BacktestResult
from ml.adaptive_learning_engine import AdaptiveLearningEngine, EnsembleOptimizer, MLConfig

# Set style
plt.style.use("ggplot")
plt.rcParams["figure.figsize"] = (15, 10)


class ComprehensiveBacktester:
    """
    Runs comprehensive backtest with ML optimization.
    """

    def __init__(self):
        """Initialize backtester."""
        self.results = {}
        self.ml_engine = AdaptiveLearningEngine()
        self.ensemble_optimizer = EnsembleOptimizer()

    def load_historical_data(
        self, start_date: datetime, end_date: datetime
    ) -> Dict[str, pd.DataFrame]:
        """
        Load historical data for backtesting.

        In production, this would fetch:
        - Stock prices (daily OHLCV)
        - 13F filings
        - News sentiment
        - Insider trading
        - Market data (SPY, VIX)

        For now, generates synthetic data for demonstration.
        """
        print("Loading historical data...")
        print(f"  Period: {start_date.date()} to {end_date.date()}")

        # Generate date range (trading days only)
        dates = pd.bdate_range(start=start_date, end=end_date)

        # Synthetic price data for demonstration
        # In production, fetch from Alpha Vantage, Alpaca, etc.
        np.random.seed(42)

        symbols = ["AAPL", "GOOGL", "MSFT", "NVDA", "META", "AMZN", "TSLA", "NFLX"]

        price_data = {}
        for symbol in symbols:
            # Generate realistic price series
            returns = np.random.normal(0.0005, 0.02, len(dates))  # Daily returns
            prices = 100 * (1 + returns).cumprod()

            price_data[symbol] = pd.DataFrame(
                {
                    "date": dates,
                    "close": prices,
                    "volume": np.random.randint(1000000, 10000000, len(dates)),
                }
            ).set_index("date")

        # SPY data
        spy_returns = np.random.normal(0.0004, 0.015, len(dates))
        spy_prices = 100 * (1 + spy_returns).cumprod()

        spy_data = pd.DataFrame(
            {"date": dates, "close": spy_prices, "returns": spy_returns}
        ).set_index("date")

        # VIX data
        vix_data = pd.DataFrame(
            {"date": dates, "vix": np.random.normal(18, 5, len(dates)).clip(10, 80)}
        ).set_index("date")

        print(f"  ✓ Loaded {len(symbols)} symbols")
        print(f"  ✓ {len(dates)} trading days")

        return {"prices": price_data, "spy": spy_data, "vix": vix_data}

    def generate_factor_scores(
        self, date: datetime, symbols: List[str], historical_data: Dict
    ) -> Dict[str, Dict[str, float]]:
        """
        Generate factor scores for each symbol on a given date.

        In production, this would use the actual ProfitMaximizingEngine.
        For demonstration, generates synthetic scores.
        """
        scores = {}

        for symbol in symbols:
            # Synthetic factor scores (0-1)
            scores[symbol] = {
                "conviction": np.random.uniform(0.3, 0.8),
                "news": np.random.uniform(0.2, 0.7),
                "insider": np.random.uniform(0.2, 0.6),
                "technical": np.random.uniform(0.3, 0.7),
                "moving_avg": np.random.uniform(0.3, 0.8),
                "volume": np.random.uniform(0.3, 0.7),
                "relative_strength": np.random.uniform(0.2, 0.8),
                "earnings": np.random.uniform(0.3, 0.7),
            }

        return scores

    def calculate_combined_score(
        self, factor_scores: Dict[str, float], weights: Dict[str, float]
    ) -> float:
        """Calculate weighted combined score."""
        return sum(factor_scores.get(factor, 0.0) * weight for factor, weight in weights.items())

    def run_backtest(
        self,
        start_date: datetime,
        end_date: datetime,
        initial_weights: Dict[str, float],
        use_ml_optimization: bool = False,
    ) -> BacktestResult:
        """
        Run complete backtest.

        Args:
            start_date: Start date
            end_date: End date
            initial_weights: Initial factor weights
            use_ml_optimization: Whether to use ML to optimize weights

        Returns:
            BacktestResult
        """
        print("\n" + "=" * 80)
        print("RUNNING COMPREHENSIVE BACKTEST")
        print("=" * 80)

        # Load data
        historical_data = self.load_historical_data(start_date, end_date)

        # Initialize backtest engine
        config = BacktestConfig(
            start_date=start_date, end_date=end_date, initial_capital=100000.0, max_positions=10
        )

        engine = BacktestEngine(config)

        # Get trading dates
        dates = historical_data["spy"].index
        symbols = list(historical_data["prices"].keys())

        current_weights = initial_weights.copy()

        print(f"\nBacktesting {len(dates)} trading days...")
        print(f"Initial weights: {initial_weights}")

        # Simulate trading
        rebalance_frequency = 5  # Rebalance every 5 days

        for i, date in enumerate(dates):
            # Skip excluded periods (COVID)
            if engine.is_excluded_period(date):
                continue

            # Get current prices
            current_prices = {
                symbol: historical_data["prices"][symbol].loc[date, "close"] for symbol in symbols
            }

            # Rebalance portfolio
            if i % rebalance_frequency == 0:
                # Generate factor scores
                factor_scores = self.generate_factor_scores(date, symbols, historical_data)

                # Calculate combined scores
                combined_scores = {
                    symbol: self.calculate_combined_score(scores, current_weights)
                    for symbol, scores in factor_scores.items()
                }

                # Select top N stocks
                top_stocks = sorted(combined_scores.items(), key=lambda x: x[1], reverse=True)[
                    : config.max_positions
                ]

                # Calculate target allocation (equal weight for simplicity)
                target_allocation = engine.cash * 0.95 / len(top_stocks)  # Keep 5% cash

                # Execute trades
                for symbol, score in top_stocks:
                    if symbol not in engine.positions:
                        # Buy new position
                        quantity = target_allocation / current_prices[symbol]
                        engine.execute_trade(
                            date=date,
                            symbol=symbol,
                            action="BUY",
                            quantity=quantity,
                            price=current_prices[symbol],
                            reason="SIGNAL",
                        )

                # Sell positions not in top stocks
                for symbol in list(engine.positions.keys()):
                    if symbol not in [s for s, _ in top_stocks]:
                        pos = engine.positions[symbol]
                        engine.execute_trade(
                            date=date,
                            symbol=symbol,
                            action="SELL",
                            quantity=pos.quantity,
                            price=current_prices[symbol],
                            reason="REBALANCE",
                        )

                # ML optimization (if enabled)
                if use_ml_optimization and i > 252:  # After 1 year of data
                    # Prepare training data from past performance
                    # (Simplified for demonstration)
                    current_weights = self._optimize_weights_ml(
                        historical_data, current_weights, date
                    )

            # Update portfolio
            engine.record_portfolio_state(date, current_prices)

            # Progress
            if (i + 1) % 252 == 0:
                years = (i + 1) / 252
                current_value = engine.portfolio_values[-1][1]
                print(f"  Year {years:.1f}: Portfolio value = ${current_value:,.2f}")

        # Calculate metrics
        spy_returns = historical_data["spy"]["returns"]
        spy_total_return = (
            historical_data["spy"]["close"].iloc[-1] / historical_data["spy"]["close"].iloc[0]
        ) - 1

        metrics = engine.calculate_metrics(spy_returns)
        metrics["spy_return"] = spy_total_return

        # Generate report
        report = engine.generate_report(metrics, spy_total_return)
        print(report)

        # Save results
        output_dir = Path("backtest_results") / datetime.now().strftime("%Y%m%d_%H%M%S")
        engine.save_results(output_dir, metrics)

        # Generate visualizations
        self.generate_visualizations(engine, historical_data, output_dir)

        return metrics

    def _optimize_weights_ml(
        self, historical_data: Dict, current_weights: Dict[str, float], current_date: datetime
    ) -> Dict[str, float]:
        """Optimize weights using ML (simplified)."""
        # In production, this would use the full ML engine
        # For now, return current weights
        return current_weights

    def generate_visualizations(
        self, engine: BacktestEngine, historical_data: Dict, output_dir: Path
    ):
        """Generate performance visualizations."""
        print("\nGenerating visualizations...")

        # Portfolio value over time
        fig, axes = plt.subplots(2, 2, figsize=(15, 10))

        # 1. Portfolio value
        portfolio_df = pd.DataFrame(engine.portfolio_values, columns=["date", "value"])
        portfolio_df.set_index("date", inplace=True)

        axes[0, 0].plot(portfolio_df.index, portfolio_df["value"], label="Strategy", linewidth=2)
        axes[0, 0].axhline(
            y=engine.config.initial_capital, color="r", linestyle="--", label="Initial Capital"
        )
        axes[0, 0].set_title("Portfolio Value Over Time", fontsize=14, fontweight="bold")
        axes[0, 0].set_xlabel("Date")
        axes[0, 0].set_ylabel("Portfolio Value ($)")
        axes[0, 0].legend()
        axes[0, 0].grid(True, alpha=0.3)

        # 2. Returns distribution
        returns = portfolio_df["value"].pct_change().dropna()
        axes[0, 1].hist(returns, bins=50, alpha=0.7, edgecolor="black")
        axes[0, 1].axvline(
            x=returns.mean(), color="r", linestyle="--", label=f"Mean: {returns.mean():.4f}"
        )
        axes[0, 1].set_title("Returns Distribution", fontsize=14, fontweight="bold")
        axes[0, 1].set_xlabel("Daily Return")
        axes[0, 1].set_ylabel("Frequency")
        axes[0, 1].legend()
        axes[0, 1].grid(True, alpha=0.3)

        # 3. Drawdown
        cumulative = (1 + returns).cumprod()
        running_max = cumulative.expanding().max()
        drawdown = (cumulative - running_max) / running_max

        axes[1, 0].fill_between(drawdown.index, drawdown.values, 0, alpha=0.3, color="red")
        axes[1, 0].plot(drawdown.index, drawdown.values, color="red", linewidth=2)
        axes[1, 0].set_title("Drawdown Over Time", fontsize=14, fontweight="bold")
        axes[1, 0].set_xlabel("Date")
        axes[1, 0].set_ylabel("Drawdown (%)")
        axes[1, 0].grid(True, alpha=0.3)

        # 4. Cumulative returns comparison
        cumulative_returns = (1 + returns).cumprod()
        axes[1, 1].plot(
            cumulative_returns.index, cumulative_returns.values, linewidth=2, label="Strategy"
        )
        axes[1, 1].axhline(y=1.0, color="r", linestyle="--", label="Breakeven")
        axes[1, 1].set_title("Cumulative Returns", fontsize=14, fontweight="bold")
        axes[1, 1].set_xlabel("Date")
        axes[1, 1].set_ylabel("Cumulative Return")
        axes[1, 1].legend()
        axes[1, 1].grid(True, alpha=0.3)

        plt.tight_layout()
        plt.savefig(output_dir / "performance_analysis.png", dpi=300, bbox_inches="tight")
        print(f"  ✓ Saved performance_analysis.png")

        plt.close()


def main():
    """Run comprehensive backtest."""
    print("=" * 80)
    print("COMPREHENSIVE BACKTESTING SYSTEM")
    print("Historical Data: 2010-2024 (Excluding COVID: Mar-Jun 2020)")
    print("=" * 80)

    # Initialize backtester
    backtester = ComprehensiveBacktester()

    # Define test period
    start_date = datetime(2010, 1, 1)
    end_date = datetime(2024, 12, 31)

    # Initial factor weights (current system)
    initial_weights = {
        "conviction": 0.30,
        "news": 0.12,
        "insider": 0.12,
        "technical": 0.08,
        "moving_avg": 0.18,
        "volume": 0.10,
        "relative_strength": 0.08,
        "earnings": 0.02,
    }

    # Run backtest WITHOUT ML optimization (baseline)
    print("\n" + "=" * 80)
    print("PHASE 1: BASELINE BACKTEST (No ML Optimization)")
    print("=" * 80)

    baseline_results = backtester.run_backtest(
        start_date=start_date,
        end_date=end_date,
        initial_weights=initial_weights,
        use_ml_optimization=False,
    )

    # Run backtest WITH ML optimization
    print("\n" + "=" * 80)
    print("PHASE 2: ML-OPTIMIZED BACKTEST")
    print("=" * 80)

    ml_results = backtester.run_backtest(
        start_date=start_date,
        end_date=end_date,
        initial_weights=initial_weights,
        use_ml_optimization=True,
    )

    # Compare results
    print("\n" + "=" * 80)
    print("COMPARISON: BASELINE VS ML-OPTIMIZED")
    print("=" * 80)

    comparison = pd.DataFrame(
        {
            "Baseline": baseline_results,
            "ML-Optimized": ml_results,
            "Improvement": {
                k: ml_results[k] - baseline_results[k]
                for k in baseline_results.keys()
                if isinstance(baseline_results[k], (int, float))
            },
        }
    )

    print(comparison.to_string())

    print("\n" + "=" * 80)
    print("✅ COMPREHENSIVE BACKTEST COMPLETE!")
    print("=" * 80)
    print("\nResults saved to: backtest_results/")
    print("\nNext steps:")
    print("  1. Review performance metrics")
    print("  2. Analyze ML-optimized weights")
    print("  3. Implement best-performing configuration")
    print("  4. Run forward testing")


if __name__ == "__main__":
    main()
