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
import re
import xml.etree.ElementTree as ET  # nosec B405 - source is Google News RSS over HTTPS
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any

import requests

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
    logger.warning(
        "vaderSentiment not installed — falling back to keyword scoring. "
        "Run: pip install vaderSentiment"
    )

_GNEWS_URL = "https://news.google.com/rss/search"
_YF_SEARCH_URL = "https://query1.finance.yahoo.com/v1/finance/search"
_YF_SEARCH_URL_2 = "https://query2.finance.yahoo.com/v1/finance/search"
_REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Accept": "application/json, text/xml, */*",
}

# Neutral defaults when no data is available
_NEUTRAL_CONTEXT: dict[str, Any] = {
    "score": 0.5,
    "headlines": [],  # legacy: list[str] — kept for backward compat with email/tests
    "articles": [],  # rich: list[dict] with title/source/age/link/quality
    "article_count": 0,
}

# ---------------------------------------------------------------------------
# Junk headline filter — drops the SEO/quote-page noise that Google News loves
# ---------------------------------------------------------------------------
_JUNK_PATTERNS = [
    # Quote-page / chart titles ("V Stock Price, Quote & Chart | VISA INC...")
    re.compile(r"\bstock price\b.*\bquote\b", re.I),
    re.compile(r"\bquote\b.*\bchart\b", re.I),
    re.compile(r"\bprice,?\s+quote\b", re.I),
    # 13F filings / share-acquisition algo filings
    re.compile(r"\bacquires\s+(shares|[\d,]+\s+shares)\b", re.I),
    re.compile(r"\bsells\s+[\d,]+\s+shares\b", re.I),
    re.compile(r"\bposition\s+(boosted|trimmed|cut|reduced|raised|lowered)\b", re.I),
    re.compile(r"\bsells?\s+[\d,]+\s+shares\s+of\b", re.I),
    re.compile(r"\bbuys?\s+[\d,]+\s+shares\s+of\b", re.I),
    re.compile(r"\b(trims?|adds?\s+to|reduces?|increases?)\s+stock\s+holdings?\b", re.I),
    re.compile(r"\b(trims?|reduces?|cuts?)\s+(stake|position|holdings?)\s+in\b", re.I),
    re.compile(r"\bhas\s+\$[\d.,]+\s+(million|billion)\s+(holdings|stake|position)\b", re.I),
    # Listicle / clickbait
    re.compile(r"\bbest\s+stocks?\s+(under|to|for|in)\b", re.I),
    re.compile(r"\btop\s+\d+\s+stocks?\b", re.I),
    re.compile(r"\bstocks?\s+to\s+(buy|watch|own)\s+now\b", re.I),
    re.compile(r"\bforget\b.*:\s*", re.I),  # "Forget X: Two Stocks To Buy Now"
    # Pure analyst-target / Wall Street question titles
    re.compile(r"^what\s+are\s+wall\s+street\s+analysts", re.I),
    re.compile(r"^should\s+you\s+buy\b", re.I),
    re.compile(r"\b(limbo|lurking|sleeping)\s+with\s+", re.I),
]

# Quality keywords — boost real news that affects positions
_QUALITY_KEYWORDS_HIGH = re.compile(
    r"\b(earnings|beats?|misses?|guidance|revenue|"
    r"raised|cuts?|downgrade|upgrade|"
    r"announces?|launches?|acquires?|merger|partnership|deal|"
    r"lawsuit|settlement|recall|fda|approval|"
    r"ceo|resigns?|appointed|fired|"
    r"dividend|buyback|split|"
    r"sec\s+(filing|charges?)|"
    r"breaking|exclusive)\b",
    re.I,
)
_QUALITY_KEYWORDS_LOW = re.compile(
    r"\b(opinion|prediction|forget|playing|limbo|target\s+price|" r"investors\s+playing|quote)\b",
    re.I,
)


def _is_junk_headline(title: str) -> bool:
    """Return True if the headline is SEO/quote-page noise we should drop."""
    if not title or len(title.strip()) < 12:
        return True
    return any(p.search(title) for p in _JUNK_PATTERNS)


def _quality_score(title: str) -> float:
    """0..1 quality score: higher means more likely to be substantive news."""
    if not title:
        return 0.0
    score = 0.5
    high_hits = len(_QUALITY_KEYWORDS_HIGH.findall(title))
    low_hits = len(_QUALITY_KEYWORDS_LOW.findall(title))
    score += min(0.4, high_hits * 0.15)
    score -= min(0.4, low_hits * 0.15)
    # Penalize all-caps screaming headlines
    if title.isupper():
        score -= 0.1
    # Penalize ticker/exchange-only chrome ("(NYSE:V)" appearing in middle)
    if re.search(r"\([A-Z]+:[A-Z]+\)", title):
        score -= 0.05
    return max(0.0, min(1.0, score))


def _format_age(pub_dt: datetime | None) -> str:
    """Human-readable age: '2h ago', '3d ago', etc."""
    if pub_dt is None:
        return ""
    now = datetime.now(timezone.utc)
    if pub_dt.tzinfo is None:
        pub_dt = pub_dt.replace(tzinfo=timezone.utc)
    delta = now - pub_dt
    secs = int(delta.total_seconds())
    if secs < 0:
        return "just now"
    if secs < 3600:
        m = max(1, secs // 60)
        return f"{m}m ago"
    if secs < 86400:
        h = secs // 3600
        return f"{h}h ago"
    d = secs // 86400
    return f"{d}d ago"


# Thresholds for signal modification
POSITIVE_THRESHOLD = 0.62  # score above this → boost confidence
NEGATIVE_THRESHOLD = 0.38  # score below this → suppress confidence
SUPPRESS_THRESHOLD = 0.20  # score below this → drop BUY signal entirely
BOOST_MULT = 1.15  # multiply confidence when news is positive
SUPPRESS_MULT = 0.80  # multiply confidence when news is negative


# ---------------------------------------------------------------------------
# Low-level news fetch (single symbol) — direct HTTP, no yfinance
# ---------------------------------------------------------------------------
def _score_title_keywords(title: str) -> float:
    """Fallback keyword scorer when VADER is not available."""
    t = title.lower()
    pos = sum(
        1
        for w in [
            "beat",
            "surge",
            "strong",
            "growth",
            "upgrade",
            "record",
            "profit",
            "raised",
            "expands",
            "rally",
        ]
        if w in t
    )
    neg = sum(
        1
        for w in [
            "miss",
            "drop",
            "weak",
            "downgrade",
            "lawsuit",
            "loss",
            "cut",
            "recall",
            "fraud",
            "crash",
        ]
        if w in t
    )
    return max(0.0, min(1.0, 0.5 + (pos - neg) * 0.1))


def _score_title(title: str) -> float:
    """Score a single headline: returns compound in [-1, 1] mapped to [0, 1]."""
    if _VADER_AVAILABLE and _analyzer is not None:
        compound = float(_analyzer.polarity_scores(title)["compound"])
        return (compound + 1.0) / 2.0  # -1..1 → 0..1
    return _score_title_keywords(title)


def _score_with_description(title: str, description: str) -> float:
    """Score title + article description/summary together.

    RSS <description> fields contain a 1-3 sentence article snippet that often
    contradicts an attention-grabbing headline.  Combining both gives a more
    accurate sentiment signal.  The title gets 60% weight (editorial intent)
    and the description gets 40% weight (article body context).
    """
    title_score = _score_title(title)
    if not description or not description.strip():
        return title_score
    desc_score = _score_title(description.strip())
    return round(0.60 * title_score + 0.40 * desc_score, 4)


def _fetch_via_google_rss(symbol: str, max_articles: int = 15) -> list[dict]:
    """
    Fetch articles via Google News RSS (no auth, no rate limit, stdlib XML).

    Returns list of dicts: {title, source, link, pub_dt, age, quality}.
    Junk headlines (SEO/quote pages/13F filings) are filtered out here.
    """
    params = {
        "q": f"{symbol} stock",
        "hl": "en-US",
        "gl": "US",
        "ceid": "US:en",
    }
    try:
        resp = requests.get(_GNEWS_URL, params=params, headers=_REQUEST_HEADERS, timeout=8)
        if resp.status_code != 200:
            return []
        root = ET.fromstring(
            resp.text
        )  # nosec B314 - trusted Google News RSS feed; no DTDs or external entities
        articles: list[dict] = []
        for item in root.findall(".//item")[:max_articles]:
            raw_title = (item.findtext("title") or "").strip()
            # Google News titles end with " - Source Name"; split it out
            source = ""
            title = raw_title
            if " - " in raw_title:
                title, source = raw_title.rsplit(" - ", 1)
                title = title.strip()
                source = source.strip()
            # Prefer explicit <source> tag if present
            src_el = item.find("source")
            if src_el is not None and (src_el.text or "").strip():
                source = (src_el.text or "").strip()

            if not title or _is_junk_headline(title):
                continue

            link = (item.findtext("link") or "").strip()
            pub_str = (item.findtext("pubDate") or "").strip()
            pub_dt: datetime | None = None
            if pub_str:
                try:
                    pub_dt = parsedate_to_datetime(pub_str)
                except (TypeError, ValueError):
                    pub_dt = None

            # Capture RSS <description> — typically a 1-3 sentence article snippet.
            # Stripping HTML tags to get plain text for VADER scoring.
            raw_desc = (item.findtext("description") or "").strip()
            # Remove simple HTML tags from the description snippet
            import re as _re

            description = _re.sub(r"<[^>]+>", " ", raw_desc).strip()

            articles.append(
                {
                    "title": title,
                    "description": description,
                    "source": source or "Google News",
                    "link": link,
                    "pub_dt": pub_dt.isoformat() if pub_dt else None,
                    "age": _format_age(pub_dt),
                    "quality": _quality_score(title),
                }
            )
        return articles
    except Exception as exc:
        logger.debug("Google RSS fetch failed for %s: %s", symbol, exc)
        return []


def _fetch_via_yf_search(symbol: str, max_articles: int = 10) -> list[dict]:
    """
    Fallback: Yahoo Finance JSON search API.
    May be rate-limited (429) under heavy parallel use. Returns list of dicts
    with same shape as _fetch_via_google_rss for consistent downstream handling.
    """
    params: dict[str, str] = {
        "q": symbol,
        "newsCount": str(max_articles),
        "enableFuzzyQuery": "false",
        "lang": "en-US",
        "region": "US",
    }
    for url in (_YF_SEARCH_URL, _YF_SEARCH_URL_2):
        try:
            resp = requests.get(url, params=params, headers=_REQUEST_HEADERS, timeout=8)
            if resp.status_code != 200:
                continue
            items = resp.json().get("news", [])
            articles: list[dict] = []
            for item in items:
                title = (item.get("title") or "").strip()
                if not title or _is_junk_headline(title):
                    continue
                publisher = (item.get("publisher") or "").strip() or "Yahoo Finance"
                link = (item.get("link") or item.get("url") or "").strip()
                pub_ts = item.get("providerPublishTime")
                pub_dt = None
                if isinstance(pub_ts, (int, float)):
                    try:
                        pub_dt = datetime.fromtimestamp(float(pub_ts), tz=timezone.utc)
                    except (ValueError, OSError):
                        pub_dt = None
                articles.append(
                    {
                        "title": title,
                        "source": publisher,
                        "link": link,
                        "pub_dt": pub_dt.isoformat() if pub_dt else None,
                        "age": _format_age(pub_dt),
                        "quality": _quality_score(title),
                    }
                )
            if articles:
                return articles
        except Exception as exc:
            logger.debug("YF search fetch failed for %s via %s: %s", symbol, url, exc)
    return []


def _fetch_articles_http(symbol: str, max_articles: int = 15) -> list[dict]:
    """
    Fetch structured news articles for a symbol.
    Primary: Google News RSS (reliable, no auth, includes publisher + date).
    Fallback: Yahoo Finance JSON search API.
    """
    articles = _fetch_via_google_rss(symbol, max_articles)
    if articles:
        return articles
    logger.debug("Google RSS returned no results for %s, trying YF search", symbol)
    return _fetch_via_yf_search(symbol, max_articles)


def fetch_symbol_news(symbol: str, max_articles: int = 15) -> dict:
    """Fetch news for one symbol and return sentiment context dict.

    Returns:
      {
        score: float in [0, 1] — average sentiment of surviving headlines,
        headlines: list[str] — top-3 titles (legacy field for back-compat),
        articles: list[dict] — top articles with title/source/link/age/quality,
        article_count: int — number of articles after junk filtering.
      }
    """
    try:
        articles = _fetch_articles_http(symbol, max_articles)
        if not articles:
            return {**_NEUTRAL_CONTEXT, "headlines": [], "articles": []}

        # Score sentiment: use title + description (RSS snippet) when available
        # for a more accurate signal than headline-only scoring.
        for art in articles:
            art["sentiment"] = _score_with_description(art["title"], art.get("description", ""))

        # Composite rank: quality dominates, sentiment magnitude is the tie-breaker.
        # This pushes substantive earnings/guidance/upgrade stories above
        # "Why is X soaring?" filler even if filler has stronger sentiment.
        articles.sort(
            key=lambda a: (a["quality"], abs(a["sentiment"] - 0.5)),
            reverse=True,
        )

        sentiments = [a["sentiment"] for a in articles]
        avg_score = sum(sentiments) / len(sentiments)

        top_articles = articles[:3]  # only keep what we'll display
        return {
            "score": round(avg_score, 4),
            "headlines": [a["title"] for a in top_articles],
            "articles": top_articles,
            "article_count": len(articles),
        }
    except Exception as exc:
        logger.debug("News fetch failed for %s: %s", symbol, exc)
        return {**_NEUTRAL_CONTEXT, "headlines": [], "articles": []}


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
        self._cache: dict[str, dict[str, Any]] = {}
        self._cache_date: date | None = None

    def _invalidate_if_stale(self):
        today = date.today()
        if self._cache_date != today:
            self._cache.clear()
            self._cache_date = today

    def get_sentiment_context(self, symbol: str) -> dict[str, Any]:
        """Return sentiment context dict for one symbol (cached)."""
        self._invalidate_if_stale()
        if symbol not in self._cache:
            self._cache[symbol] = fetch_symbol_news(symbol)
        return self._cache[symbol]

    def get_sentiment_score(self, symbol: str) -> float:
        """Return sentiment score [0,1] for one symbol (cached)."""
        return float(self.get_sentiment_context(symbol).get("score", 0.5))

    def fetch_batch(self, symbols: list[str]) -> dict[str, dict[str, Any]]:
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

    def __init__(self) -> None:
        self.provider: NewsSentimentProvider = NewsSentimentProvider()

    def fetch_for_symbols(self, symbols: list[str]) -> dict[str, dict[str, Any]]:
        """Pre-fetch sentiment for a list of symbols."""
        return self.provider.fetch_batch(symbols)

    def get_usage_summary(self) -> dict[str, Any]:
        """Return usage summary compatible with execution engine expectations."""
        return {"provider": "news_sentiment_http", "requests": len(self.provider._cache)}

    def apply(self, signals: list[dict], sentiment_map: dict[str, dict]) -> list[dict]:
        """
        Modify signal confidences in-place based on sentiment.
        Returns filtered list (strong negative BUY signals dropped).
        """
        if not sentiment_map:
            return signals

        result = []
        for sig in signals:
            symbol = sig.get("symbol", "")
            context = sentiment_map.get(symbol, _NEUTRAL_CONTEXT)
            score = context.get("score", 0.5)
            headlines = context.get("headlines", [])

            action = sig.get("action", "BUY")
            original_conf = sig.get("confidence", 0.5)

            if score > POSITIVE_THRESHOLD:
                sig = dict(sig)  # shallow copy to avoid mutating original
                sig["confidence"] = min(1.0, original_conf * BOOST_MULT)
                if headlines:
                    sig["reasoning"] = sig.get("reasoning", "") + f" | news +{score:.2f}"
                    sig["news_headlines"] = headlines
                result.append(sig)

            elif score < SUPPRESS_THRESHOLD and action == "BUY":
                # Strong negative news — drop BUY signal entirely
                logger.info(
                    "NewsFilter: dropping BUY %s (news score=%.2f, headline: %s)",
                    symbol,
                    score,
                    headlines[0] if headlines else "N/A",
                )
                # Don't append — signal is dropped

            elif score < NEGATIVE_THRESHOLD:
                sig = dict(sig)
                sig["confidence"] = original_conf * SUPPRESS_MULT
                if headlines:
                    sig["reasoning"] = sig.get("reasoning", "") + f" | news -{score:.2f}"
                    sig["news_headlines"] = headlines
                result.append(sig)

            else:
                result.append(sig)

        return result
