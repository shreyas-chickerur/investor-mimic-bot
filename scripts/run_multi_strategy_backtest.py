#!/usr/bin/env python3
"""
Multi-Strategy Backtest
Tests all 5 strategies independently and compares performance
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timedelta
import logging
from tqdm import tqdm

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class StrategyBacktester:
    """Backtest individual strategies"""
    
    def __init__(self, strategy_name, initial_capital=100000):
        self.strategy_name = strategy_name
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.positions = {}
        self.trades = []
        self.equity_curve = []
        
    def calculate_rsi(self, prices, period=14):
        """Calculate RSI"""
        if len(prices) < period + 1:
            return 50
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi.iloc[-1] if not pd.isna(rsi.iloc[-1]) else 50
    
    def generate_signals_rsi(self, data, date):
        """RSI Mean Reversion Strategy"""
        signals = []
        historical = data[data.index <= date]
        
        for symbol in data['symbol'].unique():
            symbol_data = historical[historical['symbol'] == symbol].sort_index()
            if len(symbol_data) < 50:
                continue
            
            prices = symbol_data['close']
            current_price = prices.iloc[-1]
            rsi = self.calculate_rsi(prices, 14)
            
            # RSI slope
            if len(symbol_data) >= 2:
                rsi_prev = self.calculate_rsi(symbol_data['close'].iloc[:-1], 14)
                rsi_slope = rsi - rsi_prev
            else:
                rsi_slope = 0
            
            # Buy: RSI < 30 and turning up
            if rsi < 30 and rsi_slope > 0 and symbol not in self.positions:
                signals.append({
                    'date': date, 'symbol': symbol, 'action': 'BUY',
                    'price': current_price, 'indicator': f'RSI={rsi:.1f}'
                })
            
            # Sell: RSI > 50 or held 20 days
            elif symbol in self.positions:
                entry_date = self.positions[symbol]['entry_date']
                days_held = (date - entry_date).days
                if rsi > 50 or days_held >= 20:
                    signals.append({
                        'date': date, 'symbol': symbol, 'action': 'SELL',
                        'price': current_price, 'indicator': f'RSI={rsi:.1f}, held={days_held}'
                    })
        
        return signals
    
    def generate_signals_ma_crossover(self, data, date):
        """MA Crossover Strategy"""
        signals = []
        historical = data[data.index <= date]
        
        for symbol in data['symbol'].unique():
            symbol_data = historical[historical['symbol'] == symbol].sort_index()
            if len(symbol_data) < 100:
                continue
            
            prices = symbol_data['close']
            current_price = prices.iloc[-1]
            
            # Calculate MAs
            ma_20 = prices.rolling(20).mean().iloc[-1]
            ma_100 = prices.rolling(100).mean().iloc[-1]
            ma_20_prev = prices.rolling(20).mean().iloc[-2]
            ma_100_prev = prices.rolling(100).mean().iloc[-2]
            
            # Golden cross
            if ma_20_prev <= ma_100_prev and ma_20 > ma_100 and symbol not in self.positions:
                signals.append({
                    'date': date, 'symbol': symbol, 'action': 'BUY',
                    'price': current_price, 'indicator': f'Golden Cross'
                })
            
            # Death cross
            elif ma_20_prev >= ma_100_prev and ma_20 < ma_100 and symbol in self.positions:
                signals.append({
                    'date': date, 'symbol': symbol, 'action': 'SELL',
                    'price': current_price, 'indicator': f'Death Cross'
                })
        
        return signals
    
    def generate_signals_volatility_breakout(self, data, date):
        """Volatility Breakout Strategy"""
        signals = []
        historical = data[data.index <= date]
        
        for symbol in data['symbol'].unique():
            symbol_data = historical[historical['symbol'] == symbol].sort_index()
            if len(symbol_data) < 25:
                continue
            
            prices = symbol_data['close']
            volumes = symbol_data['volume']
            current_price = prices.iloc[-1]
            prev_price = prices.iloc[-2]
            current_volume = volumes.iloc[-1]
            avg_volume = volumes.iloc[-20:].mean()
            
            # Bollinger Bands
            ma = prices.rolling(20).mean().iloc[-1]
            std = prices.rolling(20).std().iloc[-1]
            upper_band = ma + (2 * std)
            upper_band_prev = prices.rolling(20).mean().iloc[-2] + (2 * prices.rolling(20).std().iloc[-2])
            
            # Buy: 2 consecutive closes above upper band with volume
            if (current_price > upper_band and prev_price > upper_band_prev and 
                current_volume > avg_volume * 1.5 and symbol not in self.positions):
                signals.append({
                    'date': date, 'symbol': symbol, 'action': 'BUY',
                    'price': current_price, 'indicator': f'BB Breakout'
                })
            
            # Sell: Price below MA or held 7 days
            elif symbol in self.positions:
                entry_date = self.positions[symbol]['entry_date']
                days_held = (date - entry_date).days
                if current_price < ma or days_held >= 7:
                    signals.append({
                        'date': date, 'symbol': symbol, 'action': 'SELL',
                        'price': current_price, 'indicator': f'Exit, held={days_held}'
                    })
        
        return signals
    
    def generate_signals_momentum(self, data, date):
        """Simple Momentum Strategy"""
        signals = []
        historical = data[data.index <= date]
        
        for symbol in data['symbol'].unique():
            symbol_data = historical[historical['symbol'] == symbol].sort_index()
            if len(symbol_data) < 50:
                continue
            
            prices = symbol_data['close']
            current_price = prices.iloc[-1]
            
            # 20-day momentum
            momentum_20 = (prices.iloc[-1] / prices.iloc[-20] - 1) * 100 if len(prices) >= 20 else 0
            rsi = self.calculate_rsi(prices, 14)
            
            # Buy: Strong momentum and not overbought
            if momentum_20 > 5 and rsi < 70 and symbol not in self.positions:
                signals.append({
                    'date': date, 'symbol': symbol, 'action': 'BUY',
                    'price': current_price, 'indicator': f'Mom={momentum_20:.1f}%'
                })
            
            # Sell: Momentum reversal or overbought
            elif symbol in self.positions and (momentum_20 < -3 or rsi > 75):
                signals.append({
                    'date': date, 'symbol': symbol, 'action': 'SELL',
                    'price': current_price, 'indicator': f'Mom={momentum_20:.1f}%'
                })
        
        return signals
    
    def generate_signals_ml_momentum(self, data, date):
        """ML Momentum Strategy (simplified - uses feature-based scoring)"""
        signals = []
        historical = data[data.index <= date]
        
        for symbol in data['symbol'].unique():
            symbol_data = historical[historical['symbol'] == symbol].sort_index()
            if len(symbol_data) < 50:
                continue
            
            prices = symbol_data['close']
            volumes = symbol_data['volume']
            current_price = prices.iloc[-1]
            
            # Feature engineering
            rsi = self.calculate_rsi(prices, 14)
            ret_5d = (prices.iloc[-1] / prices.iloc[-5] - 1) * 100 if len(prices) >= 5 else 0
            ret_20d = (prices.iloc[-1] / prices.iloc[-20] - 1) * 100 if len(prices) >= 20 else 0
            vol_ratio = volumes.iloc[-1] / volumes.iloc[-20:].mean() if len(volumes) >= 20 else 1
            
            # Simple scoring (proxy for ML model)
            score = 0
            if 30 < rsi < 70:
                score += 1
            if ret_5d > 0:
                score += 1
            if ret_20d > 0:
                score += 1
            if vol_ratio > 1.2:
                score += 1
            
            probability = score / 4.0
            
            # Buy: High probability score
            if probability >= 0.6 and symbol not in self.positions:
                signals.append({
                    'date': date, 'symbol': symbol, 'action': 'BUY',
                    'price': current_price, 'indicator': f'ML Score={probability:.2f}'
                })
            
            # Sell: Low probability or held 5 days
            elif symbol in self.positions:
                entry_date = self.positions[symbol]['entry_date']
                days_held = (date - entry_date).days
                if probability < 0.4 or days_held >= 5:
                    signals.append({
                        'date': date, 'symbol': symbol, 'action': 'SELL',
                        'price': current_price, 'indicator': f'ML Score={probability:.2f}'
                    })
        
        return signals
    
    def execute_trades(self, signals, max_positions=10):
        """Execute trades with position limits"""
        for signal in signals:
            if signal['action'] == 'SELL' and signal['symbol'] in self.positions:
                # Execute sell
                position = self.positions[signal['symbol']]
                shares = position['shares']
                entry_price = position['entry_price']
                exit_price = signal['price']
                pnl = (exit_price - entry_price) * shares
                
                self.cash += exit_price * shares
                del self.positions[signal['symbol']]
                
                self.trades.append({
                    'date': signal['date'],
                    'symbol': signal['symbol'],
                    'action': 'SELL',
                    'shares': shares,
                    'price': exit_price,
                    'pnl': pnl,
                    'indicator': signal['indicator']
                })
        
        # Execute buys
        buy_signals = [s for s in signals if s['action'] == 'BUY']
        available_slots = max_positions - len(self.positions)
        
        for signal in buy_signals[:available_slots]:
            if self.cash > 0:
                # Equal weight allocation
                position_value = min(self.cash / (available_slots or 1), self.cash * 0.1)
                shares = int(position_value / signal['price'])
                
                if shares > 0:
                    cost = shares * signal['price']
                    self.cash -= cost
                    
                    self.positions[signal['symbol']] = {
                        'shares': shares,
                        'entry_price': signal['price'],
                        'entry_date': signal['date']
                    }
                    
                    self.trades.append({
                        'date': signal['date'],
                        'symbol': signal['symbol'],
                        'action': 'BUY',
                        'shares': shares,
                        'price': signal['price'],
                        'pnl': 0,
                        'indicator': signal['indicator']
                    })
    
    def calculate_portfolio_value(self, data, date):
        """Calculate total portfolio value"""
        position_value = 0
        for symbol, position in self.positions.items():
            symbol_data = data[(data['symbol'] == symbol) & (data.index <= date)]
            if len(symbol_data) > 0:
                current_price = symbol_data['close'].iloc[-1]
                position_value += position['shares'] * current_price
        
        return self.cash + position_value
    
    def run_backtest(self, data, strategy_type):
        """Run backtest for specific strategy"""
        logger.info(f"\n{'='*60}")
        logger.info(f"Running {self.strategy_name} backtest...")
        logger.info(f"{'='*60}")
        
        trading_days = sorted(data.index.unique())
        
        # Use tqdm for progress bar
        for date in tqdm(trading_days, desc=f"{self.strategy_name}", unit="day"):
            # Generate signals based on strategy type
            if strategy_type == 'rsi':
                signals = self.generate_signals_rsi(data, date)
            elif strategy_type == 'ma_crossover':
                signals = self.generate_signals_ma_crossover(data, date)
            elif strategy_type == 'volatility_breakout':
                signals = self.generate_signals_volatility_breakout(data, date)
            elif strategy_type == 'momentum':
                signals = self.generate_signals_momentum(data, date)
            elif strategy_type == 'ml_momentum':
                signals = self.generate_signals_ml_momentum(data, date)
            else:
                signals = []
            
            # Execute trades
            self.execute_trades(signals)
            
            # Track equity
            portfolio_value = self.calculate_portfolio_value(data, date)
            self.equity_curve.append({
                'date': date,
                'value': portfolio_value,
                'cash': self.cash,
                'positions': len(self.positions)
            })
        
        logger.info(f"✅ {self.strategy_name} complete!")
        logger.info(f"  Total trades: {len(self.trades)}")
        logger.info(f"  Final portfolio: ${portfolio_value:,.2f}")
        
        return pd.DataFrame(self.equity_curve), pd.DataFrame(self.trades)


def calculate_metrics(equity_curve, trades_df, initial_capital):
    """Calculate performance metrics"""
    if len(equity_curve) == 0:
        return {}
    
    equity_series = pd.Series(equity_curve['value'].values, index=equity_curve['date'])
    returns = equity_series.pct_change().dropna()
    
    total_return = (equity_series.iloc[-1] / initial_capital - 1) * 100
    years = (equity_series.index[-1] - equity_series.index[0]).days / 365.25
    cagr = ((equity_series.iloc[-1] / initial_capital) ** (1 / years) - 1) * 100 if years > 0 else 0
    
    # Risk metrics
    volatility = returns.std() * np.sqrt(252) * 100
    sharpe = (returns.mean() / returns.std() * np.sqrt(252)) if returns.std() > 0 else 0
    
    # Drawdown
    cumulative = equity_series / equity_series.iloc[0]
    running_max = cumulative.expanding().max()
    drawdown = (cumulative - running_max) / running_max
    max_drawdown = drawdown.min() * 100
    
    # Trade metrics
    if len(trades_df) > 0:
        winning_trades = trades_df[trades_df['pnl'] > 0]
        losing_trades = trades_df[trades_df['pnl'] < 0]
        win_rate = len(winning_trades) / len(trades_df[trades_df['action'] == 'SELL']) * 100 if len(trades_df[trades_df['action'] == 'SELL']) > 0 else 0
        avg_win = winning_trades['pnl'].mean() if len(winning_trades) > 0 else 0
        avg_loss = losing_trades['pnl'].mean() if len(losing_trades) > 0 else 0
        profit_factor = abs(winning_trades['pnl'].sum() / losing_trades['pnl'].sum()) if len(losing_trades) > 0 and losing_trades['pnl'].sum() != 0 else 0
    else:
        win_rate = avg_win = avg_loss = profit_factor = 0
    
    return {
        'Total Return (%)': total_return,
        'CAGR (%)': cagr,
        'Volatility (%)': volatility,
        'Sharpe Ratio': sharpe,
        'Max Drawdown (%)': max_drawdown,
        'Win Rate (%)': win_rate,
        'Avg Win ($)': avg_win,
        'Avg Loss ($)': avg_loss,
        'Profit Factor': profit_factor,
        'Total Trades': len(trades_df[trades_df['action'] == 'SELL'])
    }


def generate_comparison_report(results, output_dir='artifacts/backtest'):
    """Generate comparison report"""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Create comparison table
    comparison_df = pd.DataFrame(results).T
    
    report = f"""# Multi-Strategy Backtest Comparison

