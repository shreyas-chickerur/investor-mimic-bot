#!/usr/bin/env python3
"""
Comprehensive tests for Stop Loss Manager
Phase 1.1: Catastrophe Stop Losses
"""
import pytest
import sys
from pathlib import Path

# Add src to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / 'src'))

from stop_loss_manager import StopLossManager


class TestStopLossManager:
    """Test suite for StopLossManager"""
    
    def setup_method(self):
        """Setup for each test"""
        self.manager = StopLossManager(atr_multiplier=3.0)
    
    # Unit Test 1: Stop triggers at exactly 3x ATR below entry
    def test_stop_triggers_at_3x_atr(self):
        """Test that stop loss triggers at exactly 3x ATR below entry price"""
        entry_price = 100.0
        atr = 2.0
        expected_stop = entry_price - (3.0 * atr)  # 94.0
        
        self.manager.set_stop_loss('AAPL', entry_price, atr)
        
        # Should trigger at stop price
        assert self.manager.check_stop_loss('AAPL', expected_stop) == True
        
        # Should trigger below stop price
        assert self.manager.check_stop_loss('AAPL', expected_stop - 0.01) == True
    
    # Unit Test 2: Stop doesn't trigger at 2.9x ATR
    def test_stop_doesnt_trigger_above_level(self):
        """Test that stop loss doesn't trigger above the stop level"""
        entry_price = 100.0
        atr = 2.0
        stop_price = entry_price - (3.0 * atr)  # 94.0
        
        self.manager.set_stop_loss('AAPL', entry_price, atr)
        
        # Should NOT trigger just above stop
        assert self.manager.check_stop_loss('AAPL', stop_price + 0.01) == False
        
        # Should NOT trigger at entry price
        assert self.manager.check_stop_loss('AAPL', entry_price) == False
        
        # Should NOT trigger above entry
        assert self.manager.check_stop_loss('AAPL', entry_price + 10) == False
    
    # Unit Test 3: Different ATR multipliers work correctly
    def test_different_atr_multipliers(self):
        """Test stop loss with different ATR multipliers"""
        entry_price = 100.0
        atr = 2.0
        
        # Test 2x ATR
        manager_2x = StopLossManager(atr_multiplier=2.0)
        manager_2x.set_stop_loss('AAPL', entry_price, atr)
        assert manager_2x.get_stop_price('AAPL') == 96.0
        
        # Test 2.5x ATR
        manager_25x = StopLossManager(atr_multiplier=2.5)
        manager_25x.set_stop_loss('AAPL', entry_price, atr)
        assert manager_25x.get_stop_price('AAPL') == 95.0
        
        # Test 3x ATR
        manager_3x = StopLossManager(atr_multiplier=3.0)
        manager_3x.set_stop_loss('AAPL', entry_price, atr)
        assert manager_3x.get_stop_price('AAPL') == 94.0
    
    # Unit Test 4: Multiple positions tracked independently
    def test_multiple_positions_independent(self):
        """Test that multiple positions are tracked independently"""
        self.manager.set_stop_loss('AAPL', 100.0, 2.0)
        self.manager.set_stop_loss('MSFT', 200.0, 4.0)
        self.manager.set_stop_loss('GOOGL', 150.0, 3.0)
        
        # Check stop prices are correct
        assert self.manager.get_stop_price('AAPL') == 94.0
        assert self.manager.get_stop_price('MSFT') == 188.0
        assert self.manager.get_stop_price('GOOGL') == 141.0
        
        # Trigger one stop shouldn't affect others
        assert self.manager.check_stop_loss('AAPL', 93.0) == True
        assert self.manager.check_stop_loss('MSFT', 190.0) == False
        assert self.manager.check_stop_loss('GOOGL', 145.0) == False
    
    # Unit Test 5: Stop removal works correctly
    def test_stop_removal(self):
        """Test that stop loss can be removed"""
        self.manager.set_stop_loss('AAPL', 100.0, 2.0)
        assert self.manager.get_stop_price('AAPL') == 94.0
        
        self.manager.remove_stop_loss('AAPL')
        assert self.manager.get_stop_price('AAPL') == 0.0
        assert self.manager.check_stop_loss('AAPL', 50.0) == False
    
    # Unit Test 6: Zero or negative ATR handling
    def test_invalid_atr_handling(self):
        """Test handling of zero or negative ATR"""
        # Zero ATR
        self.manager.set_stop_loss('AAPL', 100.0, 0.0)
        assert self.manager.get_stop_price('AAPL') == 0.0
        
        # Negative ATR
        self.manager.set_stop_loss('MSFT', 100.0, -1.0)
        assert self.manager.get_stop_price('MSFT') == 0.0
        
        # None ATR
        self.manager.set_stop_loss('GOOGL', 100.0, None)
        assert self.manager.get_stop_price('GOOGL') == 0.0
    
    # Unit Test 7: Trailing stop updates correctly
    def test_trailing_stop_only_moves_up(self):
        """Test that trailing stop only moves up, never down"""
        entry_price = 100.0
        atr = 2.0
        
        self.manager.set_stop_loss('AAPL', entry_price, atr)
        initial_stop = self.manager.get_stop_price('AAPL')
        assert initial_stop == 94.0
        
        # Price goes up, stop should move up
        self.manager.update_trailing_stop('AAPL', 110.0, atr)
        new_stop = self.manager.get_stop_price('AAPL')
        assert new_stop == 104.0  # 110 - (3 * 2)
        assert new_stop > initial_stop
        
        # Price goes down, stop should NOT move down
        self.manager.update_trailing_stop('AAPL', 105.0, atr)
        final_stop = self.manager.get_stop_price('AAPL')
        assert final_stop == 104.0  # Should stay at 104, not move to 99
    
    # Unit Test 8: Edge case - exact stop price
    def test_exact_stop_price_triggers(self):
        """Test that hitting exact stop price triggers the stop"""
        entry_price = 100.0
        atr = 2.0
        
        self.manager.set_stop_loss('AAPL', entry_price, atr)
        stop_price = self.manager.get_stop_price('AAPL')
        
        # Exact stop price should trigger
        assert self.manager.check_stop_loss('AAPL', stop_price) == True
    
    # Unit Test 9: Very small ATR values
    def test_small_atr_values(self):
        """Test stop loss with very small ATR values"""
        entry_price = 100.0
        atr = 0.10  # Very small ATR
        
        self.manager.set_stop_loss('AAPL', entry_price, atr)
        stop_price = self.manager.get_stop_price('AAPL')
        
        assert stop_price == 99.70  # 100 - (3 * 0.10)
        assert self.manager.check_stop_loss('AAPL', 99.69) == True
        assert self.manager.check_stop_loss('AAPL', 99.71) == False
    
    # Unit Test 10: Very large ATR values
    def test_large_atr_values(self):
        """Test stop loss with very large ATR values"""
        entry_price = 100.0
        atr = 20.0  # Very large ATR (volatile stock)
        
        self.manager.set_stop_loss('AAPL', entry_price, atr)
        stop_price = self.manager.get_stop_price('AAPL')
        
        assert stop_price == 40.0  # 100 - (3 * 20)
        assert self.manager.check_stop_loss('AAPL', 39.0) == True
        assert self.manager.check_stop_loss('AAPL', 41.0) == False


