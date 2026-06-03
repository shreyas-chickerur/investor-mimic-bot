#!/usr/bin/env python3
"""
Strategy: Volatility Breakout
Buys when price closes above the Bollinger Band upper band on elevated volume —
a sign of genuine momentum rather than noise.  Exits when price returns to the
middle band (mean reversion), hits a profit target, or after 15 trading days.

Academic basis:
  Bollinger (2001) — bands as relative high/low benchmarks;
  Connors (2004) — volume-confirmed breakout as short-term momentum edge.
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


class VolatilityBreakoutStrategy(TradingStrategy):
    """Bollinger Band breakout strategy with volume confirmation."""

    def __init__(self, strategy_id: int, capital: float):
        super().__init__(strategy_id=strategy_id, name="Volatility Breakout", capital=capital)
        cfg = get_config()
        self.volume_spike_min = cfg.get(
            "strategies.volatility_breakout.volume_spike_min",
            cfg.get("strategies.volatility_breakout.volume_surge_threshold", 1.2),
        )
        self.hold_days = cfg.get("strategies.volatility_breakout.hold_days", 15)
        self.max_hold_days = cfg.get("strategies.volatility_breakout.max_hold_days", 25)
        self.profit_target_pct = cfg.get("strategies.volatility_breakout.profit_target_pct", 0.08)
        self.min_return_5d = cfg.get("strategies.volatility_breakout.min_return_5d", 0.0)
        # VIX-adaptive BB multiplier: wider bands in high-vol regimes prevent
        # false breakout signals when price swings are amplified.
        # Research: 1.8σ gives ~85% containment (too many breakouts in calm markets);
        # 2.5σ gives ~99% containment (too few signals in high-vol markets).
        self.bb_mult_low_vix = cfg.get("strategies.volatility_breakout.bb_mult_low_vix", 1.8)
        self.bb_mult_normal_vix = cfg.get("strategies.volatility_breakout.bb_mult_normal_vix", 2.0)
        self.bb_mult_high_vix = cfg.get("strategies.volatility_breakout.bb_mult_high_vix", 2.5)
        self.entry_dates: dict = {}
        self._partial_exit_done: set = set()

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

    def generate_signals(self, market_data: pd.DataFrame) -> list[dict]:
        signals: list[dict] = []
        if market_data.empty or "symbol" not in market_data.columns:
            return signals

        market_uptrend = self._spy_above_sma50(market_data)

        # VIX-adaptive BB multiplier: use current VIX to widen/tighten the bands.
        # Low VIX (<15): 1.8σ — bands are tight naturally; slightly narrower gate.
        # Normal (15-25): 2.0σ — standard setting.
        # High VIX (>25): 2.5σ — regime-corrected to prevent false breakouts.
        _vix_row = None
        if "symbol" in market_data.columns:
            _vix_rows = market_data[market_data["symbol"] == "SPY"]
            if not _vix_rows.empty and "vwap" in _vix_rows.columns:
                pass  # VIX comes from the regime state, not market data columns
        # Approximate VIX from recent SPY volatility if not available
        _spy_vol = 18.0  # default
        if "symbol" in market_data.columns:
            _spy_d = market_data[market_data["symbol"] == "SPY"]["close"]
            if len(_spy_d) >= 20:
                _rets = _spy_d.pct_change().dropna().tail(20)
                _spy_vol = float(_rets.std() * (252**0.5) * 100)

        if _spy_vol < 15:
            _bb_mult = self.bb_mult_low_vix
        elif _spy_vol > 25:
            _bb_mult = self.bb_mult_high_vix
        else:
            _bb_mult = self.bb_mult_normal_vix

        sym_map = {sym: grp for sym, grp in market_data.groupby("symbol")}

        for symbol, sym_data in sym_map.items():
            if len(sym_data) < 22:
                continue

            latest = sym_data.iloc[-1]
            price = float(latest["close"])
            sym_latest_date = sym_data.index[-1]

            bb_upper = latest.get("bb_upper", None)
            bb_middle = latest.get("bb_middle", None)
            bb_lower = latest.get("bb_lower", None)
            if bb_upper is None or pd.isna(bb_upper):
                # Fall back: compute from rolling close using VIX-adaptive multiplier
                roll = sym_data["close"].rolling(20)
                _mean = float(roll.mean().iloc[-1])
                _std = float(roll.std().iloc[-1])
                bb_upper = _mean + _bb_mult * _std
                bb_middle = _mean
                bb_lower = _mean - _bb_mult * _std
            else:
                # Recalculate with adaptive multiplier if pre-computed bands used 2.0σ
                _roll = sym_data["close"].rolling(20)
                _std = float(_roll.std().iloc[-1])
                _mean = float(bb_middle) if not pd.isna(bb_middle) else float(_roll.mean().iloc[-1])
                bb_middle = _mean
                bb_upper = _mean + _bb_mult * _std
                bb_lower = _mean - _bb_mult * _std

            vol_ratio_raw = latest.get("volume_ratio", None)
            vol_ratio = (
                float(vol_ratio_raw)
                if vol_ratio_raw is not None and not pd.isna(vol_ratio_raw)
                else 1.0
            )
            atr_raw = latest.get("atr_20", None)
            atr = float(atr_raw) if atr_raw is not None and not pd.isna(atr_raw) else None
            ret5d_raw = latest.get("returns_5d", None)
            ret5d = float(ret5d_raw) if ret5d_raw is not None and not pd.isna(ret5d_raw) else 0.0

            # --- SELL ---
            if symbol in self.positions:
                days_held = self.get_days_held(symbol, sym_latest_date)
                entry_price = getattr(self, "entry_prices", {}).get(symbol)
                shares = self.positions[symbol]
                exit_reason = None
                exit_shares = shares
                partial_exit = False

                if entry_price and entry_price > 0:
                    pnl_pct = (price - entry_price) / entry_price
                    if pnl_pct >= self.profit_target_pct and symbol not in self._partial_exit_done:
                        exit_shares = max(1, shares // 2)
                        exit_reason = f"Partial profit target: {pnl_pct:.1%} → selling 50%"
                        partial_exit = True

                # Mean-reversion exit: price returned to middle band
                if exit_reason is None and price <= bb_middle:
                    exit_reason = f"Price returned to BB middle ({bb_middle:.2f})"

                if exit_reason is None and days_held >= self.hold_days:
                    if days_held < self.max_hold_days and price > bb_middle:
                        pass  # breakout still running above middle band
                    else:
                        exit_reason = f"Time exit: held {days_held}d"

                if exit_reason:
                    signals.append(
                        {
                            "symbol": symbol,
                            "action": "SELL",
                            "shares": exit_shares,
                            "price": price,
                            "value": exit_shares * price,
                            "confidence": 0.85,
                            "reasoning": exit_reason,
                            "asof_date": sym_latest_date,
                            "partial_exit": partial_exit,
                        }
                    )
                    if partial_exit:
                        self._partial_exit_done.add(symbol)
                continue

            # --- BUY ---
            if not market_uptrend:
                continue
            if price <= bb_upper:
                continue  # no breakout
            if vol_ratio < self.volume_spike_min:
                logger.debug(
                    "VB skip %s: vol_ratio %.2f < %.2f", symbol, vol_ratio, self.volume_spike_min
                )
                continue
            if ret5d < self.min_return_5d:
                continue  # momentum not positive

            # Width of bands relative to price — wider = more volatile = more meaningful breakout
            band_width = (bb_upper - bb_lower) / bb_middle if bb_middle > 0 else 0.0
            excess = (price - bb_upper) / bb_upper if bb_upper > 0 else 0.0
            confidence = min(0.88, 0.55 + vol_ratio * 0.08 + excess * 5 + band_width * 0.5)

            shares = self.calculate_position_size(price, atr=atr, max_position_pct=0.08)
            if shares <= 0:
                continue

            signals.append(
                {
                    "symbol": symbol,
                    "action": "BUY",
                    "shares": shares,
                    "price": price,
                    "value": shares * price,
                    "confidence": confidence,
                    "reasoning": (
                        f"BB breakout: close {price:.2f} > upper {bb_upper:.2f} "
                        f"(vol spike {vol_ratio:.1f}x, 5d ret {ret5d:.1%})"
                    ),
                    "atr": atr,
                    "asof_date": sym_latest_date,
                }
            )

        return signals

    def get_description(self) -> str:
        return (
            f"Bollinger Band upper breakout with {self.volume_spike_min}× volume confirmation; "
            f"exit at middle band or {self.hold_days}d"
        )
