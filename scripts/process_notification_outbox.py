#!/usr/bin/env python3
"""Process queued notifications from database outbox.

This decouples runtime execution from notification delivery side effects.
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.database import TradingDatabase
from src.utils.email_notifier import EmailNotifier

logger = logging.getLogger(__name__)


def process_outbox(db_path: str, limit: int = 50) -> int:
    """Deliver queued notifications.

    Args:
        db_path: SQLite database path.
        limit: Maximum notifications to process.

    Returns:
        Number of successfully delivered notifications.
    """
    db = TradingDatabase(db_path=db_path)
    notifier = EmailNotifier(outbox_writer=None)

    queued = db.fetch_pending_notifications(limit=limit)
    if not queued:
        logger.info("No pending notifications in outbox")
        return 0

    delivered = 0
    for row in queued:
        notification_id = int(row["id"])
        channel = str(row.get("channel", "")).lower()
        subject = str(row.get("subject", ""))
        body = str(row.get("body", ""))

        if channel != "email":
            db.mark_notification_failed(notification_id, f"Unsupported channel: {channel}")
            continue

        try:
            notifier._send_email(subject=subject, body=body, is_html=True)
            db.mark_notification_sent(notification_id)
            delivered += 1
        except Exception as exc:  # pragma: no cover - external SMTP failures
            db.mark_notification_failed(notification_id, str(exc))
            logger.error("Failed notification %s: %s", notification_id, exc)

    logger.info("Outbox processed: delivered=%s attempted=%s", delivered, len(queued))
    return delivered


def main() -> int:
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(description="Process notification outbox")
    parser.add_argument("--db", default="trading.db", help="Database path")
    parser.add_argument("--limit", type=int, default=50, help="Maximum queued rows to process")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    process_outbox(db_path=args.db, limit=args.limit)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
