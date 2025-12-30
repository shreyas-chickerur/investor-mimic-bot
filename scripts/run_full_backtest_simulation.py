#!/usr/bin/env python3
"""
Full Walk-Forward Backtesting with Strategy Simulation
Uses existing 15-year historical data to simulate strategy execution
"""
import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
import logging
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class StrategySimulator:
    """Simulates trading strategies on historical data"""
    
    def __init__(self, initial_capital=100000):
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.positions = {}
        self.trades = []
        
    def calculate_momentum(self, prices, period=20):
        """Calculate momentum indicator"""
        if len(prices) < period:
            return 0
        return (prices.iloc[-1] / prices.iloc[-period] - 1) * 100
    
    def calculate_rsi(self, prices, period=14):
        """Calculate RSI indicator"""
        if len(prices) < period + 1:
            return 50
        
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi.iloc[-1] if not pd.isna(rsi.iloc[-1]) else 50
    
    def generate_signals(self, data, date):
        """Generate trading signals for a given date"""
        signals = []
        
        # Get data up to this date
        historical = data[data.index <= date]
        
        for symbol in data['symbol'].unique():
            symbol_data = historical[historical['symbol'] == symbol].sort_index()
            
            if len(symbol_data) < 50:  # Need minimum history
                continue
            
            prices = symbol_data['close']
            current_price = prices.iloc[-1]
            
            # Calculate indicators
            momentum_20 = self.calculate_momentum(prices, 20)
            rsi = self.calculate_rsi(prices, 14)
            
            # Simple momentum strategy: Buy if momentum > 5% and RSI < 70
            if momentum_20 > 5 and rsi < 70 and symbol not in self.positions:
                signals.append({
                    'date': date,
                    'symbol': symbol,
                    'action': 'BUY',
                    'price': current_price,
                    'momentum': momentum_20,
                    'rsi': rsi
                })
            
            # Sell if momentum < -3% or RSI > 75
            elif (momentum_20 < -3 or rsi > 75) and symbol in self.positions:
                signals.append({
                    'date': date,
                    'symbol': symbol,
                    'action': 'SELL',
                    'price': current_price,
                    'momentum': momentum_20,
                    'rsi': rsi
                })
        
        return signals
    
    def execute_trades(self, signals, max_positions=10):
        """Execute trading signals"""
        # Sort buy signals by momentum
        buy_signals = [s for s in signals if s['action'] == 'BUY']
        sell_signals = [s for s in signals if s['action'] == 'SELL']
        
        # Execute sells first
        for signal in sell_signals:
            if signal['symbol'] in self.positions:
                position = self.positions[signal['symbol']]
                shares = position['shares']
                entry_price = position['entry_price']
                exit_price = signal['price']
                
                pnl = (exit_price - entry_price) * shares
                self.cash += exit_price * shares
                
                self.trades.append({
                    'entry_date': position['entry_date'],
                    'exit_date': signal['date'],
                    'symbol': signal['symbol'],
                    'shares': shares,
                    'entry_price': entry_price,
                    'exit_price': exit_price,
                    'pnl': pnl,
                    'return_pct': (exit_price / entry_price - 1) * 100
                })
                
                del self.positions[signal['symbol']]
        
        # Execute buys
        buy_signals = sorted(buy_signals, key=lambda x: x['momentum'], reverse=True)
        
        for signal in buy_signals:
            if len(self.positions) >= max_positions:
                break
            
            if signal['symbol'] in self.positions:
                continue
            
            # Position size: 10% of portfolio value
            position_size = (self.cash + self.get_portfolio_value(signal['date'], signal['price'])) * 0.10
            shares = int(position_size / signal['price'])
            
            if shares > 0 and shares * signal['price'] <= self.cash:
                self.cash -= shares * signal['price']
                self.positions[signal['symbol']] = {
                    'shares': shares,
                    'entry_price': signal['price'],
                    'entry_date': signal['date']
                }
    
    def get_portfolio_value(self, date, current_prices=None):
        """Calculate total portfolio value"""
        position_value = sum([
            pos['shares'] * pos['entry_price'] 
            for pos in self.positions.values()
        ])
        return position_value
    
    def get_total_value(self):
        """Get total portfolio value including cash"""
        return self.cash + self.get_portfolio_value(None)


