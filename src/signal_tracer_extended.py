#!/usr/bin/env python3
"""
Signal Flow Tracer - Terminal State Extensions

Adds terminal state enforcement to existing SignalFlowTracer.
Every signal must reach exactly one terminal state.

Terminal States:
- EXECUTED
- REJECTED_BY_CORRELATION
- REJECTED_BY_HEAT
- REJECTED_BY_CIRCUIT_BREAKER
- REJECTED_BY_SIZING
- REJECTED_BY_BROKER
"""
import logging
from typing import Dict, List, Set, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)

# Terminal states
TERMINAL_STATES = {
    'EXECUTED',
    'REJECTED_BY_CORRELATION',
    'REJECTED_BY_HEAT',
    'REJECTED_BY_CIRCUIT_BREAKER',
    'REJECTED_BY_SIZING',
    'REJECTED_BY_BROKER'
}

class TerminalStateViolation(Exception):
    """Raised when terminal state requirements are violated"""
    pass

def set_terminal_state(tracer, trace_id: str, terminal_state: str, reason: str = None):
    """
    Set terminal state for a signal
    
    Args:
        tracer: SignalFlowTracer instance
        trace_id: Signal trace ID
        terminal_state: One of TERMINAL_STATES
        reason: Optional reason for rejection
        
    Raises:
        TerminalStateViolation: If terminal state already set or invalid
    """
    if terminal_state not in TERMINAL_STATES:
        raise TerminalStateViolation(
            f"Invalid terminal state: {terminal_state}. Must be one of {TERMINAL_STATES}"
        )
    
    if not hasattr(tracer, 'signal_terminal_states'):
        tracer.signal_terminal_states = {}
    
    # Check if already has terminal state
    if trace_id in tracer.signal_terminal_states:
        existing = tracer.signal_terminal_states[trace_id]
        raise TerminalStateViolation(
            f"Signal {trace_id} already has terminal state: {existing}. "
            f"Cannot set to {terminal_state}. Each signal must have exactly ONE terminal state."
        )
    
    # Set terminal state
    tracer.signal_terminal_states[trace_id] = terminal_state
    
    logger.info(f"[TERMINAL_STATE] {trace_id} → {terminal_state}" + 
                (f" | {reason}" if reason else ""))
    
    # Add to traces
    tracer.traces.append({
        'trace_id': trace_id,
        'stage': 'TERMINAL_STATE',
        'terminal_state': terminal_state,
        'reason': reason,
        'timestamp': str(datetime.now())
    })

def trace_executed_terminal(tracer, date, signal: Dict, execution_price: float, total_cost: float):
    """
    Log successful execution and set EXECUTED terminal state
    
    This replaces trace_executed() when terminal state enforcement is enabled.
    """
    trace_id = f"{date}_{signal['symbol']}_{signal['action']}"
    
    # Original execution logging
    logger.info(f"[EXECUTED] {trace_id} | Price: ${execution_price:.2f} | Cost: ${total_cost:.2f}")
    
    tracer.traces.append({
        'trace_id': trace_id,
        'date': date,
        'stage': 'EXECUTED',
        'signal': signal,
        'execution_price': execution_price,
        'total_cost': total_cost,
        'status': 'EXECUTED'
    })
    
    # Set terminal state
    set_terminal_state(tracer, trace_id, 'EXECUTED')

def trace_rejected_correlation(tracer, date, signal: Dict, reason: str):
    """Log correlation filter rejection and set terminal state"""
    trace_id = f"{date}_{signal['symbol']}_{signal['action']}"
    
    logger.warning(f"[REJECTED_BY_CORRELATION] {trace_id} | {reason}")
    
    tracer.traces.append({
        'trace_id': trace_id,
        'date': date,
        'stage': 'FILTERED',
        'signal': signal,
        'status': 'REJECTED_BY_CORRELATION',
        'reason': reason
    })
    
    set_terminal_state(tracer, trace_id, 'REJECTED_BY_CORRELATION', reason)

def trace_rejected_heat(tracer, date, signal: Dict, reason: str):
    """Log portfolio heat rejection and set terminal state"""
    trace_id = f"{date}_{signal['symbol']}_{signal['action']}"
    
    logger.warning(f"[REJECTED_BY_HEAT] {trace_id} | {reason}")
    
    tracer.traces.append({
        'trace_id': trace_id,
        'date': date,
        'stage': 'RISK_CHECK',
        'signal': signal,
        'status': 'REJECTED_BY_HEAT',
        'reason': reason
    })
    
    set_terminal_state(tracer, trace_id, 'REJECTED_BY_HEAT', reason)

def trace_rejected_circuit_breaker(tracer, date, signal: Dict, reason: str):
    """Log circuit breaker rejection and set terminal state"""
    trace_id = f"{date}_{signal['symbol']}_{signal['action']}"
    
    logger.warning(f"[REJECTED_BY_CIRCUIT_BREAKER] {trace_id} | {reason}")
    
    tracer.traces.append({
        'trace_id': trace_id,
        'date': date,
        'stage': 'RISK_CHECK',
        'signal': signal,
        'status': 'REJECTED_BY_CIRCUIT_BREAKER',
        'reason': reason
    })
    
    set_terminal_state(tracer, trace_id, 'REJECTED_BY_CIRCUIT_BREAKER', reason)

