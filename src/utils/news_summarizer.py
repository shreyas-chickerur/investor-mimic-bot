#!/usr/bin/env python3
"""
News Summarizer

Generates a one-sentence "why it matters" line for each held position by
condensing the top headlines and our position context (shares held, today's
$/% move, sentiment) through gpt-4o-mini.

Falls back gracefully to a heuristic template when:
  - OPENAI_API_KEY is not set
  - the openai package is not installed
  - the API call fails or times out

Cached to disk by date+symbol so we make at most one API call per
ticker per trading day. Cost is ~$0.01/day for ~15 tickers.

Usage:
    from src.utils.news_summarizer import NewsSummarizer
    s = NewsSummarizer()
    line = s.summarize_for_position(
        symbol="AAPL",
        articles=[{"title": "...", "source": "Reuters"}, ...],
        position={"qty": 47, "today_pnl": 23.10, "today_pct": 2.1},
        sentiment_score=0.72,
    )
    # -> "Strong Q2 beat is fueling our +$23.10 today; aligned with our long."
"""
from __future__ import annotations

import json
import logging
import os
from datetime import date
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Cache lives in /tmp so it shares lifecycle with the news cache.
_CACHE_PATH = Path("/tmp/imb_news_summary_cache.json")  # nosec B108
_DEFAULT_MODEL = os.environ.get("NEWS_SUMMARY_MODEL", "gpt-4o-mini")
_MAX_TOKENS = 60
_REQUEST_TIMEOUT = 8.0


# ---------------------------------------------------------------------------
# Heuristic fallback — used when LLM is unavailable
# ---------------------------------------------------------------------------
def _heuristic_summary(
    symbol: str,
    articles: list[dict[str, Any]],
    position: dict[str, Any] | None,
    sentiment_score: float,
) -> str:
    """Build a deterministic one-line summary from headlines + position context.

    This is the safety net when no LLM is available — it should still feel
    informative, not generic.
    """
    qty = float((position or {}).get("qty", 0) or 0)
    today_pnl = float((position or {}).get("today_pnl", 0) or 0)
    today_pct = float((position or {}).get("today_pct", 0) or 0)

    # Sentiment band
    if sentiment_score >= 0.62:
        tone = "Headlines lean bullish"
    elif sentiment_score <= 0.38:
        tone = "Headlines lean bearish"
    else:
        tone = "Headlines mixed"

    # Position alignment — today_pnl/today_pct here actually represent
    # unrealized P&L vs cost basis (see _position_context in the email
    # generator). Phrasing reflects that.
    if qty > 0 and today_pnl > 0:
        pos_phrase = (
            f"we're long {qty:.0f} sh, +${abs(today_pnl):,.2f} unrealized ({today_pct:+.2f}%)"
        )
        align = "aligned with our long" if sentiment_score > 0.55 else "watch for a fade"
    elif qty > 0 and today_pnl < 0:
        pos_phrase = (
            f"we're long {qty:.0f} sh, −${abs(today_pnl):,.2f} unrealized ({today_pct:+.2f}%)"
        )
        align = (
            "stop discipline applies"
            if sentiment_score < 0.45
            else "drawdown despite OK news — watch"
        )
    elif qty > 0:
        pos_phrase = f"we're long {qty:.0f} sh, flat"
        align = "tracking"
    else:
        pos_phrase = "no position"
        align = "watchlist"

    return f"{tone}; {pos_phrase} — {align}."


# ---------------------------------------------------------------------------
# LLM client (lazy-loaded so the import is safe without openai installed)
# ---------------------------------------------------------------------------
def _get_openai_client() -> Any | None:
    """Return an OpenAI client or None if unavailable."""
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        return None
    try:
        from openai import OpenAI  # type: ignore[import-not-found]

        return OpenAI(api_key=api_key, timeout=_REQUEST_TIMEOUT)
    except Exception as exc:
        logger.debug("OpenAI client unavailable: %s", exc)
        return None


