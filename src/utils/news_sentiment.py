#!/usr/bin/env python3
"""
News Sentiment Module
Fetches recent headlines via Yahoo Finance JSON API (direct HTTP, no yfinance).
Scores headlines using VADER; falls back to keyword scoring if VADER is absent.

Usage:
    from src.utils.news_sentiment import NewsSignalFilter, NewsSentimentProvider
    nf = NewsSignalFilter()
    sentiment_map = nf.fetch_for_symbols(['AAPL', 'MSFT'])
    signals = nf.apply(signals, sentiment_map)
"""
from __future__ import annotations

import logging
import requests
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional dependency guard — VADER (pure-Python, no binary deps)
# ---------------------------------------------------------------------------
try:
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
    _VADER_AVAILABLE = True
    _analyzer = SentimentIntensityAnalyzer()
except ImportError:
    _VADER_AVAILABLE = False
    _analyzer = None  # type: ignore
    logger.warning("vaderSentiment not installed — falling back to keyword scoring. "
                   "Run: pip install vaderSentiment")

_GNEWS_URL = "https://news.google.com/rss/search"
_YF_SEARCH_URL = "https://query1.finance.yahoo.com/v1/finance/search"
_YF_SEARCH_URL_2 = "https://query2.finance.yahoo.com/v1/finance/search"
_REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Accept": "application/json, text/xml, */*",
}

# Neutral defaults when no data is available
_NEUTRAL_CONTEXT: Dict = {'score': 0.5, 'headlines': [], 'article_count': 0}

# Thresholds for signal modification
POSITIVE_THRESHOLD = 0.62   # score above this → boost confidence
NEGATIVE_THRESHOLD = 0.38   # score below this → suppress confidence
SUPPRESS_THRESHOLD = 0.25   # score below this → drop BUY signal entirely
BOOST_MULT = 1.15            # multiply confidence when news is positive
SUPPRESS_MULT = 0.80         # multiply confidence when news is negative


# ---------------------------------------------------------------------------
# Low-level news fetch (single symbol) — direct HTTP, no yfinance
# ---------------------------------------------------------------------------
def _score_title_keywords(title: str) -> float:
    """Fallback keyword scorer when VADER is not available."""
    t = title.lower()
    pos = sum(1 for w in ['beat', 'surge', 'strong', 'growth', 'upgrade', 'record',
                           'profit', 'raised', 'expands', 'rally'] if w in t)
    neg = sum(1 for w in ['miss', 'drop', 'weak', 'downgrade', 'lawsuit', 'loss',
                           'cut', 'recall', 'fraud', 'crash'] if w in t)
    return max(0.0, min(1.0, 0.5 + (pos - neg) * 0.1))


def _score_title(title: str) -> float:
    """Score a single headline: returns compound in [-1, 1] mapped to [0, 1]."""
    if _VADER_AVAILABLE and _analyzer is not None:
        compound = _analyzer.polarity_scores(title)['compound']
        return (compound + 1.0) / 2.0  # -1..1 → 0..1
    return _score_title_keywords(title)


def _fetch_via_google_rss(symbol: str, max_articles: int = 10) -> List[str]:
    """
    Fetch headlines via Google News RSS (no auth, no rate limit, stdlib XML).
    Query: '<symbol> stock' to keep results equity-focused.
    """
    params = {
        'q': f'{symbol} stock',
        'hl': 'en-US',
        'gl': 'US',
        'ceid': 'US:en',
    }
    try:
        resp = requests.get(_GNEWS_URL, params=params, headers=_REQUEST_HEADERS, timeout=8)
        if resp.status_code != 200:
            return []
        root = ET.fromstring(resp.text)
        titles = []
        for item in root.findall('.//item')[:max_articles]:
            title = (item.findtext('title') or '').strip()
            # Google News titles often end with " - Source Name"; strip the source suffix
            if ' - ' in title:
                title = title.rsplit(' - ', 1)[0].strip()
            if title:
                titles.append(title)
        return titles
    except Exception as exc:
        logger.debug("Google RSS fetch failed for %s: %s", symbol, exc)
        return []


def _fetch_via_yf_search(symbol: str, max_articles: int = 10) -> List[str]:
    """
    Fallback: Yahoo Finance JSON search API.
    May be rate-limited (429) under heavy parallel use.
    """
    params = {
        'q': symbol,
        'newsCount': max_articles,
        'enableFuzzyQuery': 'false',
        'lang': 'en-US',
        'region': 'US',
    }
    for url in (_YF_SEARCH_URL, _YF_SEARCH_URL_2):
        try:
            resp = requests.get(url, params=params, headers=_REQUEST_HEADERS, timeout=8)
            if resp.status_code != 200:
                continue
            items = resp.json().get('news', [])
            return [item.get('title', '').strip() for item in items if item.get('title', '').strip()]
        except Exception as exc:
            logger.debug("YF search fetch failed for %s via %s: %s", symbol, url, exc)
    return []


def _fetch_headlines_http(symbol: str, max_articles: int = 10) -> List[str]:
    """
    Fetch news headlines for a symbol.
    Primary: Google News RSS (reliable, no auth).
    Fallback: Yahoo Finance JSON search API.
    """
    headlines = _fetch_via_google_rss(symbol, max_articles)
    if headlines:
        return headlines
    logger.debug("Google RSS returned no results for %s, trying YF search", symbol)
    return _fetch_via_yf_search(symbol, max_articles)


def fetch_symbol_news(symbol: str, max_articles: int = 10) -> Dict:
    """Fetch news for one symbol and return sentiment context dict."""
    try:
        headlines = _fetch_headlines_http(symbol, max_articles)

        if not headlines:
            return {'score': 0.5, 'headlines': [], 'article_count': 0}

        scores = [_score_title(t) for t in headlines]
        avg_score = sum(scores) / len(scores)
        return {
            'score': round(avg_score, 4),
            'headlines': headlines[:3],
            'article_count': len(scores),
        }
    except Exception as exc:
        logger.debug("News fetch failed for %s: %s", symbol, exc)
        return _NEUTRAL_CONTEXT.copy()


# ---------------------------------------------------------------------------
# Batch fetcher with caching
# ---------------------------------------------------------------------------
class NewsSentimentProvider:
    """
    Batch-fetch news sentiment for multiple symbols.

    Results are cached for the calendar day to avoid redundant API calls
    during a single trading session.
    """

    def __init__(self, max_workers: int = 8, per_symbol_timeout: float = 6.0):
        self.max_workers = max_workers
        self.per_symbol_timeout = per_symbol_timeout
        self._cache: Dict[str, Dict] = {}
        self._cache_date: Optional[date] = None

    def _invalidate_if_stale(self):
        today = date.today()
        if self._cache_date != today:
            self._cache.clear()
            self._cache_date = today

    def get_sentiment_context(self, symbol: str) -> Dict:
        """Return sentiment context dict for one symbol (cached)."""
        self._invalidate_if_stale()
        if symbol not in self._cache:
            self._cache[symbol] = fetch_symbol_news(symbol)
        return self._cache[symbol]

    def get_sentiment_score(self, symbol: str) -> float:
        """Return sentiment score [0,1] for one symbol (cached)."""
        return self.get_sentiment_context(symbol).get('score', 0.5)

    def fetch_batch(self, symbols: List[str]) -> Dict[str, Dict]:
        """
        Fetch sentiment for a list of symbols in parallel.
        Returns dict of {symbol: context}.
        """
        self._invalidate_if_stale()
        to_fetch = [s for s in symbols if s not in self._cache]

        if not to_fetch:
            return {s: self._cache[s] for s in symbols if s in self._cache}

        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            futures = {pool.submit(fetch_symbol_news, sym): sym for sym in to_fetch}
            for future in as_completed(futures, timeout=self.per_symbol_timeout * len(to_fetch)):
                sym = futures[future]
                try:
                    self._cache[sym] = future.result(timeout=self.per_symbol_timeout)
                except Exception:
                    self._cache[sym] = _NEUTRAL_CONTEXT.copy()

        return {s: self._cache.get(s, _NEUTRAL_CONTEXT.copy()) for s in symbols}


# ---------------------------------------------------------------------------
# Signal filter / confidence modifier
# ---------------------------------------------------------------------------
class NewsSignalFilter:
    """
    Applies news sentiment as a confidence modifier to a list of signals.

    Rules:
      - score > POSITIVE_THRESHOLD → boost confidence × 1.15
      - score < NEGATIVE_THRESHOLD → suppress confidence × 0.80
      - score < SUPPRESS_THRESHOLD AND action == BUY → drop signal entirely
    """

    def __init__(self):
        self.provider = NewsSentimentProvider()

    def fetch_for_symbols(self, symbols: List[str]) -> Dict[str, Dict]:
        """Pre-fetch sentiment for a list of symbols."""
        return self.provider.fetch_batch(symbols)

    def apply(self, signals: List[Dict], sentiment_map: Dict[str, Dict]) -> List[Dict]:
        """
        Modify signal confidences in-place based on sentiment.
        Returns filtered list (strong negative BUY signals dropped).
        """
        if not sentiment_map:
            return signals

        result = []
        for sig in signals:
            symbol = sig.get('symbol', '')
            context = sentiment_map.get(symbol, _NEUTRAL_CONTEXT)
            score = context.get('score', 0.5)
            headlines = context.get('headlines', [])

            action = sig.get('action', 'BUY')
            original_conf = sig.get('confidence', 0.5)

            if score > POSITIVE_THRESHOLD:
                sig = dict(sig)  # shallow copy to avoid mutating original
                sig['confidence'] = min(1.0, original_conf * BOOST_MULT)
                if headlines:
                    sig['reasoning'] = sig.get('reasoning', '') + f' | news +{score:.2f}'
                    sig['news_headlines'] = headlines
                result.append(sig)

            elif score < SUPPRESS_THRESHOLD and action == 'BUY':
                # Strong negative news — drop BUY signal entirely
                logger.info("NewsFilter: dropping BUY %s (news score=%.2f, headline: %s)",
                            symbol, score, headlines[0] if headlines else 'N/A')
                # Don't append — signal is dropped

            elif score < NEGATIVE_THRESHOLD:
                sig = dict(sig)
                sig['confidence'] = original_conf * SUPPRESS_MULT
                if headlines:
                    sig['reasoning'] = sig.get('reasoning', '') + f' | news -{score:.2f}'
                    sig['news_headlines'] = headlines
                result.append(sig)

            else:
                result.append(sig)

        return result
