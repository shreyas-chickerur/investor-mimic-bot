"""
Drawdown Stop Manager - Portfolio-level circuit breaker for live trading

Implements:
- 8% drawdown: Halt new entries, trigger cooldown/resume protocol
- 10% drawdown: Panic mode - flatten all positions, extended cooldown
- Automated health checks before resume
- 50% sizing ramp-up after cooldown
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta

from src.utils.email_notifier import _bullet_list, _kv_rows, build_alert_html

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

    def __init__(
        self,
        db,
        email_notifier,
        artifacts_dir="artifacts/drawdown",
        halt_threshold: float = 0.08,
        panic_threshold: float = 0.10,
        halt_cooldown_days: int = 10,
        panic_cooldown_days: int = 20,
        rampup_sizing_pct: float = 0.50,
        rampup_days: int = 5,
        flatten_on_panic: bool = True,
    ):
        """
        Initialize drawdown stop manager.

        Args:
            db: Database instance
            email_notifier: Email notifier for critical alerts
            artifacts_dir: Directory for drawdown artifacts
            halt_threshold: Drawdown threshold to halt trading (default 8%)
            panic_threshold: Drawdown threshold for panic mode (default 10%)
            halt_cooldown_days: Cooldown days after halt (default 10)
            panic_cooldown_days: Cooldown days after panic (default 20)
            rampup_sizing_pct: Position sizing during rampup (default 50%)
            rampup_days: Days in rampup mode (default 5)
            flatten_on_panic: Whether to flatten positions in panic (default True)
        """
        self.db = db
        self.email_notifier = email_notifier
        self.artifacts_dir = artifacts_dir

        # Thresholds - use parameters, fallback to env vars for backward compatibility
        self.halt_threshold = (
            halt_threshold
            if halt_threshold is not None
            else float(os.getenv("DRAWDOWN_HALT_THRESHOLD", "0.08"))
        )
        self.panic_threshold = (
            panic_threshold
            if panic_threshold is not None
            else float(os.getenv("DRAWDOWN_PANIC_THRESHOLD", "0.10"))
        )

        # Cooldown periods (trading days)
        self.halt_cooldown_days = (
            halt_cooldown_days
            if halt_cooldown_days is not None
            else int(os.getenv("HALT_COOLDOWN_DAYS", "10"))
        )
        self.panic_cooldown_days = (
            panic_cooldown_days
            if panic_cooldown_days is not None
            else int(os.getenv("PANIC_COOLDOWN_DAYS", "20"))
        )

        # Resume protocol
        self.rampup_sizing_pct = (
            rampup_sizing_pct
            if rampup_sizing_pct is not None
            else float(os.getenv("RAMPUP_SIZING_PCT", "0.50"))
        )
        self.rampup_days = (
            rampup_days if rampup_days is not None else int(os.getenv("RAMPUP_DAYS", "5"))
        )

        # Flatten on panic
        self.flatten_on_panic = (
            flatten_on_panic
            if flatten_on_panic is not None
            else (os.getenv("FLATTEN_ON_PANIC", "true").lower() == "true")
        )

        # Create artifacts directory
        os.makedirs(self.artifacts_dir, exist_ok=True)

        logger.info(
            f"DrawdownStopManager initialized: halt={self.halt_threshold:.1%}, "
            f"panic={self.panic_threshold:.1%}"
        )

    def check_drawdown_stop(
        self, current_portfolio_value: float, peak_portfolio_value: float
    ) -> tuple[bool, str, dict]:
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
            "current_value": current_portfolio_value,
            "peak_value": peak_portfolio_value,
            "drawdown_pct": drawdown,
            "halt_threshold": self.halt_threshold,
            "panic_threshold": self.panic_threshold,
            "timestamp": datetime.now().isoformat(),
        }

        # Check panic threshold (10%)
        if drawdown >= self.panic_threshold:
            reason = f"PANIC: Drawdown {drawdown:.2%} >= {self.panic_threshold:.1%}"
            logger.critical(f"🚨 {reason}")

            # Save panic artifact
            self._save_drawdown_artifact("panic", details)

            # Send critical alert
            self._send_panic_alert(drawdown, current_portfolio_value, peak_portfolio_value)

            # Set panic state in DB
            self._set_drawdown_state("PANIC", drawdown, self.panic_cooldown_days)

            return True, reason, details

        # Check halt threshold (8%)
        if drawdown >= self.halt_threshold:
            reason = f"HALT: Drawdown {drawdown:.2%} >= {self.halt_threshold:.1%}"
            logger.warning(f"⚠️ {reason}")

            # Save halt artifact
            self._save_drawdown_artifact("halt", details)

            # Send alert
            self._send_halt_alert(drawdown, current_portfolio_value, peak_portfolio_value)

            # Set halt state in DB
            self._set_drawdown_state("HALT", drawdown, self.halt_cooldown_days)

            return True, reason, details

        return False, "", details

    def get_current_state(self) -> dict[str, object]:
        """
        Get current drawdown stop state.

        Returns:
            Dict with state, cooldown_end, rampup_end, sizing_multiplier
        """
        state = self.db.get_system_state("drawdown_stop_state")

        if not state:
            return {
                "state": "NORMAL",
                "cooldown_end": None,
                "rampup_end": None,
                "sizing_multiplier": 1.0,
                "trading_allowed": True,
            }

        state_data: dict[str, object] = json.loads(state)

        # Check if cooldown expired
        if state_data["state"] in ["HALT", "PANIC"] and state_data.get("cooldown_end"):
            cooldown_end = datetime.fromisoformat(str(state_data["cooldown_end"]))
            if datetime.now() >= cooldown_end:
                # Cooldown expired, check if can resume
                can_resume, health_checks = self._run_health_checks()

                if can_resume:
                    # Enter rampup mode
                    self._set_rampup_state()
                    state_data = json.loads(self.db.get_system_state("drawdown_stop_state"))
                else:
                    # Health checks failed, extend cooldown
                    logger.warning("Health checks failed, extending cooldown by 5 days")
                    self._extend_cooldown(5)
                    state_data = json.loads(self.db.get_system_state("drawdown_stop_state"))

        # Check if rampup expired
        if state_data["state"] == "RAMPUP" and state_data.get("rampup_end"):
            rampup_end = datetime.fromisoformat(str(state_data["rampup_end"]))
            if datetime.now() >= rampup_end:
                # Rampup complete, return to normal
                self._set_normal_state()
                state_data = json.loads(self.db.get_system_state("drawdown_stop_state"))

        # Determine trading allowed and sizing multiplier
        state_data["trading_allowed"] = state_data["state"] in ["NORMAL", "RAMPUP"]
        state_data["sizing_multiplier"] = (
            self.rampup_sizing_pct if state_data["state"] == "RAMPUP" else 1.0
        )

        return state_data

    def _set_drawdown_state(self, state: str, drawdown: float, cooldown_days: int):
        """Set drawdown stop state in database. Only initializes cooldown on first trigger;
        subsequent calls while already in the same state preserve the existing cooldown_end
        so the timer cannot be indefinitely deferred by repeated daily drawdown checks."""
        existing = self.db.get_system_state("drawdown_stop_state")
        if existing:
            try:
                existing_data = json.loads(existing)
                if existing_data.get("state") == state:
                    logger.debug(
                        f"Drawdown state already {state} — preserving existing cooldown end "
                        f"{existing_data.get('cooldown_end')}"
                    )
                    return
            except (json.JSONDecodeError, KeyError):
                # Corrupted state data — overwrite with fresh state below
                logger.warning("Drawdown state data corrupted; resetting to %s", state)

        cooldown_end = datetime.now() + timedelta(days=cooldown_days)

        state_data = {
            "state": state,
            "drawdown": drawdown,
            "cooldown_days": cooldown_days,
            "cooldown_end": cooldown_end.isoformat(),
            "triggered_at": datetime.now().isoformat(),
            "rampup_end": None,
        }

        self.db.set_system_state("drawdown_stop_state", json.dumps(state_data))
        logger.info(
            "Drawdown state: NORMAL → %s (drawdown=%.2f%%, cooldown until %s)",
            state,
            drawdown * 100,
            cooldown_end.date(),
        )

        # Structured log event for observability dashboards
        try:
            from src.utils.structured_logger import StructuredLogger

            # Use a transient logger (no persistent run_id needed for state events)
            _sl = StructuredLogger(run_id="DRAWDOWN_STATE_MGR")
            threshold = self.halt_threshold if state == "HALT" else self.panic_threshold
            _sl.log_drawdown_state_change(
                old_state="NORMAL",
                new_state=state,
                drawdown_pct=drawdown,
                threshold_pct=threshold,
                cooldown_end=cooldown_end.isoformat(),
            )
        except Exception:  # nosec B110
            pass  # structured logging is best-effort; never block a state transition

    def _set_rampup_state(self):
        """Set rampup state after cooldown."""
        rampup_end = datetime.now() + timedelta(days=self.rampup_days)

        state_data = {
            "state": "RAMPUP",
            "drawdown": 0.0,
            "cooldown_days": 0,
            "cooldown_end": None,
            "triggered_at": datetime.now().isoformat(),
            "rampup_end": rampup_end.isoformat(),
            "sizing_multiplier": self.rampup_sizing_pct,
        }

        self.db.set_system_state("drawdown_stop_state", json.dumps(state_data))
        logger.info(
            f"Entered RAMPUP mode: {self.rampup_sizing_pct:.0%} sizing until {rampup_end.date()}"
        )

    def _set_normal_state(self):
        """Set normal state after rampup."""
        state_data = {
            "state": "NORMAL",
            "drawdown": 0.0,
            "cooldown_days": 0,
            "cooldown_end": None,
            "triggered_at": datetime.now().isoformat(),
            "rampup_end": None,
        }

        self.db.set_system_state("drawdown_stop_state", json.dumps(state_data))
        logger.info("Returned to NORMAL mode: full sizing resumed")

    def _extend_cooldown(self, additional_days: int):
        """Extend cooldown period."""
        state = self.db.get_system_state("drawdown_stop_state")
        if state:
            state_data = json.loads(state)
            cooldown_end = datetime.fromisoformat(state_data["cooldown_end"])
            new_cooldown_end = cooldown_end + timedelta(days=additional_days)
            state_data["cooldown_end"] = new_cooldown_end.isoformat()
            state_data["cooldown_days"] += additional_days

            self.db.set_system_state("drawdown_stop_state", json.dumps(state_data))
            logger.warning(
                f"Cooldown extended by {additional_days} days until {new_cooldown_end.date()}"
            )

    def _run_health_checks(self) -> tuple[bool, dict]:
        """
        Run automated health checks before resuming trading.

        Returns:
            Tuple of (passed, checks_dict)
        """
        checks = {
            "reconciliation": False,
            "data_quality": False,
            "no_duplicate_intents": False,
            "strategies_enabled": False,
            "timestamp": datetime.now().isoformat(),
        }

        # Check 1: Reconciliation status
        reconciliation_status = self.db.get_system_state("last_reconciliation_status")
        checks["reconciliation"] = reconciliation_status == "PASS"

        # Check 2: Data quality (check for recent data update)
        last_data_update = self.db.get_system_state("last_data_update")
        if last_data_update:
            last_update_time = datetime.fromisoformat(last_data_update)
            hours_since_update = (datetime.now() - last_update_time).total_seconds() / 3600
            checks["data_quality"] = hours_since_update < 72  # Less than 3 days old

        # Check 3: No duplicate order intents
        # Query for duplicate intents in last 24 hours
        duplicate_count = self.db.count_duplicate_order_intents(hours=24)
        checks["no_duplicate_intents"] = duplicate_count == 0

        # Check 4: At least one strategy enabled
        disabled_strategies = os.getenv("STRATEGY_DISABLED_LIST", "").split(",")
        disabled_strategies = [s.strip() for s in disabled_strategies if s.strip()]
        checks["strategies_enabled"] = len(disabled_strategies) < 7  # At least 1 of 7 enabled

        # Save health check artifact
        self._save_health_check_artifact(checks)

        # All checks must pass (skip 'timestamp' key)
        all_passed = all(v for k, v in checks.items() if k != "timestamp")

        if all_passed:
            logger.info("✅ All health checks passed, ready to resume trading")
        else:
            failed = [k for k, v in checks.items() if k != "timestamp" and not v]
            logger.warning(f"❌ Health checks failed: {', '.join(failed)}")

        return all_passed, checks

    def _save_drawdown_artifact(self, event_type: str, details: dict):
        """Save drawdown event artifact."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{event_type}_{timestamp}.json"
        filepath = os.path.join(self.artifacts_dir, filename)

        with open(filepath, "w") as f:
            json.dump(details, f, indent=2)

        logger.info(f"Saved drawdown artifact: {filepath}")

    def _save_health_check_artifact(self, checks: dict):
        """Save health check results artifact."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"health_check_{timestamp}.json"
        filepath = os.path.join(self.artifacts_dir, filename)

        with open(filepath, "w") as f:
            json.dump(checks, f, indent=2)

        logger.info(f"Saved health check artifact: {filepath}")

    def _send_halt_alert(self, drawdown: float, current_value: float, peak_value: float):
        """Send halt alert email."""
        subject = f"🛑 Trading Halt: {drawdown:.2%} Drawdown"
        body_html = (
            _kv_rows(
                [
                    ("Drawdown", f"{drawdown:.2%}"),
                    ("Threshold", f"{self.halt_threshold:.1%}"),
                    ("Current portfolio", f"${current_value:,.2f}"),
                    ("Peak portfolio", f"${peak_value:,.2f}"),
                    ("Loss from peak", f"${peak_value - current_value:,.2f}"),
                    ("Cooldown", f"{self.halt_cooldown_days} trading days"),
                ]
            )
            + "<h4 style='margin:16px 0 6px;color:#555'>Action taken</h4>"
            + _bullet_list(
                [
                    "All new entries halted",
                    "Existing positions continue to be managed",
                    f"Cooldown: {self.halt_cooldown_days} trading days",
                ]
            )
            + "<h4 style='margin:16px 0 6px;color:#555'>Resume protocol</h4>"
            + _bullet_list(
                [
                    f"Wait {self.halt_cooldown_days} trading days",
                    "Automated health checks will run",
                    f"If passed: resume at {self.rampup_sizing_pct:.0%} sizing "
                    f"for {self.rampup_days} days",
                    "Then return to normal sizing",
                ]
            )
            + "<p style='color:#555;font-size:13px;margin:12px 0 0'>"
            "No manual intervention required unless health checks fail.</p>"
        )
        html = build_alert_html(
            f"🛑 Trading Halt — {drawdown:.2%} Drawdown", body_html, accent_color="#e65100"
        )
        self.email_notifier.send_alert(subject, html)

    def _send_panic_alert(self, drawdown: float, current_value: float, peak_value: float):
        """Send panic alert email."""
        subject = f"🚨 Panic Mode: {drawdown:.2%} Drawdown"
        flatten_msg = (
            "YES — all positions will be flattened"
            if self.flatten_on_panic
            else "NO — positions will be managed normally"
        )
        body_html = (
            _kv_rows(
                [
                    ("Drawdown", f"{drawdown:.2%}"),
                    ("Threshold", f"{self.panic_threshold:.1%}"),
                    ("Current portfolio", f"${current_value:,.2f}"),
                    ("Peak portfolio", f"${peak_value:,.2f}"),
                    ("Loss from peak", f"${peak_value - current_value:,.2f}"),
                    ("Flatten positions", flatten_msg),
                    ("Cooldown", f"{self.panic_cooldown_days} trading days"),
                ]
            )
            + "<h4 style='margin:16px 0 6px;color:#555'>Action taken</h4>"
            + _bullet_list(
                [
                    "All new entries halted",
                    f"Flatten all positions: {flatten_msg}",
                    f"Extended cooldown: {self.panic_cooldown_days} trading days",
                ]
            )
            + "<h4 style='margin:16px 0 6px;color:#555'>Resume protocol</h4>"
            + _bullet_list(
                [
                    f"Wait {self.panic_cooldown_days} trading days",
                    "Automated health checks will run",
                    f"If passed: resume at {self.rampup_sizing_pct:.0%} sizing "
                    f"for {self.rampup_days} days",
                    "Then return to normal sizing",
                ]
            )
            + "<p style='color:#c62828;font-weight:600;margin:12px 0 0'>"
            "⚠️ Immediate manual review recommended.</p>"
        )
        html = build_alert_html(
            f"🚨 Panic Mode — {drawdown:.2%} Drawdown", body_html, accent_color="#b71c1c"
        )
        self.email_notifier.send_alert(subject, html)

    def should_flatten_positions(self) -> bool:
        """
        Check if positions should be flattened (panic mode).

        Returns:
            True if in panic mode and flatten is enabled
        """
        state = self.get_current_state()
        return state["state"] == "PANIC" and self.flatten_on_panic

    def get_sizing_multiplier(self) -> float:
        """
        Get current sizing multiplier based on state.

        Returns:
            Sizing multiplier (0.5 during rampup, 1.0 otherwise)
        """
        state = self.get_current_state()
        return float(state["sizing_multiplier"])  # type: ignore[arg-type]

    def is_trading_allowed(self) -> bool:
        """
        Check if new trading entries are allowed.

        Returns:
            True if trading allowed (NORMAL or RAMPUP state)
        """
        state = self.get_current_state()
        return bool(state["trading_allowed"])
