#!/usr/bin/env python3
"""
Unit Tests for Terminal State Enforcement

Phase 5: Tests that every signal reaches exactly one terminal state.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import unittest
from signal_tracer import SignalFlowTracer
from signal_tracer_extended import (
    set_terminal_state,
    trace_executed_terminal,
    trace_rejected_correlation,
    trace_rejected_heat,
    trace_rejected_circuit_breaker,
    trace_rejected_sizing,
    trace_rejected_broker,
    validate_terminal_states,
    TerminalStateViolation,
    TERMINAL_STATES
)


class TestTerminalStates(unittest.TestCase):
    """Test terminal state enforcement"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.tracer = SignalFlowTracer()
        self.date = "2025-12-23"
        self.signal = {'symbol': 'AAPL', 'action': 'BUY', 'price': 150.00}
    
    def test_all_terminal_states_defined(self):
        """Test that all required terminal states are defined"""
        required = {
            'EXECUTED',
            'REJECTED_BY_CORRELATION',
            'REJECTED_BY_HEAT',
            'REJECTED_BY_CIRCUIT_BREAKER',
            'REJECTED_BY_SIZING',
            'REJECTED_BY_BROKER'
        }
        self.assertEqual(TERMINAL_STATES, required)
    
    def test_executed_terminal_state(self):
        """Test EXECUTED terminal state"""
        self.tracer.trace_generated(self.date, "Test", [self.signal])
        trace_executed_terminal(self.tracer, self.date, self.signal, 150.05, 1500.50)
        
        trace_id = f"{self.date}_AAPL_BUY"
        self.assertIn(trace_id, self.tracer.signal_terminal_states)
        self.assertEqual(self.tracer.signal_terminal_states[trace_id], 'EXECUTED')
    
    def test_rejected_correlation_terminal_state(self):
        """Test REJECTED_BY_CORRELATION terminal state"""
        self.tracer.trace_generated(self.date, "Test", [self.signal])
        trace_rejected_correlation(self.tracer, self.date, self.signal, "Correlation > 0.7")
        
        trace_id = f"{self.date}_AAPL_BUY"
        self.assertEqual(self.tracer.signal_terminal_states[trace_id], 'REJECTED_BY_CORRELATION')
    
    def test_rejected_heat_terminal_state(self):
        """Test REJECTED_BY_HEAT terminal state"""
        self.tracer.trace_generated(self.date, "Test", [self.signal])
        trace_rejected_heat(self.tracer, self.date, self.signal, "Heat > 30%")
        
        trace_id = f"{self.date}_AAPL_BUY"
        self.assertEqual(self.tracer.signal_terminal_states[trace_id], 'REJECTED_BY_HEAT')
    
    def test_rejected_circuit_breaker_terminal_state(self):
        """Test REJECTED_BY_CIRCUIT_BREAKER terminal state"""
        self.tracer.trace_generated(self.date, "Test", [self.signal])
        trace_rejected_circuit_breaker(self.tracer, self.date, self.signal, "Daily loss > 2%")
        
        trace_id = f"{self.date}_AAPL_BUY"
        self.assertEqual(self.tracer.signal_terminal_states[trace_id], 'REJECTED_BY_CIRCUIT_BREAKER')
    
    def test_rejected_sizing_terminal_state(self):
        """Test REJECTED_BY_SIZING terminal state"""
        self.tracer.trace_generated(self.date, "Test", [self.signal])
        trace_rejected_sizing(self.tracer, self.date, self.signal, "0 shares calculated")
        
        trace_id = f"{self.date}_AAPL_BUY"
        self.assertEqual(self.tracer.signal_terminal_states[trace_id], 'REJECTED_BY_SIZING')
    
    def test_rejected_broker_terminal_state(self):
        """Test REJECTED_BY_BROKER terminal state"""
        self.tracer.trace_generated(self.date, "Test", [self.signal])
        trace_rejected_broker(self.tracer, self.date, self.signal, "Insufficient buying power")
        
        trace_id = f"{self.date}_AAPL_BUY"
        self.assertEqual(self.tracer.signal_terminal_states[trace_id], 'REJECTED_BY_BROKER')
    
    def test_duplicate_terminal_state_raises_error(self):
        """Test that setting terminal state twice raises error"""
        self.tracer.trace_generated(self.date, "Test", [self.signal])
        trace_id = f"{self.date}_AAPL_BUY"
        
        # Set first terminal state
        set_terminal_state(self.tracer, trace_id, 'EXECUTED')
        
        # Try to set second terminal state - should raise error
        with self.assertRaises(TerminalStateViolation):
            set_terminal_state(self.tracer, trace_id, 'REJECTED_BY_HEAT')
    
    def test_invalid_terminal_state_raises_error(self):
        """Test that invalid terminal state raises error"""
        trace_id = f"{self.date}_AAPL_BUY"
        
        with self.assertRaises(TerminalStateViolation):
            set_terminal_state(self.tracer, trace_id, 'INVALID_STATE')
    
    def test_validate_all_signals_have_terminal_states(self):
        """Test validation passes when all signals have terminal states"""
        signals = [
            {'symbol': 'AAPL', 'action': 'BUY', 'price': 150.00},
            {'symbol': 'MSFT', 'action': 'BUY', 'price': 300.00}
        ]
        
        self.tracer.trace_generated(self.date, "Test", signals)
        trace_executed_terminal(self.tracer, self.date, signals[0], 150.05, 1500.50)
        trace_rejected_heat(self.tracer, self.date, signals[1], "Heat > 30%")
        
        valid, violations = validate_terminal_states(self.tracer)
        self.assertTrue(valid)
        self.assertEqual(len(violations), 0)
    
    def test_validate_fails_when_signal_missing_terminal_state(self):
        """Test validation fails when signal has no terminal state"""
        signals = [
            {'symbol': 'AAPL', 'action': 'BUY', 'price': 150.00},
            {'symbol': 'MSFT', 'action': 'BUY', 'price': 300.00}
        ]
        
        self.tracer.trace_generated(self.date, "Test", signals)
        # Only set terminal state for first signal
        trace_executed_terminal(self.tracer, self.date, signals[0], 150.05, 1500.50)
        # Second signal has no terminal state
        
        valid, violations = validate_terminal_states(self.tracer)
        self.assertFalse(valid)
        self.assertGreater(len(violations), 0)
        self.assertTrue(any('MSFT' in v for v in violations))
    
    def test_multiple_signals_all_terminal_states(self):
        """Test multiple signals with different terminal states"""
        signals = [
            {'symbol': 'AAPL', 'action': 'BUY', 'price': 150.00},
            {'symbol': 'MSFT', 'action': 'BUY', 'price': 300.00},
            {'symbol': 'GOOGL', 'action': 'BUY', 'price': 140.00},
            {'symbol': 'AMZN', 'action': 'BUY', 'price': 180.00},
            {'symbol': 'TSLA', 'action': 'BUY', 'price': 250.00},
            {'symbol': 'META', 'action': 'BUY', 'price': 350.00}
        ]
        
        self.tracer.trace_generated(self.date, "Test", signals)
        
        # Set different terminal states
        trace_executed_terminal(self.tracer, self.date, signals[0], 150.05, 1500.50)
        trace_rejected_correlation(self.tracer, self.date, signals[1], "Correlation > 0.7")
        trace_rejected_heat(self.tracer, self.date, signals[2], "Heat > 30%")
        trace_rejected_circuit_breaker(self.tracer, self.date, signals[3], "Daily loss > 2%")
        trace_rejected_sizing(self.tracer, self.date, signals[4], "0 shares")
        trace_rejected_broker(self.tracer, self.date, signals[5], "Insufficient buying power")
        
        # Validate
        valid, violations = validate_terminal_states(self.tracer)
        self.assertTrue(valid)
        self.assertEqual(len(violations), 0)
        
        # Check all terminal states are set
        self.assertEqual(len(self.tracer.signal_terminal_states), 6)


if __name__ == '__main__':
    unittest.main()