class TestStopLossIntegration:
    """Integration tests for stop loss functionality"""
    
    def test_realistic_scenario_aapl(self):
        """Test realistic scenario with AAPL-like stock"""
        manager = StopLossManager(atr_multiplier=3.0)
        
        # AAPL entry at $180, ATR ~$3
        entry_price = 180.0
        atr = 3.0
        
        manager.set_stop_loss('AAPL', entry_price, atr)
        stop_price = manager.get_stop_price('AAPL')
        
        # Stop should be at $171 (180 - 9)
        assert stop_price == 171.0
        
        # Normal fluctuations shouldn't trigger
        assert manager.check_stop_loss('AAPL', 175.0) == False
        assert manager.check_stop_loss('AAPL', 172.0) == False
        
        # Catastrophic drop should trigger
        assert manager.check_stop_loss('AAPL', 170.0) == True
    
    def test_realistic_scenario_volatile_stock(self):
        """Test realistic scenario with volatile stock"""
        manager = StopLossManager(atr_multiplier=2.5)
        
        # Volatile stock entry at $50, ATR ~$5
        entry_price = 50.0
        atr = 5.0
        
        manager.set_stop_loss('TSLA', entry_price, atr)
        stop_price = manager.get_stop_price('TSLA')
        
        # Stop should be at $37.50 (50 - 12.5)
        assert stop_price == 37.50
        
        # Normal volatility shouldn't trigger
        assert manager.check_stop_loss('TSLA', 45.0) == False
        assert manager.check_stop_loss('TSLA', 40.0) == False
        
        # Major drop should trigger
        assert manager.check_stop_loss('TSLA', 37.0) == True
    
    def test_portfolio_with_multiple_stops(self):
        """Test managing stops for entire portfolio"""
        manager = StopLossManager(atr_multiplier=3.0)
        
        # Set up portfolio with 5 positions
        positions = {
            'AAPL': {'entry': 180.0, 'atr': 3.0},
            'MSFT': {'entry': 380.0, 'atr': 6.0},
            'GOOGL': {'entry': 140.0, 'atr': 2.5},
            'NVDA': {'entry': 500.0, 'atr': 15.0},
            'TSLA': {'entry': 250.0, 'atr': 10.0}
        }
        
        for symbol, data in positions.items():
            manager.set_stop_loss(symbol, data['entry'], data['atr'])
        
        # Simulate market prices
        current_prices = {
            'AAPL': 175.0,  # Down but not at stop (stop at 171)
            'MSFT': 370.0,  # Down but not at stop (stop at 362)
            'GOOGL': 132.0, # At stop level (140 - 3*2.5 = 132.5)
            'NVDA': 480.0,  # Down but not at stop (stop at 455)
            'TSLA': 210.0   # At stop level (250 - 3*10 = 220)
        }
        
        # Check which stops are hit
        stops_hit = []
        for symbol, price in current_prices.items():
            if manager.check_stop_loss(symbol, price):
                stops_hit.append(symbol)
        
        # Both GOOGL and TSLA should have stops hit
        assert 'GOOGL' in stops_hit
        assert 'TSLA' in stops_hit
        assert len(stops_hit) == 2


