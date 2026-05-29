#!/usr/bin/env python3
"""
Strategy: News Sentiment
Generates buy signals for stocks with strongly positive news sentiment, combined
with a price-trend gate to avoid catching falling knives covered by optimistic press.

Signal flow:
  1. Screen the tradeable universe down to the top candidates by recent momentum
     (returns_5d > 0, price not far below SMA-20) — reduces API calls.
  2. Fetch news sentiment in batch using NewsSentimentProvider (Google News RSS /
     Yahoo Finance; no API key required).
  3. BUY when sentiment score > BUY_THRESHOLD and price is in an uptrend.
  4. SELL when sentiment score drops below SELL_THRESHOLD OR after hold_days.

API cost: zero — uses public Google News RSS and Yahoo Finance search endpoints,
not Alpha Vantage, so no quota is consumed.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import numpy as np
import pandas as pd

from src.core.strategy_base import TradingStrategy
from src.utils.config_loader import get_config
from src.utils.news_sentiment import NewsSentimentProvider

logger = logging.getLogger(__name__)

# Sentiment score thresholds (0=very negative, 0.5=neutral, 1=very positive)
_BUY_THRESHOLD = 0.68
_SELL_THRESHOLD = 0.38
# Maximum symbols to fetch news for per run — controls latency
_MAX_CANDIDATES = 20


class NewsSentimentStrategy(TradingStrategy):
    """News-driven strategy: buy on positive sentiment, exit when news sours."""

    def __init__(self, strategy_id: int, capital: float):
        super().__init__(strategy_id=strategy_id, name="News Sentiment", capital=capital)
        cfg = get_config()
        self.buy_threshold = cfg.get("strategies.news_sentiment.buy_threshold", _BUY_THRESHOLD)
        self.sell_threshold = cfg.get("strategies.news_sentiment.sell_threshold", _SELL_THRESHOLD)
        self.hold_days = cfg.get("strategies.news_sentiment.hold_days", 7)
        self.max_hold_days = cfg.get("strategies.news_sentiment.max_hold_days", 14)
        self.max_candidates = cfg.get("strategies.news_sentiment.max_candidates", _MAX_CANDIDATES)
        self.min_ret5d = cfg.get("strategies.news_sentiment.min_ret5d", -0.02)
        self.entry_dates: dict = {}
        self._provider = NewsSentimentProvider(max_workers=8, per_symbol_timeout=5.0)
        self._sentiment_cache: dict = {}

    def _spy_above_sma50(self, market_data: pd.DataFrame) -> bool:
        spy = (
            market_data[market_data["symbol"] == "SPY"]
            if "symbol" in market_data.columns
            else pd.DataFrame()
        )
        if len(spy) < 50:
            return True
        prices = spy["close"].values
        return float(prices[-1]) > float(np.mean(prices[-50:]))

    def _screen_candidates(self, sym_map: dict, benchmarks: set) -> list[str]:
        """Return up to max_candidates symbols worth fetching news for.

        Prioritises:
          1. Symbols already held (need sentiment check for exit decisions).
          2. Symbols with recent positive 5-day return and price not too far
             below their 20-day SMA (avoid catching falling knives).
        Sorted by 5-day return descending; capped at max_candidates.
        """
        candidates: list[tuple[float, str]] = []

        for symbol, sym_data in sym_map.items():
            if symbol in benchmarks or len(sym_data) < 10:
                continue
            latest = sym_data.iloc[-1]
            ret5d_raw = latest.get("returns_5d", None)
            ret5d = float(ret5d_raw) if ret5d_raw is not None and not pd.isna(ret5d_raw) else 0.0
            sma20_ratio_raw = latest.get("price_to_sma20", None)
            sma20_ratio = (
                float(sma20_ratio_raw)
                if sma20_ratio_raw is not None and not pd.isna(sma20_ratio_raw)
                else 0.0
            )

            # Held positions are always included (need exit sentiment)
            if symbol in self.positions:
                candidates.append((1.0 + ret5d, symbol))
                continue

            if ret5d >= self.min_ret5d and sma20_ratio >= -0.05:
                candidates.append((ret5d, symbol))

        candidates.sort(reverse=True)
        return [sym for _, sym in candidates[: self.max_candidates]]

    def generate_signals(self, market_data: pd.DataFrame) -> list[dict]:
        signals: list[dict] = []
        if market_data.empty or "symbol" not in market_data.columns:
            return signals

        market_uptrend = self._spy_above_sma50(market_data)
        sym_map = {sym: grp for sym, grp in market_data.groupby("symbol")}

        # Import benchmark set to exclude ETFs from screening
        try:
            from src.data.universe_provider import UniverseProvider

            benchmarks = UniverseProvider.BENCHMARK_SYMBOLS
        except Exception:
            benchmarks = {"SPY", "QQQ", "IWM", "XLK", "XLV", "XLF", "XLP", "XLE", "XLY"}

        candidates = self._screen_candidates(sym_map, benchmarks)

        if not candidates:
            logger.info("NewsSentiment: no screened candidates this run")
            return signals

        logger.info(
            "NewsSentiment: fetching sentiment for %d symbols: %s", len(candidates), candidates
        )
        try:
            sentiment_map = self._provider.fetch_batch(candidates)
            self._sentiment_cache.update(sentiment_map)
        except Exception as exc:
            logger.warning("NewsSentiment: batch fetch failed: %s — using neutral", exc)
            sentiment_map = {}

        for symbol in candidates:
            sym_data = sym_map.get(symbol)
            if sym_data is None or len(sym_data) < 5:
                continue

            latest = sym_data.iloc[-1]
            price = float(latest["close"])
            sym_latest_date = sym_data.index[-1]
            atr_raw = latest.get("atr_20", None)
            atr = float(atr_raw) if atr_raw is not None and not pd.isna(atr_raw) else None

            context = sentiment_map.get(symbol, {"score": 0.5, "headlines": []})
            score = float(context.get("score", 0.5))
            headlines = context.get("headlines", [])
            top_headline = headlines[0] if headlines else ""

            # --- SELL held positions ---
            if symbol in self.positions:
                days_held = self.get_days_held(symbol, sym_latest_date)
                shares = self.positions[symbol]
                entry_price = getattr(self, "entry_prices", {}).get(symbol)
                in_profit = (
                    entry_price is not None
                    and float(entry_price) > 0
                    and price > float(entry_price)
                )
                # Sentiment has materially weakened from the BUY-level threshold
                # but hasn't yet crossed the hard sell_threshold.
                sentiment_weakened = score < 0.55
                exit_reason = None

                if score < self.sell_threshold:
                    exit_reason = f"Sentiment soured (score={score:.2f}): {top_headline[:60]}"
                elif days_held >= self.max_hold_days:
                    exit_reason = f"Max hold reached ({days_held}d)"
                elif days_held >= self.hold_days and (in_profit or sentiment_weakened):
                    # Same gate the ML Momentum strategy uses (commit 9f1471a):
                    # do NOT force-exit at hold_days when the trade is still
                    # underwater AND sentiment is still positive. The mechanical
                    # exit caused a synchronized AMD/TSLA/UNH/NVDA dump on
                    # 2026-05-18 — we hold to max_hold_days now instead.
                    if in_profit:
                        exit_reason = f"Sentiment hold window ({days_held}d) — exiting in profit"
                    else:
                        exit_reason = f"Sentiment weakened (score={score:.2f}) at {days_held}d hold"

                if exit_reason:
                    signals.append(
                        {
                            "symbol": symbol,
                            "action": "SELL",
                            "shares": shares,
                            "price": price,
                            "value": shares * price,
                            "confidence": 0.85,
                            "reasoning": exit_reason,
                            "asof_date": sym_latest_date,
                        }
                    )
                continue

            # --- BUY new positions ---
            if not market_uptrend:
                continue
            if score < self.buy_threshold:
                logger.debug(
                    "NewsSentiment skip %s: score %.2f < %.2f", symbol, score, self.buy_threshold
                )
                continue

            shares = self.calculate_position_size(price, atr=atr, max_position_pct=0.07)
            if shares <= 0:
                continue

            confidence = min(0.90, 0.55 + (score - self.buy_threshold) * 2.5)
            signals.append(
                {
                    "symbol": symbol,
                    "action": "BUY",
                    "shares": shares,
                    "price": price,
                    "value": shares * price,
                    "confidence": confidence,
                    "reasoning": (
                        f"Positive news sentiment score {score:.2f}: {top_headline[:80]}"
                        if top_headline
                        else f"Positive news sentiment score {score:.2f}"
                    ),
                    "atr": atr,
                    "asof_date": sym_latest_date,
                }
            )

        return signals

    def get_description(self) -> str:
        return (
            f"News sentiment (Google News RSS + VADER): buy score>{self.buy_threshold:.2f}, "
            f"sell score<{self.sell_threshold:.2f} or after {self.hold_days}d"
        )
