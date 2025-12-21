#!/usr/bin/env python3
"""
Trade Executor
Executes approved trades on Alpaca based on user decisions
"""
import os
from typing import List, Dict
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

try:
    from alpaca.trading.client import TradingClient
    from alpaca.trading.requests import MarketOrderRequest
    from alpaca.trading.enums import OrderSide, TimeInForce
except ImportError:
    print("Warning: alpaca-py not installed")


class TradeExecutor:
    """Executes trades on Alpaca based on approval decisions"""
    
    def __init__(self):
        self.api_key = os.getenv('ALPACA_API_KEY')
        self.secret_key = os.getenv('ALPACA_SECRET_KEY')
        
        if not self.api_key or not self.secret_key:
            raise ValueError("Alpaca credentials not found in environment")
        
        self.trading_client = TradingClient(self.api_key, self.secret_key, paper=True)
    
    def execute_approved_trades(self, approval_decisions: Dict[str, str], trades: List[Dict], request_id: str = None) -> Dict:
        """
        Execute trades based on approval decisions and store results in database
        
        Args:
            approval_decisions: Dict mapping trade index to 'approve' or 'reject'
            trades: List of proposed trades with symbol, shares, action
            request_id: Approval request ID for database tracking
        
        Returns:
            Dict with execution results
        """
        from database_schema import TradingDatabase
        db = TradingDatabase()
        
        results = {
            'approved': [],
            'rejected': [],
            'executed': [],
            'failed': [],
            'summary': {}
        }
        
        for i, trade in enumerate(trades):
            trade_key = f'trade_{i}'
            decision = approval_decisions.get(trade_key, 'reject')
            
            symbol = trade['symbol']
            shares = trade['shares']
            action = trade.get('action', 'BUY')
            
            if decision == 'approve':
                results['approved'].append(trade)
                
                # Execute the trade
                execution_result = self._execute_single_trade(trade)
                
                if execution_result['success']:
                    results['executed'].append({
                        'trade': trade,
                        'order_id': execution_result['order_id'],
                        'status': execution_result['status']
                    })
                    
                    # Store successful execution in database
                    db.save_trade_execution(
                        request_id=request_id or 'unknown',
                        symbol=symbol,
                        shares=shares,
                        action=action,
                        decision='approved',
                        order_id=execution_result['order_id'],
                        status=execution_result['status'],
                        executed_price=trade.get('price')
                    )
                else:
                    results['failed'].append({
                        'trade': trade,
                        'error': execution_result['error']
                    })
                    
                    # Store failed execution in database
                    db.save_trade_execution(
                        request_id=request_id or 'unknown',
                        symbol=symbol,
                        shares=shares,
                        action=action,
                        decision='approved',
                        error=execution_result['error']
                    )
            else:
                results['rejected'].append(trade)
                
                # Store rejection in database
                db.save_trade_execution(
                    request_id=request_id or 'unknown',
                    symbol=symbol,
                    shares=shares,
                    action=action,
                    decision='rejected'
                )
        
        # Generate summary
        results['summary'] = {
            'total_trades': len(trades),
            'approved': len(results['approved']),
            'rejected': len(results['rejected']),
            'executed': len(results['executed']),
            'failed': len(results['failed']),
            'timestamp': datetime.now().isoformat()
        }
        
        return results
    
    def _execute_single_trade(self, trade: Dict) -> Dict:
        """
        Execute a single trade on Alpaca
        
        Args:
            trade: Trade dict with symbol, shares, action
        
        Returns:
            Dict with success status, order_id, or error
        """
        try:
            symbol = trade['symbol']
            shares = trade['shares']
            action = trade.get('action', 'BUY').upper()
            
            # Determine order side
            order_side = OrderSide.BUY if action == 'BUY' else OrderSide.SELL
            
            # Create market order request
            order_data = MarketOrderRequest(
                symbol=symbol,
                qty=shares,
                side=order_side,
                time_in_force=TimeInForce.DAY
            )
            
            # Submit order
            order = self.trading_client.submit_order(order_data)
            
            return {
                'success': True,
                'order_id': order.id,
                'status': order.status,
                'symbol': symbol,
                'shares': shares,
                'action': action
            }
        
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'symbol': trade.get('symbol', 'UNKNOWN'),
                'shares': trade.get('shares', 0),
                'action': trade.get('action', 'BUY')
            }
    
    def log_execution_results(self, results: Dict, request_id: str):
        """Log execution results to database"""
        from database_schema import TradingDatabase
        
        db = TradingDatabase()
        
        # Log each executed trade
        for executed in results['executed']:
            trade = executed['trade']
            print(f"✅ EXECUTED: {trade['symbol']} - {trade['shares']} shares - Order ID: {executed['order_id']}")
        
        # Log each failed trade
        for failed in results['failed']:
            trade = failed['trade']
            print(f"❌ FAILED: {trade['symbol']} - {trade['shares']} shares - Error: {failed['error']}")
        
        # Log each rejected trade
        for rejected in results['rejected']:
            print(f"⏭️  REJECTED: {rejected['symbol']} - {rejected['shares']} shares")
        
        # Print summary
        summary = results['summary']
        print(f"\n📊 EXECUTION SUMMARY:")
        print(f"   Total Trades: {summary['total_trades']}")
        print(f"   Approved: {summary['approved']}")
        print(f"   Rejected: {summary['rejected']}")
        print(f"   Successfully Executed: {summary['executed']}")
        print(f"   Failed: {summary['failed']}")
        print(f"   Timestamp: {summary['timestamp']}")


def process_approval_form(form_data: Dict, trades: List[Dict]) -> Dict:
    """
    Process approval form submission and execute trades
    
    Args:
        form_data: Form data from approval page with trade decisions
        trades: List of proposed trades
    
    Returns:
        Execution results
    """
    # Extract approval decisions from form data
    approval_decisions = {}
    for key, value in form_data.items():
        if key.startswith('trade_'):
            approval_decisions[key] = value
    
    # Execute approved trades
    executor = TradeExecutor()
    results = executor.execute_approved_trades(approval_decisions, trades)
    
    # Log results
    request_id = form_data.get('request_id', 'unknown')
    executor.log_execution_results(results, request_id)
    
    return results
