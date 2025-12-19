#!/usr/bin/env python3
"""
Daily Digest Email Sender

Sends personalized daily investment digest to users every morning.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

from services.monitoring.daily_digest import generate_daily_digest
from services.monitoring.daily_digest_email_template import get_daily_digest_email_html
from utils.enhanced_logging import get_logger
from utils.environment import env
from db.connection_pool import get_db_session

logger = get_logger(__name__)


def get_all_users() -> list:
    """Get all users who should receive daily digest."""
    try:
        with get_db_session() as session:
            query = """
                SELECT DISTINCT email, name 
                FROM investors 
                WHERE email IS NOT NULL 
                  AND email != ''
            """
            result = session.execute(query)
            users = [{"email": row[0], "name": row[1] or "Investor"} for row in result.fetchall()]
            return users
    except Exception as e:
        logger.error(f"Error getting users: {e}")
        return []


def send_digest_email(user_email: str, user_name: str, html_content: str):
    """
    Send daily digest email to user.

    Args:
        user_email: User's email address
        user_name: User's name
        html_content: HTML email content
    """
    try:
        # Email configuration
        smtp_server = env.get("SMTP_SERVER", "smtp.gmail.com")
        smtp_port = int(env.get("SMTP_PORT", 587))
        smtp_username = env.get("SMTP_USERNAME")
        smtp_password = env.get("SMTP_PASSWORD")
        from_email = env.get("ALERT_EMAIL", smtp_username)

        if not all([smtp_username, smtp_password]):
            logger.error("SMTP credentials not configured")
            return False

        # Create message
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"📈 Daily Investment Digest - {datetime.now().strftime('%B %d, %Y')}"
        msg["From"] = from_email
        msg["To"] = user_email

        # Attach HTML content
        html_part = MIMEText(html_content, "html")
        msg.attach(html_part)

        # Send email
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(smtp_username, smtp_password)
            server.send_message(msg)

        logger.info(f"Daily digest sent to {user_email}")
        return True

    except Exception as e:
        logger.error(f"Error sending digest to {user_email}: {e}")
        return False


def send_daily_digests():
    """Send daily digest to all users."""
    logger.info("Starting daily digest email send")

    # Get all users
    users = get_all_users()

    if not users:
        logger.warning("No users found to send digest")
        return

    logger.info(f"Sending daily digest to {len(users)} users")

    success_count = 0
    fail_count = 0

    for user in users:
        try:
            # Generate digest content
            digest_data = generate_daily_digest(user["email"])

            # Generate HTML email
            html_content = get_daily_digest_email_html(
                market_section=digest_data.get("market_section", {}),
                portfolio_section=digest_data.get("portfolio_section", {}),
                user_name=user["name"],
            )

            # Send email
            if send_digest_email(user["email"], user["name"], html_content):
                success_count += 1
            else:
                fail_count += 1

        except Exception as e:
            logger.error(f"Error processing digest for {user['email']}: {e}")
            fail_count += 1

    logger.info(f"Daily digest complete: {success_count} sent, {fail_count} failed")


def main():
    """Main entry point."""
    logger.info("=" * 50)
    logger.info("Daily Digest Email Sender")
    logger.info(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 50)

    send_daily_digests()

    logger.info("Daily digest process complete")


if __name__ == "__main__":
    main()
