#!/usr/bin/env python3
"""
Test the multi-signal strategy engine.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

from services.strategy.multi_signal_engine import MultiSignalEngine, SignalWeights

print("=" * 80)
print("MULTI-SIGNAL STRATEGY TEST")
print("=" * 80)
print()

# Check for Alpha Vantage API key
alpha_vantage_key = os.getenv("ALPHA_VANTAGE_API_KEY")

if not alpha_vantage_key:
    print("⚠️  No Alpha Vantage API key found")
    print()
    print("To enable news sentiment analysis:")
    print("1. Get free API key: https://www.alphavantage.co/support/#api-key")
    print("2. Add to .env: ALPHA_VANTAGE_API_KEY=your_key")
    print()
    print("Running with 13F signals only...")
    print()
    fetch_news = False
else:
    print(f"✓ Alpha Vantage API key configured")
    print()
    fetch_news = True

# Initialize multi-signal engine
print("Initializing multi-signal engine...")
engine = MultiSignalEngine(
    signal_weights=SignalWeights(conviction_13f=0.70, news_sentiment=0.30),  # 70% weight on 13F  # 30% weight on news
    alpha_vantage_key=alpha_vantage_key,
)
print("✓ Engine initialized")
print()

# Compute scores
print("Computing multi-signal scores...")
print("This may take 30-60 seconds...")
print()

try:
    scores = engine.compute_multi_signal_scores(fetch_news=fetch_news)

    print(f"✓ Generated scores for {len(scores)} securities")
    print()

    # Show top 10
    print("TOP 10 RECOMMENDATIONS:")
    print("-" * 80)

    sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:10]

    for i, (symbol, score) in enumerate(sorted_scores, 1):
        print(f"{i:2d}. {symbol:6s} - Score: {score:.4f}")

    print()

    # Get detailed analysis for top 3
    if fetch_news and len(sorted_scores) >= 3:
        print("DETAILED ANALYSIS (Top 3):")
        print("-" * 80)

        top_3_symbols = [s for s, _ in sorted_scores[:3]]

        for symbol in top_3_symbols:
            print(f"\n{symbol}:")
            explanation = engine.explain_recommendation(symbol)
            print(
                f"  Conviction Score: {explanation['conviction_score']:.4f} (weight: {explanation['conviction_weight']:.0%})"
            )
            print(
                f"  Sentiment Score:  {explanation['sentiment_score']:.4f} (weight: {explanation['sentiment_weight']:.0%})"
            )
            print(f"  Articles Analyzed: {explanation['article_count']}")
            print(f"  Explanation: {explanation['explanation']}")

            if explanation["recent_headlines"]:
                print(f"  Recent Headlines:")
                for headline in explanation["recent_headlines"][:3]:
                    sentiment_emoji = "📈" if headline["sentiment"] > 0 else "📉" if headline["sentiment"] < 0 else "➡️"
                    print(f"    {sentiment_emoji} {headline['title'][:70]}...")

    print()
    print("=" * 80)
    print("✅ MULTI-SIGNAL ANALYSIS COMPLETE")
    print("=" * 80)

except Exception as e:
    print(f"✗ Error: {e}")
    import traceback

    traceback.print_exc()
    sys.exit(1)