**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  
**Period:** 15 years (2010-2025)  
**Initial Capital:** $100,000  
**Universe:** 32 large-cap US stocks

## Performance Comparison

{comparison_df.to_markdown(floatfmt='.2f')}

## Strategy Rankings

### By Total Return
{comparison_df.sort_values('Total Return (%)', ascending=False)[['Total Return (%)']].to_markdown(floatfmt='.2f')}

### By Sharpe Ratio
{comparison_df.sort_values('Sharpe Ratio', ascending=False)[['Sharpe Ratio']].to_markdown(floatfmt='.2f')}

### By Max Drawdown (Lower is Better)
{comparison_df.sort_values('Max Drawdown (%)', ascending=True)[['Max Drawdown (%)']].to_markdown(floatfmt='.2f')}

### By Win Rate
{comparison_df.sort_values('Win Rate (%)', ascending=False)[['Win Rate (%)']].to_markdown(floatfmt='.2f')}

## Key Insights

### Best Overall Strategy
**{comparison_df['Sharpe Ratio'].idxmax()}** - Highest risk-adjusted returns (Sharpe: {comparison_df['Sharpe Ratio'].max():.2f})

### Highest Returns
**{comparison_df['Total Return (%)'].idxmax()}** - {comparison_df['Total Return (%)'].max():.2f}% total return

