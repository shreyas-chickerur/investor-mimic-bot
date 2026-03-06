#!/usr/bin/env python3
"""Quick news sentiment test — called by `make news-test`."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.news_sentiment import NewsSignalFilter

SYMBOLS = ['AAPL', 'MSFT', 'NVDA', 'GOOGL', 'AMZN', 'META']

nf = NewsSignalFilter()
print("Fetching news sentiment for:", ', '.join(SYMBOLS))
print()
results = nf.fetch_for_symbols(SYMBOLS)
for sym, ctx in results.items():
    score = ctx.get('score', 0.5)
    articles = ctx.get('article_count', 0)
    if score > 0.62:
        label = '🟢 POSITIVE'
    elif score < 0.38:
        label = '🔴 NEGATIVE'
    else:
        label = '⚪ NEUTRAL'
    print(f"{sym:6s}  {label}  score={score:.3f}  articles={articles}")
    for h in ctx.get('headlines', [])[:2]:
        print(f"         → {h[:90]}")
print()
print("✅ News test complete")