class FullBacktestEngine:
    """Complete backtesting engine"""
    
    def __init__(self, initial_capital=100000):
        self.initial_capital = initial_capital
        
    def load_data(self, data_file):
        """Load historical data"""
        logger.info(f"Loading data from {data_file}")
        
        df = pd.read_csv(data_file)
        
        # Handle date column
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'])
            df = df.set_index('date')
        else:
            df.index = pd.to_datetime(df.index)
            df.index.name = 'date'
        
        logger.info(f"Data loaded: {len(df):,} rows, {df['symbol'].nunique()} symbols")
        logger.info(f"Date range: {df.index.min().date()} to {df.index.max().date()}")
        
        return df
    
    def run_backtest(self, data):
        """Run full backtest with strategy simulation"""
        logger.info("="*70)
        logger.info("WALK-FORWARD BACKTEST WITH STRATEGY SIMULATION")
        logger.info("="*70)
        
        # Get unique trading dates
        dates = sorted(data.index.unique())
        
        # Initialize simulator
        simulator = StrategySimulator(self.initial_capital)
        
        # Track equity curve
        equity_curve = []
        equity_dates = []
        
        # Simulate trading day by day
        logger.info(f"\nSimulating {len(dates)} trading days...")
        
        for i, date in enumerate(dates):
            # Generate signals
            signals = simulator.generate_signals(data, date)
            
            # Execute trades
            simulator.execute_trades(signals)
            
            # Record equity
            total_value = simulator.get_total_value()
            equity_curve.append(total_value)
            equity_dates.append(date)
            
            # Log progress every 500 days
            if (i + 1) % 500 == 0:
                logger.info(f"  Day {i+1}/{len(dates)}: Portfolio = ${total_value:,.2f}, "
                          f"Positions = {len(simulator.positions)}, Trades = {len(simulator.trades)}")
        
        logger.info(f"\nSimulation complete!")
        logger.info(f"Total trades: {len(simulator.trades)}")
        logger.info(f"Final portfolio value: ${equity_curve[-1]:,.2f}")
        
        # Create series
        equity_series = pd.Series(equity_curve, index=equity_dates)
        trades_df = pd.DataFrame(simulator.trades)
        
        return equity_series, trades_df
    
    def calculate_metrics(self, equity_curve, trades_df):
        """Calculate performance metrics"""
        
        if len(equity_curve) < 2:
            return {}
        
        # Returns
        returns = equity_curve.pct_change().dropna()
        total_return = (equity_curve.iloc[-1] / equity_curve.iloc[0]) - 1
        num_years = (equity_curve.index[-1] - equity_curve.index[0]).days / 365.25
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
        
        # Calmar
        calmar = abs(cagr / max_drawdown) if max_drawdown != 0 else 0
        
        # Trading metrics
        if len(trades_df) > 0:
            wins = trades_df[trades_df['pnl'] > 0]
            losses = trades_df[trades_df['pnl'] < 0]
            
            win_rate = len(wins) / len(trades_df)
            avg_win = wins['pnl'].mean() if len(wins) > 0 else 0
            avg_loss = losses['pnl'].mean() if len(losses) > 0 else 0
            profit_factor = abs(wins['pnl'].sum() / losses['pnl'].sum()) if len(losses) > 0 and losses['pnl'].sum() != 0 else 0
            best_trade = trades_df['return_pct'].max()
            worst_trade = trades_df['return_pct'].min()
            avg_hold_days = (pd.to_datetime(trades_df['exit_date']) - pd.to_datetime(trades_df['entry_date'])).dt.days.mean()
        else:
            win_rate = avg_win = avg_loss = profit_factor = best_trade = worst_trade = avg_hold_days = 0
        
        return {
            'total_return': total_return,
            'cagr': cagr,
            'annual_vol': annual_vol,
            'sharpe': sharpe,
            'sortino': sortino,
            'calmar': calmar,
            'max_drawdown': max_drawdown,
            'num_trades': len(trades_df),
            'win_rate': win_rate,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': profit_factor,
            'best_trade': best_trade,
            'worst_trade': worst_trade,
            'avg_hold_days': avg_hold_days
        }
    
    def generate_plots(self, equity_curve, trades_df, metrics, output_dir='artifacts/backtest'):
        """Generate performance plots"""
        
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Plot 1: Equity Curve
        fig, ax = plt.subplots(figsize=(14, 7))
        ax.plot(equity_curve.index.to_numpy(), equity_curve.values, linewidth=2, color='#2E86AB')
        ax.fill_between(equity_curve.index.to_numpy(), self.initial_capital, equity_curve.values, alpha=0.3, color='#2E86AB')
        ax.axhline(y=self.initial_capital, color='gray', linestyle='--', alpha=0.5, label='Initial Capital')
        ax.set_title('Portfolio Equity Curve (Walk-Forward Backtest)', fontsize=16, fontweight='bold', pad=20)
        ax.set_xlabel('Date', fontsize=12)
        ax.set_ylabel('Portfolio Value ($)', fontsize=12)
        ax.grid(True, alpha=0.3)
        ax.legend()
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(output_path / 'equity_curve.png', dpi=150, bbox_inches='tight')
        plt.close()
        logger.info(f"  ✓ Saved equity_curve.png")
        
        # Plot 2: Drawdown
        cumulative = equity_curve / equity_curve.iloc[0]
        running_max = cumulative.expanding().max()
        drawdown = (cumulative - running_max) / running_max
        
        fig, ax = plt.subplots(figsize=(14, 7))
        ax.fill_between(drawdown.index.to_numpy(), drawdown.values * 100, 0, alpha=0.3, color='red')
        ax.plot(drawdown.index.to_numpy(), drawdown.values * 100, color='red', linewidth=2)
        ax.set_title('Portfolio Drawdown', fontsize=16, fontweight='bold', pad=20)
        ax.set_xlabel('Date', fontsize=12)
        ax.set_ylabel('Drawdown (%)', fontsize=12)
        ax.grid(True, alpha=0.3)
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(output_path / 'drawdown.png', dpi=150, bbox_inches='tight')
        plt.close()
        logger.info(f"  ✓ Saved drawdown.png")
        
        # Plot 3: Rolling Sharpe
        returns = equity_curve.pct_change().dropna()
        rolling_sharpe = returns.rolling(252).mean() / returns.rolling(252).std() * np.sqrt(252)
        
        fig, ax = plt.subplots(figsize=(14, 7))
        ax.plot(rolling_sharpe.index.to_numpy(), rolling_sharpe.values, linewidth=2, color='#06A77D')
        ax.axhline(y=0, color='red', linestyle='--', alpha=0.3)
        ax.axhline(y=1, color='green', linestyle='--', alpha=0.3, label='Sharpe = 1.0')
        ax.set_title('Rolling 12-Month Sharpe Ratio', fontsize=16, fontweight='bold', pad=20)
        ax.set_xlabel('Date', fontsize=12)
        ax.set_ylabel('Sharpe Ratio', fontsize=12)
        ax.grid(True, alpha=0.3)
        ax.legend()
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(output_path / 'rolling_sharpe.png', dpi=150, bbox_inches='tight')
        plt.close()
        logger.info(f"  ✓ Saved rolling_sharpe.png")
        
        logger.info(f"\n✅ All plots saved to: {output_path}/")
    
    def generate_report(self, metrics, output_file):
        """Generate markdown report"""
        
        report = f"""# Walk-Forward Backtest Results

**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Portfolio Performance Metrics

### Return Metrics
- **Total Return:** {metrics['total_return']*100:.2f}%
- **CAGR:** {metrics['cagr']*100:.2f}%
- **Annual Volatility:** {metrics['annual_vol']*100:.2f}%

### Risk-Adjusted Returns
- **Sharpe Ratio:** {metrics['sharpe']:.2f}
- **Sortino Ratio:** {metrics['sortino']:.2f}
- **Calmar Ratio:** {metrics['calmar']:.2f}

### Risk Metrics
- **Max Drawdown:** {metrics['max_drawdown']*100:.2f}%

### Trading Metrics
- **Number of Trades:** {metrics['num_trades']}
- **Win Rate:** {metrics['win_rate']*100:.1f}%
- **Average Win:** ${metrics['avg_win']:.2f}
- **Average Loss:** ${metrics['avg_loss']:.2f}
- **Profit Factor:** {metrics['profit_factor']:.2f}
- **Best Trade:** {metrics['best_trade']:.2f}%
- **Worst Trade:** {metrics['worst_trade']:.2f}%
- **Avg Hold Period:** {metrics['avg_hold_days']:.1f} days

## Methodology

- **Strategy:** Simple momentum strategy with RSI filter
- **Entry:** Momentum > 5% AND RSI < 70
- **Exit:** Momentum < -3% OR RSI > 75
- **Position Sizing:** 10% of portfolio per position
- **Max Positions:** 10 concurrent positions
- **Initial Capital:** ${self.initial_capital:,}

## Risk Controls

- Maximum 10 concurrent positions
- 10% position sizing (diversification)
- RSI overbought/oversold filters
- Momentum-based entry/exit rules

## Notes

- Backtest uses actual historical data (2010-2025)
- No lookahead bias - signals generated with data available at time
- Simple strategy for demonstration purposes
- Real system uses 5 strategies with advanced risk controls

---

*This backtest uses historical data and does not guarantee future performance.*
"""
        
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w') as f:
            f.write(report)
        
        logger.info(f"✅ Performance report saved to: {output_path}")


