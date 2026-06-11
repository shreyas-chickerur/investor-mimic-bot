#!/usr/bin/env python3
"""
Strategy: Dual Momentum (12-1 cross-sectional + absolute momentum filter)

Academic basis:
  Jegadeesh & Titman (1993) — cross-sectional momentum, 3-12 month horizon.
  Asness (1994) / standard practice — skip the most recent month (12-1) to
  avoid the short-term reversal effect.
  Antonacci (2014) — "dual momentum": relative momentum picks the winners,
  ABSOLUTE momentum (the asset's own 12-1 return must be positive, and the
  market's must be positive when observable) keeps the strategy out of
  bear-market knife-catching.

Mechanics:
  1. For every non-benchmark symbol with >= lookback history, compute the
     12-1 momentum: return from t-252 to t-21 (skip the last month).
  2. Absolute filter: candidate momentum must be > 0; if SPY history is
     available, SPY's 12-1 momentum must also be > 0 (regime filter).
  3. Buy the top N by momentum, confidence scaled by cross-sectional rank.
  4. Exits via the shared min/soft/max time-exit policy: thesis = the name
     still ranks in the top 2N band (rank hysteresis); absolute ceiling at
     max_hold_days. Stop-losses are the engine's trailing ATR ratchet.

Added 2026-06 after the evidence-driven prune freed capital and complexity
budget (News Sentiment / Pairs Trading / ML Momentum disabled). Enabled with
capital only after passing the same OOS gates as every other strategy — see
docs/research/EVIDENCE_2026-06.md.
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from src.core.strategy_base import TradingStrategy
from src.utils.config_loader import get_config

logger = logging.getLogger(__name__)


class DualMomentumStrategy(TradingStrategy):
    """12-1 cross-sectional momentum with an absolute-momentum regime filter."""

    def __init__(self, strategy_id: int, capital: float):
        super().__init__(strategy_id=strategy_id, name="Dual Momentum", capital=capital)
        cfg = get_config()
        dm_cfg = cfg.get("strategies.dual_momentum", {}) or {}
        self.lookback_days: int = dm_cfg.get("lookback_days", 252)
        self.skip_days: int = dm_cfg.get("skip_days", 21)
        self.top_n: int = dm_cfg.get("top_n", 5)
        self.min_hold_days: int = dm_cfg.get("min_hold_days", 5)
        self.soft_hold_days: int = dm_cfg.get("soft_hold_days", 35)
        self.max_hold_days: int = dm_cfg.get("max_hold_days", 70)
        self.entry_dates: dict = {}

    def _momentum_12_1(self, closes: pd.Series) -> float | None:
        """Return from t-lookback to t-skip (None if insufficient history)."""
        if len(closes) < self.lookback_days + 1:
            return None
        start = float(closes.iloc[-(self.lookback_days + 1)])
        end = (
            float(closes.iloc[-(self.skip_days + 1)])
            if self.skip_days > 0
            else float(closes.iloc[-1])
        )
        if start <= 0:
            return None
        return (end - start) / start

    def _benchmarks(self) -> set:
        try:
            from src.data.universe_provider import UniverseProvider

            return set(UniverseProvider.BENCHMARK_SYMBOLS)
        except Exception:
            return {"SPY", "QQQ", "XLK", "XLF", "XLE", "XLV", "XLP", "XLY"}

    def generate_signals(self, market_data: pd.DataFrame) -> list[dict]:
        signals: list[dict] = []
        if market_data.empty or "symbol" not in market_data.columns:
            return signals

        sym_map = dict(market_data.groupby("symbol"))
        latest_date = market_data.index[-1]
        benchmarks = self._benchmarks()

        # Absolute market filter: when SPY is observable its own 12-1 momentum
        # must be positive for NEW entries (exits always processed).
        market_momentum_ok = True
        if "SPY" in sym_map:
            spy_mom = self._momentum_12_1(sym_map["SPY"]["close"])
            if spy_mom is not None:
                market_momentum_ok = spy_mom > 0

        # Cross-sectional momentum for every eligible name
        momentum: dict[str, float] = {}
        for sym, grp in sym_map.items():
            if sym in benchmarks:
                continue
            mom = self._momentum_12_1(grp["close"])
            if mom is not None:
                momentum[sym] = mom

        ranked = sorted(momentum.items(), key=lambda kv: kv[1], reverse=True)
        hold_band = {sym for sym, _ in ranked[: self.top_n * 2]}

        # --- Exits (shared time-exit policy; rank hysteresis thesis) ---
        for symbol in list(self.positions.keys()):
            grp = sym_map.get(symbol)
            if grp is None or grp.empty:
                continue
            price = float(grp.iloc[-1]["close"])
            entry_price = self.entry_prices.get(symbol)
            in_profit = entry_price is not None and entry_price > 0 and price > float(entry_price)
            exit_reason = self.evaluate_time_exit(
                symbol,
                latest_date,
                in_profit=in_profit,
                thesis_intact=symbol in hold_band if momentum else True,
                min_hold_days=self.min_hold_days,
                soft_hold_days=self.soft_hold_days,
                max_hold_days=self.max_hold_days,
            )
            if exit_reason:
                shares = self.positions[symbol]
                signals.append(
                    {
                        "symbol": symbol,
                        "action": "SELL",
                        "shares": shares,
                        "price": price,
                        "value": shares * price,
                        "confidence": 0.8,
                        "reasoning": f"Dual momentum: {exit_reason}",
                        "asof_date": latest_date,
                    }
                )

        # --- Entries ---
        if not market_momentum_ok:
            logger.info("Dual Momentum: SPY 12-1 momentum negative — no new entries")
            return signals

        capacity = max(0, self.top_n - len(self.positions))
        if capacity <= 0 or not ranked:
            return signals

        n_ranked = len(ranked)
        for rank_idx, (symbol, mom) in enumerate(ranked):
            if capacity <= 0:
                break
            if symbol in self.positions:
                continue
            if mom <= 0:
                break  # absolute filter: ranked desc, nothing below is positive
            if rank_idx >= self.top_n:
                break
            grp = sym_map[symbol]
            latest = grp.iloc[-1]
            price = float(latest["close"])
            atr_raw = latest.get("atr_20", None)
            atr = float(atr_raw) if atr_raw is not None and not pd.isna(atr_raw) else None

            shares = self.calculate_position_size(price, atr=atr, max_position_pct=0.08)
            if shares <= 0:
                continue

            # Confidence from cross-sectional rank percentile (top rank → ~0.85)
            percentile = 1.0 - (rank_idx / max(n_ranked - 1, 1))
            confidence = float(np.clip(0.5 + 0.35 * percentile, 0.5, 0.85))

            signals.append(
                {
                    "symbol": symbol,
                    "action": "BUY",
                    "shares": shares,
                    "price": price,
                    "value": shares * price,
                    "confidence": confidence,
                    "reasoning": (
                        f"Dual momentum: 12-1 return {mom:+.1%}, rank {rank_idx + 1}/{n_ranked}"
                    ),
                    "atr": atr,
                    "asof_date": latest_date,
                }
            )
            capacity -= 1

        return signals

    def get_description(self) -> str:
        return (
            f"Dual momentum: top {self.top_n} by 12-1 cross-sectional momentum, "
            "absolute momentum filter (own and SPY 12-1 must be positive)"
        )
