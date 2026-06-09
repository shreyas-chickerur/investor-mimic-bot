#!/usr/bin/env python3
"""
Kill Switch Service
Manual and automatic circuit breakers for trading system
"""
from __future__ import annotations

import logging
import os
from datetime import datetime

from src.utils.email_notifier import _bullet_list, _kv_rows, build_alert_html

logger = logging.getLogger(__name__)


class KillSwitchService:
    """Manages kill switches and circuit breakers"""

    def __init__(self, db, email_notifier):
        self.db = db
        self.email_notifier = email_notifier
        self.kill_reasons = []
        self.is_killed = False

    def check_all_switches(self, context: dict) -> bool:
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

        if os.getenv("TRADING_DISABLED", "false").lower() == "true":
            self.kill_reasons.append("MANUAL_KILL: TRADING_DISABLED=true")
            self.is_killed = True
            logger.critical("🛑 KILL SWITCH: Trading globally disabled via TRADING_DISABLED env var")
            self._send_kill_alert(
                "Manual Kill Switch",
                "Trading was disabled via the <code>TRADING_DISABLED=true</code> "
                "environment variable.",
                accent_color="#6c757d",
            )
            return True

        disabled_strategies = os.getenv("STRATEGY_DISABLED_LIST", "")
        if disabled_strategies:
            strategies = [s.strip() for s in disabled_strategies.split(",")]
            self.kill_reasons.append(f"MANUAL_KILL: Strategies disabled: {', '.join(strategies)}")
            logger.warning(f"⚠️ Strategies disabled: {', '.join(strategies)}")

        return False

    def _check_automatic_kill_conditions(self, context: dict) -> bool:
        """Check automatic kill conditions"""

        if context.get("reconciliation_status") == "FAIL":
            self.kill_reasons.append("AUTO_KILL: Broker reconciliation failed")
            self.is_killed = True
            logger.critical("🛑 KILL SWITCH: Reconciliation failure - trading halted")
            self._send_kill_alert(
                "Reconciliation Failure",
                "<p style='color:#333;margin:0 0 12px'>The local database does not match "
                "the Alpaca broker state. All trading has been halted.</p>"
                "<p style='color:#333;margin:0'>Run "
                "<code style='background:#f0f0e8;padding:2px 6px;border-radius:3px'>"
                "python3 scripts/sync_broker_state.py</code> to resolve the drift, "
                "then re-run the daily workflow.</p>",
                accent_color="#dc3545",
            )
            return True

        daily_dd = context.get("daily_drawdown", 0)
        if daily_dd > 0.05:
            self.kill_reasons.append(f"AUTO_KILL: Excessive daily drawdown {daily_dd*100:.1f}%")
            self.is_killed = True
            logger.critical(f"🛑 KILL SWITCH: Daily drawdown {daily_dd*100:.1f}% exceeds 5%")
            self._send_kill_alert(
                "🛑 Excessive Drawdown — Trading Halted",
                _kv_rows(
                    [
                        ("Current drawdown", f"{daily_dd*100:.2f}%"),
                        ("Threshold", "5.00%"),
                        ("Status", "All trading halted"),
                    ]
                )
                + "<p style='color:#555;font-size:13px;margin:12px 0 0'>Investigate "
                "the drawdown source, then resume trading by clearing the condition.</p>",
                accent_color="#dc3545",
            )
            return True

        consecutive_failures = context.get("consecutive_failures", 0)
        if consecutive_failures >= 3:
            self.kill_reasons.append(f"AUTO_KILL: {consecutive_failures} consecutive run failures")
            self.is_killed = True
            logger.critical(f"🛑 KILL SWITCH: {consecutive_failures} consecutive failures")
            self._send_kill_alert(
                "🛑 Consecutive Run Failures — Trading Halted",
                _kv_rows(
                    [
                        ("Consecutive failures", str(consecutive_failures)),
                        ("Threshold", "3"),
                        ("Status", "All trading halted"),
                    ]
                )
                + "<p style='color:#555;font-size:13px;margin:12px 0 0'>"
                "Check GitHub Actions logs for the root cause of recent failures.</p>",
                accent_color="#dc3545",
            )
            return True

        rejected_count = context.get("rejected_orders_count", 0)
        total_orders = context.get("total_orders", 1)
        rejection_rate = rejected_count / total_orders if total_orders > 0 else 0

        if rejected_count >= 5 and rejection_rate > 0.5:
            self.kill_reasons.append(
                f"AUTO_KILL: High order rejection rate {rejection_rate*100:.0f}%"
            )
            self.is_killed = True
            logger.critical(
                f"🛑 KILL SWITCH: {rejected_count} orders rejected ({rejection_rate*100:.0f}%)"
            )
            self._send_kill_alert(
                "🛑 High Order Rejection Rate — Trading Halted",
                _kv_rows(
                    [
                        ("Orders rejected", f"{rejected_count} / {total_orders}"),
                        ("Rejection rate", f"{rejection_rate*100:.0f}%"),
                        ("Threshold", "> 50% with ≥ 5 rejections"),
                    ]
                )
                + "<p style='color:#555;font-size:13px;margin:12px 0 0'>"
                "Check Alpaca for account or market-hours issues.</p>",
                accent_color="#dc3545",
            )
            return True

        return False

    def _send_kill_alert(self, reason: str, body_html: str, accent_color: str = "#dc3545"):
        """Send a consistently styled kill-switch alert email."""
        subject = f"🛑 Kill Switch Activated: {reason}"

        reasons_html = _bullet_list(self.kill_reasons) if self.kill_reasons else ""
        full_body = (
            body_html
            + (
                f"<h4 style='margin:16px 0 6px;color:#555'>Kill reasons logged</h4>"
                f"{reasons_html}"
                if reasons_html
                else ""
            )
            + f"<hr style='border:none;border-top:1px solid #eee;margin:16px 0'>"
            f"<p style='color:#555;font-size:13px;margin:0'>"
            f"<strong>Time:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}<br>"
            f"<strong>Action:</strong> All trading halted — manual review required.</p>"
        )
        html = build_alert_html(f"🛑 Kill Switch: {reason}", full_body, accent_color=accent_color)

        try:
            self.email_notifier.send_alert(subject, html)
        except Exception as e:
            # CRITICAL: operator must know trading is halted even if email fails
            logger.critical(
                "CRITICAL: kill switch fired but alert email FAILED to send — "
                "manual check required. Reason: %s. Email error: %s",
                reason,
                e,
            )

    def get_status(self) -> dict:
        """Get kill switch status"""
        return {
            "is_killed": self.is_killed,
            "kill_reasons": self.kill_reasons,
            "manual_disabled": os.getenv("TRADING_DISABLED", "false").lower() == "true",
            "disabled_strategies": os.getenv("STRATEGY_DISABLED_LIST", "").split(","),
        }

    def is_strategy_enabled(self, strategy_name: str) -> bool:
        """Check if a specific strategy is enabled"""
        disabled_list = os.getenv("STRATEGY_DISABLED_LIST", "")
        if not disabled_list:
            return True

        disabled_strategies = [s.strip().lower() for s in disabled_list.split(",")]
        return strategy_name.lower() not in disabled_strategies
