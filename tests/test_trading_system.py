#!/usr/bin/env python3
"""
Comprehensive Test Suite for Production Trading System

Tests:
1. Database initialization and schema
2. Data loading and validation
3. Indicator calculations (RSI, volatility)
4. Signal generation
5. Trade execution
6. Position management
7. Exit conditions
8. Performance tracking
9. End-to-end workflow
10. Edge cases and error handling
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
import pandas as pd
import numpy as np
import sqlite3
from datetime import datetime, timedelta
import tempfile
import shutil

from trading_system import TradingSystem

class TestTradingSystem(unittest.TestCase):
    """Comprehensive test suite for trading system"""
    
    @classmethod
    def setUpClass(cls):
        """Set up test fixtures"""
        # Load real data
        cls.df = pd.read_csv("data/training_data.csv", index_col=0)
        print(f"\n✓ Loaded {len(cls.df)} rows of data with {cls.df['symbol'].nunique()} symbols")
    
    def setUp(self):
        """Set up for each test"""
        # Create temporary database for testing
        self.temp_dir = tempfile.mkdtemp()
        self.temp_db = os.path.join(self.temp_dir, "test_trading_system.db")
        
        # Create system with temp database
        self.system = TradingSystem(capital=10000, position_size=0.10, max_positions=10, max_per_symbol=2)
        self.system.db_path = self.temp_db
        self.system._init_database()
        self.system.positions = self.system._load_positions()
    
    def tearDown(self):
        """Clean up after each test"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    # ========================================================================
    # TEST 1: DATABASE INITIALIZATION
    # ========================================================================
    
    def test_database_schema(self):
        """Test database tables are created with correct schema"""
        conn = sqlite3.connect(self.temp_db)
        cursor = conn.cursor()
        
        # Check positions table
        cursor.execute("PRAGMA table_info(positions)")
        positions_cols = {row[1] for row in cursor.fetchall()}
        required_cols = {'id', 'symbol', 'entry_date', 'entry_price', 'shares', 
                        'position_value', 'exit_date', 'exit_price', 'return_pct', 
                        'profit_loss', 'status'}
        self.assertTrue(required_cols.issubset(positions_cols), 
                       f"Missing columns in positions table: {required_cols - positions_cols}")
        
        # Check signals table
        cursor.execute("PRAGMA table_info(signals)")
        signals_cols = {row[1] for row in cursor.fetchall()}
        required_cols = {'id', 'date', 'symbol', 'signal_type', 'rsi', 
                        'volatility_20d', 'volatility_median', 'price', 'action_taken'}
        self.assertTrue(required_cols.issubset(signals_cols),
                       f"Missing columns in signals table: {required_cols - signals_cols}")
        
        # Check performance table
        cursor.execute("PRAGMA table_info(performance)")
        performance_cols = {row[1] for row in cursor.fetchall()}
        required_cols = {'id', 'date', 'total_value', 'cash', 'positions_value', 
                        'num_positions', 'daily_return', 'cumulative_return'}
        self.assertTrue(required_cols.issubset(performance_cols),
                       f"Missing columns in performance table: {required_cols - performance_cols}")
        
        conn.close()
        print("✓ Database schema validated")
    
    # ========================================================================
    # TEST 2: INDICATOR CALCULATIONS
    # ========================================================================
    
    def test_rsi_calculation(self):
        """Test RSI calculation is correct"""
        # Get sample data
        sample = self.df[self.df['symbol'] == 'AAPL'].head(100)
        prices = sample['close']
        
        # Calculate RSI
        rsi = self.system.calculate_rsi(prices)
        
        # RSI should be between 0 and 100
        valid_rsi = rsi.dropna()
        self.assertTrue((valid_rsi >= 0).all() and (valid_rsi <= 100).all(),
                       "RSI values should be between 0 and 100")
        
        # Should have NaN for first value (needs at least 2 values for diff)
        self.assertTrue(pd.isna(rsi.iloc[0]),
                       "First RSI value should be NaN")
        
        print("✓ RSI calculation validated")
    
    def test_volatility_calculation(self):
        """Test volatility calculation is correct"""
        # Get sample data
        sample = self.df[self.df['symbol'] == 'AAPL'].head(100)
        prices = sample['close']
        
        # Calculate volatility
        vol = self.system.calculate_volatility(prices, 20)
        
        # Volatility should be positive
        valid_vol = vol.dropna()
        self.assertTrue((valid_vol >= 0).all(),
                       "Volatility should be non-negative")
        
        # Should have NaN for first 20 values
        self.assertTrue(pd.isna(vol.iloc[:20]).all(),
                       "First 20 volatility values should be NaN")
        
        print("✓ Volatility calculation validated")
    
    # ========================================================================
    # TEST 3: SIGNAL GENERATION
    # ========================================================================
    
    def test_signal_generation(self):
        """Test signal generation produces valid signals"""
        # Prepare stock data
        stock_data = self.df[['symbol', 'close']].copy()
        stock_data['date'] = self.df.index
        stock_data = stock_data.reset_index(drop=True)
        
        # Generate signals
        signals = self.system.generate_signals(stock_data)
        
        # Signals should be a DataFrame
        self.assertIsInstance(signals, pd.DataFrame)
        
        # If signals exist, check structure
        if len(signals) > 0:
            required_cols = {'symbol', 'date', 'rsi', 'volatility_20d', 
                           'volatility_median', 'price', 'signal'}
            self.assertTrue(required_cols.issubset(set(signals.columns)),
                           f"Missing columns in signals: {required_cols - set(signals.columns)}")
            
            # All RSI should be < 30
            self.assertTrue((signals['rsi'] < 30).all(),
                           "All signals should have RSI < 30")
            
            # All volatility should be < 1.25x median
            self.assertTrue((signals['volatility_20d'] < signals['volatility_median'] * 1.25).all(),
                           "All signals should have volatility < 1.25x median")
        
        print(f"✓ Signal generation validated ({len(signals)} signals)")
    
    # ========================================================================
    # TEST 4: TRADE EXECUTION
    # ========================================================================
    
    def test_trade_execution(self):
        """Test trade execution works correctly"""
        # Create mock signals
        signals = pd.DataFrame([
            {
                'symbol': 'AAPL',
                'date': '2024-01-01',
                'rsi': 25.0,
                'volatility_20d': 0.015,
                'volatility_median': 0.016,
                'price': 150.0,
                'signal': 'BUY'
            }
        ])
        
        # Execute trades
        trades = self.system.execute_trades(signals)
        
        # Should have executed 1 trade
        self.assertEqual(len(trades), 1)
        
        # Check trade details
        trade = trades[0]
        self.assertEqual(trade['symbol'], 'AAPL')
        self.assertEqual(trade['price'], 150.0)
        self.assertEqual(trade['shares'], 6)  # $1000 / $150 = 6.67 -> 6 shares
        self.assertEqual(trade['value'], 900.0)  # 6 * $150
        
        # Check database
        conn = sqlite3.connect(self.temp_db)
        positions = pd.read_sql_query("SELECT * FROM positions WHERE status = 'open'", conn)
        self.assertEqual(len(positions), 1)
        self.assertEqual(positions.iloc[0]['symbol'], 'AAPL')
        conn.close()
        
        print("✓ Trade execution validated")
    
    def test_diversification_limits(self):
        """Test diversification limits are enforced"""
        # Create signals for same symbol
        signals = pd.DataFrame([
            {'symbol': 'AAPL', 'date': '2024-01-01', 'rsi': 25.0, 
             'volatility_20d': 0.015, 'volatility_median': 0.016, 'price': 150.0, 'signal': 'BUY'},
            {'symbol': 'AAPL', 'date': '2024-01-02', 'rsi': 24.0, 
             'volatility_20d': 0.014, 'volatility_median': 0.016, 'price': 148.0, 'signal': 'BUY'},
            {'symbol': 'AAPL', 'date': '2024-01-03', 'rsi': 23.0, 
             'volatility_20d': 0.013, 'volatility_median': 0.016, 'price': 146.0, 'signal': 'BUY'},
        ])
        
        # Execute trades
        trades = self.system.execute_trades(signals)
        
        # Should only execute 2 trades (max_per_symbol = 2)
        self.assertEqual(len(trades), 2)
        
        print("✓ Diversification limits validated")
    
    # ========================================================================
    # TEST 5: POSITION MANAGEMENT
    # ========================================================================
    
    def test_position_loading(self):
        """Test positions are loaded correctly from database"""
        # Insert test position
        conn = sqlite3.connect(self.temp_db)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO positions (symbol, entry_date, entry_price, shares, position_value, status)
            VALUES (?, ?, ?, ?, ?, 'open')
        ''', ('AAPL', '2024-01-01', 150.0, 10, 1500.0))
        conn.commit()
        conn.close()
        
        # Reload positions
        positions = self.system._load_positions()
        
        # Should have 1 position
        self.assertEqual(len(positions), 1)
        self.assertEqual(positions.iloc[0]['symbol'], 'AAPL')
        self.assertEqual(positions.iloc[0]['shares'], 10)
        
        print("✓ Position loading validated")
    
    def test_max_positions_limit(self):
        """Test maximum positions limit is enforced"""
        # Create 15 signals (more than max_positions = 10)
        signals = pd.DataFrame([
            {'symbol': f'SYM{i}', 'date': '2024-01-01', 'rsi': 25.0,
             'volatility_20d': 0.015, 'volatility_median': 0.016, 'price': 100.0, 'signal': 'BUY'}
            for i in range(15)
        ])
        
        # Execute trades
        trades = self.system.execute_trades(signals)
        
        # Should only execute 10 trades
        self.assertEqual(len(trades), 10)
        
        print("✓ Max positions limit validated")
    
    # ========================================================================
    # TEST 6: EXIT CONDITIONS
    # ========================================================================
    
    def test_holding_period_exit(self):
        """Test positions exit after 20 days"""
        # Insert position from 25 days ago
        entry_date = (datetime.now() - timedelta(days=25)).date()
        
        conn = sqlite3.connect(self.temp_db)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO positions (symbol, entry_date, entry_price, shares, position_value, status)
            VALUES (?, ?, ?, ?, ?, 'open')
        ''', ('AAPL', entry_date.isoformat(), 150.0, 10, 1500.0))
        conn.commit()
        conn.close()
        
        # Reload positions
        self.system.positions = self.system._load_positions()
        
        # Check exits
        current_prices = {'AAPL': 160.0}
        exits = self.system.check_exits(current_prices)
        
        # Should have 1 exit
        self.assertEqual(len(exits), 1)
        self.assertEqual(exits[0]['symbol'], 'AAPL')
        self.assertGreater(exits[0]['days_held'], 20)
        
        # Check position is closed in database
        conn = sqlite3.connect(self.temp_db)
        positions = pd.read_sql_query("SELECT * FROM positions WHERE status = 'closed'", conn)
        self.assertEqual(len(positions), 1)
        conn.close()
        
        print("✓ Holding period exit validated")
    
    # ========================================================================
    # TEST 7: PERFORMANCE TRACKING
    # ========================================================================
    
    def test_performance_logging(self):
        """Test performance is logged correctly"""
        # Log performance
        current_prices = {}
        perf = self.system.log_performance(current_prices)
        
        # Check performance metrics
        self.assertEqual(perf['total_value'], 10000.0)
        self.assertEqual(perf['cash'], 10000.0)
        self.assertEqual(perf['positions_value'], 0.0)
        self.assertEqual(perf['num_positions'], 0)
        self.assertEqual(perf['cumulative_return'], 0.0)
        
        # Check database
        conn = sqlite3.connect(self.temp_db)
        performance = pd.read_sql_query("SELECT * FROM performance", conn)
        self.assertEqual(len(performance), 1)
        self.assertEqual(performance.iloc[0]['total_value'], 10000.0)
        conn.close()
        
        print("✓ Performance logging validated")
    
    # ========================================================================
    # TEST 8: END-TO-END WORKFLOW
    # ========================================================================
    
    def test_end_to_end_workflow(self):
        """Test complete daily workflow"""
        # Prepare stock data
        stock_data = self.df[['symbol', 'close']].copy()
        stock_data['date'] = self.df.index
        stock_data = stock_data.reset_index(drop=True)
        
        # Get current prices
        current_prices = self.df.groupby('symbol')['close'].last().to_dict()
        
        # Run daily workflow
        results = self.system.run_daily(stock_data, current_prices)
        
        # Check results structure
        self.assertIn('exits', results)
        self.assertIn('signals', results)
        self.assertIn('trades', results)
        self.assertIn('performance', results)
        
        # Check performance
        perf = results['performance']
        self.assertIn('total_value', perf)
        self.assertIn('cumulative_return', perf)
        
        print("✓ End-to-end workflow validated")
    
    # ========================================================================
    # TEST 9: EDGE CASES
    # ========================================================================
    
    def test_empty_signals(self):
        """Test system handles empty signals gracefully"""
        empty_signals = pd.DataFrame()
        trades = self.system.execute_trades(empty_signals)
        
        # Should return empty list
        self.assertEqual(len(trades), 0)
        
        print("✓ Empty signals handling validated")
    
    def test_missing_price_data(self):
        """Test system handles missing price data"""
        # Insert position
        conn = sqlite3.connect(self.temp_db)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO positions (symbol, entry_date, entry_price, shares, position_value, status)
            VALUES (?, ?, ?, ?, ?, 'open')
        ''', ('MISSING', '2024-01-01', 150.0, 10, 1500.0))
        conn.commit()
        conn.close()
        
        # Reload positions
        self.system.positions = self.system._load_positions()
        
        # Check exits with missing symbol
        current_prices = {'AAPL': 160.0}  # MISSING not in prices
        exits = self.system.check_exits(current_prices)
        
        # Should not crash, should return empty
        self.assertEqual(len(exits), 0)
        
        print("✓ Missing price data handling validated")
    
    def test_insufficient_capital(self):
        """Test system handles insufficient capital"""
        # Create signal with very high price
        signals = pd.DataFrame([
            {'symbol': 'EXPENSIVE', 'date': '2024-01-01', 'rsi': 25.0,
             'volatility_20d': 0.015, 'volatility_median': 0.016, 
             'price': 50000.0, 'signal': 'BUY'}  # $50K per share
        ])
        
        # Execute trades
        trades = self.system.execute_trades(signals)
        
        # Should not execute (can't afford even 1 share)
        self.assertEqual(len(trades), 0)
        
        print("✓ Insufficient capital handling validated")
    
    # ========================================================================
    # TEST 10: DATA VALIDATION
    # ========================================================================
    
    def test_data_integrity(self):
        """Test training data has required columns and valid values"""
        # Check required columns exist
        required_cols = ['close', 'rsi', 'volatility_20d', 'future_return_20d', 'symbol']
        for col in required_cols:
            self.assertIn(col, self.df.columns, f"Missing required column: {col}")
        
        # Check no completely empty columns
        for col in required_cols:
            self.assertGreater(self.df[col].notna().sum(), 0, 
                             f"Column {col} is completely empty")
        
        # Check symbol count
        self.assertGreater(self.df['symbol'].nunique(), 0, 
                          "No symbols in data")
        
        print(f"✓ Data integrity validated ({len(self.df)} rows, {self.df['symbol'].nunique()} symbols)")

def run_tests():
    """Run all tests and print summary"""
    print("=" * 80)
    print("COMPREHENSIVE TEST SUITE")
    print("=" * 80)
    
    # Create test suite
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestTradingSystem)
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print(f"\nTests run: {result.testsRun}")
    print(f"Successes: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    
    if result.wasSuccessful():
        print("\n✅ ALL TESTS PASSED")
        return 0
    else:
        print("\n❌ SOME TESTS FAILED")
        return 1

if __name__ == '__main__':
    exit_code = run_tests()
    sys.exit(exit_code)
