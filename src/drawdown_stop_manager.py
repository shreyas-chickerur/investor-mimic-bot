"""
Drawdown Stop Manager - Portfolio-level circuit breaker for live trading

Implements:
- 8% drawdown: Halt new entries, trigger cooldown/resume protocol
- 10% drawdown: Panic mode - flatten all positions, extended cooldown
- Automated health checks before resume
- 50% sizing ramp-up after cooldown
"""

import os
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Tuple, Optional

logger = logging.getLogger(__name__)


class DrawdownStopManager:
    """
    Manages portfolio-level drawdown stops and cooldown/resume protocol.
    
    Hard requirements for $1,000 live capital:
    - 8% drawdown: Halt new entries, 10-day cooldown
    - 10% drawdown: Flatten all positions, 20-day cooldown
    - Automated health checks before resume
    - 50% sizing for 5 days after resume
    """
    
    def __init__(self, db, email_notifier, artifacts_dir='artifacts/drawdown'):
        """
        Initialize drawdown stop manager.
        
        Args:
            db: Database instance
            email_notifier: Email notifier for critical alerts
            artifacts_dir: Directory for drawdown artifacts
        """
        self.db = db
        self.email_notifier = email_notifier
        self.artifacts_dir = artifacts_dir
        
        # Thresholds
        self.halt_threshold = float(os.getenv('DRAWDOWN_HALT_THRESHOLD', '0.08'))  # 8%
        self.panic_threshold = float(os.getenv('DRAWDOWN_PANIC_THRESHOLD', '0.10'))  # 10%
        
        # Cooldown periods (trading days)
        self.halt_cooldown_days = int(os.getenv('HALT_COOLDOWN_DAYS', '10'))
        self.panic_cooldown_days = int(os.getenv('PANIC_COOLDOWN_DAYS', '20'))
        
        # Resume protocol
        self.rampup_sizing_pct = float(os.getenv('RAMPUP_SIZING_PCT', '0.50'))  # 50%
        self.rampup_days = int(os.getenv('RAMPUP_DAYS', '5'))
        
        # Flatten on panic
        self.flatten_on_panic = os.getenv('FLATTEN_ON_PANIC', 'true').lower() == 'true'
        
        # Create artifacts directory
        os.makedirs(self.artifacts_dir, exist_ok=True)
        
        logger.info(f"DrawdownStopManager initialized: halt={self.halt_threshold:.1%}, "
                   f"panic={self.panic_threshold:.1%}")
    
    def check_drawdown_stop(self, current_portfolio_value: float, 
                           peak_portfolio_value: float) -> Tuple[bool, str, Dict]:
        """
        Check if drawdown stop should be triggered.
        
        Args:
            current_portfolio_value: Current portfolio value
            peak_portfolio_value: Peak portfolio value (all-time high)
        
        Returns:
            Tuple of (is_stopped, reason, details)
        """
        # Calculate drawdown
        if peak_portfolio_value <= 0:
            return False, "", {}
        
        drawdown = (peak_portfolio_value - current_portfolio_value) / peak_portfolio_value
        
        details = {
            'current_value': current_portfolio_value,
            'peak_value': peak_portfolio_value,
            'drawdown_pct': drawdown,
            'halt_threshold': self.halt_threshold,
            'panic_threshold': self.panic_threshold,
            'timestamp': datetime.now().isoformat()
        }
        
        # Check panic threshold (10%)
        if drawdown >= self.panic_threshold:
            reason = f"PANIC: Drawdown {drawdown:.2%} >= {self.panic_threshold:.1%}"
            logger.critical(f"🚨 {reason}")
            
            # Save panic artifact
            self._save_drawdown_artifact('panic', details)
            
            # Send critical alert
            self._send_panic_alert(drawdown, current_portfolio_value, peak_portfolio_value)
            
            # Set panic state in DB
            self._set_drawdown_state('PANIC', drawdown, self.panic_cooldown_days)
            
            return True, reason, details
        
        # Check halt threshold (8%)
        if drawdown >= self.halt_threshold:
            reason = f"HALT: Drawdown {drawdown:.2%} >= {self.halt_threshold:.1%}"
            logger.warning(f"⚠️ {reason}")
            
            # Save halt artifact
            self._save_drawdown_artifact('halt', details)
            
            # Send alert
            self._send_halt_alert(drawdown, current_portfolio_value, peak_portfolio_value)
            
            # Set halt state in DB
            self._set_drawdown_state('HALT', drawdown, self.halt_cooldown_days)
            
            return True, reason, details
        
        return False, "", details
    
    def get_current_state(self) -> Dict:
        """
        Get current drawdown stop state.
        
        Returns:
            Dict with state, cooldown_end, rampup_end, sizing_multiplier
        """
        state = self.db.get_system_state('drawdown_stop_state')
        
        if not state:
            return {
                'state': 'NORMAL',
                'cooldown_end': None,
                'rampup_end': None,
                'sizing_multiplier': 1.0,
                'trading_allowed': True
            }
        
        state_data = json.loads(state)
        
        # Check if cooldown expired
        if state_data['state'] in ['HALT', 'PANIC']:
            cooldown_end = datetime.fromisoformat(state_data['cooldown_end'])
            if datetime.now() >= cooldown_end:
                # Cooldown expired, check if can resume
                can_resume, health_checks = self._run_health_checks()
                
                if can_resume:
                    # Enter rampup mode
                    self._set_rampup_state()
                    state_data = json.loads(self.db.get_system_state('drawdown_stop_state'))
                else:
                    # Health checks failed, extend cooldown
                    logger.warning("Health checks failed, extending cooldown by 5 days")
                    self._extend_cooldown(5)
                    state_data = json.loads(self.db.get_system_state('drawdown_stop_state'))
        
        # Check if rampup expired
        if state_data['state'] == 'RAMPUP':
            rampup_end = datetime.fromisoformat(state_data['rampup_end'])
            if datetime.now() >= rampup_end:
                # Rampup complete, return to normal
                self._set_normal_state()
                state_data = json.loads(self.db.get_system_state('drawdown_stop_state'))
        
        # Determine trading allowed and sizing multiplier
        state_data['trading_allowed'] = state_data['state'] in ['NORMAL', 'RAMPUP']
        state_data['sizing_multiplier'] = (
            self.rampup_sizing_pct if state_data['state'] == 'RAMPUP' else 1.0
        )
        
        return state_data
    
    def _set_drawdown_state(self, state: str, drawdown: float, cooldown_days: int):
        """Set drawdown stop state in database."""
        cooldown_end = datetime.now() + timedelta(days=cooldown_days)
        
        state_data = {
            'state': state,
            'drawdown': drawdown,
            'cooldown_days': cooldown_days,
            'cooldown_end': cooldown_end.isoformat(),
            'triggered_at': datetime.now().isoformat(),
            'rampup_end': None
        }
        
        self.db.set_system_state('drawdown_stop_state', json.dumps(state_data))
        logger.info(f"Drawdown state set to {state}, cooldown until {cooldown_end.date()}")
    
    def _set_rampup_state(self):
        """Set rampup state after cooldown."""
        rampup_end = datetime.now() + timedelta(days=self.rampup_days)
        
        state_data = {
            'state': 'RAMPUP',
            'drawdown': 0.0,
            'cooldown_days': 0,
            'cooldown_end': None,
            'triggered_at': datetime.now().isoformat(),
            'rampup_end': rampup_end.isoformat(),
            'sizing_multiplier': self.rampup_sizing_pct
        }
        
        self.db.set_system_state('drawdown_stop_state', json.dumps(state_data))
        logger.info(f"Entered RAMPUP mode: {self.rampup_sizing_pct:.0%} sizing until {rampup_end.date()}")
    
    def _set_normal_state(self):
        """Set normal state after rampup."""
        state_data = {
            'state': 'NORMAL',
            'drawdown': 0.0,
            'cooldown_days': 0,
            'cooldown_end': None,
            'triggered_at': datetime.now().isoformat(),
            'rampup_end': None
        }
        
        self.db.set_system_state('drawdown_stop_state', json.dumps(state_data))
        logger.info("Returned to NORMAL mode: full sizing resumed")
    
    def _extend_cooldown(self, additional_days: int):
        """Extend cooldown period."""
        state = self.db.get_system_state('drawdown_stop_state')
        if state:
            state_data = json.loads(state)
            cooldown_end = datetime.fromisoformat(state_data['cooldown_end'])
            new_cooldown_end = cooldown_end + timedelta(days=additional_days)
            state_data['cooldown_end'] = new_cooldown_end.isoformat()
            state_data['cooldown_days'] += additional_days
            
            self.db.set_system_state('drawdown_stop_state', json.dumps(state_data))
            logger.warning(f"Cooldown extended by {additional_days} days until {new_cooldown_end.date()}")
    
    def _run_health_checks(self) -> Tuple[bool, Dict]:
        """
        Run automated health checks before resuming trading.
        
        Returns:
            Tuple of (passed, checks_dict)
        """
        checks = {
            'reconciliation': False,
            'data_quality': False,
            'no_duplicate_intents': False,
            'strategies_enabled': False,
            'timestamp': datetime.now().isoformat()
        }
        
        # Check 1: Reconciliation status
        reconciliation_status = self.db.get_system_state('last_reconciliation_status')
        checks['reconciliation'] = reconciliation_status == 'PASS'
        
        # Check 2: Data quality (check for recent data update)
        last_data_update = self.db.get_system_state('last_data_update')
        if last_data_update:
            last_update_time = datetime.fromisoformat(last_data_update)
            hours_since_update = (datetime.now() - last_update_time).total_seconds() / 3600
            checks['data_quality'] = hours_since_update < 72  # Less than 3 days old
        
        # Check 3: No duplicate order intents
        # Query for duplicate intents in last 24 hours
        duplicate_count = self.db.count_duplicate_order_intents(hours=24)
        checks['no_duplicate_intents'] = duplicate_count == 0
        
        # Check 4: At least one strategy enabled
        disabled_strategies = os.getenv('STRATEGY_DISABLED_LIST', '').split(',')
        disabled_strategies = [s.strip() for s in disabled_strategies if s.strip()]
        checks['strategies_enabled'] = len(disabled_strategies) < 4  # At least 1 of 4 enabled
        
        # Save health check artifact
        self._save_health_check_artifact(checks)
        
        # All checks must pass
        all_passed = all(checks.values() if k != 'timestamp' else True 
                        for k in checks.keys())
        
        if all_passed:
            logger.info("✅ All health checks passed, ready to resume trading")
        else:
            failed = [k for k, v in checks.items() if k != 'timestamp' and not v]
            logger.warning(f"❌ Health checks failed: {', '.join(failed)}")
        
        return all_passed, checks
    
    def _save_drawdown_artifact(self, event_type: str, details: Dict):
        """Save drawdown event artifact."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{event_type}_{timestamp}.json"
        filepath = os.path.join(self.artifacts_dir, filename)
        
        with open(filepath, 'w') as f:
            json.dump(details, f, indent=2)
        
        logger.info(f"Saved drawdown artifact: {filepath}")
    
    def _save_health_check_artifact(self, checks: Dict):
        """Save health check results artifact."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"health_check_{timestamp}.json"
        filepath = os.path.join(self.artifacts_dir, filename)
        
        with open(filepath, 'w') as f:
            json.dump(checks, f, indent=2)
        
        logger.info(f"Saved health check artifact: {filepath}")
    
    def _send_halt_alert(self, drawdown: float, current_value: float, peak_value: float):
        """Send halt alert email."""
        subject = f"🛑 TRADING HALT: {drawdown:.2%} Drawdown"
        
        message = f"""
TRADING HALT TRIGGERED

Drawdown: {drawdown:.2%} (threshold: {self.halt_threshold:.1%})
Current Portfolio: ${current_value:,.2f}
Peak Portfolio: ${peak_value:,.2f}
Loss: ${peak_value - current_value:,.2f}

ACTION TAKEN:
- All new entries HALTED
- Existing positions will continue to be managed
- Cooldown period: {self.halt_cooldown_days} trading days

RESUME PROTOCOL:
1. Wait {self.halt_cooldown_days} trading days
2. Run automated health checks
3. If passed: Resume at {self.rampup_sizing_pct:.0%} sizing for {self.rampup_days} days
4. Then return to normal sizing

No manual intervention required unless health checks fail.
"""
        
        self.email_notifier.send_critical_alert(subject, message)
    
    def _send_panic_alert(self, drawdown: float, current_value: float, peak_value: float):
        """Send panic alert email."""
        subject = f"🚨 PANIC MODE: {drawdown:.2%} Drawdown"
        
        flatten_msg = "YES - All positions will be flattened" if self.flatten_on_panic else "NO - Positions will be managed normally"
        
        message = f"""
PANIC MODE TRIGGERED

Drawdown: {drawdown:.2%} (threshold: {self.panic_threshold:.1%})
Current Portfolio: ${current_value:,.2f}
Peak Portfolio: ${peak_value:,.2f}
Loss: ${peak_value - current_value:,.2f}

ACTION TAKEN:
- All new entries HALTED
- Flatten all positions: {flatten_msg}
- Extended cooldown: {self.panic_cooldown_days} trading days

RESUME PROTOCOL:
1. Wait {self.panic_cooldown_days} trading days
2. Run automated health checks
3. If passed: Resume at {self.rampup_sizing_pct:.0%} sizing for {self.rampup_days} days
4. Then return to normal sizing

IMMEDIATE MANUAL REVIEW RECOMMENDED.
"""
        
        self.email_notifier.send_critical_alert(subject, message)
    
    def should_flatten_positions(self) -> bool:
        """
        Check if positions should be flattened (panic mode).
        
        Returns:
            True if in panic mode and flatten is enabled
        """
        state = self.get_current_state()
        return state['state'] == 'PANIC' and self.flatten_on_panic
    
    def get_sizing_multiplier(self) -> float:
        """
        Get current sizing multiplier based on state.
        
        Returns:
            Sizing multiplier (0.5 during rampup, 1.0 otherwise)
        """
        state = self.get_current_state()
        return state['sizing_multiplier']
    
    def is_trading_allowed(self) -> bool:
        """
        Check if new trading entries are allowed.
        
        Returns:
            True if trading allowed (NORMAL or RAMPUP state)
        """
        state = self.get_current_state()
        return state['trading_allowed']
