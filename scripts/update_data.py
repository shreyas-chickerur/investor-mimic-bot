#!/usr/bin/env python3
"""
Quick Data Update Script
Updates training_data.csv with latest market data from Alpaca
"""
import os
import sys
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

import pandas as pd
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

SYMBOLS = [
    'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'TSLA', 'NVDA', 'AMD',
    'NFLX', 'DIS', 'PYPL', 'INTC', 'CSCO', 'ADBE', 'CRM', 'ORCL',
    'QCOM', 'TXN', 'AVGO', 'COST', 'SBUX', 'MCD', 'NKE', 'WMT',
    'HD', 'LOW', 'TGT', 'CVS', 'UNH', 'JNJ', 'PFE', 'ABBV',
    'MRK', 'TMO', 'DHR', 'MDT'
]

def calculate_rsi(prices, period=14):
    """Calculate RSI"""
    deltas = prices.diff()
    gain = (deltas.where(deltas > 0, 0)).rolling(window=period).mean()
    loss = (-deltas.where(deltas < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calculate_volatility(prices, period=20):
    """Calculate volatility"""
    returns = prices.pct_change()
    volatility = returns.rolling(window=period).std()
    return volatility

def main():
    """Update data with latest prices"""
    print("=" * 80)
    print("UPDATING TRAINING DATA")
    print("=" * 80)
    
    # Get Alpaca credentials
    api_key = os.getenv('ALPACA_API_KEY')
    secret_key = os.getenv('ALPACA_SECRET_KEY')
    
    if not api_key or not secret_key:
        print("ERROR: Missing Alpaca credentials")
        sys.exit(1)
    
    # Initialize client
    client = StockHistoricalDataClient(api_key, secret_key)
    
    # CRITICAL FIX: Get 300 days of data for MA strategies (need 200-day MA)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=300)
    
    print(f"\nFetching data from {start_date.date()} to {end_date.date()}")
    print(f"Symbols: {len(SYMBOLS)}")
    
    # Fetch data
    request = StockBarsRequest(
        symbol_or_symbols=SYMBOLS,
        timeframe=TimeFrame.Day,
        start=start_date,
        end=end_date
    )
    
    print("\nFetching from Alpaca...")
    bars = client.get_stock_bars(request)
    
    # Combine all symbols
    all_data = []
    for symbol in SYMBOLS:
        if symbol in bars:
            df = bars[symbol].df.reset_index()
            df['symbol'] = symbol
            all_data.append(df)
            print(f"  ✓ {symbol}: {len(df)} bars")
        else:
            print(f"  ✗ {symbol}: No data")
    
    if not all_data:
        print("\nERROR: No data fetched")
        sys.exit(1)
    
    # Combine
    combined = pd.concat(all_data, ignore_index=True)
    combined = combined.rename(columns={'timestamp': 'date'})
    
    # Calculate technical indicators by symbol
    print("\nCalculating indicators...")
    processed = []
    
    for symbol, group in combined.groupby('symbol'):
        group = group.sort_values('date').copy()
        
        # Returns
        group['returns_1d'] = group['close'].pct_change()
        group['returns_5d'] = group['close'].pct_change(5)
        group['returns_20d'] = group['close'].pct_change(20)
        group['returns_60d'] = group['close'].pct_change(60)
        
        # Moving averages
        group['sma_20'] = group['close'].rolling(20).mean()
        group['sma_50'] = group['close'].rolling(50).mean()
        group['sma_200'] = group['close'].rolling(200).mean()
        
        # Price ratios
        group['price_to_sma20'] = group['close'] / group['sma_20']
        group['price_to_sma50'] = group['close'] / group['sma_50']
        group['price_to_sma200'] = group['close'] / group['sma_200']
        
        # Volatility
        group['volatility_20d'] = calculate_volatility(group['close'], 20)
        group['volatility_60d'] = calculate_volatility(group['close'], 60)
        
        # Volume
        group['volume_sma_20'] = group['volume'].rolling(20).mean()
        group['volume_ratio'] = group['volume'] / group['volume_sma_20']
        
        # RSI
        group['rsi'] = calculate_rsi(group['close'])
        
        # Future returns (for backtesting)
        group['future_return_5d'] = group['close'].pct_change(5).shift(-5)
        group['future_return_20d'] = group['close'].pct_change(20).shift(-20)
        
        # Placeholder institutional data
        group['institutional_holders'] = 0
        group['total_institutional_value'] = 0
        group['avg_portfolio_weight'] = 0
        
        processed.append(group)
    
    final = pd.concat(processed, ignore_index=True)
    
    # Set date as index (CRITICAL FIX)
    final = final.set_index('date')
    
    # Save
    output_path = Path(__file__).parent.parent / 'data' / 'training_data.csv'
    final.to_csv(output_path)
    
    print(f"\n✅ Saved {len(final)} rows to {output_path}")
    print(f"Date range: {final.index.min()} to {final.index.max()}")
    print(f"Symbols: {final['symbol'].nunique()}")
    
    # Verify the fix
    print("\n🔍 Verifying date index...")
    test_df = pd.read_csv(output_path, index_col=0)
    test_df.index = pd.to_datetime(test_df.index)
    print(f"Index type: {type(test_df.index[0])}")
    print(f"First date: {test_df.index[0]}")
    print(f"Last date: {test_df.index[-1]}")
    print("✅ Date index verified!")

if __name__ == '__main__':
    main()
