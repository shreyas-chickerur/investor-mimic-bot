#!/usr/bin/env python3
"""
In-house error tracker — replaces Sentry with zero external dependencies.

Catches unhandled exceptions via sys.excepthook, persists them to the
error_log DB table, and sends a styled HTML alert email.  Deduplication
prevents repeat emails for the same error type within a single run.

Usage (in runner_main.py):
    from src.utils.error_tracker import init_error_tracker
    init_error_tracker(db, email_notifier)
"""
from __future__ import annotations

import html as _html
import logging
import sys
import traceback
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.core.database import TradingDatabase
    from src.utils.email_notifier import EmailNotifier

logger = logging.getLogger(__name__)

# Errors already alerted this process lifetime — prevents duplicate emails
# for the same exception type in a single run.
_alerted_types: set[str] = set()


def _build_error_html(
    error_type: str,
    message: str,
    stack_trace: str,
    run_id: str,
    context: dict | None = None,
) -> str:
    """Build a styled HTML email body for an unhandled exception."""
    from src.utils.email_notifier import _kv_rows, build_alert_html

    kv_pairs = [
        ("Error type", error_type),
        ("Run ID", run_id),
    ]
    if context:
        for k, v in context.items():
            kv_pairs.append((str(k), str(v)[:200]))

    trace_html = (
        f"<div style='background:#1a1a2e;border-radius:6px;padding:14px 16px;margin-top:12px'>"
        f"<pre style='margin:0;color:#e0e0e0;font-size:12px;white-space:pre-wrap;"
        f"font-family:monospace;overflow-x:auto'>"
        f"{_html.escape(stack_trace[-3000:])}"  # last 3000 chars — most relevant
        f"</pre></div>"
    )

    body = (
        f"<p style='color:#c62828;font-weight:600;font-size:15px;margin:0 0 12px'>"
        f"{_html.escape(str(message)[:300])}</p>"
        + _kv_rows(kv_pairs)
        + "<h4 style='margin:16px 0 6px;color:#555'>Stack trace</h4>"
        + trace_html
        + "<p style='color:#555;font-size:13px;margin:12px 0 0'>"
        "Check GitHub Actions logs for the full context.</p>"
    )
    return build_alert_html(
        f"🔥 Unhandled Exception: {error_type}",
        body,
        accent_color="#b71c1c",
    )


class ErrorTracker:
    """Captures unhandled exceptions, persists them, and sends email alerts.

    Install via init_error_tracker(); the instance is kept alive for the
    lifetime of the process so sys.excepthook stays registered.
    """

    def __init__(self, db: TradingDatabase, email_notifier: EmailNotifier):
        self._db = db
        self._email = email_notifier
        self._run_id: str = getattr(db, "run_id", "UNKNOWN")
        self._previous_hook = sys.excepthook
        sys.excepthook = self._handle_exception
        logger.info("In-house error tracker active (run_id=%s)", self._run_id)

    def _handle_exception(self, exc_type, exc_value, exc_tb) -> None:
        """sys.excepthook replacement — called on every unhandled exception."""
        # Always delegate to the original hook first (prints traceback to stderr)
        self._previous_hook(exc_type, exc_value, exc_tb)

        # KeyboardInterrupt / SystemExit are not crashes — skip alerting
        if issubclass(exc_type, (KeyboardInterrupt, SystemExit)):
            return

        error_type = exc_type.__name__
        message = str(exc_value)
        stack = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))

        self.capture(error_type=error_type, message=message, stack_trace=stack)

    def capture(
        self,
        error_type: str,
        message: str,
        stack_trace: str = "",
        context: dict | None = None,
    ) -> None:
        """Record an error and send a one-time alert email for this error type."""
        global _alerted_types

        # Persist to DB regardless of deduplication
        alert_sent = False
        try:
            self._db.record_error(
                error_type=error_type,
                message=message,
                stack_trace=stack_trace,
                context=context,
                alert_sent=False,
            )
        except Exception as db_exc:
            logger.warning("error_tracker: DB persist failed: %s", db_exc)

        # Send email only once per error type per process lifetime
        if error_type not in _alerted_types:
            _alerted_types.add(error_type)
            try:
                html = _build_error_html(
                    error_type=error_type,
                    message=message,
                    stack_trace=stack_trace,
                    run_id=self._run_id,
                    context=context,
                )
                self._email.send_alert(f"🔥 Unhandled Exception: {error_type}", html)
                alert_sent = True
                logger.info("error_tracker: alert sent for %s", error_type)
            except Exception as email_exc:
                logger.warning("error_tracker: email alert failed: %s", email_exc)

            # Update DB row with alert_sent status
            if alert_sent:
                try:
                    self._db.record_error(
                        error_type=f"{error_type}_ALERT_SENT",
                        message=message[:100],
                        alert_sent=True,
                    )
                except Exception:  # nosec B110
                    pass  # secondary DB write — best-effort only
        else:
            logger.debug("error_tracker: duplicate %s — skipping repeat email", error_type)


# Module-level singleton so it survives for the process lifetime
_tracker: ErrorTracker | None = None


def init_error_tracker(db: TradingDatabase, email_notifier: EmailNotifier) -> ErrorTracker:
    """Initialise the global error tracker.  Safe to call multiple times
    (subsequent calls are no-ops that return the existing instance).
    """
    global _tracker
    if _tracker is None:
        _tracker = ErrorTracker(db, email_notifier)
    return _tracker


def capture(
    error_type: str,
    message: str,
    stack_trace: str = "",
    context: dict | None = None,
) -> None:
    """Convenience function for manually reporting caught exceptions."""
    if _tracker is not None:
        _tracker.capture(
            error_type=error_type,
            message=message,
            stack_trace=stack_trace,
            context=context,
        )
    else:
        logger.warning("error_tracker not initialised — call init_error_tracker() first")
