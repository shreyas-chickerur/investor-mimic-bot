#!/usr/bin/env python3
"""
Email Notification System
Sends critical alert emails.

Daily digest emails are generated and sent via scripts/generate_daily_email.py
in workflow execution.
"""
from __future__ import annotations

import html as _html_mod
import logging
import os
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Callable

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Local archive of sent mail
# ---------------------------------------------------------------------------


def _slugify_subject(subject: str, max_len: int = 60) -> str:
    """Filesystem-safe slug from an email subject (emoji/punctuation dropped)."""
    cleaned = "".join(c if (c.isalnum() or c in " -_") else " " for c in subject)
    slug = "-".join(cleaned.split()).strip("-_")[:max_len]
    return slug or "email"


def archive_email(subject: str, body_html: str, archive_dir: str | None = None) -> str | None:
    """Write a copy of an outgoing email to a local, gitignored directory.

    Lets us review exactly what the bot sent without trawling the DB. The
    directory (default ``sent_emails/``, overridable via ``EMAIL_ARCHIVE_DIR``)
    is gitignored — bodies contain portfolio values, P&L and positions and must
    never be pushed. Best-effort: any failure here must never block delivery,
    so callers should treat this as fire-and-forget.

    Returns the written path, or ``None`` if archiving was skipped/failed.
    """
    try:
        directory: str = (
            archive_dir or os.getenv("EMAIL_ARCHIVE_DIR", "sent_emails") or "sent_emails"
        )
        os.makedirs(directory, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        path = os.path.join(directory, f"{ts}__{_slugify_subject(subject)}.html")
        # Prepend a comment header so the subject is visible even if the body
        # is a full HTML document with its own <title>.
        header = f"<!-- Subject: {subject} | archived {datetime.now().isoformat()} -->\n"
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(header + body_html)
        return path
    except Exception as exc:  # pragma: no cover - never break delivery
        logger.warning("Could not archive sent email locally: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Shared HTML template
# ---------------------------------------------------------------------------


def build_alert_html(
    title: str,
    body_html: str,
    accent_color: str = "#dc3545",
    footer_html: str = "",
) -> str:
    """Return a consistently styled alert email as an HTML string.

    Args:
        title: Header text shown on the coloured banner (may include emoji).
        body_html: Inner HTML for the card body — caller is responsible for
                   escaping any user-controlled strings inside.
        accent_color: CSS hex colour for the header banner (default red).
        footer_html: Optional extra HTML appended below the timestamp line.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
    footer_extra = f"<br>{footer_html}" if footer_html else ""
    return f"""<!DOCTYPE html>
<html>
<body style="margin:0;padding:0;background:#f4f4f4;font-family:-apple-system,'Helvetica Neue',Arial,sans-serif">
  <table width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;margin:24px auto">
    <tr>
      <td style="background:{accent_color};color:#fff;padding:18px 24px;
                 border-radius:8px 8px 0 0">
        <h2 style="margin:0;font-size:18px;font-weight:700">{title}</h2>
      </td>
    </tr>
    <tr>
      <td style="background:#fff;padding:24px;border:1px solid #e0e0e0;
                 border-top:none;border-radius:0 0 8px 8px">
        {body_html}
        <hr style="border:none;border-top:1px solid #eee;margin:20px 0 12px">
        <p style="margin:0;color:#999;font-size:12px">
          {timestamp} · Investor Mimic Trading System{footer_extra}
        </p>
      </td>
    </tr>
  </table>
</body>
</html>"""


def _kv_rows(pairs: list[tuple[str, str]]) -> str:
    """Render a list of (label, value) tuples as a simple two-column table."""
    rows = "".join(
        f"<tr><td style='padding:4px 16px 4px 0;color:#555;white-space:nowrap'>"
        f"<strong>{_html_mod.escape(str(k))}</strong></td>"
        f"<td style='padding:4px 0;color:#111'>{_html_mod.escape(str(v))}</td></tr>"
        for k, v in pairs
    )
    return f"<table style='border-collapse:collapse;font-size:14px;margin:12px 0'>{rows}</table>"


def _bullet_list(items: list[str]) -> str:
    """Render a list of strings as a styled <ul>."""
    lis = "".join(
        f"<li style='margin-bottom:4px;color:#333'>{_html_mod.escape(str(i))}</li>" for i in items
    )
    return f"<ul style='padding-left:20px;margin:8px 0 16px'>{lis}</ul>"


# ---------------------------------------------------------------------------
# EmailNotifier
# ---------------------------------------------------------------------------


class EmailNotifier:
    """Handles email notifications for the trading system."""

    def __init__(self, outbox_writer: Callable[[str, str, str, str], int] | None = None):
        self.smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.sender_email = os.getenv("SENDER_EMAIL")
        self.sender_password = os.getenv("SENDER_PASSWORD")
        self.recipient_email = os.getenv("RECIPIENT_EMAIL")
        self.outbox_writer = outbox_writer

        if not all([self.sender_email, self.sender_password, self.recipient_email]):
            logger.warning("Email credentials not configured - notifications disabled")
            self.enabled = False
        else:
            self.enabled = True

    def send_alert(self, subject: str, message: str):
        """Send a critical alert email.

        ``message`` may be either plain text or a complete HTML document.
        If it is plain text it is wrapped in a minimal styled card so the
        rendered output is still readable.  Callers that need rich formatting
        should build their body with :func:`build_alert_html` and pass the
        result here.
        """
        # Build the final HTML body
        is_html = message.lstrip().startswith("<")
        if is_html:
            html_body = message
        else:
            html_body = build_alert_html(
                title=subject,
                body_html=f"<pre style='white-space:pre-wrap;font-family:monospace;"
                f"background:#f8f9fa;padding:12px;border-radius:4px;"
                f"font-size:13px'>{_html_mod.escape(message)}</pre>",
            )

        if self.outbox_writer:
            self.outbox_writer("email", "alert", subject, html_body)
            logger.info("Queued alert notification to outbox")
            return

        if not self.enabled:
            logger.warning("Email notifications disabled - alert not sent")
            return

        self._send_email(subject, html_body, is_html=True)

    def send_error_alert(self, error_message: str, details: str = ""):
        """Send an error alert email."""
        subject = f"🚨 Trading System Error — {datetime.now().strftime('%Y-%m-%d')}"

        details_html = (
            f"<div style='background:#f8f9fa;border-left:4px solid #dc3545;"
            f"padding:12px 16px;margin-top:12px;border-radius:0 4px 4px 0'>"
            f"<pre style='margin:0;white-space:pre-wrap;font-size:13px;font-family:monospace'>"
            f"{_html_mod.escape(str(details))}</pre></div>"
            if details
            else ""
        )
        body_html = (
            f"<p style='font-size:15px;color:#333;margin:0 0 8px'>"
            f"{_html_mod.escape(error_message)}</p>"
            f"{details_html}"
            f"<p style='margin-top:16px;color:#666;font-size:13px'>"
            f"<strong>Action required:</strong> check GitHub Actions logs for details.</p>"
        )
        html = build_alert_html("🚨 Error Alert", body_html, accent_color="#dc3545")

        if self.outbox_writer:
            self.outbox_writer("email", "error", subject, html)
            logger.info("Queued error notification to outbox")
            return

        if not self.enabled:
            logger.error(f"Email disabled, error not sent: {error_message}")
            return

        self._send_email(subject, html, is_html=True)

    def _send_email(self, subject: str, body: str, is_html: bool = True):
        """Send email via SMTP."""

        # __init__ already gated on these being non-None via self.enabled,
        # but assert for mypy + defence-in-depth in case _send_email is
        # invoked directly when self.enabled is False.
        assert self.sender_email is not None
        assert self.sender_password is not None
        assert self.recipient_email is not None

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = self.sender_email
            msg["To"] = self.recipient_email

            if is_html:
                msg.attach(MIMEText(body, "html"))
            else:
                msg.attach(MIMEText(body, "plain"))

            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.sender_email, self.sender_password)
                server.send_message(msg)

            logger.info(f"Email sent successfully: {subject}")
            # Keep a local, gitignored copy of everything we actually send.
            archive_email(subject, body)

        except Exception as e:
            logger.error(f"Failed to send email: {e}")


def send_error_alert(error_message: str, details: str = ""):
    """Convenience function to send error alert."""
    notifier = EmailNotifier()
    notifier.send_error_alert(error_message, details)
