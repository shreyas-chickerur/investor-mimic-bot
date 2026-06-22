#!/usr/bin/env python3
"""
Strategy: Statistical Pairs Trading (Market-Neutral)

Exploits the temporary divergence of price ratios between cointegrated stock
pairs. When the ratio deviates significantly from its rolling mean (measured
in standard deviations), we buy the underperformer and short the outperformer
simultaneously.

Academic basis:
  Gatev, Goetzmann & Rouwenhorst (2006) — "Pairs Trading: Performance of a
  Relative-Value Arbitrage Rule."  The strategy earns ~6% annual alpha on
  equity pairs with long-term cointegration.

Implementation:
  - Market-neutral: simultaneously LONG the lagging leg + SHORT the leading leg
  - When ratio z-score < -entry_threshold:
      BUY numerator (lagging) + SHORT_SELL denominator (outperforming)
  - Exit when ratio returns to within exit_threshold σ of mean:
      SELL numerator (close long) + BUY_TO_COVER denominator (close short)
  - Alpaca paper accounts support short selling natively; no special config needed

Universe pairs (selected for known cointegration within the existing universe):
  JPM / BAC   — large-cap US banks, same macro drivers
  AAPL / MSFT — mega-cap tech, correlated but mean-reverting spread
  XOM / CVX   — integrated US energy majors, crude oil exposure
  V / MA      — global payment duopoly, near-identical business model
  ABBV / MRK  — large-cap US pharma, patent-cliff exposure
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

logger = logging.getLogger(__name__)

# Pairs: (numerator, denominator) — we BUY numerator when it is undervalued
# relative to denominator (negative z-score on the price ratio).
_DEFAULT_PAIRS: list[tuple[str, str]] = [
    ("JPM", "BAC"),
    ("AAPL", "MSFT"),
    ("XOM", "CVX"),
    ("V", "MA"),
    ("ABBV", "MRK"),
]

# Data-driven pairs produced by scripts/research/screen_pairs.py. When present
# this REPLACES the hardcoded defaults (the 5 defaults all failed validation —
# EXP-2026-06-22-pairs-universe-screen). Each entry carries a per-pair
# max_hold_days aligned to the pair's measured half-life.
_PAIRS_UNIVERSE_PATH = Path(__file__).parent.parent.parent / "data" / "pairs_universe.json"


def load_screened_pairs() -> tuple[list[tuple[str, str]], dict[str, int]]:
    """Load (pairs, per-numerator max_hold) from the screener output.

    Returns the hardcoded defaults with an empty hold-map when the file is
    absent or empty, so behaviour is unchanged until a screen has been run.
    """
    try:
        import json

        if _PAIRS_UNIVERSE_PATH.exists():
            data = json.loads(_PAIRS_UNIVERSE_PATH.read_text())
            entries = data.get("pairs", [])
            if entries:
                pairs = [(e["num"], e["den"]) for e in entries]
                holds = {
                    e["num"]: int(e["max_hold_days"]) for e in entries if e.get("max_hold_days")
                }
                return pairs, holds
    except Exception as exc:  # never let a bad file break signal generation
        logger.warning("pairs_universe.json unreadable (%s) — using defaults", exc)
    return _DEFAULT_PAIRS, {}


class PairsTradingStrategy(TradingStrategy):
    """Statistical pairs trading: buy the lagging leg when the spread z-score
    is sufficiently negative, exit when the spread reverts to mean."""

    def __init__(self, strategy_id: int, capital: float):
        super().__init__(strategy_id=strategy_id, name="Pairs Trading", capital=capital)
        cfg = get_config()
        pt_cfg = cfg.get("strategies.pairs_trading", {}) or {}
        self.entry_threshold: float = pt_cfg.get("entry_z_threshold", 1.5)
        self.exit_threshold: float = pt_cfg.get("exit_z_threshold", 0.3)
        self.lookback: int = pt_cfg.get("lookback_days", 60)
        self.max_hold_days: int = pt_cfg.get("max_hold_days", 20)
        # Prefer the data-driven, half-life-aligned pairs from the screener;
        # _pair_holds maps a numerator → its per-pair max-hold (overrides the
        # global max_hold_days for that pair).
        self.pairs, self._pair_holds = load_screened_pairs()
        self.entry_dates: dict = {}
        # Track which pairs are currently held so we don't double-enter
        self._active_pairs: dict[str, str] = {}  # num → denom (long leg → short leg)

    def _spy_above_sma50(self, market_data: pd.DataFrame) -> bool:
        """Market uptrend gate."""
        spy = (
            market_data[market_data["symbol"] == "SPY"]
            if "symbol" in market_data.columns
            else pd.DataFrame()
        )
        if len(spy) < 50:
            return True
        prices = spy["close"].values
        return float(prices[-1]) > float(np.mean(prices[-50:]))

    def _compute_zscore(
        self, sym_map: dict[str, pd.DataFrame], num: str, denom: str
    ) -> float | None:
        """Compute z-score of the num/denom price ratio over self.lookback days.

        Returns None if either symbol has insufficient history.
        """
        if num not in sym_map or denom not in sym_map:
            return None
        p_num = sym_map[num]["close"].tail(self.lookback)
        p_den = sym_map[denom]["close"].tail(self.lookback)
        if len(p_num) < 20 or len(p_den) < 20:
            return None
        # Align by index
        p_num, p_den = p_num.align(p_den, join="inner")
        if len(p_num) < 20:
            return None
        ratio = p_num / p_den
        mean = float(ratio.mean())
        std = float(ratio.std())
        if std <= 0:
            return None
        return float((ratio.iloc[-1] - mean) / std)

    def generate_signals(self, market_data: pd.DataFrame) -> list[dict]:
        signals: list[dict] = []
        if market_data.empty or "symbol" not in market_data.columns:
            return signals

        market_uptrend = self._spy_above_sma50(market_data)
        sym_map = {sym: grp for sym, grp in market_data.groupby("symbol")}
        latest_date = market_data.index[-1] if len(market_data) > 0 else None

        # Rebuild the num→denom pair map from held positions. _active_pairs is
        # in-memory only and strategies are re-instantiated every daily run, so
        # without this reconstruction multi-day pairs could NEVER exit (the
        # lookup below would always miss).
        for pair_num, pair_den in self.pairs:
            if pair_num in self.positions and pair_num not in self._active_pairs:
                self._active_pairs[pair_num] = pair_den

        # --- Orphan-short sweep: a short whose long partner is gone (e.g. the
        # long leg was stopped out, or the pairs universe changed) has no exit
        # path of its own — force a cover.
        paired_shorts = set(self._active_pairs.values())
        for short_sym, short_qty in self.short_positions.items():
            if short_sym in paired_shorts:
                continue
            if short_sym not in sym_map:
                logger.error(
                    "PAIRS_ORPHAN_SHORT: %s (%.0f shares) has no paired long and no "
                    "market data today — will retry cover next run",
                    short_sym,
                    short_qty,
                )
                continue
            cover_price = float(sym_map[short_sym].iloc[-1]["close"])
            logger.warning(
                "PAIRS_ORPHAN_SHORT: covering %s (%.0f shares) — no paired long position",
                short_sym,
                short_qty,
            )
            signals.append(
                {
                    "symbol": short_sym,
                    "action": "BUY_TO_COVER",
                    "shares": short_qty,
                    "price": cover_price,
                    "value": short_qty * cover_price,
                    "confidence": 0.9,
                    "reasoning": "Orphan short cleanup: paired long leg no longer held",
                    "asof_date": latest_date,
                }
            )

        # --- Exits for held positions ---
        for symbol in list(self.positions.keys()):
            if symbol not in sym_map:
                continue
            denom = self._active_pairs.get(symbol)
            if denom is None:
                continue
            if denom not in sym_map:
                # Defer the ENTIRE pair exit: selling only the long leg would
                # orphan the short with no strategy-level exit path. Data gaps
                # are transient; both legs exit together on the next run.
                logger.error(
                    "PAIRS_ORPHAN_SHORT risk: no market data for short leg %s — "
                    "deferring exit of pair %s/%s to next run",
                    denom,
                    symbol,
                    denom,
                )
                continue
            days_held = self.get_days_held(symbol, latest_date)
            price = float(sym_map[symbol].iloc[-1]["close"])
            z = self._compute_zscore(sym_map, symbol, denom)

            pair_max_hold = self._pair_holds.get(symbol, self.max_hold_days)
            exit_reason = None
            if z is not None and abs(z) <= self.exit_threshold:
                exit_reason = f"Pairs spread reverted: z={z:.2f} ≤ {self.exit_threshold}"
            elif days_held >= pair_max_hold:
                exit_reason = f"Max hold {pair_max_hold}d reached"

            if exit_reason:
                # Close the long leg
                signals.append(
                    {
                        "symbol": symbol,
                        "action": "SELL",
                        "shares": self.positions[symbol],
                        "price": price,
                        "value": self.positions[symbol] * price,
                        "confidence": 0.85,
                        "reasoning": f"Pairs exit (long leg): {exit_reason}",
                        "asof_date": latest_date,
                    }
                )
                # Close the short leg with the ACTUAL short size — the legs are
                # sized by equal notional, so the share counts differ.
                denom_price = float(sym_map[denom].iloc[-1]["close"])
                cover_shares = self.short_positions.get(denom, self.positions[symbol])
                signals.append(
                    {
                        "symbol": denom,
                        "action": "BUY_TO_COVER",
                        "shares": cover_shares,
                        "price": denom_price,
                        "value": cover_shares * denom_price,
                        "confidence": 0.85,
                        "reasoning": f"Pairs exit (short leg cover): {exit_reason}",
                        "asof_date": latest_date,
                    }
                )
                self._active_pairs.pop(symbol, None)

        if not market_uptrend:
            logger.info("Pairs Trading: market downtrend — skipping new entries")
            return signals

        # --- New entries for unoccupied pairs ---
        for num, denom in self.pairs:
            # Skip if we're already holding the numerator leg
            if num in self.positions:
                continue
            if num not in sym_map or denom not in sym_map:
                continue

            z = self._compute_zscore(sym_map, num, denom)
            if z is None:
                continue

            # BUY the numerator (lagging) + SHORT_SELL the denominator (leading)
            # when the spread has diverged past the entry threshold.
            if z < -self.entry_threshold:
                price = float(sym_map[num].iloc[-1]["close"])
                denom_price = float(sym_map[denom].iloc[-1]["close"])
                atr = sym_map[num].iloc[-1].get("atr_20", None)
                if atr is not None and pd.isna(atr):
                    atr = None
                shares = self.calculate_position_size(price, atr=atr, max_position_pct=0.04)
                if shares <= 0:
                    continue
                confidence = min(0.85, 0.50 + abs(z) * 0.10)
                reasoning = (
                    f"Pairs entry: {num}/{denom} ratio z={z:.2f} < "
                    f"-{self.entry_threshold} (mean-reversion setup)"
                )
                # Long the lagging leg
                signals.append(
                    {
                        "symbol": num,
                        "action": "BUY",
                        "shares": shares,
                        "price": price,
                        "value": shares * price,
                        "confidence": confidence,
                        "reasoning": f"{reasoning} — LONG leg",
                        "atr": atr,
                        "asof_date": latest_date,
                    }
                )
                # Short the leading leg (equal notional value makes the trade market-neutral)
                denom_shares = max(1, int((shares * price) / denom_price))
                signals.append(
                    {
                        "symbol": denom,
                        "action": "SHORT_SELL",
                        "shares": denom_shares,
                        "price": denom_price,
                        "value": denom_shares * denom_price,
                        "confidence": confidence,
                        "reasoning": f"{reasoning} — SHORT leg",
                        "asof_date": latest_date,
                    }
                )
                self._active_pairs[num] = denom

        return signals

    def get_description(self) -> str:
        pair_str = ", ".join(f"{n}/{d}" for n, d in self.pairs)
        return (
            f"Statistical pairs mean-reversion: BUY lagging leg when "
            f"z-score < -{self.entry_threshold}σ ({pair_str})"
        )
