#!/usr/bin/env python3
"""Dump emails from a trading DB's notification_outbox into local HTML files.

Emails are actually sent from the GitHub Actions runner, so the on-send archive
in ``email_notifier.archive_email`` never reaches your machine. The full body of
every notification IS persisted in the ``notification_outbox`` table, which rides
along in the ``trading-database`` artifact. This script reconstructs a browsable
local archive from that table so you can review exactly what went out.

Usage:
    # after `gh run download <id> -n trading-database -D tmp/diagnose`
    python3 scripts/dump_sent_emails.py --db tmp/diagnose/trading.db
    python3 scripts/dump_sent_emails.py --db trading.db --status SENT --since 2026-06-01

Output lands in ``sent_emails/`` (gitignored) by default; override with --out.
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.email_notifier import _slugify_subject  # noqa: E402


def dump(db_path: str, out_dir: str, status: str | None, since: str | None) -> int:
    """Write one HTML file per matching notification_outbox row. Returns count."""
    if not os.path.exists(db_path):
        print(f"DB not found: {db_path}", file=sys.stderr)
        return 0

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        clauses, params = [], []
        if status:
            clauses.append("UPPER(status) = ?")
            params.append(status.upper())
        if since:
            clauses.append("created_at >= ?")
            params.append(since)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        rows = conn.execute(
            "SELECT id, category, subject, body, status, created_at "
            f"FROM notification_outbox{where} ORDER BY id",
            params,
        ).fetchall()
    finally:
        conn.close()

    os.makedirs(out_dir, exist_ok=True)
    written = 0
    index_lines = []
    for r in rows:
        ts = str(r["created_at"] or "").replace(":", "").replace(" ", "_").replace("-", "")[:15]
        prefix = ts or f"id{r['id']}"
        fname = f"{prefix}__{_slugify_subject(str(r['subject']))}.html"
        path = os.path.join(out_dir, fname)
        header = (
            f"<!-- id={r['id']} status={r['status']} category={r['category']} "
            f"created_at={r['created_at']} subject={r['subject']} -->\n"
        )
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(header + (r["body"] or ""))
        written += 1
        index_lines.append(
            f"{r['created_at']}  [{r['status']:>6}]  {r['category']:<6}  "
            f"{r['subject']}  -> {fname}"
        )

    if index_lines:
        with open(os.path.join(out_dir, "INDEX.txt"), "w", encoding="utf-8") as fh:
            fh.write("\n".join(index_lines) + "\n")

    print(f"Wrote {written} email(s) to {out_dir}/ (+ INDEX.txt)")
    return written


def main() -> int:
    """CLI entrypoint."""
    p = argparse.ArgumentParser(description="Dump notification_outbox to local HTML files")
    p.add_argument("--db", default="trading.db", help="Path to the trading DB")
    p.add_argument(
        "--out", default=None, help="Output dir (default sent_emails/ or $EMAIL_ARCHIVE_DIR)"
    )
    p.add_argument("--status", default=None, help="Filter by status (e.g. SENT, PENDING, FAILED)")
    p.add_argument("--since", default=None, help="Only created_at >= this (e.g. 2026-06-01)")
    args = p.parse_args()
    out_dir = args.out or os.getenv("EMAIL_ARCHIVE_DIR", "sent_emails")
    dump(args.db, out_dir, args.status, args.since)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
