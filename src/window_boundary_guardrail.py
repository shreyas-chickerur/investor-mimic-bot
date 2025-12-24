#!/usr/bin/env python3
"""
Window Boundary Guardrail Test

Fix 2: Clarify and enforce window boundary behavior
Ensures that if positions are reset and trades = 0, return must be 0.
"""

def test_window_boundary_guardrail(trades, initial_capital, final_value, positions_at_start, positions_at_end):
    """
    Guardrail test for window boundary behavior
    
    Args:
        trades: Number of trades executed in window
        initial_capital: Starting capital for window
        final_value: Ending capital for window
        positions_at_start: Number of positions at window start
        positions_at_end: Number of positions at window end
    
    Returns:
        tuple: (passed, message)
    """
    # Calculate return
    total_return = ((final_value - initial_capital) / initial_capital) * 100
    
    # Guardrail: If positions reset and no trades, return must be 0
    if positions_at_start == 0 and trades == 0 and positions_at_end == 0:
        if abs(total_return) > 0.01:  # Allow for tiny rounding errors
            return False, f"FAIL: No positions, no trades, but return = {total_return:.2f}% (expected 0%)"
        else:
            return True, f"PASS: No positions, no trades, return = {total_return:.2f}% (correct)"
    
    # If trades occurred or positions carried forward, any return is valid
    return True, f"PASS: {trades} trades, return = {total_return:.2f}%"


def explain_window_behavior():
    """
    Explain the window boundary behavior policy
    
    Returns:
        str: Explanation of policy
    """
    return """
WINDOW BOUNDARY BEHAVIOR POLICY:

1. Position Handling:
   - Positions are NOT reset at window boundaries
   - Positions carry forward across windows
   - P&L attribution continues from entry date

2. Return Calculation:
   - Returns calculated from window start capital
   - Includes unrealized P&L from carried positions
   - Includes realized P&L from closed positions

3. Guardrail Rule:
   - IF: No positions at start AND no trades AND no positions at end
   - THEN: Return MUST be 0% (within rounding tolerance)
   
4. Example Scenarios:

   Scenario A: Carry Forward
   - Start: 1 position (AAPL, bought in previous window)
   - Trades: 0 new trades
   - End: 1 position (AAPL, still held)
   - Return: Can be non-zero (unrealized P&L from AAPL)
   - Status: VALID
   
   Scenario B: Fresh Window
   - Start: 0 positions
   - Trades: 0 new trades
   - End: 0 positions
   - Return: MUST be 0%
   - Status: VALID only if return = 0%
   
   Scenario C: New Trades
   - Start: 0 positions
   - Trades: 3 new trades
   - End: 3 positions
   - Return: Can be non-zero (unrealized P&L from new positions)
   - Status: VALID

5. Why This Matters:
   - Prevents phantom returns from data errors
   - Ensures P&L attribution is correct
   - Validates position tracking accuracy
"""
