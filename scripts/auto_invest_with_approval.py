#!/usr/bin/env python3
"""
Automated Investment Script with Email Approval

This script requires manual approval before executing trades.
It will:
1. Analyze the market and generate trade recommendations
2. Send you an email with a summary and approval links
3. Wait for your approval (or rejection)
4. Execute trades only after you approve

Usage:
    python3 scripts/auto_invest_with_approval.py --approval-email your@email.com
"""

import argparse
import asyncio
import logging
import sys
import time
from datetime import datetime
from decimal import Decimal
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from alpaca.trading.client import TradingClient

from config import settings
from services.approval.trade_approval import TradeApprovalManager
from services.execution.alpaca_executor import AlpacaExecutionService
from services.execution.planner import TradePlanner
from services.strategy.allocation import weights_to_dollars
from services.strategy.conviction_engine import ConvictionConfig, ConvictionEngine
from services.strategy.risk import apply_risk_constraints
from utils.logging_config import setup_logger

logger = setup_logger(__name__)


async def run_investment_workflow_with_approval(
    approval_email: str,
    min_cash: Decimal = Decimal("1000"),
    max_positions: int = 10,
    cash_buffer_pct: float = 10.0,
    approval_timeout_minutes: int = 60,
    check_interval_seconds: int = 30,
):
    """
    Run the investment workflow with email approval.

    Args:
        approval_email: Email address to send approval request to
        min_cash: Minimum cash threshold to trigger investment
        max_positions: Maximum number of positions to hold
        cash_buffer_pct: Percentage of cash to keep as buffer
        approval_timeout_minutes: Minutes to wait for approval
        check_interval_seconds: Seconds between approval checks
    """
    logger.info("=" * 80)
    logger.info("AUTOMATED INVESTMENT WORKFLOW (WITH APPROVAL)")
    logger.info("=" * 80)
    logger.info(f"Approval Email: {approval_email}")
    logger.info(f"Min Cash Threshold: ${min_cash:,.2f}")
    logger.info(f"Max Positions: {max_positions}")
    logger.info(f"Cash Buffer: {cash_buffer_pct}%")
    logger.info(f"Approval Timeout: {approval_timeout_minutes} minutes")
    logger.info("")

    # Initialize services
    client = TradingClient(
        api_key=settings.ALPACA_API_KEY,
        secret_key=settings.ALPACA_SECRET_KEY,
        paper=settings.ALPACA_PAPER,
    )

    approval_manager = TradeApprovalManager()

    # Check available cash
    account = client.get_account()
    buying_power = Decimal(str(account.buying_power))
    logger.info(f"Current buying power: ${buying_power:,.2f}")

    # Check if we should invest
    last_investment_file = Path("data/last_investment.txt")
    last_investment_file.parent.mkdir(parents=True, exist_ok=True)

    if buying_power < min_cash:
        logger.info(f"Buying power below threshold ${min_cash:,.2f}")
        return

    # Check if already invested today
    today = datetime.now().date()
    if last_investment_file.exists():
        last_date_str = last_investment_file.read_text().strip()
        try:
            last_date = datetime.fromisoformat(last_date_str).date()
            if last_date == today:
                logger.info(f"Already invested today ({today})")
                return
        except ValueError:
            pass

    # Calculate investable cash
    cash_buffer = buying_power * Decimal(str(cash_buffer_pct / 100))
    investable_cash = buying_power - cash_buffer

    logger.info(f"Investable cash: ${investable_cash:,.2f} (after ${cash_buffer:,.2f} buffer)")

    if investable_cash <= 0:
        logger.warning("No investable cash after buffer")
        return

    # Run strategy
    logger.info("Running conviction strategy...")

    conviction_config = ConvictionConfig(lookback_days=365, recency_weight=0.5, min_conviction_score=0.01)

    engine = ConvictionEngine(conviction_config)

    try:
        raw_weights = engine.compute_conviction_scores()
        logger.info(f"Generated conviction scores for {len(raw_weights)} securities")
    except Exception as e:
        logger.error(f"Failed to compute conviction scores: {e}")
        return

    if not raw_weights:
        logger.warning("No conviction scores generated - check database")
        return

    # Apply risk constraints
    constrained_weights = apply_risk_constraints(
        raw_weights, max_position_pct=10.0, max_sector_pct=30.0, cash_buffer_pct=cash_buffer_pct
    )

    # Limit to max positions
    sorted_weights = sorted(constrained_weights.items(), key=lambda x: x[1], reverse=True)
    top_weights = dict(sorted_weights[:max_positions])

    logger.info(f"Selected top {len(top_weights)} positions")

    # Convert to dollar amounts
    dollar_allocations = weights_to_dollars(top_weights, float(investable_cash))

    # Get current prices for better estimates
    planner = TradePlanner()
    positions = client.get_all_positions()
    current_positions = {p.symbol: float(p.qty) for p in positions}

    trade_plan = planner.generate_buy_plan(
        target_allocations=dollar_allocations, current_positions=current_positions, price_map={}
    )

    # Prepare trade proposals for approval
    trades_for_approval = []
    total_investment = 0.0

    for trade in trade_plan:
        # Estimate price and value
        estimated_price = dollar_allocations.get(trade.symbol, 0) / trade.quantity if trade.quantity > 0 else 0
        estimated_value = estimated_price * trade.quantity
        allocation_pct = (estimated_value / float(investable_cash)) * 100 if investable_cash > 0 else 0

        trades_for_approval.append(
            {
                "symbol": trade.symbol,
                "quantity": trade.quantity,
                "estimated_price": estimated_price,
                "estimated_value": estimated_value,
                "allocation_pct": allocation_pct,
            }
        )
        total_investment += estimated_value

    logger.info(f"\nGenerated {len(trades_for_approval)} trades totaling ${total_investment:,.2f}")

    # Create approval request
    logger.info("Creating approval request...")
    approval_request = approval_manager.create_approval_request(
        trades=trades_for_approval,
        total_investment=total_investment,
        available_cash=float(buying_power),
        cash_buffer=float(cash_buffer),
        expiry_hours=int(approval_timeout_minutes / 60),
    )

    logger.info(f"Approval request created: {approval_request.request_id}")

    # Send approval email
    logger.info(f"Sending approval email to {approval_email}...")
    email_sent = await approval_manager.send_approval_email(request=approval_request, recipient_email=approval_email)

    if not email_sent:
        logger.error("Failed to send approval email")
        logger.info("You can still approve manually via API:")
        logger.info(f"  Approve: POST http://localhost:8000/api/v1/approvals/{approval_request.request_id}/approve")
        logger.info(f"  Reject:  POST http://localhost:8000/api/v1/approvals/{approval_request.request_id}/reject")
    else:
        logger.info("✓ Approval email sent successfully")

    # Wait for approval
    logger.info(f"\nWaiting for approval (timeout: {approval_timeout_minutes} minutes)...")
    logger.info("Check your email for the approval link")

    max_checks = int((approval_timeout_minutes * 60) / check_interval_seconds)

    for check_num in range(max_checks):
        # Check approval status
        if approval_manager.is_approved(approval_request.request_id):
            logger.info("\n✓ APPROVED! Proceeding with trades...")
            break

        # Check if rejected
        request = approval_manager.get_request(approval_request.request_id)
        if request and request.status.value == "REJECTED":
            logger.info("\n✗ REJECTED - Trades cancelled")
            return

        # Check if expired
        if not approval_manager.is_pending(approval_request.request_id):
            logger.warning("\n⏱ Approval request expired")
            return

        # Wait and show progress
        if check_num % 10 == 0:  # Log every 5 minutes (assuming 30s intervals)
            remaining_minutes = ((max_checks - check_num) * check_interval_seconds) / 60
            logger.info(f"Still waiting... ({remaining_minutes:.1f} minutes remaining)")

        await asyncio.sleep(check_interval_seconds)
    else:
        logger.warning("\n⏱ Timeout waiting for approval")
        return

    # Execute trades
    logger.info("\nExecuting approved trades...")

    executor = AlpacaExecutionService.from_env(paper=settings.ALPACA_PAPER)

    results = await executor.execute_plan(trade_plan)

    # Log results
    logger.info("\nExecution Results:")
    successful = sum(1 for r in results if r.success)
    logger.info(f"  Successful: {successful}/{len(results)}")

    for result in results:
        status = "✓" if result.success else "✗"
        logger.info(f"  {status} {result.symbol}: {result.message}")

    # Update last investment date
    last_investment_file.write_text(datetime.now().isoformat())

    logger.info("\n" + "=" * 80)
    logger.info("INVESTMENT COMPLETE")
    logger.info("=" * 80)


