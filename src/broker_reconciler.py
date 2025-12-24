#!/usr/bin/env python3
"""
Broker Reconciliation System

Daily reconciliation between local state and Alpaca broker.
Enters PAUSED state on mismatch and blocks all trading until resolved.

Phase 5 - Critical Component
"""
import os
import logging
from typing import Dict, List, Tuple, Optional
from datetime import datetime
from dotenv import load_dotenv
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetOrdersRequest
from alpaca.trading.enums import OrderSide, QueryOrderStatus

load_dotenv()
logger = logging.getLogger(__name__)

class ReconciliationMismatch(Exception):
    """Raised when reconciliation finds a mismatch"""
    pass

class BrokerReconciler:
    """
    Reconciles local trading state with Alpaca broker
    
    Checks:
    - Positions (symbol, qty, avg price)
    - Cash/buying power
    - Open orders
    - Filled trades
    
    On mismatch: Enter PAUSED state, block trading, alert
    """
    
    def __init__(self, email_notifier=None):
        """
        Initialize broker reconciler
        
        Args:
            email_notifier: EmailNotifier instance for alerts
        """
        self.api_key = os.getenv('ALPACA_API_KEY')
        self.secret_key = os.getenv('ALPACA_SECRET_KEY')
        self.paper = os.getenv('ALPACA_PAPER', 'true').lower() == 'true'
        
        if not self.api_key or not self.secret_key:
            logger.warning("Alpaca API credentials not found in environment")
            self.client = None
        else:
            self.client = TradingClient(self.api_key, self.secret_key, paper=self.paper)
        self.email_notifier = email_notifier
        self.is_paused = False
        self.last_reconciliation = None
        self.mismatch_details = []
    
    def reconcile_daily(self, local_positions: Dict, local_cash: float, 
                       local_orders: List = None) -> Tuple[bool, List[str]]:
        """
        Perform daily reconciliation
        
        Args:
            local_positions: Dict of {symbol: {'qty': int, 'avg_price': float}}
            local_cash: Local cash balance
            local_orders: List of local open orders (optional)
            
        Returns:
            (success: bool, discrepancies: List[str])
        """
        logger.info("="*80)
        logger.info("BROKER RECONCILIATION - STARTING")
        logger.info("="*80)
        
        discrepancies = []
        
        try:
            if self.client is None:
                raise ValueError("Alpaca client not configured")
            # 1. Reconcile positions
            position_discrepancies = self._reconcile_positions(local_positions)
            discrepancies.extend(position_discrepancies)
            
            # 2. Reconcile cash
            cash_discrepancies = self._reconcile_cash(local_cash)
            discrepancies.extend(cash_discrepancies)
            
            # 3. Reconcile open orders
            if local_orders is not None:
                order_discrepancies = self._reconcile_orders(local_orders)
                discrepancies.extend(order_discrepancies)
            
            # 4. Check for phantom positions (in broker but not local)
            phantom_discrepancies = self._check_phantom_positions(local_positions)
            discrepancies.extend(phantom_discrepancies)
            
            self.last_reconciliation = datetime.now()
            
            if discrepancies:
                logger.error(f"❌ RECONCILIATION FAILED - {len(discrepancies)} discrepancies found")
                for disc in discrepancies:
                    logger.error(f"  - {disc}")
                
                self._enter_paused_state(discrepancies)
                return False, discrepancies
            else:
                logger.info("✅ RECONCILIATION PASSED - All checks successful")
                self.is_paused = False
                self.mismatch_details = []
                return True, []
                
        except Exception as e:
            error_msg = f"Reconciliation error: {str(e)}"
            logger.error(error_msg)
            discrepancies.append(error_msg)
            self._enter_paused_state(discrepancies)
            return False, discrepancies
    
    def _reconcile_positions(self, local_positions: Dict) -> List[str]:
        """Reconcile positions between local and broker"""
        discrepancies = []
        
        try:
            # Get broker positions
            broker_positions = self.client.get_all_positions()
            broker_dict = {
                pos.symbol: {
                    'qty': int(pos.qty),
                    'avg_price': float(pos.avg_entry_price)
                }
                for pos in broker_positions
            }
            
            logger.info(f"Local positions: {len(local_positions)}, Broker positions: {len(broker_dict)}")
            
            # Check each local position
            for symbol, local_data in local_positions.items():
                if symbol not in broker_dict:
                    disc = f"Position mismatch: {symbol} exists locally but not in broker"
                    discrepancies.append(disc)
                    continue
                
                broker_data = broker_dict[symbol]
                
                # Check quantity
                if local_data['qty'] != broker_data['qty']:
                    disc = f"Quantity mismatch for {symbol}: local={local_data['qty']}, broker={broker_data['qty']}"
                    discrepancies.append(disc)
                
                # Check average price (allow 1% tolerance for rounding)
                price_diff_pct = abs(local_data['avg_price'] - broker_data['avg_price']) / broker_data['avg_price'] * 100
                if price_diff_pct > 1.0:
                    disc = f"Price mismatch for {symbol}: local=${local_data['avg_price']:.2f}, broker=${broker_data['avg_price']:.2f} ({price_diff_pct:.2f}% diff)"
                    discrepancies.append(disc)
            
            # Check for positions in broker but not local
            for symbol in broker_dict:
                if symbol not in local_positions:
                    disc = f"Position mismatch: {symbol} exists in broker but not locally"
                    discrepancies.append(disc)
            
        except Exception as e:
            discrepancies.append(f"Error reconciling positions: {str(e)}")
        
        return discrepancies
    
    def _reconcile_cash(self, local_cash: float) -> List[str]:
        """Reconcile cash balance"""
        discrepancies = []
        
        try:
            account = self.client.get_account()
            broker_cash = float(account.cash)
            broker_buying_power = float(account.buying_power)
            
            logger.info(f"Cash - Local: ${local_cash:,.2f}, Broker: ${broker_cash:,.2f}, Buying Power: ${broker_buying_power:,.2f}")
            
            # Allow 1% tolerance for rounding
            cash_diff_pct = abs(local_cash - broker_cash) / broker_cash * 100 if broker_cash > 0 else 0
            
            if cash_diff_pct > 1.0:
                disc = f"Cash mismatch: local=${local_cash:,.2f}, broker=${broker_cash:,.2f} ({cash_diff_pct:.2f}% diff)"
                discrepancies.append(disc)
            
        except Exception as e:
            discrepancies.append(f"Error reconciling cash: {str(e)}")
        
        return discrepancies
    
    def _reconcile_orders(self, local_orders: List) -> List[str]:
        """Reconcile open orders"""
        discrepancies = []
        
        try:
            # Get open orders from broker
            request = GetOrdersRequest(status=QueryOrderStatus.OPEN)
            broker_orders = self.client.get_orders(filter=request)
            
            logger.info(f"Orders - Local: {len(local_orders)}, Broker: {len(broker_orders)}")
            
            broker_order_ids = {order.id for order in broker_orders}
            local_order_ids = {order.get('id') for order in local_orders if order.get('id')}
            
            # Check for stuck orders (in local but not broker)
            stuck_orders = local_order_ids - broker_order_ids
            if stuck_orders:
                disc = f"Stuck orders found (local but not in broker): {stuck_orders}"
                discrepancies.append(disc)
            
            # Check for phantom orders (in broker but not local)
            phantom_orders = broker_order_ids - local_order_ids
            if phantom_orders:
                disc = f"Phantom orders found (broker but not local): {phantom_orders}"
                discrepancies.append(disc)
            
        except Exception as e:
            discrepancies.append(f"Error reconciling orders: {str(e)}")
        
        return discrepancies
    
    def _check_phantom_positions(self, local_positions: Dict) -> List[str]:
        """Check for positions in broker that shouldn't exist"""
        discrepancies = []
        
        try:
            broker_positions = self.client.get_all_positions()
            
            for pos in broker_positions:
                if pos.symbol not in local_positions:
                    disc = f"Phantom position: {pos.symbol} ({pos.qty} shares) exists in broker but not tracked locally"
                    discrepancies.append(disc)
            
        except Exception as e:
            discrepancies.append(f"Error checking phantom positions: {str(e)}")
        
        return discrepancies
    
    def _enter_paused_state(self, discrepancies: List[str]):
        """
        Enter PAUSED state on reconciliation failure
        
        - Sets is_paused flag
        - Stores mismatch details
        - Sends email alert
        - Blocks all trading
        """
        self.is_paused = True
        self.mismatch_details = discrepancies
        
        logger.critical("="*80)
        logger.critical("⚠️  SYSTEM PAUSED - RECONCILIATION FAILURE")
        logger.critical("="*80)
        logger.critical("Trading is BLOCKED until reconciliation passes")
        logger.critical(f"Discrepancies found: {len(discrepancies)}")
        for disc in discrepancies:
            logger.critical(f"  - {disc}")
        logger.critical("="*80)
        
        # Send email alert
        if self.email_notifier:
            try:
                subject = "🚨 TRADING SYSTEM PAUSED - Reconciliation Failure"
                disc_list = '\n'.join([f'- {disc}' for disc in discrepancies])
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                body = f"""CRITICAL ALERT: Trading system has been PAUSED due to reconciliation failure.

Time: {timestamp}
Status: PAUSED - All trading blocked

Discrepancies Found ({len(discrepancies)}):
{disc_list}

Action Required:
1. Review discrepancies above
2. Manually reconcile local state with broker
3. Fix any data corruption
4. Run reconciliation again
5. System will resume only after successful reconciliation

DO NOT TRADE MANUALLY until this is resolved."""
                self.email_notifier.send_alert(subject, body)
                logger.info("✅ Email alert sent")
            except Exception as e:
                logger.error(f"Failed to send email alert: {e}")
    
    def check_if_paused(self) -> Tuple[bool, List[str]]:
        """
        Check if system is in PAUSED state
        
        Returns:
            (is_paused: bool, mismatch_details: List[str])
        """
        return self.is_paused, self.mismatch_details
    
    def force_resume(self):
        """
        Force resume trading (use with caution)
        
        Should only be called after manual verification that
        discrepancies have been resolved.
        """
        logger.warning("⚠️  FORCE RESUME - Trading unpaused manually")
        self.is_paused = False
        self.mismatch_details = []
    
    def get_broker_state(self) -> Dict:
        """
        Get current broker state for comparison
        
        Returns:
            Dict with positions, cash, orders
        """
        try:
            positions = self.client.get_all_positions()
            account = self.client.get_account()
            orders_request = GetOrdersRequest(status=QueryOrderStatus.OPEN)
            orders = self.client.get_orders(filter=orders_request)
            
            return {
                'positions': {
                    pos.symbol: {
                        'qty': int(pos.qty),
                        'avg_price': float(pos.avg_entry_price),
                        'market_value': float(pos.market_value),
                        'unrealized_pl': float(pos.unrealized_pl)
                    }
                    for pos in positions
                },
                'cash': float(account.cash),
                'buying_power': float(account.buying_power),
                'portfolio_value': float(account.portfolio_value),
                'open_orders': len(orders),
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error getting broker state: {e}")
            return {}


if __name__ == "__main__":
    # Test reconciliation
    logging.basicConfig(level=logging.INFO)
    
    reconciler = BrokerReconciler()
    
    # Get current broker state
    broker_state = reconciler.get_broker_state()
    print("\nCurrent Broker State:")
    print(f"Positions: {len(broker_state.get('positions', {}))}")
    print(f"Cash: ${broker_state.get('cash', 0):,.2f}")
    print(f"Portfolio Value: ${broker_state.get('portfolio_value', 0):,.2f}")
    
    # Test reconciliation with current state
    success, discrepancies = reconciler.reconcile_daily(
        local_positions=broker_state.get('positions', {}),
        local_cash=broker_state.get('cash', 0)
    )
    
    print(f"\nReconciliation: {'✅ PASS' if success else '❌ FAIL'}")
    if discrepancies:
        print("Discrepancies:")
        for disc in discrepancies:
            print(f"  - {disc}")
