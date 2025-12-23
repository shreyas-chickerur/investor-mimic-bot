#!/usr/bin/env python3
"""
DEPRECATED: Use multi_strategy_main.py instead

This file is kept for backwards compatibility but should not be used.
The multi-strategy system (multi_strategy_main.py) is the production version.
"""
import sys
print("=" * 80)
print("⚠️  WARNING: This script is DEPRECATED")
print("=" * 80)
print("Please use: python3 src/multi_strategy_main.py")
print("Or run: make run")
print("=" * 80)
sys.exit(1)

# DEPRECATED CODE BELOW - DO NOT USE
"""
OLD SINGLE-STRATEGY CODE - DEPRECATED
Automated Trading System - Main Execution
Consolidates paper trading execution and logging
"""
import os
import sys
from pathlib import Path
import traceback
import logging
from datetime import datetime, timedelta

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / 'src'))

# Set up environment
os.chdir(project_root)

from trading_system import TradingSystem
from dotenv import load_dotenv
import pandas as pd

load_dotenv()

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/trading.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

try:
    from alpaca.trading.client import TradingClient
    from alpaca.trading.requests import MarketOrderRequest
    from alpaca.trading.enums import OrderSide, TimeInForce
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockBarsRequest
    from alpaca.data.timeframe import TimeFrame
except ImportError:
    logger.error("alpaca-py not installed")
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
    """Main execution function"""
    print("=" * 80)
    print("ALPACA PAPER TRADING - AUTOMATED RUN")
    print("=" * 80)
    
    try:
        # Get credentials
        api_key = os.getenv('ALPACA_API_KEY')
        secret_key = os.getenv('ALPACA_SECRET_KEY')
        
        if not api_key or not secret_key:
            logger.critical("Missing Alpaca credentials")
            print("ERROR: Missing Alpaca credentials")
            print("Set ALPACA_API_KEY and ALPACA_SECRET_KEY environment variables")
            sys.exit(1)
        
        # Initialize clients
        logger.info("Initializing Alpaca clients")
        trading_client = TradingClient(api_key, secret_key, paper=True)
        data_client = StockHistoricalDataClient(api_key, secret_key)
        
        # Get account info
        account = trading_client.get_account()
        portfolio_value = float(account.portfolio_value)
        cash = float(account.cash)
        
        print(f"\n📊 Account Status:")
        print(f"   Portfolio Value: ${portfolio_value:,.2f}")
        print(f"   Cash: ${cash:,.2f}")
        logger.info(f"Portfolio: ${portfolio_value:.2f}, Cash: ${cash:.2f}")
        
        # Load historical data
        print(f"\nLoading historical data from training_data.csv...")
        data_file = project_root / 'data' / 'training_data.csv'
        
        if not data_file.exists():
            logger.error(f"Data file not found: {data_file}")
            print(f"ERROR: Data file not found: {data_file}")
            sys.exit(1)
        
        combined = pd.read_csv(data_file, index_col=0)
        print(f"✅ Loaded {len(combined)} rows of data")
        logger.info(f"Loaded {len(combined)} rows of historical data")
        
        # Get latest data (last 100 days)
        combined['date'] = pd.to_datetime(combined.index)
        latest_date = combined['date'].max()
        cutoff_date = latest_date - timedelta(days=100)
        combined = combined[combined['date'] >= cutoff_date].copy()
        
        print(f"✅ Using {len(combined)} recent bars for {combined['symbol'].nunique()} symbols")
        
        # Initialize trading system
        capital = cash
        system = TradingSystem(capital=capital, position_size=0.10, max_positions=10, max_per_symbol=2)
        
        # Prepare data
        stock_data = combined[['symbol', 'close', 'date']].copy()
        
        # Generate signals
        print("\n🔍 Generating signals...")
        logger.info("Generating trading signals")
        signals = system.generate_signals(stock_data)
        
        if len(signals) > 0:
            print(f"\n📈 Found {len(signals)} BUY signals:")
            logger.info(f"Generated {len(signals)} buy signals")
            
            for _, signal in signals.iterrows():
                print(f"   {signal['symbol']}: RSI={signal['rsi']:.1f}, Vol={signal['volatility_20d']:.4f}, Price=${signal['price']:.2f}")
            
            # Execute trades
            print("\n💰 Executing trades via Alpaca...")
            for _, signal in signals.iterrows():
                symbol = signal['symbol']
                price = signal['price']
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
                        logger.info(f"BUY {shares} shares of {symbol} @ ${price:.2f} - Order ID: {order.id}")
                    except Exception as e:
                        print(f"  ❌ Error executing buy for {symbol}: {e}")
                        logger.error(f"Failed to buy {symbol}: {e}")
        else:
            print("\n   No buy signals today")
            logger.info("No buy signals generated")
        
        # Check for exits
        print("\n🔄 Checking for exits...")
        positions = trading_client.get_all_positions()
        
        if positions:
            logger.info(f"Currently holding {len(positions)} positions")
            for position in positions:
                print(f"   Holding: {position.qty} shares of {position.symbol} @ ${position.avg_entry_price}")
        else:
            print("   No open positions")
            logger.info("No open positions")
        
        print("\n" + "=" * 80)
        print("✅ PAPER TRADING RUN COMPLETE")
        print("=" * 80)
        logger.info("Paper trading run completed successfully")
        
    except Exception as e:
        logger.critical(f"Fatal error in main execution: {e}", exc_info=True)
        print(f"\n❌ FATAL ERROR: {e}")
        print(traceback.format_exc())
        sys.exit(1)

if __name__ == "__main__":
    main()
