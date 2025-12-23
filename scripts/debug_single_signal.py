#!/usr/bin/env python3
"""
Deep-dive debugging: Trace a single signal through the entire execution pipeline
Purpose: Identify EXACTLY where and why trades are being blocked
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import pandas as pd
import logging

logging.basicConfig(level=logging.DEBUG, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

from portfolio_risk_manager import PortfolioRiskManager
from execution_costs import ExecutionCostModel

def test_signal_execution():
    """Manually trace a single signal through execution"""
    
    logger.info("="*80)
    logger.info("SINGLE SIGNAL EXECUTION DEBUG")
    logger.info("="*80)
    
    # Create a synthetic signal (like signal injection would)
    signal = {
        'symbol': 'AAPL',
        'action': 'BUY',
        'price': 150.00,
        'shares': 10,
        'confidence': 0.7,
        'reasoning': 'Debug test signal'
    }
    
    logger.info(f"\n1. SIGNAL CREATED:")
    logger.info(f"   Symbol: {signal['symbol']}")
    logger.info(f"   Action: {signal['action']}")
    logger.info(f"   Price: ${signal['price']:.2f}")
    logger.info(f"   Shares: {signal['shares']}")
    logger.info(f"   Value: ${signal['shares'] * signal['price']:.2f}")
    
    # Test position sizing
    logger.info(f"\n2. POSITION SIZING CHECK:")
    if signal['shares'] == 0:
        logger.error("   ❌ BLOCKED: Signal has 0 shares")
        return False
    else:
        logger.info(f"   ✅ PASSED: {signal['shares']} shares")
    
    # Test cash availability
    cash = 100000.00
    total_value = signal['shares'] * signal['price']
    
    logger.info(f"\n3. CASH AVAILABILITY CHECK:")
    logger.info(f"   Available cash: ${cash:,.2f}")
    logger.info(f"   Required: ${total_value:.2f}")
    
    if total_value > cash:
        logger.error(f"   ❌ BLOCKED: Insufficient cash")
        return False
    else:
        logger.info(f"   ✅ PASSED: Sufficient cash")
    
    # Test execution costs
    cost_model = ExecutionCostModel()
    exec_price, slippage, commission, total_cost = cost_model.calculate_execution_price(
        signal['price'], 'BUY', signal['shares']
    )
    
    logger.info(f"\n4. EXECUTION COST CALCULATION:")
    logger.info(f"   Quoted price: ${signal['price']:.2f}")
    logger.info(f"   Execution price: ${exec_price:.2f}")
    logger.info(f"   Slippage: ${slippage:.4f}")
    logger.info(f"   Commission: ${commission:.2f}")
    logger.info(f"   Total cost: ${total_cost:.2f}")
    
    total_with_costs = exec_price * signal['shares'] + total_cost
    logger.info(f"   Total value with costs: ${total_with_costs:.2f}")
    
    if total_with_costs > cash:
        logger.error(f"   ❌ BLOCKED: Insufficient cash after costs")
        return False
    else:
        logger.info(f"   ✅ PASSED: Can afford with costs")
    
    # Test portfolio risk
    portfolio_risk = PortfolioRiskManager()
    portfolio_value = 100000.00
    current_exposure = 0.00  # No existing positions
    
    logger.info(f"\n5. PORTFOLIO RISK CHECK:")
    logger.info(f"   Portfolio value: ${portfolio_value:,.2f}")
    logger.info(f"   Current exposure: ${current_exposure:.2f}")
    logger.info(f"   New position value: ${total_with_costs:.2f}")
    logger.info(f"   New exposure: ${current_exposure + total_with_costs:.2f}")
    logger.info(f"   New exposure %: {((current_exposure + total_with_costs) / portfolio_value * 100):.2f}%")
    logger.info(f"   Max allowed (30%): ${portfolio_value * 0.30:,.2f}")
    
    can_add = portfolio_risk.can_add_position(total_with_costs, current_exposure, portfolio_value)
    
    if not can_add:
        logger.error(f"   ❌ BLOCKED: Portfolio heat limit exceeded")
        return False
    else:
        logger.info(f"   ✅ PASSED: Within portfolio heat limit")
    
    # If we got here, trade should execute
    logger.info(f"\n6. EXECUTION:")
    logger.info(f"   ✅ ALL CHECKS PASSED - TRADE SHOULD EXECUTE")
    logger.info(f"   Buy {signal['shares']} {signal['symbol']} @ ${exec_price:.2f}")
    logger.info(f"   Total cost: ${total_with_costs:.2f}")
    logger.info(f"   Remaining cash: ${cash - total_with_costs:,.2f}")
    
    return True

def test_why_backtester_fails():
    """Test why the same signal fails in backtester"""
    
    logger.info("\n" + "="*80)
    logger.info("BACKTESTER CONTEXT TEST")
    logger.info("="*80)
    
    # Load actual market data
    df = pd.read_csv('data/training_data.csv', index_col=0)
    df.index = pd.to_datetime(df.index)
    
    # Get a single day
    test_date = df.index[-1]
    daily_data = df[df.index == test_date]
    
    logger.info(f"\nTest date: {test_date}")
    logger.info(f"Daily data shape: {daily_data.shape}")
    logger.info(f"Symbols in daily data: {daily_data['symbol'].nunique()}")
    
    # Check if AAPL exists
    aapl_data = daily_data[daily_data['symbol'] == 'AAPL']
    
    if len(aapl_data) == 0:
        logger.error("❌ AAPL not in daily data!")
        return False
    
    logger.info(f"✅ AAPL found in data")
    logger.info(f"AAPL close: ${aapl_data['close'].iloc[0]:.2f}")
    
    # The issue might be that backtester can't find the price
    # Or that the signal format doesn't match what backtester expects
    
    return True

if __name__ == '__main__':
    logger.info("Starting execution debug...\n")
    
    # Test 1: Can a signal execute in isolation?
    result1 = test_signal_execution()
    
    # Test 2: Why does it fail in backtester context?
    result2 = test_why_backtester_fails()
    
    logger.info("\n" + "="*80)
    logger.info("DEBUG SUMMARY")
    logger.info("="*80)
    logger.info(f"Isolated execution test: {'✅ PASS' if result1 else '❌ FAIL'}")
    logger.info(f"Backtester context test: {'✅ PASS' if result2 else '❌ FAIL'}")
    
    if result1 and result2:
        logger.info("\n✅ Signal CAN execute - issue is in backtester integration")
    elif result1 and not result2:
        logger.info("\n⚠️  Signal can execute but backtester context has issues")
    else:
        logger.info("\n❌ Signal cannot execute - fundamental issue with execution logic")