def main():
    """Run full backtest"""
    
    # Check for data
    data_file = 'data/training_data.csv'
    if not Path(data_file).exists():
        logger.error(f"Data file not found: {data_file}")
        logger.info("Run 'make fetch-data' to download historical data")
        return
    
    # Run backtest
    engine = FullBacktestEngine(initial_capital=100000)
    
    # Load data
    data = engine.load_data(data_file)
    
    # Run simulation
    equity_curve, trades_df = engine.run_backtest(data)
    
    # Calculate metrics
    logger.info("\nCalculating performance metrics...")
    metrics = engine.calculate_metrics(equity_curve, trades_df)
    
    # Print results
    logger.info("\n" + "="*70)
    logger.info("BACKTEST RESULTS")
    logger.info("="*70)
    logger.info(f"Total Return: {metrics['total_return']*100:.2f}%")
    logger.info(f"CAGR: {metrics['cagr']*100:.2f}%")
    logger.info(f"Sharpe Ratio: {metrics['sharpe']:.2f}")
    logger.info(f"Max Drawdown: {metrics['max_drawdown']*100:.2f}%")
    logger.info(f"Win Rate: {metrics['win_rate']*100:.1f}%")
    logger.info(f"Number of Trades: {metrics['num_trades']}")
    logger.info("="*70)
    
    # Generate plots
    logger.info("\nGenerating performance plots...")
    engine.generate_plots(equity_curve, trades_df, metrics)
    
    # Generate report
    logger.info("\nGenerating performance report...")
    engine.generate_report(metrics, 'artifacts/backtest/performance_report.md')
    
    logger.info("\n🎉 Full backtest complete!")
    logger.info(f"📊 View results:")
    logger.info(f"   - Report: artifacts/backtest/performance_report.md")
    logger.info(f"   - Equity: artifacts/backtest/equity_curve.png")
    logger.info(f"   - Drawdown: artifacts/backtest/drawdown.png")
    logger.info(f"   - Sharpe: artifacts/backtest/rolling_sharpe.png")


if __name__ == '__main__':
    main()