### Lowest Risk
**{comparison_df['Max Drawdown (%)'].idxmax()}** - Smallest drawdown ({comparison_df['Max Drawdown (%)'].max():.2f}%)

### Most Consistent
**{comparison_df['Win Rate (%)'].idxmax()}** - {comparison_df['Win Rate (%)'].max():.2f}% win rate

## Recommendations for Improvement

### Strategy-Specific Improvements

1. **RSI Mean Reversion**
   - Consider dynamic RSI thresholds based on volatility regime
   - Add volume confirmation for stronger signals
   - Implement trailing stops for better exit timing

2. **MA Crossover**
   - Test adaptive MA periods (faster in trending markets)
   - Add regime filter (disable in choppy markets)
   - Consider exponential MAs for faster response

3. **Volatility Breakout**
   - Implement ATR-based position sizing
   - Add momentum confirmation (ADX > 25)
   - Use tighter stops in low volatility environments

4. **Momentum**
   - Add sector rotation (rotate to strongest sectors)
   - Implement relative strength ranking
   - Consider multi-timeframe momentum

5. **ML Momentum**
   - Train actual ML model on historical data
   - Add more features (sector, market regime, sentiment)
   - Implement online learning for adaptation

### Portfolio-Level Improvements

1. **Dynamic Allocation**
   - Allocate more capital to strategies with higher recent Sharpe
   - Reduce allocation to strategies in drawdown
   - Cap any single strategy at 35% of portfolio

