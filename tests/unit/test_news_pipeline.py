"""Unit tests for the news fetching + summarization pipeline.

Covers:
  - Junk-headline filter drops the SEO/quote-page/13F noise we hate
  - Quality scorer prefers substantive financial events over filler
  - News summarizer falls back to heuristic when no API key is set
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from src.utils.news_sentiment import (
    _is_junk_headline,
    _quality_score,
)
from src.utils.news_summarizer import NewsSummarizer, _heuristic_summary


# ---------------------------------------------------------------------------
# Junk filter
# ---------------------------------------------------------------------------
class TestJunkFilter:
    @pytest.mark.parametrize(
        "title",
        [
            "V Stock Price, Quote & Chart | VISA INC-CLASS A SHARES (NYSE:V)",
            "AAPL Stock Price, Quote & News",
            "Rayburn West Financial Services LLC Acquires Shares of 16,697 Coca-Cola",
            "Pinnacle Associates Ltd. Trims Stock Holdings in Apple Inc.",
            "Big Fund Cuts Position in Tesla",
            "Vanguard Has $2.5 billion holdings in Microsoft",
            "Best Stocks Under $50 to Buy Right Now",
            "Top 10 Stocks to Watch This Week",
            "Forget UnitedHealth: Two Stocks To Buy Now",
            "What Are Wall Street Analysts' Target Price for Accenture",
            "Should You Buy Apple Stock Today?",
            "Investors Playing Limbo With Accenture",
            "AAPL",  # too short
            "",  # empty
        ],
    )
    def test_drops_known_junk(self, title: str) -> None:
        assert _is_junk_headline(title), f"should drop junk: {title!r}"

    @pytest.mark.parametrize(
        "title",
        [
            "Apple beats Q2 earnings, raises full-year guidance",
            "Visa announces $5 billion buyback program",
            "Goldman upgrades Microsoft to Buy from Hold",
            "FDA approves Pfizer's new diabetes drug",
            "Tesla CEO Elon Musk announces new partnership with SpaceX",
            "JPMorgan beats Q3 estimates on strong trading revenue",
        ],
    )
    def test_keeps_real_news(self, title: str) -> None:
        assert not _is_junk_headline(title), f"should keep real news: {title!r}"


# ---------------------------------------------------------------------------
# Quality scorer
# ---------------------------------------------------------------------------
class TestQualityScore:
    def test_substantive_news_scores_higher_than_filler(self) -> None:
        substantive = "Apple beats Q2 earnings and raises guidance"
        filler = "Apple opinion: target price prediction"
        assert _quality_score(substantive) > _quality_score(filler)

    def test_score_in_unit_interval(self) -> None:
        for title in [
            "Earnings beat upgrades guidance dividend buyback",  # max boost
            "Opinion prediction forget playing limbo target price quote",  # max penalty
            "",  # empty
        ]:
            score = _quality_score(title)
            assert 0.0 <= score <= 1.0


# ---------------------------------------------------------------------------
# Summarizer heuristic fallback
# ---------------------------------------------------------------------------
class TestSummarizerHeuristic:
    def test_long_position_with_gain(self) -> None:
        out = _heuristic_summary(
            symbol="AAPL",
            articles=[{"title": "Apple beats earnings"}],
            position={"qty": 47, "today_pnl": 100.0, "today_pct": 2.5},
            sentiment_score=0.78,
        )
        assert "long 47 sh" in out
        assert "$100.00" in out
        assert "aligned" in out.lower()

    def test_long_position_with_loss(self) -> None:
        out = _heuristic_summary(
            symbol="NVDA",
            articles=[{"title": "Nvidia downgraded"}],
            position={"qty": 10, "today_pnl": -45.0, "today_pct": -3.2},
            sentiment_score=0.30,
        )
        assert "long 10 sh" in out
        assert "stop discipline" in out.lower()

    def test_no_position_falls_back_to_watchlist(self) -> None:
        out = _heuristic_summary(
            symbol="XYZ",
            articles=[{"title": "Mixed news"}],
            position=None,
            sentiment_score=0.5,
        )
        assert "no position" in out
        assert "watchlist" in out


# ---------------------------------------------------------------------------
# Summarizer end-to-end (no API key path)
# ---------------------------------------------------------------------------
class TestSummarizerNoApiKey:
    def test_falls_back_to_heuristic_when_no_api_key(
        self, tmp_path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Force no API key, redirect cache to a temp path
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.setattr(
            "src.utils.news_summarizer._CACHE_PATH",
            tmp_path / "summary_cache.json",
        )

        s = NewsSummarizer()
        assert s.llm_enabled is False

        line = s.summarize_for_position(
            symbol="AAPL",
            articles=[{"title": "Apple beats earnings"}],
            position={"qty": 10, "today_pnl": 50, "today_pct": 1.0},
            sentiment_score=0.7,
        )
        # Heuristic always produces something useful
        assert isinstance(line, str)
        assert len(line) > 10
        assert "AAPL" not in line  # heuristic doesn't echo ticker
        assert "long 10 sh" in line

    def test_cached_after_first_call(self, tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.setattr(
            "src.utils.news_summarizer._CACHE_PATH",
            tmp_path / "summary_cache.json",
        )

        s = NewsSummarizer()
        first = s.summarize_for_position("AAPL", [{"title": "x"}], {"qty": 1}, 0.5)
        # Mutate the heuristic args; cache should still return the first answer
        with patch(
            "src.utils.news_summarizer._heuristic_summary",
            return_value="DIFFERENT",
        ):
            second = s.summarize_for_position("AAPL", [{"title": "x"}], {"qty": 1}, 0.5)
        assert first == second
