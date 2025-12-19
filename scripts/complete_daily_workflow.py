#!/usr/bin/env python3
"""
Complete Daily Workflow - Full "Black Box" System

This script runs the complete multi-signal analysis and generates
buy/sell recommendations with email approval.

Combines:
- 13F Filings (40%)
- News Sentiment (20%)
- Insider Trading (20%)
- Technical Indicators (20%)
"""

import os
import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

from alpaca.trading.client import TradingClient

from services.approval.trade_approval import TradeApprovalManager
from services.monitoring.email_notifier import EmailConfig, EmailNotifier
from services.strategy.complete_signal_engine import CompleteSignalEngine, CompleteSignalWeights
from utils.logging_config import setup_logger

logger = setup_logger(__name__)


def main():
    print("=" * 80)
    print("COMPLETE DAILY INVESTMENT WORKFLOW")
    print("=" * 80)
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Get configuration
    alpha_vantage_key = os.getenv("ALPHA_VANTAGE_API_KEY")
    approval_email = os.getenv("ALERT_EMAIL", "schickerur2020@gmail.com")

    print("Configuration:")
    print(f"  Alpha Vantage API: {'✓ Configured' if alpha_vantage_key else '✗ Not configured'}")
    print(f"  Approval Email: {approval_email}")
    print()

    # Initialize Alpaca client
    api_key = os.getenv("ALPACA_API_KEY")
    secret_key = os.getenv("ALPACA_SECRET_KEY")
    paper = os.getenv("ALPACA_PAPER", "True").lower() == "true"

    client = TradingClient(api_key, secret_key, paper=paper)
    account = client.get_account()
    buying_power = Decimal(str(account.buying_power))

    print(f"Alpaca Account:")
    print(f"  Mode: {'Paper Trading' if paper else 'Live Trading'}")
    print(f"  Buying Power: ${buying_power:,.2f}")
    print()

    # Check if we should invest
    min_cash = Decimal("1000")
    if buying_power < min_cash:
        print(f"⚠️  Buying power ${buying_power:,.2f} below minimum ${min_cash:,.2f}")
        print("Waiting for more funds...")
        return

    # Initialize complete signal engine
    print("Initializing complete signal engine...")
    print("  Signal Weights:")
    print("    - 13F Conviction:    40%")
    print("    - News Sentiment:    20%")
    print("    - Insider Trading:   20%")
    print("    - Technical:         20%")
    print()

    engine = CompleteSignalEngine(
        signal_weights=CompleteSignalWeights(
            conviction_13f=0.40, news_sentiment=0.20, insider_trading=0.20, technical=0.20
        ),
        alpha_vantage_key=alpha_vantage_key,
    )

    # Get recommendations
    print("Analyzing market with all signals...")
    print("This may take 30-60 seconds...")
    print()

    try:
        recommendations = engine.get_recommendations(top_n=10)

        print(f"✓ Generated {len(recommendations)} recommendations")
        print()

        # Display recommendations
        print("TOP 10 RECOMMENDATIONS:")
        print("-" * 80)
        print(f"{'Rank':<6} {'Symbol':<10} {'Score':<10} {'Recommendation':<15} {'Confidence':<12}")
        print("-" * 80)

        for i, rec in enumerate(recommendations, 1):
            print(f"{i:<6} {rec.symbol:<10} {rec.final_score:.4f}    {rec.recommendation:<15} {rec.confidence:.1%}")

        print()

        # Show detailed breakdown for top 3
        print("DETAILED ANALYSIS (Top 3):")
        print("-" * 80)

        for rec in recommendations[:3]:
            print(f"\n{rec.symbol}:")
            print(f"  Final Score:      {rec.final_score:.4f}")
            print(f"  Recommendation:   {rec.recommendation.upper()} (confidence: {rec.confidence:.1%})")
            print(f"  Signal Breakdown:")
            print(f"    13F Conviction:   {rec.conviction_score:.4f} (40% weight)")
            print(f"    News Sentiment:   {rec.sentiment_score:.4f} (20% weight)")
            print(f"    Insider Trading:  {rec.insider_score:.4f} (20% weight)")
            print(f"    Technical:        {rec.technical_score:.4f} (20% weight)")

        print()
        print("=" * 80)

        # Calculate investment amounts
        cash_buffer_pct = 0.10
        cash_buffer = buying_power * Decimal(str(cash_buffer_pct))
        investable_cash = buying_power - cash_buffer

        print(f"\nInvestment Allocation:")
        print(f"  Available Cash:    ${buying_power:,.2f}")
        print(f"  Cash Buffer (10%): ${cash_buffer:,.2f}")
        print(f"  Investable:        ${investable_cash:,.2f}")
        print()

        # Prepare trades for approval
        trades = []
        for rec in recommendations:
            # Allocate based on final score
            allocation = float(investable_cash) * rec.final_score

            # Estimate shares (would fetch real price in production)
            estimated_price = 100.0  # Placeholder
            shares = allocation / estimated_price

            trades.append(
                {
                    "symbol": rec.symbol,
                    "quantity": shares,
                    "estimated_price": estimated_price,
                    "estimated_value": allocation,
                    "allocation_pct": rec.final_score * 100,
                }
            )

        total_investment = sum(t["estimated_value"] for t in trades)

        print("PROPOSED TRADES:")
        print("-" * 80)
        for trade in trades:
            print(
                f"  {trade['symbol']:<10} {trade['quantity']:>8.2f} shares @ ${trade['estimated_price']:>8.2f} = ${trade['estimated_value']:>10,.2f} ({trade['allocation_pct']:>5.1f}%)"
            )
        print("-" * 80)
        print(f"  {'TOTAL':<10} {'':<8} {'':<8} {'':<3} ${total_investment:>10,.2f}")
        print()

        # Create approval request
        print("Creating approval request...")
        approval_manager = TradeApprovalManager()

        request = approval_manager.create_approval_request(
            trades=trades,
            total_investment=total_investment,
            available_cash=float(buying_power),
            cash_buffer=float(cash_buffer),
            expiry_hours=24,
        )

        print(f"✓ Approval request created: {request.request_id}")
        print()

        # Send approval email
        print(f"Sending approval email to {approval_email}...")

        smtp_server = os.getenv("SMTP_SERVER")
        smtp_port = int(os.getenv("SMTP_PORT", "587"))
        smtp_username = os.getenv("SMTP_USERNAME")
        smtp_password = os.getenv("SMTP_PASSWORD")

        if not all([smtp_server, smtp_username, smtp_password]):
            print("✗ Email not configured")
            print("Add SMTP settings to .env file")
            return

        email_config = EmailConfig(
            smtp_server=smtp_server,
            smtp_port=smtp_port,
            smtp_username=smtp_username,
            smtp_password=smtp_password,
            from_email=smtp_username,
        )

        notifier = EmailNotifier(email_config)

        # Build email content
        trade_summary = "\n".join(
            [
                f"  • {t['symbol']}: {t['quantity']:.2f} shares @ ${t['estimated_price']:.2f} = ${t['estimated_value']:,.2f}"
                for t in trades
            ]
        )

        approve_url = f"http://localhost:8000/api/v1/approve/{request.request_id}/approve"
        reject_url = f"http://localhost:8000/api/v1/approve/{request.request_id}/reject"

        message = f"""
Complete Multi-Signal Analysis Complete

Your investment bot has analyzed the market using all available signals:
- 13F Filings (40%)
- News Sentiment (20%)
- Insider Trading (20%)
- Technical Indicators (20%)

SUMMARY:
--------
Total Investment: ${total_investment:,.2f}
Available Cash: ${buying_power:,.2f}
Cash Buffer: ${cash_buffer:,.2f}
Number of Trades: {len(trades)}

TOP RECOMMENDATIONS:
-------------------
{chr(10).join([f'{i}. {rec.symbol} - {rec.recommendation.upper()} (confidence: {rec.confidence:.0%})' for i, rec in enumerate(recommendations[:5], 1)])}

PROPOSED TRADES:
---------------
{trade_summary}

APPROVAL:
---------
This request expires in 24 hours.

To approve these trades, click:
{approve_url}

To reject these trades, click:
{reject_url}

Request ID: {request.request_id}

---
Generated by Complete Signal Engine
{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""

        success = notifier.send_alert(
            to_emails=[approval_email],
            subject=f"Trade Approval Required: ${total_investment:,.2f}",
            message=message,
            level="INFO",
        )

        if success:
            print(f"✓ Approval email sent to {approval_email}")
            print()
            print("Next steps:")
            print("1. Check your email")
            print("2. Review the recommendations")
            print("3. Click 'Approve' or 'Reject'")
            print()
            print(f"Approval URL: {approve_url}")
        else:
            print("✗ Failed to send email")
            print(f"Manual approval URL: {approve_url}")

        print()
        print("=" * 80)
        print("WORKFLOW COMPLETE")
        print("=" * 80)

    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
