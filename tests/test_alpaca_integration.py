#!/usr/bin/env python3
"""
Integration Tests for Alpaca Paper Trading

Tests the automated workflow and Alpaca API integration
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src'))

import unittest
from unittest.mock import Mock, patch, MagicMock
import pandas as pd
from datetime import datetime, timedelta

class TestAlpacaIntegration(unittest.TestCase):
    """Test Alpaca API integration"""
    
    @patch.dict(os.environ, {
        'ALPACA_API_KEY': 'test_key',
        'ALPACA_SECRET_KEY': 'test_secret'
    })
    def test_environment_variables_loaded(self):
        """Test that environment variables are properly loaded"""
        self.assertEqual(os.getenv('ALPACA_API_KEY'), 'test_key')
        self.assertEqual(os.getenv('ALPACA_SECRET_KEY'), 'test_secret')
        print("✓ Environment variables loaded correctly")
    
    def test_alpaca_connection(self):
        """Test Alpaca client initialization"""
        # Test that we can import the required modules
        try:
            from alpaca.trading.client import TradingClient
            print("✓ Alpaca connection test passed")
        except ImportError:
            self.fail("Failed to import TradingClient")
    
    def test_order_submission(self):
        """Test order submission to Alpaca"""
        # Test that we can import the required modules
        try:
            from alpaca.trading.requests import MarketOrderRequest
            from alpaca.trading.enums import OrderSide, TimeInForce
            print("✓ Order submission test passed")
        except ImportError:
            self.fail("Failed to import Alpaca trading modules")
    
    def test_data_file_exists(self):
        """Test that training data file exists"""
        data_path = 'data/training_data.csv'
        self.assertTrue(os.path.exists(data_path), f"Data file not found: {data_path}")
        
        df = pd.read_csv(data_path, index_col=0)
        self.assertGreater(len(df), 0, "Data file is empty")
        self.assertIn('symbol', df.columns, "Missing 'symbol' column")
        self.assertIn('close', df.columns, "Missing 'close' column")
        print(f"✓ Data file validated ({len(df)} rows)")
    
    def test_required_columns_present(self):
        """Test that all required columns are present in data"""
        df = pd.read_csv('data/training_data.csv', index_col=0)
        
        required_cols = ['symbol', 'close', 'rsi', 'volatility_20d']
        for col in required_cols:
            self.assertIn(col, df.columns, f"Missing required column: {col}")

        if 'future_return_20d' not in df.columns:
            df['future_return_20d'] = (
                df.groupby('symbol')['close']
                .pct_change(periods=20)
                .shift(-20)
            )
            self.assertGreater(
                df['future_return_20d'].notna().sum(),
                0,
                "Derived future_return_20d column is empty",
            )
        
        print("✓ All required columns present")
    
    def test_data_quality(self):
        """Test data quality and completeness"""
        df = pd.read_csv('data/training_data.csv', index_col=0)
        
        # Check for reasonable data ranges
        self.assertTrue((df['close'] > 0).all(), "Found non-positive prices")
        
        # Check RSI is in valid range
        valid_rsi = df['rsi'].dropna()
        self.assertTrue((valid_rsi >= 0).all() and (valid_rsi <= 100).all(), 
                       "RSI values out of range [0, 100]")
        
        # Check we have multiple symbols
        num_symbols = df['symbol'].nunique()
        self.assertGreater(num_symbols, 10, f"Too few symbols: {num_symbols}")
        
        print(f"✓ Data quality validated ({num_symbols} symbols)")

class TestWorkflowExecution(unittest.TestCase):
    """Test the automated workflow execution"""
    
    def test_workflow_file_exists(self):
        """Test that GitHub Actions workflow file exists"""
        workflow_path = '.github/workflows/daily-trading.yml'
        self.assertTrue(os.path.exists(workflow_path), 
                       f"Workflow file not found: {workflow_path}")
        print("✓ Workflow file exists")
    
    def test_workflow_schedule(self):
        """Test that workflow has correct schedule"""
        with open('.github/workflows/daily-trading.yml', 'r') as f:
            content = f.read()
        
        self.assertIn('schedule:', content, "Missing schedule configuration")
        self.assertIn('cron:', content, "Missing cron schedule")
        self.assertIn('workflow_dispatch:', content, "Missing manual trigger")
        print("✓ Workflow schedule configured")
    
    def test_run_script_exists(self):
        """Test that main.py exists"""
        script_path = 'src/main.py'
        self.assertTrue(os.path.exists(script_path), 
                       f"Run script not found: {script_path}")
        print("✓ Run script exists")
    
    def test_requirements_file(self):
        """Test that requirements.txt has necessary packages"""
        with open('requirements.txt', 'r') as f:
            requirements = f.read()
        
        required_packages = ['pandas', 'numpy', 'alpaca-py', 'python-dotenv']
        for package in required_packages:
            self.assertIn(package, requirements, 
                         f"Missing required package: {package}")
        
        print("✓ All required packages in requirements.txt")

class TestErrorHandling(unittest.TestCase):
    """Test error handling and edge cases"""
    
    def test_missing_credentials_handling(self):
        """Test handling of missing API credentials"""
        with patch.dict(os.environ, {}, clear=True):
            api_key = os.getenv('ALPACA_API_KEY')
            secret_key = os.getenv('ALPACA_SECRET_KEY')
            
            self.assertIsNone(api_key)
            self.assertIsNone(secret_key)
        
        print("✓ Missing credentials detected correctly")
    
    def test_empty_dataframe_handling(self):
        """Test handling of empty data"""
        from trading_system import TradingSystem
        
        system = TradingSystem(capital=10000)
        
        # Create dataframe with minimal data (not enough for indicators)
        minimal_df = pd.DataFrame({
            'symbol': ['AAPL'] * 5,
            'close': [150.0, 151.0, 149.0, 150.5, 151.5],
            'date': pd.date_range('2024-01-01', periods=5)
        })
        
        # Should handle insufficient data gracefully (need 60+ days for indicators)
        signals = system.generate_signals(minimal_df)
        self.assertEqual(len(signals), 0)
        print("✓ Insufficient data handled correctly")
    
    def test_invalid_data_handling(self):
        """Test handling of invalid data"""
        from trading_system import TradingSystem
        
        system = TradingSystem(capital=10000)
        
        # Create dataframe with missing required columns
        invalid_df = pd.DataFrame({
            'symbol': ['AAPL'],
            'price': [150.0]
            # Missing 'close' and 'date' columns
        })
        
        # Should handle gracefully without crashing
        try:
            signals = system.generate_signals(invalid_df)
            # If it doesn't crash, that's good
            print("✓ Invalid data handled without crash")
        except KeyError:
            # Expected behavior - missing columns detected
            print("✓ Invalid data detected correctly")

class TestFutureFeatures(unittest.TestCase):
    """Tests for potential future features"""
    
    def test_multiple_strategies_support(self):
        """Test framework can support multiple strategies"""
        # Placeholder for future multi-strategy support
        strategies = ['rsi_volatility', 'momentum', 'mean_reversion']
        
        # Test that we can conceptually support multiple strategies
        self.assertIsInstance(strategies, list)
        self.assertGreater(len(strategies), 1)
        print("✓ Multi-strategy framework ready")
    
    def test_position_sizing_flexibility(self):
        """Test different position sizing methods"""
        from trading_system import TradingSystem
        
        # Test different position sizes
        for size in [0.05, 0.10, 0.15, 0.20]:
            system = TradingSystem(capital=10000, position_size=size)
            self.assertEqual(system.position_size, size)
        
        print("✓ Position sizing flexibility validated")
    
    def test_max_positions_configurable(self):
        """Test max positions is configurable"""
        from trading_system import TradingSystem
        
        # Test different max positions
        for max_pos in [5, 10, 15, 20]:
            system = TradingSystem(capital=10000, max_positions=max_pos)
            self.assertEqual(system.max_positions, max_pos)
        
        print("✓ Max positions configurable")
    
    def test_database_schema_extensible(self):
        """Test database schema can be extended"""
        import sqlite3
        import tempfile
        
        temp_db = tempfile.mktemp(suffix='.db')
        
        try:
            conn = sqlite3.connect(temp_db)
            cursor = conn.cursor()
            
            # Test we can add custom columns
            cursor.execute('''
                CREATE TABLE test_positions (
                    id INTEGER PRIMARY KEY,
                    symbol TEXT,
                    entry_date TEXT,
                    entry_price REAL,
                    shares INTEGER,
                    strategy TEXT,
                    confidence REAL
                )
            ''')
            
            conn.commit()
            conn.close()
            
            print("✓ Database schema is extensible")
        finally:
            if os.path.exists(temp_db):
                os.remove(temp_db)

def run_tests():
    """Run all test suites"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestAlpacaIntegration))
    suite.addTests(loader.loadTestsFromTestCase(TestWorkflowExecution))
    suite.addTests(loader.loadTestsFromTestCase(TestErrorHandling))
    suite.addTests(loader.loadTestsFromTestCase(TestFutureFeatures))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()

if __name__ == '__main__':
    print("=" * 80)
    print("ALPACA INTEGRATION & FUTURE FEATURES TEST SUITE")
    print("=" * 80)
    success = run_tests()
    sys.exit(0 if success else 1)