def trace_rejected_sizing(tracer, date, signal: Dict, reason: str):
    """Log zero-share sizing rejection and set terminal state"""
    trace_id = f"{date}_{signal['symbol']}_{signal['action']}"
    
    logger.error(f"[REJECTED_BY_SIZING] {trace_id} | {reason}")
    
    tracer.traces.append({
        'trace_id': trace_id,
        'date': date,
        'stage': 'SIZED',
        'signal': signal,
        'status': 'REJECTED_BY_SIZING',
        'reason': reason
    })
    
    set_terminal_state(tracer, trace_id, 'REJECTED_BY_SIZING', reason)

def trace_rejected_broker(tracer, date, signal: Dict, reason: str):
    """Log broker rejection and set terminal state"""
    trace_id = f"{date}_{signal['symbol']}_{signal['action']}"
    
    logger.error(f"[REJECTED_BY_BROKER] {trace_id} | {reason}")
    
    tracer.traces.append({
        'trace_id': trace_id,
        'date': date,
        'stage': 'EXECUTION',
        'signal': signal,
        'status': 'REJECTED_BY_BROKER',
        'reason': reason
    })
    
    set_terminal_state(tracer, trace_id, 'REJECTED_BY_BROKER', reason)

def validate_terminal_states(tracer) -> Tuple[bool, List[str]]:
    """
    Validate that all generated signals have exactly one terminal state
    
    Args:
        tracer: SignalFlowTracer instance
        
    Returns:
        (all_valid: bool, violations: List[str])
    """
    violations = []
    
    # Get all generated signals
    generated_signals = [t for t in tracer.traces if t.get('stage') == 'GENERATED']
    generated_trace_ids = {t['trace_id'] for t in generated_signals}
    
    if not hasattr(tracer, 'signal_terminal_states'):
        tracer.signal_terminal_states = {}
    
    # Check each generated signal has terminal state
    for trace_id in generated_trace_ids:
        if trace_id not in tracer.signal_terminal_states:
            violations.append(f"Signal {trace_id} has NO terminal state")
    
    # Check for duplicate terminal states (shouldn't happen with enforcement, but verify)
    terminal_state_traces = [t for t in tracer.traces if t.get('stage') == 'TERMINAL_STATE']
    trace_id_counts = {}
    for t in terminal_state_traces:
        tid = t['trace_id']
        trace_id_counts[tid] = trace_id_counts.get(tid, 0) + 1
    
    for trace_id, count in trace_id_counts.items():
        if count > 1:
            violations.append(f"Signal {trace_id} has {count} terminal states (should be exactly 1)")
    
    if violations:
        logger.error("="*80)
        logger.error("TERMINAL STATE VIOLATIONS DETECTED")
        logger.error("="*80)
        for v in violations:
            logger.error(f"  ❌ {v}")
        logger.error("="*80)
        return False, violations
    else:
        logger.info("✅ All signals have exactly one terminal state")
        return True, []

def print_terminal_state_summary(tracer):
    """Print summary of terminal states"""
    if not hasattr(tracer, 'signal_terminal_states'):
        logger.warning("No terminal state tracking enabled")
        return
    
    logger.info("\n" + "="*80)
    logger.info("TERMINAL STATE SUMMARY")
    logger.info("="*80)
    
    # Count by terminal state
    state_counts = {}
    for state in tracer.signal_terminal_states.values():
        state_counts[state] = state_counts.get(state, 0) + 1
    
    logger.info(f"\nTotal Signals: {len(tracer.signal_terminal_states)}")
    logger.info("\nBy Terminal State:")
    for state in sorted(state_counts.keys()):
        count = state_counts[state]
        pct = (count / len(tracer.signal_terminal_states) * 100) if tracer.signal_terminal_states else 0
        logger.info(f"  {state:30} {count:3} ({pct:5.1f}%)")
    
    logger.info("="*80)


if __name__ == "__main__":
    # Test terminal state enforcement
    from signal_tracer import SignalFlowTracer
    
    logging.basicConfig(level=logging.INFO)
    
    tracer = SignalFlowTracer()
    
    # Generate test signals
    date = "2025-12-23"
    signals = [
        {'symbol': 'AAPL', 'action': 'BUY', 'price': 150.00},
        {'symbol': 'MSFT', 'action': 'BUY', 'price': 300.00},
        {'symbol': 'GOOGL', 'action': 'BUY', 'price': 140.00}
    ]
    
    tracer.trace_generated(date, "Test Strategy", signals)
    
    # Set terminal states
    trace_executed_terminal(tracer, date, signals[0], 150.05, 1500.50)
    trace_rejected_correlation(tracer, date, signals[1], "Correlation > 0.7 with existing position")
    trace_rejected_heat(tracer, date, signals[2], "Portfolio heat would exceed 30%")
    
    # Validate
    valid, violations = validate_terminal_states(tracer)
    print(f"\nValidation: {'✅ PASS' if valid else '❌ FAIL'}")
    
    # Print summary
    print_terminal_state_summary(tracer)
