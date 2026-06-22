#!/usr/bin/env python3
"""
Record point-in-time news sentiment (EXP-2026-06-22-news-pit-recording).

News Sentiment scores LIVE Google-News RSS inside generate_signals, so a
backtest applies today's scores to historical prices — pure look-ahead, which
is exactly why the strategy is disabled and unvalidatable offline. This script
captures each symbol's sentiment WITH the as-of date so a leak-free history
accumulates. Once enough has built up (see the experiment's success criterion),
the strategy can be backtested honestly with a t+1 execution lag.

Idempotent per day: re-running overwrites the same (asof_date, symbol) rows.

Usage:
    python3 scripts/record_sentiment.py [--db trading.db] [--asof YYYY-MM-DD]
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="trading.db")
    ap.add_argument("--asof", default=datetime.now().strftime("%Y-%m-%d"))
    ap.add_argument("--limit", type=int, default=0, help="cap symbols (for testing)")
    args = ap.parse_args()

    from src.core.database import TradingDatabase  # ensures the table exists
    from src.data.universe_provider import UniverseProvider
    from src.utils.news_sentiment import NewsSentimentProvider

    TradingDatabase(args.db)  # _init_database creates sentiment_history if absent

    symbols = list(UniverseProvider().get_universe())
    if args.limit:
        symbols = symbols[: args.limit]

    provider = NewsSentimentProvider()
    contexts = provider.fetch_batch(symbols)

    rows = []
    for sym, ctx in contexts.items():
        score = float(ctx.get("score", 0.5))
        n = len(ctx.get("headlines", []) or ctx.get("articles", []) or [])
        rows.append((args.asof, sym, score, n))

    con = sqlite3.connect(args.db, timeout=10)
    con.executemany(
        "INSERT OR REPLACE INTO sentiment_history "
        "(asof_date, symbol, score, headline_count) VALUES (?, ?, ?, ?)",
        rows,
    )
    con.commit()
    distinct = con.execute("SELECT COUNT(DISTINCT asof_date) FROM sentiment_history").fetchone()[0]
    con.close()

    print(
        f"Recorded {len(rows)} sentiment rows for {args.asof}; "
        f"sentiment_history now spans {distinct} distinct date(s)."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
