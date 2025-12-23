#!/usr/bin/env python3
"""
Run All 5 Strategies and Generate Dashboard
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import pandas as pd
from datetime import datetime
from alpaca_data_fetcher import AlpacaDataFetcher
from strategies.strategy_rsi_mean_reversion import RSIMeanReversionStrategy
from strategies.strategy_ml_momentum import MLMomentumStrategy
from strategies.strategy_news_sentiment import NewsSentimentStrategy
from strategies.strategy_ma_crossover import MACrossoverStrategy
from strategies.strategy_volatility_breakout import VolatilityBreakoutStrategy

def main():
    print("=" * 80)
    print("MULTI-STRATEGY SIGNAL ANALYSIS")
    print("=" * 80)
    
    # Fetch market data
    print("\n📊 Fetching market data...")
    fetcher = AlpacaDataFetcher()
    market_data = fetcher.fetch_latest_data()
    
    if market_data is None or market_data.empty:
        print("❌ Failed to fetch market data")
        return
    
    print(f"✅ Loaded data for {market_data['symbol'].nunique()} symbols")
    
    # Initialize all 5 strategies
    capital_per_strategy = 20000
    
    strategies = [
        ("RSI Mean Reversion", RSIMeanReversionStrategy(capital_per_strategy)),
        ("ML Momentum", MLMomentumStrategy(capital_per_strategy)),
        ("News Sentiment", NewsSentimentStrategy(capital_per_strategy)),
        ("MA Crossover", MACrossoverStrategy(capital_per_strategy)),
        ("Volatility Breakout", VolatilityBreakoutStrategy(capital_per_strategy))
    ]
    
    # Run each strategy
    all_results = []
    
    for name, strategy in strategies:
        print(f"\n{'=' * 80}")
        print(f"📈 {name}")
        print(f"{'=' * 80}")
        
        try:
            signals = strategy.generate_signals(market_data)
            
            result = {
                'strategy': name,
                'signals': len(signals) if signals is not None else 0,
                'status': 'Success',
                'details': signals if signals is not None and len(signals) > 0 else None
            }
            
            if signals is not None and len(signals) > 0:
                print(f"✅ Found {len(signals)} signals:")
                print(signals[['symbol', 'signal', 'price']].to_string(index=False))
            else:
                print("❌ No signals generated")
            
            all_results.append(result)
            
        except Exception as e:
            print(f"❌ Error: {e}")
            all_results.append({
                'strategy': name,
                'signals': 0,
                'status': f'Error: {str(e)}',
                'details': None
            })
    
    # Generate summary dashboard
    print(f"\n{'=' * 80}")
    print("📊 STRATEGY DASHBOARD SUMMARY")
    print(f"{'=' * 80}")
    
    print(f"\n{'Strategy':<25} {'Signals':<10} {'Status':<20}")
    print("-" * 80)
    
    total_signals = 0
    for result in all_results:
        print(f"{result['strategy']:<25} {result['signals']:<10} {result['status']:<20}")
        total_signals += result['signals']
    
    print("-" * 80)
    print(f"{'TOTAL':<25} {total_signals:<10}")
    
    # Show detailed signals if any
    if total_signals > 0:
        print(f"\n{'=' * 80}")
        print("📋 DETAILED SIGNALS")
        print(f"{'=' * 80}")
        
        for result in all_results:
            if result['details'] is not None and len(result['details']) > 0:
                print(f"\n🎯 {result['strategy']}:")
                print(result['details'].to_string(index=False))
    else:
        print("\n⚠️  No signals from any strategy")
        print("This is normal - strategies are selective and wait for optimal conditions")
    
    print(f"\n{'=' * 80}")
    print(f"Analysis completed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'=' * 80}")

if __name__ == '__main__':
    main()