2. **Regime Detection**
   - Identify market regimes (trend, chop, high/low vol)
   - Disable underperforming strategies in unfavorable regimes
   - Adjust position sizing based on regime

3. **Risk Management**
   - Implement portfolio-level stop loss (-2% daily)
   - Add correlation filtering (reject correlated positions)
   - Use volatility-adjusted position sizing

4. **Execution**
   - Add execution cost modeling (slippage, commissions)
   - Implement smart order routing
   - Consider market impact for large positions

---

**Data Source:** Alpha Vantage  
**Backtest Type:** Walk-forward simulation  
**Report Location:** `artifacts/backtest/multi_strategy_comparison.md`
"""
    
    # Save report
    report_path = output_path / 'multi_strategy_comparison.md'
    with open(report_path, 'w') as f:
        f.write(report)
    
    logger.info(f"✅ Comparison report saved: {report_path}")
    
    return comparison_df


def plot_strategy_comparison(equity_curves, output_dir='artifacts/backtest'):
    """Plot all strategies on one chart"""
    output_path = Path(output_dir)
    
    fig, ax = plt.subplots(figsize=(16, 8))
    
    colors = ['#2E86AB', '#A23B72', '#F18F01', '#06A77D', '#D62246']
    
    for i, (strategy_name, equity_curve) in enumerate(equity_curves.items()):
        equity_series = pd.Series(equity_curve['value'].values, index=equity_curve['date'])
        normalized = equity_series / equity_series.iloc[0] * 100
        ax.plot(normalized.index.to_numpy(), normalized.values, linewidth=2, 
                color=colors[i % len(colors)], label=strategy_name, alpha=0.8)
    
    ax.axhline(y=100, color='gray', linestyle='--', alpha=0.5, label='Initial Capital')
    ax.set_title('Multi-Strategy Performance Comparison (Normalized)', 
                 fontsize=16, fontweight='bold', pad=20)
    ax.set_xlabel('Date', fontsize=12)
    ax.set_ylabel('Portfolio Value (Normalized to 100)', fontsize=12)
    ax.grid(True, alpha=0.3)
    ax.legend(loc='best', fontsize=10)
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(output_path / 'strategy_comparison.png', dpi=150, bbox_inches='tight')
    plt.close()
    
    logger.info(f"✅ Comparison plot saved: {output_path / 'strategy_comparison.png'}")


def main():
    """Run multi-strategy backtest"""
    logger.info("="*60)
    logger.info("MULTI-STRATEGY BACKTEST")
    logger.info("="*60)
    
    # Load cleaned data
    logger.info("Loading cleaned data...")
    data = pd.read_csv('data/training_data_clean.csv')
    data['date'] = pd.to_datetime(data['date'])
    data = data.set_index('date')
    
    logger.info(f"Data loaded: {len(data):,} rows, {data['symbol'].nunique()} symbols")
    logger.info(f"Date range: {data.index.min()} to {data.index.max()}")
    
    # Define strategies
    strategies = {
        'RSI Mean Reversion': 'rsi',
        'MA Crossover': 'ma_crossover',
        'Volatility Breakout': 'volatility_breakout',
        'Momentum': 'momentum',
        'ML Momentum': 'ml_momentum'
    }
    
    # Run backtests
    results = {}
    equity_curves = {}
    all_trades = {}
    
    for strategy_name, strategy_type in strategies.items():
        backtester = StrategyBacktester(strategy_name, initial_capital=100000)
        equity_curve, trades_df = backtester.run_backtest(data, strategy_type)
        
        # Calculate metrics
        metrics = calculate_metrics(equity_curve, trades_df, 100000)
        results[strategy_name] = metrics
        equity_curves[strategy_name] = equity_curve
        all_trades[strategy_name] = trades_df
    
    # Generate comparison report
    logger.info("\n" + "="*60)
    logger.info("Generating comparison report...")
    logger.info("="*60)
    
    comparison_df = generate_comparison_report(results)
    plot_strategy_comparison(equity_curves)
    
    # Print summary
    logger.info("\n" + "="*60)
    logger.info("BACKTEST COMPLETE!")
    logger.info("="*60)
    logger.info(f"\n{comparison_df.to_string()}")
    logger.info("\n📊 Files generated:")
    logger.info("   - artifacts/backtest/multi_strategy_comparison.md")
    logger.info("   - artifacts/backtest/strategy_comparison.png")


if __name__ == '__main__':
    main()
