#!/usr/bin/env python3
"""
Wrapper script to run paper trading from any directory
"""
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / 'src'))

# Set up environment
os.chdir(project_root)

# Import and run
from trading_system import TradingSystem
from logger import get_logger
from dotenv import load_dotenv
import pandas as pd
from datetime import datetime, timedelta
import traceback

load_dotenv()

# Initialize logger
logger = get_logger()

try:
    from alpaca.trading.client import TradingClient
    from alpaca.trading.requests import MarketOrderRequest
    from alpaca.trading.enums import OrderSide, TimeInForce
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockBarsRequest
    from alpaca.data.timeframe import TimeFrame
except ImportError:
    print("ERROR: alpaca-py not installed")
    print("Install with: pip3 install alpaca-py python-dotenv")
    sys.exit(1)

# Symbols to trade
SYMBOLS = [
    'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'TSLA', 'NVDA', 'AMD',
    'NFLX', 'DIS', 'PYPL', 'INTC', 'CSCO', 'ADBE', 'CRM', 'ORCL',
    'QCOM', 'TXN', 'AVGO', 'COST', 'SBUX', 'MCD', 'NKE', 'WMT',
    'HD', 'LOW', 'TGT', 'CVS', 'UNH', 'JNJ', 'PFE', 'ABBV',
    'MRK', 'TMO', 'DHR', 'MDT'
]

def main():
    print("=" * 80)
    print("ALPACA PAPER TRADING - AUTOMATED RUN")
    print("=" * 80)
    
    try:
        # Get credentials
        api_key = os.getenv('ALPACA_API_KEY')
        secret_key = os.getenv('ALPACA_SECRET_KEY')
        
        if not api_key or not secret_key:
            error_msg = "Missing Alpaca credentials"
            logger.log_error('CONFIGURATION', error_msg, severity='CRITICAL')
            print("ERROR: Missing Alpaca credentials")
            print("Set ALPACA_API_KEY and ALPACA_SECRET_KEY environment variables")
            sys.exit(1)
        
        # Initialize clients
        trading_client = TradingClient(api_key, secret_key, paper=True)
        data_client = StockHistoricalDataClient(api_key, secret_key)
        
        # Get account info
        account = trading_client.get_account()
        print(f"\n📊 Account Status:")
        print(f"   Portfolio Value: ${float(account.portfolio_value):,.2f}")
        print(f"   Cash: ${float(account.cash):,.2f}")
        
        # Log performance snapshot
        logger.log_performance(
            portfolio_value=float(account.portfolio_value),
            cash=float(account.cash),
            positions_value=float(account.portfolio_value) - float(account.cash),
            num_positions=0  # Will update after getting positions
        )
    
    # Load historical data from file
    print(f"\nLoading historical data from training_data.csv...")
    data_file = project_root / 'data' / 'training_data.csv'
    
    if not data_file.exists():
        print(f"ERROR: Data file not found: {data_file}")
        sys.exit(1)
    
    combined = pd.read_csv(data_file, index_col=0)
    print(f"✅ Loaded {len(combined)} rows of data")
    
    # Get latest data for each symbol (last 100 days)
    combined['date'] = pd.to_datetime(combined.index)
    latest_date = combined['date'].max()
    cutoff_date = latest_date - timedelta(days=100)
    combined = combined[combined['date'] >= cutoff_date].copy()
    
    print(f"✅ Using {len(combined)} recent bars for {combined['symbol'].nunique()} symbols")
    
    # Initialize trading system
    capital = float(account.cash)
    system = TradingSystem(capital=capital, position_size=0.10, max_positions=10, max_per_symbol=2)
    
    # Prepare data
    stock_data = combined[['symbol', 'close', 'date']].copy()
    
    # Generate signals
    print("\n🔍 Generating signals...")
    signals = system.generate_signals(stock_data)
    
    if len(signals) > 0:
        print(f"\n📈 Found {len(signals)} BUY signals:")
        for _, signal in signals.iterrows():
            print(f"   {signal['symbol']}: RSI={signal['rsi']:.1f}, Vol={signal['volatility_20d']:.4f}, Price=${signal['price']:.2f}")
        
        # Execute trades
        print("\n💰 Executing trades via Alpaca...")
        for _, signal in signals.iterrows():
            symbol = signal['symbol']
            price = signal['price']
            portfolio_value = float(account.portfolio_value)
            position_value = portfolio_value * 0.10
            shares = int(position_value / price)
            
            if shares > 0:
                try:
                    order_data = MarketOrderRequest(
                        symbol=symbol,
                        qty=shares,
                        side=OrderSide.BUY,
                        time_in_force=TimeInForce.DAY
                    )
                    order = trading_client.submit_order(order_data)
                    print(f"  ✅ BUY order submitted: {shares} shares of {symbol} (Order ID: {order.id})")
                    logger.log_trade('BUY', symbol, shares, price, order.id, 'SUCCESS')
                except Exception as e:
                    print(f"  ❌ Error executing buy for {symbol}: {e}")
                    logger.log_error('TRADE_EXECUTION', f"Failed to buy {symbol}", str(e), {'symbol': symbol, 'shares': shares, 'price': price})
                    logger.log_trade('BUY', symbol, shares, price, None, 'FAILED', str(e))
    else:
        print("\n   No buy signals today")
    
    # Check for exits
    print("\n🔄 Checking for exits...")
    positions = trading_client.get_all_positions()
    
    if positions:
        for position in positions:
            print(f"   Holding: {position.qty} shares of {position.symbol} @ ${position.avg_entry_price}")
    else:
        print("   No open positions")
    
    print("\n" + "=" * 80)
    print("✅ PAPER TRADING RUN COMPLETE")
    print("=" * 80)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.log_error('SYSTEM', 'Fatal error in main execution', traceback.format_exc(), severity='CRITICAL')
        print(f"\n❌ FATAL ERROR: {e}")
        print(traceback.format_exc())
        sys.exit(1)
