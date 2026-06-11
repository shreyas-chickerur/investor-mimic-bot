#!/usr/bin/env python3
"""
Strategy 6: Cross-Sectional Factor Momentum

Ranks stocks by a composite factor score and buys the top quintile.
Factors (all computable from existing market data + optional fundamentals):
  1. Price momentum (60-day return)
  2. Quality proxy (low vol + positive momentum)
  3. Mean-reversion signal (RSI oversold range)
  4. Volume confirmation (rising vol on up-moves)
  5. Excess momentum over SPY (alpha, not beta)
  6. Sector relative strength (stock vs sector ETF)
  7. Fundamental quality (ROE / debt, optional via data/fundamentals.json)
  8. Fundamental value (1/PE ratio, optional via data/fundamentals.json)

Academic basis:
  - Jegadeesh & Titman (1993): 12-1 momentum
  - Asness et al. (2013): Value and Momentum Everywhere
  - Novy-Marx (2012): Quality minus Junk

Holds positions for 20 trading days, then re-ranks.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import logging

import numpy as np
import pandas as pd

from src.core.strategy_base import TradingStrategy

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).parent.parent.parent
_FUNDAMENTALS_PATH = _PROJECT_ROOT / "data" / "fundamentals.json"

# Stock → sector ETF mapping
_SECTOR_MAP: dict[str, str] = {
    # Tech
    "AAPL": "XLK",
    "MSFT": "XLK",
    "GOOGL": "XLK",
    "AMZN": "XLK",
    "META": "XLK",
    "NVDA": "XLK",
    "ADBE": "XLK",
    "AVGO": "XLK",
    "CRM": "XLK",
    "AMD": "XLK",
    "ACN": "XLK",
    # Consumer Discretionary
    "TSLA": "XLY",
    "NFLX": "XLY",
    "COST": "XLY",
    "MCD": "XLY",
    "NKE": "XLY",
    "WMT": "XLY",
    "HD": "XLY",
    "DIS": "XLY",
    # Healthcare
    "JNJ": "XLV",
    "ABBV": "XLV",
    "MRK": "XLV",
    "TMO": "XLV",
    "DHR": "XLV",
    "ABT": "XLV",
    "UNH": "XLV",
    "LLY": "XLV",
    # Financials
    "MA": "XLF",
    "JPM": "XLF",
    "V": "XLF",
    # Consumer Staples
    "KO": "XLP",
    "PEP": "XLP",
    "PG": "XLP",
    # Energy
    "XOM": "XLE",
    "CVX": "XLE",
    # Telecom → use SPY as fallback
    "VZ": "SPY",
}


class FactorMomentumStrategy(TradingStrategy):
    """Cross-sectional factor momentum: buy top-ranked stocks by composite score."""

    def __init__(self, strategy_id: int, capital: float):
        super().__init__(
            strategy_id=strategy_id,
            name="Factor Momentum",
            capital=capital,
        )
        self.hold_days = 20
        self.max_hold_days = 35  # absolute ceiling even for profitable positions
        self.min_hold_days = 0
        self.top_n = 3  # Buy top 3 stocks (reduced from 5 — higher conviction, lower cost drag)
        self.profit_target_pct = 0.12  # Exit at 12% gain — lock in before mean-reversion
        self.stop_loss_pct = 0.08  # retained for reference; exits now via StopLossManager
        self.let_winners_run_pct = 0.05  # hold past time exit if ≥5% in profit
        self.entry_dates = {}
        self._last_rerank_date = None
        self._partial_exit_done: set = set()

    def _load_fundamentals(self, max_age_days: int = 90) -> dict[str, dict]:
        """Load fundamental data from data/fundamentals.json.

        Returns empty dict when the file is absent or older than ``max_age_days``.
        Fundamentals are updated quarterly; data older than 90 days is stale enough
        that using it may score companies on outdated earnings/debt ratios.
        """
        if not _FUNDAMENTALS_PATH.exists():
            return {}
        try:
            from datetime import datetime as _dt

            age_days = (_dt.now() - _dt.fromtimestamp(_FUNDAMENTALS_PATH.stat().st_mtime)).days
            if age_days > max_age_days:
                logger.warning(
                    "Fundamentals data is %d days old (max %d) — skipping to avoid stale scores. "
                    "Run scripts/update_fundamental_data.py to refresh.",
                    age_days,
                    max_age_days,
                )
                return {}
            with open(_FUNDAMENTALS_PATH) as f:
                return json.load(f)
        except Exception as exc:
            logger.warning("Could not load fundamentals: %s", exc)
        return {}

    def _sector_regime_multipliers(self, market_data: pd.DataFrame) -> dict[str, float]:
        """Return a score multiplier per sector ETF based on 20-day trend.

        Sector ETF above its 20-day SMA  → multiplier 1.10 (mild tailwind)
        Sector ETF below its 20-day SMA  → multiplier 0.80 (mild headwind)
        Insufficient data                → multiplier 1.00 (neutral)
        """
        multipliers: dict[str, float] = {}
        for etf in set(_SECTOR_MAP.values()):
            rows = (
                market_data[market_data["symbol"] == etf]
                if "symbol" in market_data.columns
                else pd.DataFrame()
            )
            if len(rows) < 20:
                multipliers[etf] = 1.0
                continue
            prices = rows["close"].values
            sma20 = float(np.mean(prices[-20:]))
            last_price = float(prices[-1])
            if last_price > sma20:
                multipliers[etf] = 1.10
            else:
                multipliers[etf] = 0.80
        return multipliers

    def _compute_factor_scores(self, market_data: pd.DataFrame) -> dict[str, float]:
        """Compute composite factor score per symbol using cross-sectional percentile ranks.

        Factors:
          1. Momentum (60d return)              weight 0.25
          2. Quality proxy (low vol + momentum)  weight 0.15
          3. Mean-reversion (RSI 25-45)          weight 0.10
          4. Volume confirmation                  weight 0.10
          5. Excess momentum over SPY             weight 0.15
          6. Sector relative strength             weight 0.10
          7. Fundamental quality (ROE/debt)       weight 0.10  (if available)
          8. Fundamental value (1/PE)             weight 0.05  (if available)
        """
        counts = market_data.groupby("symbol").size()
        eligible = counts[counts >= 60].index
        if len(eligible) < 3:
            return {}

        filtered = market_data[market_data["symbol"].isin(eligible)]
        latest_df = filtered.groupby("symbol").last()

        # Exclude benchmark ETFs from scoring (they are data sources, not trading candidates)
        from src.data.universe_provider import UniverseProvider

        benchmarks = UniverseProvider.BENCHMARK_SYMBOLS
        tradeable = latest_df.index.difference(list(benchmarks))
        if len(tradeable) < 3:
            return {}
        latest_df = latest_df.loc[tradeable]

        # --- Factor 1: 60d momentum ---
        momentum = latest_df["returns_60d"].fillna(0.0).astype(float)

        # --- Factor 2: Quality proxy ---
        vol_20d = latest_df["volatility_20d"].fillna(0.2).astype(float)
        quality = -vol_20d + momentum.clip(lower=0) * 0.5

        # --- Factor 3: Mean-reversion (RSI 25-45 oversold) ---
        rsi = latest_df["rsi"].fillna(50.0).astype(float)
        reversion_score = pd.Series(
            np.where((rsi >= 25) & (rsi <= 45), (45 - rsi) / 20, 0.0),
            index=latest_df.index,
        )

        # --- Factor 4: Volume confirmation ---
        vol_ratio = latest_df["volume_ratio"].fillna(1.0).astype(float)
        ret_5d = latest_df["returns_5d"].fillna(0.0).astype(float)
        volume_confirm = vol_ratio * ret_5d.clip(lower=0)

        # --- Factor 5: Excess momentum over SPY (alpha momentum) ---
        spy_ret = 0.0
        if "SPY" in filtered["symbol"].values or (
            "symbol" in market_data.columns and "SPY" in market_data["symbol"].values
        ):
            spy_rows = market_data[market_data["symbol"] == "SPY"]
            if not spy_rows.empty:
                spy_last = spy_rows.iloc[-1]
                spy_ret = float(spy_last.get("returns_60d", 0.0) or 0.0)
        excess_momentum = momentum - spy_ret

        # --- Factor 6: Sector relative strength ---
        sector_excess = pd.Series(0.0, index=latest_df.index)
        for sym in latest_df.index:
            sector_etf = _SECTOR_MAP.get(sym, "SPY")
            etf_rows = (
                market_data[market_data["symbol"] == sector_etf]
                if "symbol" in market_data.columns
                else pd.DataFrame()
            )
            if not etf_rows.empty:
                etf_ret = float(etf_rows.iloc[-1].get("returns_60d", 0.0) or 0.0)
                sector_excess[sym] = float(latest_df.loc[sym, "returns_60d"] or 0.0) - etf_ret

        # --- Factors 7 & 8: Fundamental quality + value (optional) ---
        fundamentals = self._load_fundamentals()
        fund_quality = pd.Series(0.0, index=latest_df.index)
        fund_value = pd.Series(0.0, index=latest_df.index)
        has_fundamentals = bool(fundamentals)
        if has_fundamentals:
            for sym in latest_df.index:
                f = fundamentals.get(sym, {})
                roe = float(f.get("roe", 0.0) or 0.0)
                debt_eq = float(f.get("debt_to_equity", 1.0) or 1.0)
                pe = float(f.get("pe_ratio", 20.0) or 20.0)
                fund_quality[sym] = roe / max(debt_eq, 0.1)
                fund_value[sym] = 1.0 / max(pe, 1.0)

        # Assemble and cross-sectionally rank
        factors = pd.DataFrame(
            {
                "momentum": momentum,
                "quality": quality,
                "reversion": reversion_score,
                "volume": volume_confirm,
                "excess_momentum": excess_momentum,
                "sector_rs": sector_excess,
                "fund_quality": fund_quality,
                "fund_value": fund_value,
            },
            index=latest_df.index,
        )

        for col in factors.columns:
            factors[f"{col}_pct"] = factors[col].rank(pct=True)

        if has_fundamentals:
            factors["composite"] = (
                0.25 * factors["momentum_pct"]
                + 0.15 * factors["quality_pct"]
                + 0.10 * factors["reversion_pct"]
                + 0.10 * factors["volume_pct"]
                + 0.15 * factors["excess_momentum_pct"]
                + 0.10 * factors["sector_rs_pct"]
                + 0.10 * factors["fund_quality_pct"]
                + 0.05 * factors["fund_value_pct"]
            )
        else:
            factors["composite"] = (
                0.30 * factors["momentum_pct"]
                + 0.15 * factors["quality_pct"]
                + 0.10 * factors["reversion_pct"]
                + 0.10 * factors["volume_pct"]
                + 0.20 * factors["excess_momentum_pct"]
                + 0.15 * factors["sector_rs_pct"]
            )
            logger.debug("Fundamentals unavailable — using 6-factor model")

        # E2: Apply sector regime tilt — multiply composite by sector ETF trend multiplier
        sector_mults = self._sector_regime_multipliers(market_data)
        tilted: dict[str, float] = {}
        for sym, score in factors["composite"].items():
            etf = _SECTOR_MAP.get(sym, "SPY")
            mult = sector_mults.get(etf, 1.0)
            tilted[sym] = score * mult
            if mult != 1.0:
                logger.debug(
                    f"Sector tilt {sym} ({etf}): {score:.3f} × {mult:.2f} = {tilted[sym]:.3f}"
                )

        return tilted

    def generate_signals(self, market_data: pd.DataFrame) -> list[dict]:
        """Generate signals by ranking stocks and buying top quintile."""
        signals = []
        latest_date = market_data.index[-1] if len(market_data) > 0 else None
        if latest_date is None:
            return signals

        # Market regime gate — block new BUY entries in a confirmed downtrend.
        # Uses the same SPY 50-SMA check as every other strategy in the platform.
        # Existing positions continue to be managed (profit targets, time exits).
        _market_uptrend = True
        if "symbol" in market_data.columns:
            _spy = market_data[market_data["symbol"] == "SPY"]
            if len(_spy) >= 50:
                _spy_close = _spy["close"].values
                _market_uptrend = float(_spy_close[-1]) > float(np.mean(_spy_close[-50:]))
            else:
                logger.debug(
                    "Factor Momentum: insufficient SPY history for regime check — assuming uptrend"
                )
        if not _market_uptrend:
            logger.info(
                "Factor Momentum: SPY below 50-SMA (downtrend) — skipping new BUY signals; "
                "exits still processed"
            )

        # Pre-build symbol→DataFrame lookup once — avoids repeated boolean filter per position
        sym_map = {sym: grp for sym, grp in market_data.groupby("symbol")}  # noqa: C416

        # Compute factor scores ONCE, before exits: the rebalance exit needs to
        # know whether a held name still ranks well. Rank hysteresis (hold while
        # in the top 2*top_n) replaces blind calendar liquidation — a position
        # only rotates out when something meaningfully better has displaced it.
        scores = self._compute_factor_scores(market_data) or {}
        _ranked_syms = [s for s, _ in sorted(scores.items(), key=lambda x: x[1], reverse=True)]
        _hold_band = set(_ranked_syms[: self.top_n * 2])

        # Check SELL first — profit target, stop-loss, or time-based rebalance
        for symbol in list(self.positions.keys()):
            days_held = self.get_days_held(symbol, latest_date)
            sym_data = sym_map.get(symbol)
            if sym_data is None or sym_data.empty:
                continue
            price = float(sym_data.iloc[-1]["close"])
            shares = self.positions[symbol]
            entry_price = getattr(self, "entry_prices", {}).get(symbol)

            exit_reason = None
            exit_shares = shares
            partial_exit = False

            if entry_price and entry_price > 0:
                pnl_pct = (price - entry_price) / entry_price
                if pnl_pct >= self.profit_target_pct and symbol not in self._partial_exit_done:
                    # First tranche: sell 50%; trailing ATR stop manages the remainder.
                    exit_shares = max(1, shares // 2)
                    exit_reason = (
                        f"Partial profit target: {pnl_pct:.1%} gain → selling 50% "
                        f"({exit_shares} of {shares} shares)"
                    )
                    partial_exit = True
            # Stop-losses handled by StopLossManager (trailing ATR ratchet); no fixed pct here.

            # Time exit via the shared min/soft/max policy. Thesis intact =
            # the name still ranks in the top 2*top_n of the composite (rank
            # hysteresis) — calendar liquidation of a still-well-ranked name
            # was pure churn. Winners-run and LTCG deferral preserved.
            in_profit = entry_price is not None and entry_price > 0 and price > float(entry_price)
            approaching_ltcg = 250 <= days_held < 370
            _winner_running = bool(
                entry_price
                and entry_price > 0
                and (price - entry_price) / entry_price >= self.let_winners_run_pct
            )
            if exit_reason is None:
                exit_reason = self.evaluate_time_exit(
                    symbol,
                    latest_date,
                    in_profit=in_profit,
                    thesis_intact=symbol in _hold_band if scores else True,
                    min_hold_days=self.min_hold_days,
                    soft_hold_days=self.hold_days,
                    max_hold_days=self.max_hold_days,
                    hold_winner=_winner_running or (approaching_ltcg and in_profit),
                )

            if exit_reason:
                signals.append(
                    {
                        "symbol": symbol,
                        "action": "SELL",
                        "shares": exit_shares,
                        "price": price,
                        "value": exit_shares * price,
                        "confidence": 0.9 if partial_exit else 0.7,
                        "reasoning": exit_reason,
                        "asof_date": latest_date,
                        "partial_exit": partial_exit,
                    }
                )
                if partial_exit:
                    self._partial_exit_done.add(symbol)

        # Only generate new BUY signals if market is in uptrend and we have capacity
        if not _market_uptrend:
            return signals

        current_positions = len(self.positions)
        buy_capacity = (
            self.top_n - current_positions + len([s for s in signals if s["action"] == "SELL"])
        )

        if buy_capacity <= 0:
            return signals

        # Factor scores were computed once above (shared with the exit logic)
        if not scores:
            return signals

        # Rank and select top N (exclude already held)
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        candidates = [(sym, score) for sym, score in ranked if sym not in self.positions][
            :buy_capacity
        ]

        for symbol, score in candidates:
            sym_data = sym_map.get(symbol)
            if sym_data is None or sym_data.empty:
                continue

            latest = sym_data.iloc[-1]
            price = float(latest["close"])
            atr = float(latest.get("atr_20", 0)) if not pd.isna(latest.get("atr_20", np.nan)) else 0

            shares = self.calculate_position_size(
                price, atr=atr if atr > 0 else None, max_position_pct=0.08
            )
            if shares <= 0:
                continue

            confidence = min(0.9, 0.4 + score)

            signals.append(
                {
                    "symbol": symbol,
                    "action": "BUY",
                    "shares": shares,
                    "price": price,
                    "value": shares * price,
                    "confidence": confidence,
                    "reasoning": f"Factor rank score {score:.3f} (top {len(candidates)})",
                    "atr": atr if atr > 0 else None,
                    "asof_date": latest_date,
                }
            )

        return signals

    def get_description(self) -> str:
        return (
            "Cross-sectional factor momentum: ranks stocks by composite "
            "(momentum + quality + mean-reversion + volume), buys top quintile"
        )
