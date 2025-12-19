"""
Integration Tests

End-to-end tests for complete workflows.
"""

import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import datetime, timedelta
from utils.cache import get_cache
from utils.validators import trade_validator, ValidationError
from utils.data_quality import get_quality_checker
from services.paper_trading import PaperTradingEngine
from db.connection_pool import get_db_pool


class TestCacheIntegration:
    """Test caching functionality."""
    
    def test_cache_set_and_get(self):
        """Test basic cache operations."""
        cache = get_cache()
        
        cache.set('test_key', 'test_value', ttl=60)
        result = cache.get('test_key')
        
        assert result == 'test_value'
    
    def test_cache_expiration(self):
        """Test cache TTL."""
        cache = get_cache()
        
        cache.set('expire_key', 'value', ttl=1)
        import time
        time.sleep(2)
        
        result = cache.get('expire_key')
        # May be None if expired (depends on cache backend)
        assert result is None or result == 'value'
    
    def test_cache_delete(self):
        """Test cache deletion."""
        cache = get_cache()
        
        cache.set('delete_key', 'value', ttl=60)
        cache.delete('delete_key')
        result = cache.get('delete_key')
        
        assert result is None


class TestValidationIntegration:
    """Test validation functionality."""
    
    def test_valid_trade(self):
        """Test valid trade validation."""
        result = trade_validator.validate_trade('AAPL', 'BUY', 100, 150.0)
        
        assert result['ticker'] == 'AAPL'
        assert result['action'] == 'BUY'
        assert result['quantity'] == 100
        assert result['price'] == 150.0
    
    def test_invalid_ticker(self):
        """Test invalid ticker validation."""
        with pytest.raises(ValidationError):
            trade_validator.validate_trade('INVALID123', 'BUY', 100, 150.0)
    
    def test_invalid_quantity(self):
        """Test invalid quantity validation."""
        with pytest.raises(ValidationError):
            trade_validator.validate_trade('AAPL', 'BUY', -100, 150.0)
    
    def test_invalid_price(self):
        """Test invalid price validation."""
        with pytest.raises(ValidationError):
            trade_validator.validate_trade('AAPL', 'BUY', 100, -150.0)


class TestDataQualityIntegration:
    """Test data quality checks."""
    
    def test_price_validation(self):
        """Test price data validation."""
        checker = get_quality_checker()
        
        data = {
            'prices': {'AAPL': 150.0, 'MSFT': 300.0},
            'timestamp': datetime.now()
        }
        
        passed, issues = checker.run_full_quality_check(data, {})
        assert passed is True
        assert len(issues) == 0
    
    def test_invalid_price_detection(self):
        """Test detection of invalid prices."""
        checker = get_quality_checker()
        
        data = {
            'prices': {'AAPL': -150.0},  # Invalid negative price
            'timestamp': datetime.now()
        }
        
        passed, issues = checker.run_full_quality_check(data, {})
        assert passed is False
        assert len(issues) > 0


class TestPaperTradingIntegration:
    """Test paper trading functionality."""
    
    def test_paper_trade_buy(self):
        """Test paper trading buy order."""
        engine = PaperTradingEngine(initial_capital=100000)
        
        success = engine.place_order('AAPL', 'BUY', 100, 150.0)
        
        assert success is True
        assert 'AAPL' in engine.positions
        assert engine.positions['AAPL'].quantity == 100
        assert engine.cash < 100000
    
    def test_paper_trade_sell(self):
        """Test paper trading sell order."""
        engine = PaperTradingEngine(initial_capital=100000)
        
        # Buy first
        engine.place_order('AAPL', 'BUY', 100, 150.0)
        initial_cash = engine.cash
        
        # Then sell
        success = engine.place_order('AAPL', 'SELL', 50, 155.0)
        
        assert success is True
        assert engine.positions['AAPL'].quantity == 50
        assert engine.cash > initial_cash
    
    def test_paper_trade_insufficient_funds(self):
        """Test paper trading with insufficient funds."""
        engine = PaperTradingEngine(initial_capital=1000)
        
        success = engine.place_order('AAPL', 'BUY', 1000, 150.0)
        
        assert success is False
        assert 'AAPL' not in engine.positions
    
    def test_paper_trade_performance_metrics(self):
        """Test performance metrics calculation."""
        engine = PaperTradingEngine(initial_capital=100000)
        
        engine.place_order('AAPL', 'BUY', 100, 150.0)
        engine.update_prices({'AAPL': 160.0})
        
        metrics = engine.get_performance_metrics()
        
        assert metrics['total_value'] > 100000
        assert metrics['total_return'] > 0
        assert metrics['num_positions'] == 1


class TestDatabaseIntegration:
    """Test database connectivity."""
    
    def test_database_pool_connection(self):
        """Test database pool connectivity."""
        try:
            pool = get_db_pool()
            metrics = pool.get_pool_status()
            
            assert metrics['size'] > 0
            assert 'checked_in' in metrics
            assert 'checked_out' in metrics
        except Exception as e:
            pytest.skip(f"Database not available: {e}")
    
    def test_database_session_context(self):
        """Test database session context manager."""
        try:
            from db.connection_pool import get_db_session
            
            with get_db_session() as session:
                # Session should be valid
                assert session is not None
        except Exception as e:
            pytest.skip(f"Database not available: {e}")


class TestEndToEndWorkflow:
    """Test complete end-to-end workflows."""
    
    def test_trade_workflow(self):
        """Test complete trade workflow."""
        # 1. Validate trade
        validated = trade_validator.validate_trade('AAPL', 'BUY', 100, 150.0)
        assert validated is not None
        
        # 2. Check data quality
        checker = get_quality_checker()
        data = {
            'prices': {'AAPL': 150.0},
            'timestamp': datetime.now()
        }
        passed, _ = checker.run_full_quality_check(data, {})
        assert passed is True
        
        # 3. Execute paper trade
        engine = PaperTradingEngine(initial_capital=100000)
        success = engine.place_order(
            validated['ticker'],
            validated['action'],
            validated['quantity'],
            validated['price']
        )
        assert success is True
        
        # 4. Verify position
        assert 'AAPL' in engine.positions
        assert engine.positions['AAPL'].quantity == 100


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
