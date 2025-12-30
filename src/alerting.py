#!/usr/bin/env python3
"""
Critical Alerting System
Phase 1.3: Sends alerts for critical system issues

Alerts for:
- Drawdown > 15%
- No trades in 7 days
- Broker reconciliation failures
- Database integrity issues

Notification channels:
- Email (always)
- SMS via Twilio (optional, graceful degradation)
"""
import os
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class AlertLevel:
    """Alert severity levels"""
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class CriticalAlertSystem:
    """
    Manages critical system alerts
    
    Features:
    - Multiple notification channels (email, SMS)
    - Graceful degradation if services unavailable
    - Alert history tracking
    - Configurable thresholds
    """
    
    def __init__(self, db_path: str = "trading.db"):
        self.db_path = db_path
        
        # Initialize email notifier
        from email_notifier import EmailNotifier
        self.email_notifier = EmailNotifier()
        
        # Initialize Twilio (optional)
        self.twilio_client = None
        self.twilio_enabled = False
        self._init_twilio()
        
        # Alert thresholds
        self.drawdown_threshold = float(os.getenv('ALERT_DRAWDOWN_THRESHOLD', '0.15'))  # 15%
        self.no_trade_days = int(os.getenv('ALERT_NO_TRADE_DAYS', '7'))  # 7 days
        
        logger.info(f"Alert System initialized: Email={'enabled' if self.email_notifier else 'disabled'}, "
                   f"SMS={'enabled' if self.twilio_enabled else 'disabled'}")
    
    def _init_twilio(self):
        """Initialize Twilio for SMS alerts (optional)"""
        try:
            account_sid = os.getenv('TWILIO_ACCOUNT_SID')
            auth_token = os.getenv('TWILIO_AUTH_TOKEN')
            
            if account_sid and auth_token:
                from twilio.rest import Client
                self.twilio_client = Client(account_sid, auth_token)
                self.twilio_from = os.getenv('TWILIO_PHONE_FROM')
                self.twilio_to = os.getenv('TWILIO_PHONE_TO')
                
                if self.twilio_from and self.twilio_to:
                    self.twilio_enabled = True
                    logger.info("Twilio SMS alerts enabled")
                else:
                    logger.warning("Twilio credentials found but phone numbers not configured")
            else:
                logger.info("Twilio not configured - SMS alerts disabled (email only)")
        except ImportError:
            logger.warning("Twilio library not installed - SMS alerts disabled")
        except Exception as e:
            logger.error(f"Failed to initialize Twilio: {e}")
    
    def send_alert(self, level: str, title: str, message: str, details: Optional[Dict] = None):
        """
        Send alert via all available channels
        
        Args:
            level: Alert level (INFO, WARNING, CRITICAL)
            title: Alert title
            message: Alert message
            details: Optional additional details
        """
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Format alert message
        alert_text = f"""
{'='*60}
{level} ALERT: {title}
{'='*60}
Time: {timestamp}

{message}
"""
        
        if details:
            alert_text += "\n\nDetails:\n"
            for key, value in details.items():
                alert_text += f"  {key}: {value}\n"
        
        alert_text += f"\n{'='*60}\n"
        
        # Log alert
        if level == AlertLevel.CRITICAL:
            logger.critical(alert_text)
        elif level == AlertLevel.WARNING:
            logger.warning(alert_text)
        else:
            logger.info(alert_text)
        
        # Send via email
        success_email = self._send_email_alert(level, title, alert_text)
        
        # Send via SMS (if enabled and critical)
        success_sms = False
        if self.twilio_enabled and level == AlertLevel.CRITICAL:
            success_sms = self._send_sms_alert(title, message)
        
        return success_email or success_sms
    
    def _send_email_alert(self, level: str, title: str, message: str) -> bool:
        """Send alert via email"""
        try:
            subject = f"[{level}] Trading System Alert: {title}"
            self.email_notifier.send_email(subject, message)
            logger.info(f"Email alert sent: {title}")
            return True
        except Exception as e:
            logger.error(f"Failed to send email alert: {e}")
            return False
    
    def _send_sms_alert(self, title: str, message: str) -> bool:
        """Send alert via SMS (Twilio)"""
        try:
            # SMS messages are limited to 160 characters, so truncate
            sms_text = f"[CRITICAL] {title}: {message}"[:160]
            
            self.twilio_client.messages.create(
                body=sms_text,
                from_=self.twilio_from,
                to=self.twilio_to
            )
            logger.info(f"SMS alert sent: {title}")
            return True
        except Exception as e:
            logger.error(f"Failed to send SMS alert: {e}")
            return False
    
    def check_drawdown_alert(self, current_portfolio_value: float, peak_portfolio_value: float) -> bool:
        """
        Check if drawdown exceeds threshold and send alert
        
        Args:
            current_portfolio_value: Current portfolio value
            peak_portfolio_value: Peak portfolio value
            
        Returns:
            True if alert was sent
        """
        if peak_portfolio_value <= 0:
            return False
        
        drawdown = (peak_portfolio_value - current_portfolio_value) / peak_portfolio_value
        
        if drawdown >= self.drawdown_threshold:
            self.send_alert(
                AlertLevel.CRITICAL,
                "High Drawdown Detected",
                f"Portfolio drawdown has exceeded {self.drawdown_threshold*100:.1f}% threshold",
                {
                    'Current Drawdown': f"{drawdown*100:.2f}%",
                    'Threshold': f"{self.drawdown_threshold*100:.1f}%",
                    'Current Value': f"${current_portfolio_value:,.2f}",
                    'Peak Value': f"${peak_portfolio_value:,.2f}",
                    'Loss Amount': f"${peak_portfolio_value - current_portfolio_value:,.2f}"
                }
            )
            return True
        
        return False
    
    def check_no_trade_alert(self, db) -> bool:
        """
        Check if no trades in specified days and send alert
        
        Args:
            db: Database instance
            
        Returns:
            True if alert was sent
        """
        try:
            # Get last trade date
            conn = db.get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT MAX(executed_at) as last_trade
                FROM trades
            """)
            
            result = cursor.fetchone()
            
            if result and result[0]:
                last_trade_date = datetime.fromisoformat(result[0])
                days_since_trade = (datetime.now() - last_trade_date).days
                
                if days_since_trade >= self.no_trade_days:
                    self.send_alert(
                        AlertLevel.WARNING,
                        "No Trades Executed",
                        f"No trades have been executed in the last {days_since_trade} days",
                        {
                            'Days Since Last Trade': days_since_trade,
                            'Threshold': f"{self.no_trade_days} days",
                            'Last Trade Date': last_trade_date.strftime('%Y-%m-%d %H:%M:%S'),
                            'Possible Causes': 'No signals generated, all signals filtered, or system error'
                        }
                    )
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking no-trade alert: {e}")
            return False
    
    def check_reconciliation_alert(self, reconciliation_status: str, discrepancies: List[str]) -> bool:
        """
        Check broker reconciliation status and send alert if failed
        
        Args:
            reconciliation_status: Status from reconciliation (PASS/FAIL)
            discrepancies: List of discrepancy messages
            
        Returns:
            True if alert was sent
        """
        if reconciliation_status == "FAIL":
            discrepancy_text = "\n  - ".join(discrepancies) if discrepancies else "Unknown discrepancies"
            
            self.send_alert(
                AlertLevel.CRITICAL,
                "Broker Reconciliation Failed",
                "Local database state does not match broker state - TRADING HALTED",
                {
                    'Status': reconciliation_status,
                    'Discrepancies': f"\n  - {discrepancy_text}",
                    'Action Required': 'Review discrepancies and run manual reconciliation',
                    'Trading Status': 'PAUSED until reconciliation passes'
                }
            )
            return True
        
        return False
    
    def check_database_integrity(self, db) -> bool:
        """
        Check database integrity and send alert if issues found
        
        Args:
            db: Database instance
            
        Returns:
            True if alert was sent
        """
        try:
            issues = []
            
            conn = db.get_connection()
            cursor = conn.cursor()
            
            # Check 1: Orphaned trades (trades without signals)
            cursor.execute("""
                SELECT COUNT(*) 
                FROM trades t
                LEFT JOIN signals s ON t.signal_id = s.id
                WHERE t.signal_id IS NOT NULL AND s.id IS NULL
            """)
            orphaned_trades = cursor.fetchone()[0]
            if orphaned_trades > 0:
                issues.append(f"{orphaned_trades} orphaned trades (no matching signal)")
            
            # Check 2: Signals without terminal states
            cursor.execute("""
                SELECT COUNT(*)
                FROM signals
                WHERE terminal_state IS NULL
                AND generated_at < datetime('now', '-1 day')
            """)
            non_terminal_signals = cursor.fetchone()[0]
            if non_terminal_signals > 0:
                issues.append(f"{non_terminal_signals} signals without terminal state (>1 day old)")
            
            # Check 3: Negative position shares
            cursor.execute("""
                SELECT COUNT(*)
                FROM positions
                WHERE shares < 0
            """)
            negative_positions = cursor.fetchone()[0]
            if negative_positions > 0:
                issues.append(f"{negative_positions} positions with negative shares")
            
            if issues:
                self.send_alert(
                    AlertLevel.WARNING,
                    "Database Integrity Issues",
                    f"Found {len(issues)} database integrity issue(s)",
                    {
                        'Issues Found': "\n  - " + "\n  - ".join(issues),
                        'Recommendation': 'Review database and run integrity checks'
                    }
                )
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking database integrity: {e}")
            # Send alert about the check failure itself
            self.send_alert(
                AlertLevel.WARNING,
                "Database Integrity Check Failed",
                f"Failed to run database integrity checks: {str(e)}",
                {'Error': str(e)}
            )
            return True
    
    def run_all_checks(self, db, current_portfolio_value: float, peak_portfolio_value: float,
                       reconciliation_status: str = "SKIPPED", discrepancies: List[str] = None) -> Dict[str, bool]:
        """
        Run all alert checks
        
        Args:
            db: Database instance
            current_portfolio_value: Current portfolio value
            peak_portfolio_value: Peak portfolio value
            reconciliation_status: Reconciliation status
            discrepancies: List of reconciliation discrepancies
            
        Returns:
            Dict of check results
        """
        results = {
            'drawdown_alert': False,
            'no_trade_alert': False,
            'reconciliation_alert': False,
            'database_integrity_alert': False
        }
        
        logger.info("Running all critical alert checks...")
        
        # Check drawdown
        results['drawdown_alert'] = self.check_drawdown_alert(
            current_portfolio_value, peak_portfolio_value
        )
        
        # Check no trades
        results['no_trade_alert'] = self.check_no_trade_alert(db)
        
        # Check reconciliation
        if reconciliation_status != "SKIPPED":
            results['reconciliation_alert'] = self.check_reconciliation_alert(
                reconciliation_status, discrepancies or []
            )
        
        # Check database integrity
        results['database_integrity_alert'] = self.check_database_integrity(db)
        
        alerts_sent = sum(results.values())
        if alerts_sent > 0:
            logger.warning(f"Alert checks complete: {alerts_sent} alert(s) sent")
        else:
            logger.info("Alert checks complete: No alerts triggered")
        
        return results


def create_alert_system(db_path: str = "trading.db") -> CriticalAlertSystem:
    """Convenience function to create alert system"""
    return CriticalAlertSystem(db_path)
