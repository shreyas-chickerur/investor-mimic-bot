#!/usr/bin/env python3
"""
Automated Investment Script

This script checks for available buying power in your Alpaca account
and automatically invests according to your strategy.

Designed to work with Alpaca's recurring deposit feature.

Usage:
    # Run once
    python3 scripts/auto_invest.py
    
    # Run with custom parameters
    python3 scripts/auto_invest.py --min-cash 1000 --max-positions 10
    
    # Dry run (no actual trades)
    python3 scripts/auto_invest.py --dry-run
    
Schedule this to run daily (e.g., via cron):
    0 10 * * 1-5 cd /path/to/bot && python3 scripts/auto_invest.py
"""

import argparse
import asyncio
import logging
import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from alpaca.trading.client import TradingClient

from config import settings
from services.execution.alpaca_executor import AlpacaExecutor
from services.execution.planner import ExecutionPlanner
from services.strategy.allocation import weights_to_dollars
from services.strategy.conviction_engine import ConvictionConfig, ConvictionEngine
from services.strategy.risk import apply_risk_constraints
from utils.logging_config import setup_logger

logger = setup_logger(__name__)


async def get_available_cash(client: TradingClient) -> Decimal:
    """Get available buying power from Alpaca account."""
    account = client.get_account()
    buying_power = Decimal(str(account.buying_power))
    logger.info(f"Current buying power: ${buying_power:,.2f}")
    return buying_power


async def check_if_should_invest(
    buying_power: Decimal, min_cash_threshold: Decimal, last_investment_file: Path
) -> bool:
    """
    Determine if we should invest based on available cash.

    Args:
        buying_power: Current buying power
        min_cash_threshold: Minimum cash needed to trigger investment
        last_investment_file: File tracking last investment date

    Returns:
        True if should invest, False otherwise
    """
    # Check if we have enough cash
    if buying_power < min_cash_threshold:
        logger.info(f"Buying power ${buying_power:,.2f} below threshold ${min_cash_threshold:,.2f}")
        return False

    # Check if we already invested today
    today = datetime.now().date()
    if last_investment_file.exists():
        last_date_str = last_investment_file.read_text().strip()
        try:
            last_date = datetime.fromisoformat(last_date_str).date()
            if last_date == today:
                logger.info(f"Already invested today ({today})")
                return False
        except ValueError:
            logger.warning(f"Could not parse last investment date: {last_date_str}")

    logger.info(f"Ready to invest: ${buying_power:,.2f} available")
    return True


async def run_investment_workflow(
    dry_run: bool = False,
    min_cash: Decimal = Decimal("1000"),
    max_positions: int = 10,
    cash_buffer_pct: float = 10.0,
):
    """
    Run the complete investment workflow.

    Args:
        dry_run: If True, don't execute actual trades
        min_cash: Minimum cash threshold to trigger investment
        max_positions: Maximum number of positions to hold
        cash_buffer_pct: Percentage of cash to keep as buffer
    """
    logger.info("=" * 80)
    logger.info("AUTOMATED INVESTMENT WORKFLOW")
    logger.info("=" * 80)
    logger.info(f"Mode: {'DRY RUN' if dry_run else 'LIVE'}")
    logger.info(f"Min Cash Threshold: ${min_cash:,.2f}")
    logger.info(f"Max Positions: {max_positions}")
    logger.info(f"Cash Buffer: {cash_buffer_pct}%")
    logger.info("")

    # Initialize Alpaca client
    client = TradingClient(
        api_key=settings.ALPACA_API_KEY,
        secret_key=settings.ALPACA_SECRET_KEY,
        paper=settings.ALPACA_PAPER,
    )

    # Check available cash
    buying_power = await get_available_cash(client)

    # Check if we should invest
    last_investment_file = Path("data/last_investment.txt")
    last_investment_file.parent.mkdir(parents=True, exist_ok=True)

    should_invest = await check_if_should_invest(buying_power, min_cash, last_investment_file)

    if not should_invest:
        logger.info("No investment needed at this time")
        return

    # Calculate cash buffer
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

    # Get conviction scores (this queries the database)
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

    # Log allocations
    logger.info("\nTarget Allocations:")
    for symbol, amount in sorted(dollar_allocations.items(), key=lambda x: x[1], reverse=True):
        logger.info(f"  {symbol}: ${amount:,.2f}")

    # Execute trades
    if dry_run:
        logger.info("\n" + "=" * 80)
        logger.info("DRY RUN - No trades executed")
        logger.info("=" * 80)
    else:
        logger.info("\nExecuting trades...")

        executor = AlpacaExecutor(
            api_key=settings.ALPACA_API_KEY,
            secret_key=settings.ALPACA_SECRET_KEY,
            paper=settings.ALPACA_PAPER,
        )

        planner = ExecutionPlanner()

        # Get current positions
        positions = client.get_all_positions()
        current_positions = {p.symbol: float(p.qty) for p in positions}

        # Generate trade plan
        trade_plan = planner.generate_buy_plan(
            target_allocations=dollar_allocations,
            current_positions=current_positions,
            price_map={},  # Executor will fetch current prices
        )

        logger.info(f"Generated {len(trade_plan)} trades")

        # Execute trades
        results = await executor.execute_trades(trade_plan)

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
        description="Automated investment script for Alpaca account",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry run
  python3 scripts/auto_invest.py --dry-run
  
  # Live with custom settings
  python3 scripts/auto_invest.py --min-cash 2000 --max-positions 15
  
  # Schedule daily via cron (10 AM on weekdays)
  0 10 * * 1-5 cd /path/to/bot && python3 scripts/auto_invest.py
        """,
    )

    parser.add_argument("--dry-run", action="store_true", help="Run without executing actual trades")

    parser.add_argument(
        "--min-cash",
        type=float,
        default=1000.0,
        help="Minimum cash threshold to trigger investment (default: 1000)",
    )

    parser.add_argument(
        "--max-positions",
        type=int,
        default=10,
        help="Maximum number of positions to hold (default: 10)",
    )

    parser.add_argument(
        "--cash-buffer-pct",
        type=float,
        default=10.0,
        help="Percentage of cash to keep as buffer (default: 10)",
    )

    args = parser.parse_args()

    # Run the workflow
    try:
        asyncio.run(
            run_investment_workflow(
                dry_run=args.dry_run,
                min_cash=Decimal(str(args.min_cash)),
                max_positions=args.max_positions,
                cash_buffer_pct=args.cash_buffer_pct,
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