def main():
    parser = argparse.ArgumentParser(
        description="Automated investment with email approval",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--approval-email",
        type=str,
        required=True,
        help="Email address to send approval requests to",
    )

    parser.add_argument("--min-cash", type=float, default=1000.0, help="Minimum cash threshold (default: 1000)")

    parser.add_argument("--max-positions", type=int, default=10, help="Maximum positions (default: 10)")

    parser.add_argument("--cash-buffer-pct", type=float, default=10.0, help="Cash buffer percentage (default: 10)")

    parser.add_argument(
        "--approval-timeout",
        type=int,
        default=60,
        help="Minutes to wait for approval (default: 60)",
    )

    parser.add_argument(
        "--check-interval",
        type=int,
        default=30,
        help="Seconds between approval checks (default: 30)",
    )

    args = parser.parse_args()

    # Validate email configuration
    from config.settings import get_notification_config

    config = get_notification_config()
    if not config or not config.email_config:
        logger.error("Email notifications not configured!")
        logger.error("Please configure SMTP settings in your .env file:")
        logger.error("  SMTP_SERVER=smtp.gmail.com")
        logger.error("  SMTP_PORT=587")
        logger.error("  SMTP_USERNAME=your-email@gmail.com")
        logger.error("  SMTP_PASSWORD=your-app-password")
        sys.exit(1)

    # Run workflow
    try:
        asyncio.run(
            run_investment_workflow_with_approval(
                approval_email=args.approval_email,
                min_cash=Decimal(str(args.min_cash)),
                max_positions=args.max_positions,
                cash_buffer_pct=args.cash_buffer_pct,
                approval_timeout_minutes=args.approval_timeout,
                check_interval_seconds=args.check_interval,
            )
        )
    except KeyboardInterrupt:
        logger.info("\nInterrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.exception(f"Workflow failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
