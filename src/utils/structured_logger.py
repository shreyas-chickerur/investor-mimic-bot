#!/usr/bin/env python3
"""
Structured JSON Event Logger
Logs events as JSON for observability and analysis
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class StructuredLogger:
    """Logs structured JSON events"""

    EVENT_TYPES = [
        "SIGNAL_GENERATED",
        "SIGNAL_REJECTED",
        "SIGNAL_CONFLICT",
        "ORDER_INTENT_CREATED",
        "ORDER_SUBMITTED",
        "ORDER_FILLED",
        "ORDER_REJECTED",
        "RECONCILIATION_CHECK",
        "KILL_SWITCH_TRIGGERED",
        "STRATEGY_DISABLED",
        "RISK_LIMIT_HIT",
        "REGIME_CHANGE",
        "DRAWDOWN_STATE_CHANGE",
        "STOP_LOSS_NEAR_MISS",
        "COOLDOWN_STATUS",
        "ERROR",
    ]

    def __init__(self, run_id: str, log_dir: str = "logs/events"):
        self.run_id = run_id
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        self.log_file = self.log_dir / f"events_{run_id}.jsonl"

        logger.info(f"Structured logger initialized: {self.log_file}")

    def log_event(
        self,
        event_type: str,
        data: dict[str, Any],
        strategy_id: int | None = None,
        symbol: str | None = None,
        stage: str | None = None,
    ):
        """
        Log a structured event

        Args:
            event_type: One of EVENT_TYPES
            data: Event-specific data
            strategy_id: Optional strategy ID
            symbol: Optional symbol
            stage: Optional pipeline stage
        """
        if event_type not in self.EVENT_TYPES:
            logger.warning(f"Unknown event type: {event_type}")

        event = {
            "timestamp": datetime.now().isoformat(),
            "run_id": self.run_id,
            "event_type": event_type,
            "strategy_id": strategy_id,
            "symbol": symbol,
            "stage": stage,
            "data": data,
        }

        try:
            with open(self.log_file, "a") as f:
                f.write(json.dumps(event) + "\n")
        except Exception as _log_exc:
            import logging as _logging

            _logging.getLogger(__name__).warning("structured_logger write failed: %s", _log_exc)

    def log_signal_generated(
        self, strategy_id: int, symbol: str, action: str, confidence: float, reasoning: str
    ):
        """Log signal generation event"""
        self.log_event(
            "SIGNAL_GENERATED",
            {"action": action, "confidence": confidence, "reasoning": reasoning},
            strategy_id=strategy_id,
            symbol=symbol,
            stage="GENERATION",
        )

    def log_signal_rejected(
        self,
        strategy_id: int,
        symbol: str,
        stage: str,
        reason_code: str,
        details: dict | None = None,
    ):
        """Log signal rejection event"""
        self.log_event(
            "SIGNAL_REJECTED",
            {"reason_code": reason_code, "details": details or {}},
            strategy_id=strategy_id,
            symbol=symbol,
            stage=stage,
        )

    def log_order_intent(
        self, intent_id: str, strategy_id: int, symbol: str, side: str, qty: float
    ):
        """Log order intent creation"""
        self.log_event(
            "ORDER_INTENT_CREATED",
            {"intent_id": intent_id, "side": side, "qty": qty},
            strategy_id=strategy_id,
            symbol=symbol,
            stage="ORDER_INTENT",
        )

    def log_order_submitted(
        self, intent_id: str, broker_order_id: str, strategy_id: int, symbol: str
    ):
        """Log order submission"""
        self.log_event(
            "ORDER_SUBMITTED",
            {"intent_id": intent_id, "broker_order_id": broker_order_id},
            strategy_id=strategy_id,
            symbol=symbol,
            stage="EXECUTION",
        )

    def log_order_filled(
        self, broker_order_id: str, strategy_id: int, symbol: str, qty: float, price: float
    ):
        """Log order fill"""
        self.log_event(
            "ORDER_FILLED",
            {"broker_order_id": broker_order_id, "qty": qty, "price": price},
            strategy_id=strategy_id,
            symbol=symbol,
            stage="EXECUTION",
        )

    def log_kill_switch(self, reason: str, details: dict | None = None):
        """Log kill switch activation"""
        self.log_event(
            "KILL_SWITCH_TRIGGERED",
            {"reason": reason, "details": details or {}},
            stage="KILL_SWITCH",
        )

    def log_regime_change(
        self,
        old_regime: str,
        new_regime: str,
        vix: float,
        affected_strategies: list[str],
        details: dict | None = None,
    ):
        """Log when the detected market regime changes."""
        self.log_event(
            "REGIME_CHANGE",
            {
                "old_regime": old_regime,
                "new_regime": new_regime,
                "vix": vix,
                "affected_strategies": affected_strategies,
                **(details or {}),
            },
            stage="REGIME",
        )

    def log_drawdown_state_change(
        self,
        old_state: str,
        new_state: str,
        drawdown_pct: float,
        threshold_pct: float,
        cooldown_end: str | None = None,
    ):
        """Log when drawdown manager transitions between states (NORMAL/HALT/PANIC/RAMPUP)."""
        self.log_event(
            "DRAWDOWN_STATE_CHANGE",
            {
                "old_state": old_state,
                "new_state": new_state,
                "drawdown_pct": round(drawdown_pct * 100, 2),
                "threshold_pct": round(threshold_pct * 100, 2),
                "cooldown_end": cooldown_end,
            },
            stage="DRAWDOWN",
        )

    def log_stop_loss_near_miss(
        self, symbol: str, current_price: float, stop_price: float, atr: float, days_near: int = 1
    ):
        """Log when a position is within 1 ATR of its stop (early-warning signal)."""
        distance = current_price - stop_price
        self.log_event(
            "STOP_LOSS_NEAR_MISS",
            {
                "current_price": round(current_price, 4),
                "stop_price": round(stop_price, 4),
                "distance_to_stop": round(distance, 4),
                "atr": round(atr, 4),
                "distance_in_atrs": round(distance / atr, 2) if atr > 0 else None,
                "consecutive_days_near": days_near,
            },
            symbol=symbol,
            stage="RISK",
        )

    def log_cooldown_status(
        self, state: str, cooldown_end: str | None, resume_at: str | None, days_remaining: int
    ):
        """Log ongoing cooldown state so operators know when trading resumes."""
        self.log_event(
            "COOLDOWN_STATUS",
            {
                "state": state,
                "cooldown_end": cooldown_end,
                "resume_at": resume_at,
                "days_remaining": days_remaining,
            },
            stage="DRAWDOWN",
        )
