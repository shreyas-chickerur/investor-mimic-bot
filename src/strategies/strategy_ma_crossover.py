#!/usr/bin/env python3
"""
Strategy: Moving Average Crossover
Classic trend-following: buy the golden cross (20-day SMA crosses above 50-day SMA),
sell the death cross or after a 30-day hold.

Additional filters reduce false signals:
  - ADX > 20 confirms a trending (not choppy) market
  - Volume ratio > 0.8 ensures the move has participation
  - SPY above its own 50-day SMA as broad market gate
  - Stop-losses managed by StopLossManager (trailing ATR ratchet)
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


class MACrossoverStrategy(TradingStrategy):
    """Moving average crossover: 20-day SMA crosses 50-day SMA."""

    def __init__(self, strategy_id: int, capital: float):
        super().__init__(strategy_id=strategy_id, name="MA Crossover", capital=capital)
        cfg = get_config()
        self.short_window = cfg.get("strategies.ma_crossover.short_window", 20)
        self.long_window = cfg.get("strategies.ma_crossover.long_window", 50)
        self.adx_min = cfg.get("strategies.ma_crossover.adx_min", 20)
        self.hold_days = cfg.get("strategies.ma_crossover.hold_days", 30)
        self.max_hold_days = cfg.get("strategies.ma_crossover.max_hold_days", 50)
        self.profit_target_pct = cfg.get("strategies.ma_crossover.profit_target_pct", 0.12)
        self.let_winners_run_pct = cfg.get("strategies.ma_crossover.let_winners_run_pct", 0.05)
        self.volume_min_ratio = cfg.get("strategies.ma_crossover.volume_min_ratio", 0.8)
        self.entry_dates: dict = {}

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
        sym_map = {sym: grp for sym, grp in market_data.groupby("symbol")}

        for symbol, sym_data in sym_map.items():
            if len(sym_data) < self.long_window + 2:
                continue

            latest = sym_data.iloc[-1]
            prev = sym_data.iloc[-2]
            price = float(latest["close"])
            sym_latest_date = sym_data.index[-1]

            # Pull SMA values — prefer pre-computed columns, fall back to rolling
            sma20_now = (
                float(latest["sma_20"])
                if "sma_20" in latest.index and not pd.isna(latest["sma_20"])
                else float(sym_data["close"].rolling(self.short_window).mean().iloc[-1])
            )
            sma50_now = (
                float(latest["sma_50"])
                if "sma_50" in latest.index and not pd.isna(latest["sma_50"])
                else float(sym_data["close"].rolling(self.long_window).mean().iloc[-1])
            )
            sma20_prev = (
                float(prev["sma_20"])
                if "sma_20" in prev.index and not pd.isna(prev["sma_20"])
                else float(sym_data["close"].rolling(self.short_window).mean().iloc[-2])
            )
            sma50_prev = (
                float(prev["sma_50"])
                if "sma_50" in prev.index and not pd.isna(prev["sma_50"])
                else float(sym_data["close"].rolling(self.long_window).mean().iloc[-2])
            )

            if any(pd.isna(v) for v in [sma20_now, sma50_now, sma20_prev, sma50_prev]):
                continue

            golden_cross = sma20_prev <= sma50_prev and sma20_now > sma50_now
            death_cross = sma20_prev >= sma50_prev and sma20_now < sma50_now

            adx_raw = latest.get("adx", None)
            adx = float(adx_raw) if adx_raw is not None and not pd.isna(adx_raw) else None
            vol_ratio_raw = latest.get("volume_ratio", None)
            vol_ok = (
                vol_ratio_raw is None
                or pd.isna(vol_ratio_raw)
                or float(vol_ratio_raw) >= self.volume_min_ratio
            )
            atr_raw = latest.get("atr_20", None)
            atr = float(atr_raw) if atr_raw is not None and not pd.isna(atr_raw) else None

            # --- SELL ---
            if symbol in self.positions:
                days_held = self.get_days_held(symbol, sym_latest_date)
                entry_price = getattr(self, "entry_prices", {}).get(symbol)
                shares = self.positions[symbol]
                exit_reason = None
                exit_shares = shares
                partial_exit = False

                if death_cross:
                    exit_reason = f"Death cross: SMA{self.short_window} ({sma20_now:.2f}) crossed below SMA{self.long_window} ({sma50_now:.2f})"
                elif entry_price and entry_price > 0:
                    pnl_pct = (price - entry_price) / entry_price
                    if pnl_pct >= self.profit_target_pct and symbol not in self._partial_exit_done:
                        exit_shares = max(1, shares // 2)
                        exit_reason = f"Partial profit target: {pnl_pct:.1%} → selling 50%"
                        partial_exit = True

                if exit_reason is None and days_held >= self.hold_days:
                    if (
                        entry_price
                        and entry_price > 0
                        and days_held < self.max_hold_days
                        and (price - entry_price) / entry_price >= self.let_winners_run_pct
                        and sma20_now > sma50_now  # trend intact
                    ):
                        pass  # let winner run
                    elif 365 <= days_held < 370:
                        pass  # hold to 1-year LTCG threshold
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
                            "confidence": 1.0,
                            "reasoning": exit_reason,
                            "asof_date": sym_latest_date,
                            "partial_exit": partial_exit,
                        }
                    )
                    if partial_exit:
                        self._partial_exit_done.add(symbol)
                continue

            # --- BUY ---
            if not golden_cross or not market_uptrend:
                continue
            if adx is not None and adx < self.adx_min:
                logger.debug("MA skip %s: ADX %.1f < %.1f (choppy)", symbol, adx, self.adx_min)
                continue
            if not vol_ok:
                continue

            shares = self.calculate_position_size(price, atr=atr, max_position_pct=0.09)
            if shares <= 0:
                continue

            gap_pct = (sma20_now - sma50_now) / sma50_now if sma50_now else 0.0
            confidence = min(0.88, 0.55 + abs(gap_pct) * 5 + (((adx or 25) - 20) / 100))
            signals.append(
                {
                    "symbol": symbol,
                    "action": "BUY",
                    "shares": shares,
                    "price": price,
                    "value": shares * price,
                    "confidence": confidence,
                    "reasoning": (
                        f"Golden cross: SMA{self.short_window} ({sma20_now:.2f}) > "
                        f"SMA{self.long_window} ({sma50_now:.2f})"
                        + (f", ADX {adx:.1f}" if adx else "")
                    ),
                    "atr": atr,
                    "asof_date": sym_latest_date,
                }
            )

        return signals

    def get_description(self) -> str:
        return (
            f"Golden/death cross: SMA{self.short_window} vs SMA{self.long_window}, "
            f"ADX>{self.adx_min} trend filter, hold up to {self.hold_days}d"
        )