def _llm_summary(
    symbol: str,
    articles: list[dict[str, Any]],
    position: dict[str, Any] | None,
    sentiment_score: float,
) -> str | None:
    """Call OpenAI for a one-sentence summary. Returns None on any failure."""
    client = _get_openai_client()
    if client is None:
        return None

    titles = [a.get("title", "") for a in articles[:3] if a.get("title")]
    if not titles:
        return None

    qty = float((position or {}).get("qty", 0) or 0)
    today_pnl = float((position or {}).get("today_pnl", 0) or 0)
    today_pct = float((position or {}).get("today_pct", 0) or 0)

    pos_line = (
        f"We're long {qty:.0f} shares; today P&L " f"${today_pnl:+,.2f} ({today_pct:+.2f}%)."
        if qty > 0
        else "No current position."
    )

    user_prompt = (
        f"Ticker: {symbol}\n"
        f"Position: {pos_line}\n"
        f"Average headline sentiment: {sentiment_score:.2f} (0=bearish, 1=bullish).\n"
        f"Recent headlines:\n- " + "\n- ".join(titles) + "\n\n"
        "Write ONE plain-English sentence (max 22 words) explaining what "
        "these headlines mean for our position today. Be specific, not "
        "generic — tie the headlines to the P&L if possible. No emojis. "
        "No quotes around the sentence."
    )

    try:
        resp = client.chat.completions.create(
            model=_DEFAULT_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a concise equities desk analyst. You produce "
                        "ONE-sentence summaries for daily trading digests."
                    ),
                },
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
            max_tokens=_MAX_TOKENS,
        )
        choice = resp.choices[0]
        text = (getattr(choice.message, "content", "") or "").strip()
        # Strip stray quotes / surrounding punctuation
        text = text.strip().strip('"').strip("'").strip()
        if not text:
            return None
        if not text.endswith("."):
            text += "."
        return text
    except Exception as exc:
        logger.debug("LLM summary failed for %s: %s", symbol, exc)
        return None


# ---------------------------------------------------------------------------
# Public API — cached batch summarizer
# ---------------------------------------------------------------------------
class NewsSummarizer:
    """Day-cached LLM summarizer with heuristic fallback."""

    def __init__(self) -> None:
        self._cache: dict[str, str] = {}
        self._cache_date: date | None = None
        self._load_cache()

    # ── persistence ──────────────────────────────────────────────────────
    def _load_cache(self) -> None:
        try:
            if not _CACHE_PATH.exists():
                return
            data = json.loads(_CACHE_PATH.read_text())
            cached_date_str = data.get("date", "")
            if cached_date_str == date.today().isoformat():
                self._cache = dict(data.get("summaries", {}))
                self._cache_date = date.today()
        except Exception as exc:
            logger.debug("News summary cache load failed: %s", exc)

    def _save_cache(self) -> None:
        try:
            _CACHE_PATH.write_text(
                json.dumps(
                    {
                        "date": date.today().isoformat(),
                        "summaries": self._cache,
                    },
                    indent=2,
                )
            )
        except Exception as exc:
            logger.debug("News summary cache write failed: %s", exc)

    def _invalidate_if_stale(self) -> None:
        today = date.today()
        if self._cache_date != today:
            self._cache.clear()
            self._cache_date = today

    # ── main entry point ─────────────────────────────────────────────────
    def summarize_for_position(
        self,
        symbol: str,
        articles: list[dict[str, Any]],
        position: dict[str, Any] | None,
        sentiment_score: float,
    ) -> str:
        """Return a one-sentence why-it-matters line for the symbol.

        Order of fallback: cached value → LLM → heuristic.
        """
        self._invalidate_if_stale()
        if symbol in self._cache:
            return self._cache[symbol]

        text = _llm_summary(symbol, articles, position, sentiment_score)
        if not text:
            text = _heuristic_summary(symbol, articles, position, sentiment_score)

        self._cache[symbol] = text
        self._save_cache()
        return text

    @property
    def llm_enabled(self) -> bool:
        """True if an LLM-backed summary is reachable."""
        return _get_openai_client() is not None
