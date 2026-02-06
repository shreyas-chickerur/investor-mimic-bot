#!/usr/bin/env python3
"""
Emergency script to close all positions via Alpaca API.

Usage:
    python scripts/close_all_positions.py [--confirm]

Without --confirm, runs in dry-run mode showing what would be closed.
"""
import os
import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


def close_all_positions(confirm: bool = False):
    """Close all open positions via Alpaca."""
    from alpaca.trading.client import TradingClient

    api_key = os.getenv('ALPACA_API_KEY')
    secret_key = os.getenv('ALPACA_SECRET_KEY')
    paper = os.getenv('ALPACA_PAPER', 'true').lower() == 'true'

    if not api_key or not secret_key:
        logger.error("❌ ALPACA_API_KEY and ALPACA_SECRET_KEY must be set")
        return False

    client = TradingClient(api_key, secret_key, paper=paper)
    positions = client.get_all_positions()

    if not positions:
        logger.info("✅ No open positions to close")
        return True

    logger.info(f"{'⚠️  DRY RUN — ' if not confirm else ''}Found {len(positions)} open positions:")
    for pos in positions:
        logger.info(f"  {pos.symbol}: {pos.qty} shares @ ${float(pos.avg_entry_price):.2f}")

    if not confirm:
        logger.info("\nRun with --confirm to actually close all positions")
        return True

    logger.info("\n🔴 Closing all positions...")
    client.close_all_positions(cancel_orders=True)
    logger.info("✅ All positions closed and open orders cancelled")
    return True


if __name__ == "__main__":
    confirm = '--confirm' in sys.argv
    success = close_all_positions(confirm=confirm)
    sys.exit(0 if success else 1)
