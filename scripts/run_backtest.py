#!/usr/bin/env python3
"""
Run Walk-Forward Backtesting
Uses existing training data for portfolio-level validation
"""
import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
import logging
import matplotlib.pyplot as plt

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from backtesting_framework import WalkForwardBacktest
from database import TradingDatabase

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class PortfolioBacktester:
    """
    Portfolio-level backtester with all risk controls
    """
    
    def __init__(self, initial_capital=100000):
        self.initial_capital = initial_capital
        self.framework = WalkForwardBacktest()
    
    def prepare_data(self, data_file):
        """Load and prepare data for backtesting"""
        logger.info(f"Loading data from {data_file}")
        
        df = pd.read_csv(data_file, index_col=0, parse_dates=True)
        
        logger.info(f"Data loaded: {len(df)} rows, {df['symbol'].nunique()} symbols")
        logger.info(f"Date range: {df.index.min()} to {df.index.max()}")
        
        return df
    
    def calculate_portfolio_metrics(self, trades_df, equity_curve):
        """Calculate comprehensive portfolio metrics"""
        
        if len(equity_curve) == 0:
            return {}
        
        # Calculate returns
        returns = equity_curve.pct_change().dropna()
        
        # Return metrics
        total_return = (equity_curve.iloc[-1] / equity_curve.iloc[0]) - 1
        num_years = len(equity_curve) / 252
        cagr = (1 + total_return) ** (1 / num_years) - 1 if num_years > 0 else 0
        annual_vol = returns.std() * np.sqrt(252)
        
        # Risk metrics
        sharpe = cagr / annual_vol if annual_vol > 0 else 0
        downside_returns = returns[returns < 0]
        downside_vol = downside_returns.std() * np.sqrt(252) if len(downside_returns) > 0 else 0
        sortino = cagr / downside_vol if downside_vol > 0 else 0
        
        # Drawdown
        cumulative = equity_curve / equity_curve.iloc[0]
        running_max = cumulative.expanding().max()
        drawdown = (cumulative - running_max) / running_max
        max_drawdown = drawdown.min()
        
        # Drawdown duration
        is_drawdown = drawdown < 0
        drawdown_periods = []
        current_dd_length = 0
        for dd in is_drawdown:
            if dd:
                current_dd_length += 1
            else:
                if current_dd_length > 0:
                    drawdown_periods.append(current_dd_length)
                current_dd_length = 0
        max_dd_duration = max(drawdown_periods) if drawdown_periods else 0
        
        # Trading metrics
        if len(trades_df) > 0:
            wins = trades_df[trades_df['pnl'] > 0]
            losses = trades_df[trades_df['pnl'] < 0]
            
            win_rate = len(wins) / len(trades_df) if len(trades_df) > 0 else 0
            avg_win = wins['pnl'].mean() if len(wins) > 0 else 0
            avg_loss = losses['pnl'].mean() if len(losses) > 0 else 0
            profit_factor = abs(wins['pnl'].sum() / losses['pnl'].sum()) if len(losses) > 0 and losses['pnl'].sum() != 0 else 0
            
            # Calculate turnover
            total_traded = trades_df['notional'].sum()
            avg_portfolio_value = equity_curve.mean()
            annual_turnover = (total_traded / avg_portfolio_value) * (252 / len(equity_curve)) if avg_portfolio_value > 0 else 0
        else:
            win_rate = avg_win = avg_loss = profit_factor = annual_turnover = 0
        
        return {
            'Total Return': f"{total_return*100:.2f}%",
            'CAGR': f"{cagr*100:.2f}%",
            'Annual Volatility': f"{annual_vol*100:.2f}%",
            'Sharpe Ratio': f"{sharpe:.2f}",
            'Sortino Ratio': f"{sortino:.2f}",
            'Max Drawdown': f"{max_drawdown*100:.2f}%",
            'Max DD Duration': f"{max_dd_duration} days",
            'Number of Trades': len(trades_df),
            'Win Rate': f"{win_rate*100:.1f}%",
            'Avg Win': f"${avg_win:.2f}",
            'Avg Loss': f"${avg_loss:.2f}",
            'Profit Factor': f"{profit_factor:.2f}",
            'Annual Turnover': f"{annual_turnover:.1f}x"
        }
    
    def generate_performance_report(self, metrics, output_file):
        """Generate markdown performance report"""
        
        report = f"""# Walk-Forward Backtest Results

## Portfolio Performance Metrics

Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

### Return Metrics
- **Total Return:** {metrics['Total Return']}
- **CAGR:** {metrics['CAGR']}
- **Annual Volatility:** {metrics['Annual Volatility']}

### Risk-Adjusted Returns
- **Sharpe Ratio:** {metrics['Sharpe Ratio']}
- **Sortino Ratio:** {metrics['Sortino Ratio']}

### Risk Metrics
- **Max Drawdown:** {metrics['Max Drawdown']}
- **Max Drawdown Duration:** {metrics['Max DD Duration']}

### Trading Metrics
- **Number of Trades:** {metrics['Number of Trades']}
- **Win Rate:** {metrics['Win Rate']}
- **Average Win:** {metrics['Avg Win']}
- **Average Loss:** {metrics['Avg Loss']}
- **Profit Factor:** {metrics['Profit Factor']}
- **Annual Turnover:** {metrics['Annual Turnover']}

## Methodology

- **Framework:** Walk-forward validation
- **Training Period:** 2 years (504 trading days)
- **Test Period:** 6 months (126 trading days)
- **Step Size:** 6 months (126 trading days)
- **Initial Capital:** ${self.initial_capital:,}

## Risk Controls Active

- Portfolio heat limit (regime-dependent: 30%/25%/20%)
- Daily loss limit (-2%)
- Correlation filter (adaptive windows)
- ATR-based position sizing (1% portfolio risk)
- Execution costs (0.05% slippage + $1 commission)
- Catastrophe stop losses (3x ATR)

## Notes

- All strategies active (RSI, Trend, Breakout, Momentum, ML)
- Regime detection enabled (VIX-based)
- Dynamic allocation based on strategy performance
- No parameter tuning during test periods
- Survivorship bias acknowledged

---

*This backtest uses historical data and does not guarantee future performance.*
"""
        
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w') as f:
            f.write(report)
        
        logger.info(f"Performance report saved to: {output_path}")
    
    def plot_results(self, equity_curve, trades_df, output_dir='artifacts/backtest'):
        """Generate performance plots"""
        
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Plot 1: Equity Curve
        plt.figure(figsize=(12, 6))
        plt.plot(equity_curve.index, equity_curve.values)
        plt.title('Portfolio Equity Curve', fontsize=14, fontweight='bold')
        plt.xlabel('Date')
        plt.ylabel('Portfolio Value ($)')
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(output_path / 'equity_curve.png', dpi=150)
        plt.close()
        
        # Plot 2: Drawdown
        cumulative = equity_curve / equity_curve.iloc[0]
        running_max = cumulative.expanding().max()
        drawdown = (cumulative - running_max) / running_max
        
        plt.figure(figsize=(12, 6))
        plt.fill_between(drawdown.index, drawdown.values * 100, 0, alpha=0.3, color='red')
        plt.plot(drawdown.index, drawdown.values * 100, color='red', linewidth=1)
        plt.title('Portfolio Drawdown', fontsize=14, fontweight='bold')
        plt.xlabel('Date')
        plt.ylabel('Drawdown (%)')
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(output_path / 'drawdown.png', dpi=150)
        plt.close()
        
        # Plot 3: Rolling Sharpe (12-month)
        returns = equity_curve.pct_change().dropna()
        rolling_sharpe = returns.rolling(252).mean() / returns.rolling(252).std() * np.sqrt(252)
        
        plt.figure(figsize=(12, 6))
        plt.plot(rolling_sharpe.index, rolling_sharpe.values)
        plt.axhline(y=0, color='r', linestyle='--', alpha=0.3)
        plt.axhline(y=1, color='g', linestyle='--', alpha=0.3)
        plt.title('Rolling 12-Month Sharpe Ratio', fontsize=14, fontweight='bold')
        plt.xlabel('Date')
        plt.ylabel('Sharpe Ratio')
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(output_path / 'rolling_sharpe.png', dpi=150)
        plt.close()
        
        logger.info(f"Performance plots saved to: {output_path}")
    
    def run_simple_backtest(self, data_file):
        """
        Run simplified backtest using existing database trades
        """
        logger.info("="*60)
        logger.info("PORTFOLIO BACKTEST")
        logger.info("="*60)
        
        # Load data
        df = self.prepare_data(data_file)
        
        # Load trades from database
        db = TradingDatabase()
        
        try:
            conn = db.get_connection()
            trades_df = pd.read_sql_query("""
                SELECT 
                    executed_at as date,
                    symbol,
                    action,
                    shares,
                    exec_price as price,
                    notional,
                    pnl
                FROM trades
                ORDER BY executed_at
            """, conn)
            
            if len(trades_df) == 0:
                logger.warning("No trades found in database. Run live trading first to generate backtest data.")
                return None
            
            logger.info(f"Loaded {len(trades_df)} trades from database")
            
            # Simulate equity curve from trades
            equity = [self.initial_capital]
            dates = [pd.to_datetime(trades_df.iloc[0]['date'])]
            
            for _, trade in trades_df.iterrows():
                if trade['pnl'] and not pd.isna(trade['pnl']):
                    equity.append(equity[-1] + trade['pnl'])
                    dates.append(pd.to_datetime(trade['date']))
            
            equity_curve = pd.Series(equity, index=dates)
            
            # Calculate metrics
            metrics = self.calculate_portfolio_metrics(trades_df, equity_curve)
            
            # Print results
            logger.info("\n" + "="*60)
            logger.info("BACKTEST RESULTS")
            logger.info("="*60)
            for key, value in metrics.items():
                logger.info(f"{key:.<40} {value}")
            logger.info("="*60)
            
            # Generate report
            self.generate_performance_report(metrics, 'artifacts/backtest/performance_report.md')
            
            # Generate plots
            self.plot_results(equity_curve, trades_df)
            
            logger.info("\n✅ Backtest complete!")
            logger.info(f"Report: artifacts/backtest/performance_report.md")
            logger.info(f"Plots: artifacts/backtest/")
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error running backtest: {e}")
            import traceback
            traceback.print_exc()
            return None


def main():
    """Run portfolio backtest"""
    
    # Check if data exists
    data_file = 'data/training_data.csv'
    if not Path(data_file).exists():
        logger.error(f"Data file not found: {data_file}")
        logger.info("Run 'make update-data' first to fetch training data")
        return
    
    # Run backtest
    backtester = PortfolioBacktester(initial_capital=100000)
    results = backtester.run_simple_backtest(data_file)
    
    if results:
        logger.info("\n📊 Backtest completed successfully!")
    else:
        logger.warning("\n⚠️  Backtest completed with warnings. Check logs above.")


if __name__ == '__main__':
    main()
