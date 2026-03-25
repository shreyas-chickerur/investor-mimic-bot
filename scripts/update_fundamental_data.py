#!/usr/bin/env python3
"""
Update Fundamental Data

Fetches P/E ratio, ROE, and debt-to-equity for each universe symbol
from Alpha Vantage OVERVIEW endpoint (1 call per symbol, free tier = 25/day).

Saves to data/fundamentals.json. Run weekly — data changes quarterly.
Factor Momentum will automatically upgrade to the 8-factor model once
this file exists.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / '.env')

import logging
import requests

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

from src.data.universe_provider import UniverseProvider

_SAVE_PATH = Path(__file__).parent.parent / 'data' / 'fundamentals.json'
_AV_BASE = 'https://www.alphavantage.co/query'
_FIELDS = {
    'PERatio': 'pe_ratio',
    'ReturnOnEquityTTM': 'roe',
    'DebtToEquityRatio': 'debt_to_equity',
    'PEGRatio': 'peg_ratio',
    'PriceToBookRatio': 'price_to_book',
    'EPS': 'eps',
    'RevenueTTM': 'revenue_ttm',
    'GrossProfitTTM': 'gross_profit_ttm',
    'MarketCapitalization': 'market_cap',
}


def _fetch_overview(symbol: str, api_key: str) -> dict:
    params = {'function': 'OVERVIEW', 'symbol': symbol, 'apikey': api_key}
    try:
        resp = requests.get(_AV_BASE, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        if 'Symbol' not in data:
            logger.warning("  %s: no data returned (%s)", symbol, list(data.keys())[:3])
            return {}
        result = {}
        for av_key, our_key in _FIELDS.items():
            val = data.get(av_key)
            if val and val not in ('None', '-', ''):
                try:
                    result[our_key] = float(val)
                except (ValueError, TypeError):
                    pass
        return result
    except Exception as exc:
        logger.error("  %s: request failed — %s", symbol, exc)
        return {}


def main() -> bool:
    api_key = os.getenv('ALPHA_VANTAGE_API_KEY')
    if not api_key:
        logger.error("ALPHA_VANTAGE_API_KEY not set — skipping fundamental update")
        return False

    universe = UniverseProvider()
    # Only fetch tradeable stocks, not sector ETFs
    symbols = [s for s in universe.get_universe()
               if s not in UniverseProvider.BENCHMARK_SYMBOLS]

    # Load existing data so we only re-fetch stale/missing symbols
    existing: dict = {}
    if _SAVE_PATH.exists():
        try:
            with open(_SAVE_PATH) as f:
                existing = json.load(f)
            logger.info("Loaded %d existing fundamental records", len(existing))
        except Exception:
            existing = {}

    fundamentals = dict(existing)
    fetched, skipped, failed = 0, 0, 0

    logger.info("Fetching fundamentals for %d symbols (free tier: ~12s delay per call) ...",
                len(symbols))

    for i, sym in enumerate(symbols, 1):
        # Free tier: 5 calls/min → 12s between calls
        if i > 1:
            time.sleep(12)

        logger.info("[%d/%d] %s ...", i, len(symbols), sym)
        data = _fetch_overview(sym, api_key)
        if data:
            fundamentals[sym] = data
            fetched += 1
            logger.info("  -> PE=%.1f  ROE=%.3f  D/E=%.2f",
                        data.get('pe_ratio', 0), data.get('roe', 0),
                        data.get('debt_to_equity', 0))
        else:
            failed += 1

    _SAVE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(_SAVE_PATH, 'w') as f:
        json.dump(fundamentals, f, indent=2)

    logger.info("\nDone: %d fetched, %d skipped, %d failed → saved to %s",
                fetched, skipped, failed, _SAVE_PATH)
    return True


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
