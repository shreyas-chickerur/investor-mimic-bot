#!/usr/bin/env python3
"""
Strategy Runner
Executes all strategies daily and tracks performance
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from strategy_database import StrategyDatabase
from strategies.strategy_rsi_mean_reversion import RSIMeanReversionStrategy
from strategies.strategy_ml_momentum import MLMomentumStrategy
from strategies.strategy_news_sentiment import NewsSentimentStrategy
from strategies.strategy_ma_crossover import MACrossoverStrategy
from strategies.strategy_volatility_breakout import VolatilityBreakoutStrategy
from alpaca_data_fetcher import AlpacaDataFetcher
from trade_executor import TradeExecutor
import pandas as pd
from datetime import datetime


class StrategyRunner:
    """Runs all strategies and executes trades"""
    
    def __init__(self):
        self.db = StrategyDatabase()
        self.fetcher = AlpacaDataFetcher()
        self.executor = TradeExecutor()
        self.strategies = []
    
    def initialize_strategies(self, total_capital: float = 100000):
        """Initialize all 5 strategies with equal capital allocation"""
        capital_per_strategy = total_capital / 5
        
        # Get or create strategies in database
        existing = self.db.get_all_strategies()
        
        if not existing:
            print("🚀 Initializing 5 strategies...")
            
            strategy_configs = [
                ("RSI Mean Reversion", "Buy when RSI < 30, sell after 20 days"),
                ("ML Momentum", "Random Forest predicts momentum from technical features"),
                ("News Sentiment", "Combines news sentiment with technical indicators"),
                ("MA Crossover", "Golden cross (50/200 MA) trend following"),
                ("Volatility Breakout", "Bollinger Band breakouts with volume confirmation")
            ]
            
            for name, desc in strategy_configs:
                strategy_id = self.db.create_strategy(name, desc, capital_per_strategy)
                print(f"   ✅ Created: {name} (ID: {strategy_id}, Capital: ${capital_per_strategy:,.0f})")
        
        # Load strategies
        strategies_data = self.db.get_all_strategies()
        
        for s in strategies_data:
            if s['name'] == "RSI Mean Reversion":
                strategy = RSIMeanReversionStrategy(s['id'], s['capital_allocation'])
            elif s['name'] == "ML Momentum":
                strategy = MLMomentumStrategy(s['id'], s['capital_allocation'])
            elif s['name'] == "News Sentiment":
                strategy = NewsSentimentStrategy(s['id'], s['capital_allocation'])
            elif s['name'] == "MA Crossover":
                strategy = MACrossoverStrategy(s['id'], s['capital_allocation'])
            elif s['name'] == "Volatility Breakout":
                strategy = VolatilityBreakoutStrategy(s['id'], s['capital_allocation'])
            else:
                continue
            
            self.strategies.append(strategy)
        
        print(f"\n✅ Loaded {len(self.strategies)} strategies")
    
    def fetch_market_data(self, symbols: list = None) -> pd.DataFrame:
        """Fetch market data for all symbols"""
        if symbols is None:
            # Default symbols from your trading universe
            symbols = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA', 'BRK.B', 
                      'UNH', 'JNJ', 'V', 'WMT', 'JPM', 'MA', 'PG', 'HD', 'CVX', 'MRK',
                      'ABBV', 'PEP', 'KO', 'COST', 'AVGO', 'TMO', 'MCD', 'CSCO', 'ACN',
                      'ABT', 'DHR', 'VZ', 'ADBE', 'NKE', 'CRM', 'TXN', 'NEE', 'PM']
        
        print(f"\n📊 Fetching market data for {len(symbols)} symbols...")
        
        # In production, fetch from Alpaca or data provider
        # For now, create sample data structure
        market_data = []
        
        for symbol in symbols:
            try:
                # Fetch latest price and calculate indicators
                # This is simplified - in production, fetch full OHLCV history
                data = {
                    'symbol': symbol,
                    'close': 100.0,  # Placeholder
                    'volume': 1000000,
                    'rsi': 50.0,  # Placeholder
                }
                market_data.append(data)
            except:
                continue
        
        return pd.DataFrame(market_data)
    
    def run_all_strategies(self, market_data: pd.DataFrame, execute_trades: bool = True):
        """Run all strategies and optionally execute trades"""
        print(f"\n{'='*80}")
        print(f"RUNNING ALL STRATEGIES - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*80}\n")
        
        all_signals = []
        
        for strategy in self.strategies:
            print(f"🤖 {strategy.name}...")
            
            # Generate signals
            signals = strategy.generate_signals(market_data)
            
            print(f"   Generated {len(signals)} signals")
            
            # Save signals to database
            for signal in signals:
                self.db.save_signal(strategy.strategy_id, signal)
                all_signals.append({
                    'strategy': strategy.name,
                    'strategy_id': strategy.strategy_id,
                    **signal
                })
            
            # Execute trades if enabled
            if execute_trades and signals:
                for signal in signals:
                    try:
                        # Execute on Alpaca
                        if signal['action'] == 'BUY':
                            print(f"   💰 BUY {signal['symbol']}: {signal['shares']} shares @ ${signal['price']:.2f}")
                        else:
                            print(f"   💸 SELL {signal['symbol']}: {signal['shares']} shares @ ${signal['price']:.2f}")
                        
                        # Update strategy positions
                        if signal['action'] == 'BUY':
                            strategy.add_position(signal['symbol'], signal['shares'])
                            strategy.update_capital(-signal['value'])
                        else:
                            strategy.remove_position(signal['symbol'], signal['shares'])
                            strategy.update_capital(signal['value'])
                        
                        # Record trade
                        strategy.record_trade(signal)
                        self.db.save_trade(strategy.strategy_id, signal)
                        
                    except Exception as e:
                        print(f"   ❌ Error executing {signal['action']} {signal['symbol']}: {e}")
            
            # Get current prices for performance calculation
            current_prices = {row['symbol']: row['close'] for _, row in market_data.iterrows()}
            
            # Calculate and save performance
            metrics = strategy.get_metrics(current_prices)
            self.db.save_performance(strategy.strategy_id, metrics)
            
            print(f"   📊 Performance: ${metrics['portfolio_value']:,.2f} ({metrics['return_pct']:+.2f}%)")
            print()
        
        return all_signals
    
    def get_rankings(self) -> list:
        """Get strategy rankings by performance"""
        return self.db.get_comparison_data()


def main():
    """Main execution"""
    print("="*80)
    print("MULTI-STRATEGY TRADING SYSTEM")
    print("="*80)
    
    runner = StrategyRunner()
    
    # Initialize strategies
    runner.initialize_strategies(total_capital=100000)
    
    # Fetch market data
    market_data = runner.fetch_market_data()
    
    # Run all strategies
    signals = runner.run_all_strategies(market_data, execute_trades=False)
    
    # Show rankings
    print("\n" + "="*80)
    print("STRATEGY RANKINGS")
    print("="*80)
    
    rankings = runner.get_rankings()
    for i, strategy in enumerate(rankings, 1):
        print(f"{i}. {strategy['name']}: {strategy['return_pct']:+.2f}% "
              f"(${strategy['portfolio_value']:,.0f}, {strategy['total_trades']} trades)")
    
    print("\n✅ Strategy run complete!")


if __name__ == '__main__':
    main()
