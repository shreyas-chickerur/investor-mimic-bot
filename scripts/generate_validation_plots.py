#!/usr/bin/env python3
"""
Validation Plot Generation
Generates all required plots for empirical validation report

REQUIRED PLOTS (per specification):
1. Portfolio-level: Equity curve (log), drawdown, rolling Sharpe, exposure
2. Strategy-level: Capital allocation, contribution to returns
3. Regime-level: Timeline, performance by regime
"""
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ValidationPlotGenerator:
    """Generate all required validation plots"""
    
    def __init__(self, output_dir: str = 'backtest_results/plots'):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Set plot style
        plt.style.use('seaborn-v0_8-darkgrid')
        
    def generate_all_plots(self, equity_curve: pd.DataFrame, trades: pd.DataFrame, 
                          regime_data: pd.DataFrame = None):
        """Generate all required plots"""
        logger.info("Generating validation plots...")
        
        # Portfolio-level plots
        self.plot_equity_curve(equity_curve)
        self.plot_drawdown_curve(equity_curve)
        self.plot_rolling_sharpe(equity_curve)
        self.plot_portfolio_heat(equity_curve)
        
        # Strategy-level plots (if data available)
        # TODO: Implement when strategy-level data is tracked
        
        # Regime-level plots (if data available)
        if regime_data is not None:
            self.plot_regime_timeline(regime_data)
        
        logger.info(f"All plots saved to {self.output_dir}")
    
    def plot_equity_curve(self, equity_curve: pd.DataFrame):
        """Plot equity curve (log scale)"""
        fig, ax = plt.subplots(figsize=(14, 7))
        
        ax.semilogy(equity_curve['date'], equity_curve['portfolio_value'], 
                   linewidth=2, color='#2E86AB', label='Portfolio Value')
        
        ax.set_xlabel('Date', fontsize=12)
        ax.set_ylabel('Portfolio Value ($)', fontsize=12)
        ax.set_title('Portfolio Equity Curve (Log Scale)', fontsize=14, fontweight='bold')
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=10)
        
        # Format x-axis
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
        ax.xaxis.set_major_locator(mdates.YearLocator())
        plt.xticks(rotation=45)
        
        plt.tight_layout()
        plt.savefig(self.output_dir / 'equity_curve.png', dpi=300, bbox_inches='tight')
        plt.close()
        
        logger.info("✓ Equity curve plot saved")
    
    def plot_drawdown_curve(self, equity_curve: pd.DataFrame):
        """Plot drawdown curve"""
        # Calculate drawdown
        running_max = equity_curve['portfolio_value'].expanding().max()
        drawdown = (equity_curve['portfolio_value'] - running_max) / running_max * 100
        
        fig, ax = plt.subplots(figsize=(14, 7))
        
        ax.fill_between(equity_curve['date'], drawdown, 0, 
                        color='#A23B72', alpha=0.6, label='Drawdown')
        ax.plot(equity_curve['date'], drawdown, 
               linewidth=1.5, color='#6B1E3F', label='Drawdown %')
        
        ax.set_xlabel('Date', fontsize=12)
        ax.set_ylabel('Drawdown (%)', fontsize=12)
        ax.set_title('Portfolio Drawdown Over Time', fontsize=14, fontweight='bold')
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=10)
        
        # Format x-axis
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
        ax.xaxis.set_major_locator(mdates.YearLocator())
        plt.xticks(rotation=45)
        
        # Add max drawdown annotation
        max_dd_idx = drawdown.idxmin()
        max_dd_value = drawdown.min()
        max_dd_date = equity_curve.loc[max_dd_idx, 'date']
        ax.annotate(f'Max DD: {max_dd_value:.2f}%', 
                   xy=(max_dd_date, max_dd_value),
                   xytext=(10, 10), textcoords='offset points',
                   bbox=dict(boxstyle='round,pad=0.5', fc='yellow', alpha=0.7),
                   arrowprops=dict(arrowstyle='->', connectionstyle='arc3,rad=0'))
        
        plt.tight_layout()
        plt.savefig(self.output_dir / 'drawdown_curve.png', dpi=300, bbox_inches='tight')
        plt.close()
        
        logger.info("✓ Drawdown curve plot saved")
    
    def plot_rolling_sharpe(self, equity_curve: pd.DataFrame, window: int = 252):
        """Plot rolling 12-month Sharpe ratio"""
        # Calculate daily returns
        equity_curve['daily_return'] = equity_curve['portfolio_value'].pct_change()
        
        # Calculate rolling Sharpe (annualized)
        rolling_sharpe = (
            equity_curve['daily_return'].rolling(window=window).mean() * np.sqrt(252) /
            equity_curve['daily_return'].rolling(window=window).std()
        )
        
        fig, ax = plt.subplots(figsize=(14, 7))
        
        ax.plot(equity_curve['date'], rolling_sharpe, 
               linewidth=2, color='#18A558', label='Rolling 12-Month Sharpe')
        ax.axhline(y=0, color='black', linestyle='--', linewidth=1, alpha=0.5)
        ax.axhline(y=1.0, color='green', linestyle='--', linewidth=1, alpha=0.5, label='Sharpe = 1.0')
        ax.axhline(y=2.0, color='red', linestyle='--', linewidth=1, alpha=0.5, label='Sharpe = 2.0 (Warning)')
        
        ax.set_xlabel('Date', fontsize=12)
        ax.set_ylabel('Rolling Sharpe Ratio', fontsize=12)
        ax.set_title('Rolling 12-Month Sharpe Ratio', fontsize=14, fontweight='bold')
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=10)
        
        # Format x-axis
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
        ax.xaxis.set_major_locator(mdates.YearLocator())
        plt.xticks(rotation=45)
        
        plt.tight_layout()
        plt.savefig(self.output_dir / 'rolling_sharpe.png', dpi=300, bbox_inches='tight')
        plt.close()
        
        logger.info("✓ Rolling Sharpe plot saved")
    
    def plot_portfolio_heat(self, equity_curve: pd.DataFrame):
        """Plot portfolio heat (exposure) over time"""
        if 'positions_value' not in equity_curve.columns:
            logger.warning("No positions_value data, skipping heat plot")
            return
        
        # Calculate heat as percentage of portfolio
        heat_pct = (equity_curve['positions_value'] / equity_curve['portfolio_value']) * 100
        
        fig, ax = plt.subplots(figsize=(14, 7))
        
        ax.fill_between(equity_curve['date'], heat_pct, 0, 
                        color='#F18F01', alpha=0.6, label='Portfolio Heat')
        ax.plot(equity_curve['date'], heat_pct, 
               linewidth=1.5, color='#C73E1D', label='Heat %')
        
        # Add regime-dependent heat limits
        ax.axhline(y=20, color='green', linestyle='--', linewidth=1, alpha=0.5, label='High Vol Limit (20%)')
        ax.axhline(y=30, color='blue', linestyle='--', linewidth=1, alpha=0.5, label='Normal Limit (30%)')
        ax.axhline(y=40, color='orange', linestyle='--', linewidth=1, alpha=0.5, label='Low Vol Limit (40%)')
        
        ax.set_xlabel('Date', fontsize=12)
        ax.set_ylabel('Portfolio Heat (%)', fontsize=12)
        ax.set_title('Portfolio Heat (Capital Exposed) Over Time', fontsize=14, fontweight='bold')
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=10)
        
        # Format x-axis
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
        ax.xaxis.set_major_locator(mdates.YearLocator())
        plt.xticks(rotation=45)
        
        plt.tight_layout()
        plt.savefig(self.output_dir / 'portfolio_heat.png', dpi=300, bbox_inches='tight')
        plt.close()
        
        logger.info("✓ Portfolio heat plot saved")
    
    def plot_regime_timeline(self, regime_data: pd.DataFrame):
        """Plot regime timeline"""
        fig, ax = plt.subplots(figsize=(14, 5))
        
        # Map regimes to numeric values for plotting
        regime_map = {'low_volatility': 1, 'normal': 2, 'high_volatility': 3}
        regime_numeric = regime_data['regime'].map(regime_map)
        
        # Color map
        colors = {1: '#18A558', 2: '#2E86AB', 3: '#A23B72'}
        
        for regime_val, color in colors.items():
            mask = regime_numeric == regime_val
            ax.scatter(regime_data.loc[mask, 'date'], 
                      regime_numeric[mask],
                      c=color, s=10, alpha=0.6)
        
        ax.set_xlabel('Date', fontsize=12)
        ax.set_ylabel('Regime', fontsize=12)
        ax.set_yticks([1, 2, 3])
        ax.set_yticklabels(['Low Vol', 'Normal', 'High Vol'])
        ax.set_title('Market Regime Timeline', fontsize=14, fontweight='bold')
        ax.grid(True, alpha=0.3, axis='x')
        
        # Format x-axis
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
        ax.xaxis.set_major_locator(mdates.YearLocator())
        plt.xticks(rotation=45)
        
        plt.tight_layout()
        plt.savefig(self.output_dir / 'regime_timeline.png', dpi=300, bbox_inches='tight')
        plt.close()
        
        logger.info("✓ Regime timeline plot saved")

def main():
    """Test plot generation with sample data"""
    # This would be called with actual backtest results
    logger.info("Plot generator ready. Call with actual backtest results.")

if __name__ == '__main__':
    main()
