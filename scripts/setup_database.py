#!/usr/bin/env python3
"""
Initialize trading database for CI/CD and fresh installations.
Delegates entirely to TradingDatabase._init_database() — the single source
of truth for the schema — so this script never drifts out of sync.
Safe to run multiple times (idempotent).
"""
import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.database import TradingDatabase


def init_database(db_path: str = 'trading.db') -> bool:
    """
    Initialize all trading database tables by delegating to TradingDatabase.

    Args:
        db_path: Path to the SQLite database file.

    Returns:
        True on success.
    """
    print(f'Initializing database: {db_path}')
    # Instantiating TradingDatabase calls _init_database(), which creates
    # every table (strategies, signals, trades, positions, broker_state,
    # system_state, signal_funnel, signal_rejections, order_intents) and
    # all indexes via CREATE TABLE IF NOT EXISTS — fully idempotent.
    TradingDatabase(db_path=db_path)
    print(f'✅ Database initialized successfully: {db_path}')
    print('   Tables: strategies, signals, trades, positions, broker_state,')
    print('           system_state, signal_funnel, signal_rejections, order_intents')
    return True


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Initialize trading database')
    parser.add_argument('--db', default='trading.db', help='Database file path')
    args = parser.parse_args()

    success = init_database(args.db)
    sys.exit(0 if success else 1)