# Property-based tests using hypothesis
try:
    from hypothesis import given, strategies as st
    
    class TestStopLossProperties:
        """Property-based tests for stop loss logic"""
        
        @given(
            entry_price=st.floats(min_value=1.0, max_value=1000.0),
            atr=st.floats(min_value=0.1, max_value=50.0),
            atr_multiplier=st.floats(min_value=2.0, max_value=5.0)
        )
        def test_stop_always_below_entry(self, entry_price, atr, atr_multiplier):
            """Property: Stop price should always be below entry price"""
            manager = StopLossManager(atr_multiplier=atr_multiplier)
            manager.set_stop_loss('TEST', entry_price, atr)
            stop_price = manager.get_stop_price('TEST')
            
            assert stop_price < entry_price
        
        @given(
            entry_price=st.floats(min_value=1.0, max_value=1000.0),
            atr=st.floats(min_value=0.1, max_value=50.0),
            price_drop_pct=st.floats(min_value=0.0, max_value=0.99)
        )
        def test_large_drops_always_trigger(self, entry_price, atr, price_drop_pct):
            """Property: Large price drops should always trigger stop"""
            manager = StopLossManager(atr_multiplier=3.0)
            manager.set_stop_loss('TEST', entry_price, atr)
            
            # Drop price by more than 3x ATR
            current_price = entry_price - (4.0 * atr)
            
            if current_price > 0:  # Ensure price is positive
                assert manager.check_stop_loss('TEST', current_price) == True

except ImportError:
    print("hypothesis not installed, skipping property-based tests")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
