#!/usr/bin/env python3
"""
Add missing technical indicators to training data
"""
import pandas as pd
import numpy as np
from pathlib import Path

def add_missing_indicators(df):
    """Add all missing technical indicators"""
    print("Adding missing indicators...")
    
    df = df.copy()
    df = df.sort_values(['symbol', df.index.name or 'date'])
    
    for symbol in df['symbol'].unique():
        mask = df['symbol'] == symbol
        symbol_data = df[mask].copy()
        
        # RSI slope (if RSI exists)
        if 'rsi' in symbol_data.columns:
            symbol_data['rsi_slope'] = symbol_data['rsi'].diff()
        
        # Bollinger Bands (if not present)
        if 'bb_upper' not in symbol_data.columns:
            bb_middle = symbol_data['close'].rolling(window=20).mean()
            bb_std = symbol_data['close'].rolling(window=20).std()
            symbol_data['bb_middle'] = bb_middle
            symbol_data['bb_upper'] = bb_middle + (bb_std * 2)
            symbol_data['bb_lower'] = bb_middle - (bb_std * 2)
        
        # ATR (if not present)
        if 'atr_20' not in symbol_data.columns:
            high_low = symbol_data['high'] - symbol_data['low']
            high_close = abs(symbol_data['high'] - symbol_data['close'].shift())
            low_close = abs(symbol_data['low'] - symbol_data['close'].shift())
            tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
            symbol_data['atr_20'] = tr.rolling(window=20).mean()
        
        # VWAP (daily cumulative)
        if 'vwap' not in symbol_data.columns:
            symbol_data['vwap'] = (symbol_data['close'] * symbol_data['volume']).cumsum() / symbol_data['volume'].cumsum()
        
        # ADX (simplified)
        if 'adx' not in symbol_data.columns:
            plus_dm = symbol_data['high'].diff()
            minus_dm = -symbol_data['low'].diff()
            plus_dm[plus_dm < 0] = 0
            minus_dm[minus_dm < 0] = 0
            
            high_low = symbol_data['high'] - symbol_data['low']
            high_close = abs(symbol_data['high'] - symbol_data['close'].shift())
            low_close = abs(symbol_data['low'] - symbol_data['close'].shift())
            tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
            tr_smooth = tr.rolling(window=14).mean()
            
            plus_di = 100 * (plus_dm.rolling(window=14).mean() / tr_smooth)
            minus_di = 100 * (minus_dm.rolling(window=14).mean() / tr_smooth)
            dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
            symbol_data['adx'] = dx.rolling(window=14).mean()
        
        # SMA 100 (if not present)
        if 'sma_100' not in symbol_data.columns:
            symbol_data['sma_100'] = symbol_data['close'].rolling(window=100).mean()
        
        # Update main dataframe
        df.loc[mask, symbol_data.columns] = symbol_data
    
    print("Indicators added successfully")
    return df

def main():
    """Add missing indicators to training data"""
    print("="*60)
    print("ADDING MISSING TECHNICAL INDICATORS")
    print("="*60)
    
    # Load data
    data_file = Path('data/training_data.csv')
    print(f"\nLoading {data_file}...")
    
    df = pd.read_csv(data_file, index_col=0)
    df.index = pd.to_datetime(df.index)
    
    print(f"Loaded {len(df)} rows, {df['symbol'].nunique()} symbols")
    print(f"Columns before: {len(df.columns)}")
    
    # Add indicators
    df = add_missing_indicators(df)
    
    print(f"Columns after: {len(df.columns)}")
    
    # Save
    print(f"\nSaving to {data_file}...")
    df.to_csv(data_file)
    
    print("\n✅ Complete! Indicators added:")
    new_cols = ['rsi_slope', 'bb_upper', 'bb_lower', 'bb_middle', 'atr_20', 'vwap', 'adx', 'sma_100']
    for col in new_cols:
        if col in df.columns:
            print(f"  ✅ {col}")
    
    print("\nReady for backtesting!")

if __name__ == '__main__':
    main()
