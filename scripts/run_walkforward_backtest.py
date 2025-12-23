#!/usr/bin/env python3
"""
Walk-Forward Backtest Runner
Executes portfolio-level walk-forward validation as specified

CONFIGURATION (DO NOT MODIFY WITHOUT EXPLICIT INSTRUCTION):
- Training window: 2 years
- Test window: 6 months
- Step size: 6 months
- No parameter tuning in test windows
- All strategies, filters, costs, regime detection active
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging
import json

from portfolio_backtester import PortfolioBacktester
from regime_detector import RegimeDetector
from correlation_filter import CorrelationFilter
from portfolio_risk_manager import PortfolioRiskManager
from execution_costs import ExecutionCostModel
from dynamic_allocator import DynamicAllocator

from strategies.strategy_rsi_mean_reversion import RSIMeanReversionStrategy
from strategies.strategy_ma_crossover import MACrossoverStrategy
from strategies.strategy_ml_momentum import MLMomentumStrategy
from strategies.strategy_news_sentiment import NewsSentimentStrategy
from strategies.strategy_volatility_breakout import VolatilityBreakoutStrategy

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/walkforward_backtest.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class WalkForwardBacktester:
    """
    Walk-forward backtesting framework
    
    Strictly follows specification:
    - 2 year training window
    - 6 month test window
    - 6 month step size
    - No parameter optimization
    """
    
    def __init__(self, 
                 data_path: str,
                 vix_data_path: str = None,
                 initial_capital: float = 100000):
        """
        Initialize walk-forward backtester
        
        Args:
            data_path: Path to market data CSV
            vix_data_path: Path to VIX data CSV (optional)
            initial_capital: Starting capital
        """
        self.data_path = data_path
        self.vix_data_path = vix_data_path
        self.initial_capital = initial_capital
        
        # Walk-forward parameters (FIXED - DO NOT MODIFY)
        self.training_window_days = 730  # 2 years
        self.test_window_days = 180  # 6 months
        self.step_size_days = 180  # 6 months
        
        logger.info("Walk-Forward Backtester initialized")
        logger.info(f"Training window: {self.training_window_days} days")
        logger.info(f"Test window: {self.test_window_days} days")
        logger.info(f"Step size: {self.step_size_days} days")
    
    def load_data(self) -> pd.DataFrame:
        """Load market data"""
        logger.info(f"Loading market data from {self.data_path}")
        
        df = pd.read_csv(self.data_path, index_col=0)
        df.index = pd.to_datetime(df.index)
        
        logger.info(f"Loaded {len(df)} rows, {df['symbol'].nunique()} symbols")
        logger.info(f"Date range: {df.index.min()} to {df.index.max()}")
        
        # Check for minimum 10 years of data
        years = (df.index.max() - df.index.min()).days / 365.25
        if years < 10:
            logger.warning(f"Only {years:.1f} years of data available (minimum 10 recommended)")
        
        return df
    
    def load_vix_data(self) -> pd.DataFrame:
        """Load VIX data if available"""
        if not self.vix_data_path or not Path(self.vix_data_path).exists():
            logger.warning("VIX data not available - regime detection will use default")
            return None
        
        logger.info(f"Loading VIX data from {self.vix_data_path}")
        vix_df = pd.read_csv(self.vix_data_path, index_col=0)
        vix_df.index = pd.to_datetime(vix_df.index)
        
        logger.info(f"Loaded VIX data: {len(vix_df)} days")
        return vix_df
    
    def create_walk_forward_windows(self, data: pd.DataFrame):
        """
        Create walk-forward windows
        
        Returns:
            List of (train_start, train_end, test_start, test_end) tuples
        """
        dates = sorted(data.index.unique())
        min_date = dates[0]
        max_date = dates[-1]
        
        windows = []
        
        # Start with first possible training window
        current_start = min_date
        
        while True:
            # Training window
            train_start = current_start
            train_end = train_start + timedelta(days=self.training_window_days)
            
            # Test window
            test_start = train_end + timedelta(days=1)
            test_end = test_start + timedelta(days=self.test_window_days)
            
            # Check if we have enough data
            if test_end > max_date:
                break
            
            windows.append((train_start, train_end, test_start, test_end))
            
            # Step forward
            current_start = current_start + timedelta(days=self.step_size_days)
        
        logger.info(f"Created {len(windows)} walk-forward windows")
        return windows
    
    def run_walk_forward(self, market_data: pd.DataFrame, vix_data: pd.DataFrame = None):
        """
        Execute walk-forward backtest
        
        Args:
            market_data: Market data DataFrame
            vix_data: VIX data DataFrame (optional)
            
        Returns:
            Dict with results
        """
        windows = self.create_walk_forward_windows(market_data)
        
        all_results = []
        combined_equity = []
        combined_trades = []
        
        for i, (train_start, train_end, test_start, test_end) in enumerate(windows):
            logger.info(f"\n{'='*80}")
            logger.info(f"Window {i+1}/{len(windows)}")
            logger.info(f"Train: {train_start.date()} to {train_end.date()}")
            logger.info(f"Test:  {test_start.date()} to {test_end.date()}")
            logger.info(f"{'='*80}")
            
            # Get test data
            test_data = market_data[(market_data.index >= test_start) & 
                                   (market_data.index <= test_end)]
            
            if len(test_data) == 0:
                logger.warning("No data in test window, skipping")
                continue
            
            # Initialize strategies (NO TRAINING - using fixed parameters)
            capital_per_strategy = self.initial_capital / 5
            strategies = [
                RSIMeanReversionStrategy(1, capital_per_strategy),
                MACrossoverStrategy(2, capital_per_strategy),
                MLMomentumStrategy(3, capital_per_strategy),
                NewsSentimentStrategy(4, capital_per_strategy),
                VolatilityBreakoutStrategy(5, capital_per_strategy)
            ]
            
            # Initialize modules
            regime_detector = RegimeDetector()
            correlation_filter = CorrelationFilter()
            portfolio_risk = PortfolioRiskManager()
            cost_model = ExecutionCostModel()
            
            # Run backtest on test window
            backtester = PortfolioBacktester(
                initial_capital=self.initial_capital,
                start_date=test_start.strftime('%Y-%m-%d'),
                end_date=test_end.strftime('%Y-%m-%d')
            )
            
            results = backtester.run_backtest(
                market_data=test_data,
                strategies=strategies,
                regime_detector=regime_detector,
                correlation_filter=correlation_filter,
                portfolio_risk=portfolio_risk,
                cost_model=cost_model
            )
            
            # Store results
            results['window'] = i + 1
            results['test_start'] = test_start
            results['test_end'] = test_end
            all_results.append(results)
            
            # Combine equity curves
            if 'equity_curve' in results and len(results['equity_curve']) > 0:
                combined_equity.append(results['equity_curve'])
            
            # Combine trades
            if 'trades' in results and len(results['trades']) > 0:
                combined_trades.append(results['trades'])
            
            # Log window results
            logger.info(f"Window {i+1} Results:")
            logger.info(f"  Return: {results.get('total_return', 0):.2f}%")
            logger.info(f"  Sharpe: {results.get('sharpe_ratio', 0):.2f}")
            logger.info(f"  Max DD: {results.get('max_drawdown', 0):.2f}%")
            logger.info(f"  Trades: {results.get('total_trades', 0)}")
        
        # Combine all results
        if combined_equity:
            full_equity = pd.concat(combined_equity, ignore_index=False)
        else:
            full_equity = pd.DataFrame()
        
        if combined_trades:
            full_trades = pd.concat(combined_trades, ignore_index=True)
        else:
            full_trades = pd.DataFrame()
        
        # Calculate aggregate metrics
        aggregate_results = self._calculate_aggregate_metrics(
            all_results, full_equity, full_trades
        )
        
        return {
            'window_results': all_results,
            'aggregate_results': aggregate_results,
            'full_equity_curve': full_equity,
            'all_trades': full_trades
        }
    
    def _calculate_aggregate_metrics(self, window_results, equity_curve, trades):
        """Calculate aggregate metrics across all windows"""
        if len(equity_curve) == 0:
            return {}
        
        # Portfolio-level metrics
        initial_value = equity_curve.iloc[0]['portfolio_value']
        final_value = equity_curve.iloc[-1]['portfolio_value']
        total_return = (final_value - initial_value) / initial_value
        
        # Calculate CAGR
        days = (equity_curve.iloc[-1]['date'] - equity_curve.iloc[0]['date']).days
        years = days / 365.25
        cagr = (final_value / initial_value) ** (1 / years) - 1 if years > 0 else 0
        
        # Daily returns
        equity_curve['daily_return'] = equity_curve['portfolio_value'].pct_change()
        daily_returns = equity_curve['daily_return'].dropna()
        
        # Volatility
        annual_vol = daily_returns.std() * np.sqrt(252)
        
        # Sharpe ratio
        sharpe = np.sqrt(252) * (daily_returns.mean() / daily_returns.std()) if daily_returns.std() > 0 else 0
        
        # Sortino ratio
        downside_returns = daily_returns[daily_returns < 0]
        downside_std = downside_returns.std() if len(downside_returns) > 0 else 0
        sortino = np.sqrt(252) * (daily_returns.mean() / downside_std) if downside_std > 0 else 0
        
        # Max drawdown
        running_max = equity_curve['portfolio_value'].expanding().max()
        drawdown = (equity_curve['portfolio_value'] - running_max) / running_max
        max_drawdown = abs(drawdown.min()) * 100
        
        # Calmar ratio
        calmar = cagr / (max_drawdown / 100) if max_drawdown > 0 else 0
        
        # Trade statistics
        if len(trades) > 0:
            completed_trades = trades[trades['action'] == 'SELL']
            if len(completed_trades) > 0:
                winning_trades = completed_trades[completed_trades['pnl'] > 0]
                win_rate = len(winning_trades) / len(completed_trades) * 100
                avg_win = winning_trades['pnl'].mean() if len(winning_trades) > 0 else 0
                losing_trades = completed_trades[completed_trades['pnl'] <= 0]
                avg_loss = losing_trades['pnl'].mean() if len(losing_trades) > 0 else 0
                profit_factor = abs(winning_trades['pnl'].sum() / losing_trades['pnl'].sum()) if len(losing_trades) > 0 and losing_trades['pnl'].sum() != 0 else 0
            else:
                win_rate = 0
                avg_win = 0
                avg_loss = 0
                profit_factor = 0
        else:
            win_rate = 0
            avg_win = 0
            avg_loss = 0
            profit_factor = 0
        
        return {
            'initial_capital': initial_value,
            'final_value': final_value,
            'total_return_pct': total_return * 100,
            'cagr': cagr * 100,
            'annual_volatility': annual_vol * 100,
            'sharpe_ratio': sharpe,
            'sortino_ratio': sortino,
            'calmar_ratio': calmar,
            'max_drawdown_pct': max_drawdown,
            'win_rate_pct': win_rate,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': profit_factor,
            'total_trades': len(trades),
            'num_windows': len(window_results)
        }
    
    def save_results(self, results: dict, output_dir: str = 'backtest_results'):
        """Save backtest results to disk"""
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Save equity curve
        if len(results['full_equity_curve']) > 0:
            equity_file = output_path / f'equity_curve_{timestamp}.csv'
            results['full_equity_curve'].to_csv(equity_file)
            logger.info(f"Saved equity curve to {equity_file}")
        
        # Save trades
        if len(results['all_trades']) > 0:
            trades_file = output_path / f'trades_{timestamp}.csv'
            results['all_trades'].to_csv(trades_file, index=False)
            logger.info(f"Saved trades to {trades_file}")
        
        # Save aggregate metrics
        metrics_file = output_path / f'metrics_{timestamp}.json'
        with open(metrics_file, 'w') as f:
            # Convert to JSON-serializable format
            metrics = results['aggregate_results'].copy()
            json.dump(metrics, f, indent=2)
        logger.info(f"Saved metrics to {metrics_file}")
        
        return output_path

def main():
    """Run walk-forward backtest"""
    logger.info("="*80)
    logger.info("WALK-FORWARD BACKTEST - EMPIRICAL VALIDATION")
    logger.info("="*80)
    
    # Data paths
    data_path = 'data/training_data.csv'
    vix_path = 'data/vix_data.csv'  # Optional
    
    # Initialize
    backtester = WalkForwardBacktester(
        data_path=data_path,
        vix_data_path=vix_path if Path(vix_path).exists() else None,
        initial_capital=100000
    )
    
    # Load data
    market_data = backtester.load_data()
    vix_data = backtester.load_vix_data()
    
    # Run walk-forward backtest
    results = backtester.run_walk_forward(market_data, vix_data)
    
    # Save results
    output_dir = backtester.save_results(results)
    
    # Print summary
    print("\n" + "="*80)
    print("WALK-FORWARD BACKTEST RESULTS")
    print("="*80)
    
    metrics = results['aggregate_results']
    print(f"\nInitial Capital:     ${metrics['initial_capital']:,.2f}")
    print(f"Final Value:         ${metrics['final_value']:,.2f}")
    print(f"Total Return:        {metrics['total_return_pct']:.2f}%")
    print(f"CAGR:                {metrics['cagr']:.2f}%")
    print(f"Annual Volatility:   {metrics['annual_volatility']:.2f}%")
    print(f"\nSharpe Ratio:        {metrics['sharpe_ratio']:.2f}")
    print(f"Sortino Ratio:       {metrics['sortino_ratio']:.2f}")
    print(f"Calmar Ratio:        {metrics['calmar_ratio']:.2f}")
    print(f"\nMax Drawdown:        {metrics['max_drawdown_pct']:.2f}%")
    print(f"Win Rate:            {metrics['win_rate_pct']:.1f}%")
    print(f"Profit Factor:       {metrics['profit_factor']:.2f}")
    print(f"\nTotal Trades:        {metrics['total_trades']}")
    print(f"Windows Tested:      {metrics['num_windows']}")
    print("="*80)
    
    # Check for red flags
    print("\nVALIDATION CHECKS:")
    if metrics['sharpe_ratio'] > 2.0:
        print("⚠️  WARNING: Sharpe > 2.0 - Possible leakage or overfitting")
    if metrics['max_drawdown_pct'] < 5.0:
        print("⚠️  WARNING: Max DD < 5% - Unrealistic, check for bias")
    if metrics['win_rate_pct'] > 65.0:
        print("⚠️  WARNING: Win rate > 65% - Suspicious, investigate")
    
    if (metrics['sharpe_ratio'] <= 2.0 and 
        metrics['max_drawdown_pct'] >= 5.0 and 
        metrics['win_rate_pct'] <= 65.0):
        print("✅ No obvious red flags detected")
    
    print("\nResults saved to:", output_dir)
    
    return results

if __name__ == '__main__':
    results = main()
