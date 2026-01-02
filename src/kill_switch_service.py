#!/usr/bin/env python3
"""
Kill Switch Service
Manual and automatic circuit breakers for trading system
"""
import os
import logging
from typing import Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class KillSwitchService:
    """Manages kill switches and circuit breakers"""
    
    def __init__(self, db, email_notifier):
        self.db = db
        self.email_notifier = email_notifier
        self.kill_reasons = []
        self.is_killed = False
    
    def check_all_switches(self, context: Dict) -> bool:
        """
        Check all kill switches. Returns True if trading should proceed.
        
        Args:
            context: Dict with keys: reconciliation_status, daily_drawdown, 
                     consecutive_failures, rejected_orders_count
        """
        self.kill_reasons = []
        self.is_killed = False
        
        if self._check_manual_kill_switches():
            return False
        
        if self._check_automatic_kill_conditions(context):
            return False
        
        return True
    
    def _check_manual_kill_switches(self) -> bool:
        """Check manual env var kill switches"""
        
        if os.getenv('TRADING_DISABLED', 'false').lower() == 'true':
            self.kill_reasons.append("MANUAL_KILL: TRADING_DISABLED=true")
            self.is_killed = True
            logger.critical("🛑 KILL SWITCH: Trading globally disabled via TRADING_DISABLED env var")
            self._send_kill_alert("Manual Kill Switch", "TRADING_DISABLED=true")
            return True
        
        disabled_strategies = os.getenv('STRATEGY_DISABLED_LIST', '')
        if disabled_strategies:
            strategies = [s.strip() for s in disabled_strategies.split(',')]
            self.kill_reasons.append(f"MANUAL_KILL: Strategies disabled: {', '.join(strategies)}")
            logger.warning(f"⚠️ Strategies disabled: {', '.join(strategies)}")
        
        return False
    
    def _check_automatic_kill_conditions(self, context: Dict) -> bool:
        """Check automatic kill conditions"""
        
        if context.get('reconciliation_status') == 'FAIL':
            self.kill_reasons.append("AUTO_KILL: Broker reconciliation failed")
            self.is_killed = True
            logger.critical("🛑 KILL SWITCH: Reconciliation failure - trading halted")
            self._send_kill_alert("Reconciliation Failure", 
                                 "Broker positions/cash do not match database. Trading halted.")
            return True
        
        daily_dd = context.get('daily_drawdown', 0)
        if daily_dd > 0.05:
            self.kill_reasons.append(f"AUTO_KILL: Excessive daily drawdown {daily_dd*100:.1f}%")
            self.is_killed = True
            logger.critical(f"🛑 KILL SWITCH: Daily drawdown {daily_dd*100:.1f}% exceeds 5%")
            self._send_kill_alert("Excessive Drawdown", 
                                 f"Daily drawdown {daily_dd*100:.1f}% exceeds 5% threshold")
            return True
        
        consecutive_failures = context.get('consecutive_failures', 0)
        if consecutive_failures >= 3:
            self.kill_reasons.append(f"AUTO_KILL: {consecutive_failures} consecutive run failures")
            self.is_killed = True
            logger.critical(f"🛑 KILL SWITCH: {consecutive_failures} consecutive failures")
            self._send_kill_alert("Consecutive Failures", 
                                 f"{consecutive_failures} runs have failed in a row")
            return True
        
        rejected_count = context.get('rejected_orders_count', 0)
        total_orders = context.get('total_orders', 1)
        rejection_rate = rejected_count / total_orders if total_orders > 0 else 0
        
        if rejected_count >= 5 and rejection_rate > 0.5:
            self.kill_reasons.append(f"AUTO_KILL: High order rejection rate {rejection_rate*100:.0f}%")
            self.is_killed = True
            logger.critical(f"🛑 KILL SWITCH: {rejected_count} orders rejected ({rejection_rate*100:.0f}%)")
            self._send_kill_alert("High Order Rejection Rate", 
                                 f"{rejected_count}/{total_orders} orders rejected")
            return True
        
        return False
    
    def _send_kill_alert(self, reason: str, details: str):
        """Send critical alert email"""
        subject = f"🛑 KILL SWITCH ACTIVATED: {reason}"
        message = f"""
TRADING SYSTEM KILL SWITCH ACTIVATED

Reason: {reason}
Details: {details}
Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

All trading has been halted. Manual intervention required.

To resume trading:
1. Investigate and resolve the issue
2. Set TRADING_DISABLED=false (if manually disabled)
3. Restart the system

Kill reasons logged:
{chr(10).join(f'  - {r}' for r in self.kill_reasons)}
"""
        
        try:
            self.email_notifier.send_alert(subject, message)
        except Exception as e:
            logger.error(f"Failed to send kill switch alert: {e}")
    
    def get_status(self) -> Dict:
        """Get kill switch status"""
        return {
            'is_killed': self.is_killed,
            'kill_reasons': self.kill_reasons,
            'manual_disabled': os.getenv('TRADING_DISABLED', 'false').lower() == 'true',
            'disabled_strategies': os.getenv('STRATEGY_DISABLED_LIST', '').split(',')
        }
    
    def is_strategy_enabled(self, strategy_name: str) -> bool:
        """Check if a specific strategy is enabled"""
        disabled_list = os.getenv('STRATEGY_DISABLED_LIST', '')
        if not disabled_list:
            return True
        
        disabled_strategies = [s.strip().lower() for s in disabled_list.split(',')]
        return strategy_name.lower() not in disabled_strategies
