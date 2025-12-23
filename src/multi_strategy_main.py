#!/usr/bin/env python3
"""
Multi-Strategy Trading System - Main Execution
Runs all 5 strategies independently with separate tracking
"""
import os
import sys
from pathlib import Path
from datetime import datetime
import logging

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / 'src'))

from dotenv import load_dotenv
load_dotenv()

from strategy_database import StrategyDatabase
from strategies.strategy_rsi_mean_reversion import RSIMeanReversionStrategy
from strategies.strategy_ml_momentum import MLMomentumStrategy
from strategies.strategy_news_sentiment import NewsSentimentStrategy
from strategies.strategy_ma_crossover import MACrossoverStrategy
from strategies.strategy_volatility_breakout import VolatilityBreakoutStrategy
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce
import pandas as pd

# Setup logging - CRITICAL FIX: Ensure logs directory exists
Path('logs').mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/multi_strategy.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class MultiStrategyRunner:
    """Runs all 5 strategies with independent tracking"""
    
    def __init__(self):
        self.db = StrategyDatabase()
        
        # Get Alpaca credentials
        api_key = os.getenv('ALPACA_API_KEY')
        secret_key = os.getenv('ALPACA_SECRET_KEY')
        
        if not api_key or not secret_key:
            raise ValueError("Missing Alpaca credentials")
        
        self.trading_client = TradingClient(api_key, secret_key, paper=True)
        
        # Get account info - CRITICAL FIX: Use portfolio value, not just cash
        account = self.trading_client.get_account()
        self.portfolio_value = float(account.portfolio_value)
        self.cash_available = float(account.cash)
        
        logger.info(f"Portfolio: ${self.portfolio_value:.2f}, Cash: ${self.cash_available:.2f}")
    
    def initialize_strategies(self):
        """Initialize all 5 strategies with equal capital allocation"""
        # CRITICAL FIX: Use portfolio value for allocation, not just cash
        capital_per_strategy = self.portfolio_value / 5
        
        # Check if strategies already exist
        existing = self.db.get_all_strategies()
        
        if existing:
            logger.info(f"Found {len(existing)} existing strategies")
            strategies = []
            for strat in existing:
                strategy = self._create_strategy_instance(strat['id'], strat['name'], capital_per_strategy)
                # CRITICAL FIX: Load positions from Alpaca for each strategy
                self._load_strategy_positions(strategy)
                strategies.append(strategy)
            return strategies
        
        # Create new strategies
        logger.info("Initializing 5 new strategies...")
        
        strategy_configs = [
            ("RSI Mean Reversion", "Buy when RSI < 30 + low volatility, hold 20 days", RSIMeanReversionStrategy),
            ("ML Momentum", "Machine learning momentum prediction", MLMomentumStrategy),
            ("News Sentiment", "News sentiment + technical indicators", NewsSentimentStrategy),
            ("MA Crossover", "Golden cross (50/200 MA) trend following", MACrossoverStrategy),
            ("Volatility Breakout", "Bollinger Band breakouts with volume", VolatilityBreakoutStrategy)
        ]
        
        strategies = []
        for name, desc, strategy_class in strategy_configs:
            strategy_id = self.db.create_strategy(name, desc, capital_per_strategy)
            strategy = strategy_class(strategy_id, capital_per_strategy)
            # CRITICAL FIX: Load positions for new strategies too
            self._load_strategy_positions(strategy)
            strategies.append(strategy)
            logger.info(f"  Created: {name} (ID: {strategy_id}, Capital: ${capital_per_strategy:.2f})")
        
        return strategies
    
    def _load_strategy_positions(self, strategy):
        """Load current positions for a strategy from database"""
        try:
            # Get all open trades for this strategy
            trades = self.db.get_strategy_trades(strategy.strategy_id)
            
            # Build positions dict
            positions = {}
            for trade in trades:
                if trade['action'] == 'BUY':
                    symbol = trade['symbol']
                    shares = trade['shares']
                    if symbol in positions:
                        positions[symbol] += shares
                    else:
                        positions[symbol] = shares
                elif trade['action'] == 'SELL':
                    symbol = trade['symbol']
                    shares = trade['shares']
                    if symbol in positions:
                        positions[symbol] -= shares
                        if positions[symbol] <= 0:
                            del positions[symbol]
            
            strategy.positions = positions
            logger.info(f"  Loaded {len(positions)} positions for {strategy.name}")
        except Exception as e:
            logger.error(f"Error loading positions for {strategy.name}: {e}")
            strategy.positions = {}
    
    def _create_strategy_instance(self, strategy_id, name, capital):
        """Create strategy instance based on name"""
        strategy_map = {
            "RSI Mean Reversion": RSIMeanReversionStrategy,
            "ML Momentum": MLMomentumStrategy,
            "News Sentiment": NewsSentimentStrategy,
            "MA Crossover": MACrossoverStrategy,
            "Volatility Breakout": VolatilityBreakoutStrategy
        }
        
        strategy_class = strategy_map.get(name)
        if strategy_class:
            return strategy_class(strategy_id, capital)
        return None
    
    def load_market_data(self):
        """Load market data from CSV"""
        data_file = project_root / 'data' / 'training_data.csv'
        
        if not data_file.exists():
            logger.error(f"Data file not found: {data_file}")
            return None
        
        df = pd.read_csv(data_file, index_col=0)
        df.index = pd.to_datetime(df.index)
        
        # Get last 100 days
        from datetime import timedelta
        latest_date = df.index.max()
        cutoff_date = latest_date - timedelta(days=100)
        df = df[df.index >= cutoff_date].copy()
        
        logger.info(f"Loaded {len(df)} rows for {df['symbol'].nunique()} symbols")
        return df
    
    def run_all_strategies(self, market_data):
        """Run all strategies and execute trades"""
        strategies = self.initialize_strategies()
        
        print("\n" + "=" * 80)
        print("MULTI-STRATEGY EXECUTION")
        print("=" * 80)
        
        all_signals = []
        
        for strategy in strategies:
            print(f"\n📈 {strategy.name}")
            print("-" * 80)
            
            try:
                signals = strategy.generate_signals(market_data)
                
                if signals and len(signals) > 0:
                    print(f"✅ Generated {len(signals)} signals")
                    
                    # Log signals to database
                    for signal in signals:
                        self.db.log_signal(
                            strategy.strategy_id,
                            signal.get('symbol'),
                            signal.get('action', 'BUY'),
                            signal.get('confidence', 0.5),
                            signal.get('reasoning', '')
                        )
                    
                    # Execute trades
                    executed = self._execute_strategy_trades(strategy, signals[:3])  # Top 3 signals
                    all_signals.extend(executed)
                else:
                    print("❌ No signals generated")
                
                # Record daily performance
                current_prices = market_data.groupby('symbol')['close'].last().to_dict()
                self._record_performance(strategy, current_prices)
                
            except Exception as e:
                logger.error(f"Error in {strategy.name}: {e}")
                print(f"❌ Error: {e}")
        
        return all_signals
    
    def _execute_strategy_trades(self, strategy, signals):
        """Execute trades for a specific strategy"""
        executed = []
        
        for signal in signals:
            symbol = signal.get('symbol')
            action = signal.get('action', 'BUY')
            shares = signal.get('shares', 0)
            price = signal.get('price', 0)
            
            if action == 'BUY' and shares > 0:
                try:
                    order_data = MarketOrderRequest(
                        symbol=symbol,
                        qty=shares,
                        side=OrderSide.BUY,
                        time_in_force=TimeInForce.DAY
                    )
                    order = self.trading_client.submit_order(order_data)
                    
                    print(f"  ✅ BUY {shares} {symbol} @ ${price:.2f} (Order: {order.id})")
                    
                    # Log trade
                    self.db.log_trade(
                        strategy.strategy_id,
                        symbol,
                        'BUY',
                        shares,
                        price,
                        shares * price,
                        order.id
                    )
                    
                    executed.append({
                        'strategy': strategy.name,
                        'symbol': symbol,
                        'shares': shares,
                        'price': price
                    })
                    
                except Exception as e:
                    logger.error(f"Failed to execute {symbol}: {e}")
                    print(f"  ❌ Failed {symbol}: {e}")
        
        return executed
    
    def _record_performance(self, strategy, current_prices):
        """Record daily performance for strategy"""
        portfolio_value = strategy.get_portfolio_value(current_prices)
        return_pct = strategy.get_return_pct(current_prices)
        
        self.db.record_daily_performance(
            strategy.strategy_id,
            portfolio_value,
            strategy.capital,
            portfolio_value - strategy.capital,
            return_pct,
            len(strategy.positions)
        )
    
    def generate_performance_report(self):
        """Generate performance report for all strategies"""
        print("\n" + "=" * 80)
        print("📊 STRATEGY PERFORMANCE DASHBOARD")
        print("=" * 80)
        
        strategies = self.db.get_all_strategies()
        
        print(f"\n{'Strategy':<25} {'Capital':<12} {'Return':<10} {'Positions':<10} {'Trades':<10}")
        print("-" * 80)
        
        for strat in strategies:
            perf = self.db.get_latest_performance(strat['id'])
            trades = self.db.get_strategy_trades(strat['id'])
            
            if perf:
                return_pct = perf.get('total_return_pct', 0)
                num_positions = perf.get('num_positions', 0)
            else:
                return_pct = 0
                num_positions = 0
            
            print(f"{strat['name']:<25} ${strat['capital_allocation']:<11,.0f} {return_pct:>+8.2f}% {num_positions:<10} {len(trades):<10}")
        
        print("-" * 80)

def main():
    """Main execution"""
    print("=" * 80)
    print("MULTI-STRATEGY TRADING SYSTEM")
    print("=" * 80)
    
    try:
        runner = MultiStrategyRunner()
        
        # Load market data
        print("\n📊 Loading market data...")
        market_data = runner.load_market_data()
        
        if market_data is None:
            logger.error("Failed to load market data")
            return
        
        # Run all strategies
        signals = runner.run_all_strategies(market_data)
        
        # Generate report
        runner.generate_performance_report()
        
        print("\n" + "=" * 80)
        print(f"✅ EXECUTION COMPLETE - {len(signals)} trades executed")
        print("=" * 80)
        
        logger.info("Multi-strategy execution completed successfully")
        
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        print(f"\n❌ FATAL ERROR: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
