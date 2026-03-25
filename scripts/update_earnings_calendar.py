#!/usr/bin/env python3
"""
Update Earnings Calendar

Fetches the next 3-month earnings schedule from Alpha Vantage
(single API call) and saves it to data/earnings_calendar.csv.

Run daily or weekly — one free-tier call is sufficient.
"""
from __future__ import annotations

import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / '.env')

import logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

from src.data.alpha_vantage_fetcher import AlphaVantageFetcher
from src.data.universe_provider import UniverseProvider

_SAVE_PATH = Path(__file__).parent.parent / 'data' / 'earnings_calendar.csv'


def main() -> bool:
    api_key = os.getenv('ALPHA_VANTAGE_API_KEY')
    if not api_key:
        logger.error("ALPHA_VANTAGE_API_KEY not set — skipping earnings calendar update")
        return False

    symbols = UniverseProvider().get_universe()
    logger.info("Fetching earnings calendar for %d universe symbols ...", len(symbols))

    try:
        fetcher = AlphaVantageFetcher(api_key=api_key, premium=False)
        df = fetcher.fetch_earnings_calendar(
            symbols=symbols,
            horizon='3month',
            save_path=str(_SAVE_PATH),
        )
        if df.empty:
            logger.warning("No upcoming earnings found for universe symbols")
            return False

        logger.info("Saved %d earnings events to %s", len(df), _SAVE_PATH)
        logger.info("\nUpcoming earnings (next 14 days):")
        import pandas as pd
        from datetime import datetime, timedelta
        soon = df[df['reportDate'] <= datetime.now() + timedelta(days=14)]
        for _, row in soon.sort_values('reportDate').iterrows():
            logger.info("  %s  %s", row['reportDate'].date(), row['symbol'])
        return True

    except Exception as exc:
        logger.error("Failed to update earnings calendar: %s", exc)
        return False


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
