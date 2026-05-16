#!/usr/bin/env python3
"""
Strategy 1: RSI Mean Reversion
Buy when RSI < 30 (oversold), sell after 20 days
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


import pandas as pd

from src.core.strategy_base import TradingStrategy
from src.utils.config_loader import get_config


class RSIMeanReversionStrategy(TradingStrategy):
    """RSI-based mean reversion strategy"""

    def __init__(self, strategy_id: int, capital: float):
        super().__init__(strategy_id=strategy_id, name="RSI Mean Reversion", capital=capital)
        # Load parameters from config
        config = get_config()
        self.rsi_period = config.get("strategies.rsi_mean_reversion.rsi_period", 14)
        self.rsi_oversold = config.get("strategies.rsi_mean_reversion.rsi_oversold", 30)
        self.rsi_overbought = config.get("strategies.rsi_mean_reversion.rsi_overbought", 70)
        self.rsi_slope_threshold = config.get(
            "strategies.rsi_mean_reversion.rsi_slope_threshold", 5
        )
        self.vwap_proximity_pct = config.get(
            "strategies.rsi_mean_reversion.vwap_proximity_pct", 0.02
        )

        # Legacy attributes for backward compatibility
        self.rsi_threshold = 35  # entry threshold (< 35 = meaningfully oversold, not just dip)
        self.rsi_exit = 55  # exit threshold (> 55 = recovery complete)
        self.hold_days = 20
        self.max_hold_days = 40  # absolute ceiling even for profitable positions
        self.profit_target_pct = 0.05  # exit at 5% profit
        self.stop_loss_pct = 0.07  # exit at 7% loss (mean reversion can fail hard)
        self.let_winners_run_pct = 0.03  # hold past time exit if ≥3% in profit and RSI not extended
        self.volume_spike_threshold = 1.5  # skip if volume >1.5x avg (capitulation, not reversion)

    def generate_signals(self, market_data: pd.DataFrame) -> list[dict]:
        """Generate buy signals for oversold stocks with improved filters."""
        signals = []

        if market_data.empty or "symbol" not in market_data.columns:
            return signals

        sym_map = {sym: grp for sym, grp in market_data.groupby("symbol")}  # noqa: C416

        for symbol, symbol_data in sym_map.items():
            if len(symbol_data) < 2:
                continue

            latest = symbol_data.iloc[-1]
            latest_date = symbol_data.index[-1]

            if "rsi" not in latest.index or pd.isna(latest["rsi"]):
                continue

            rsi = float(latest["rsi"])
            price = float(latest["close"])
            atr = latest.get("atr_20", None)
            if atr is not None and pd.isna(atr):
                atr = None

            # RSI slope (1-day delta)
            rsi_slope = float(symbol_data["rsi"].iloc[-1] - symbol_data["rsi"].iloc[-2])

            # Trend filter: skip oversold buys when price is below SMA-100 (downtrend).
            sma_100 = latest.get("sma_100", None)
            in_uptrend = sma_100 is None or pd.isna(sma_100) or price > float(sma_100)

            # Volume filter: skip if today's volume > 1.5x 20-day avg (panic/capitulation selling).
            # High-volume oversold = distribution, not mean reversion setup.
            vol_ratio_raw = latest.get("volume_ratio", None)
            is_capitulation = (
                vol_ratio_raw is not None
                and not pd.isna(vol_ratio_raw)
                and float(vol_ratio_raw) > self.volume_spike_threshold
            )

            # BUY: RSI < 35 AND turning up AND uptrend AND not capitulation selling
            if (
                rsi < self.rsi_threshold
                and rsi_slope > 0
                and in_uptrend
                and not is_capitulation
                and symbol not in self.positions
            ):
                shares = self.calculate_position_size(price, atr=atr, max_position_pct=0.10)
                if shares <= 0:
                    continue
                signals.append(
                    {
                        "symbol": symbol,
                        "action": "BUY",
                        "shares": shares,
                        "price": price,
                        "value": shares * price,
                        "confidence": max(
                            0.1, min(1.0, (self.rsi_threshold - rsi) / self.rsi_threshold)
                        ),
                        "reasoning": (
                            f"RSI {rsi:.1f} < {self.rsi_threshold} (oversold), slope {rsi_slope:+.2f} (turning up)"
                            + (
                                f", vol_ratio {float(vol_ratio_raw):.1f}x (normal)"
                                if vol_ratio_raw is not None
                                else ""
                            )
                        ),
                        "atr": atr,
                        "asof_date": latest_date,
                    }
                )

            # SELL: RSI recovered > 55  OR  5% profit target  OR  7% stop-loss  OR  20-day time exit
            elif symbol in self.positions:
                days_held = self.get_days_held(symbol, latest_date)
                shares = self.positions[symbol]
                entry_price = getattr(self, "entry_prices", {}).get(symbol)

                exit_reason = None
                if rsi > self.rsi_exit:
                    exit_reason = f"RSI {rsi:.1f} > {self.rsi_exit} (mean reversion complete)"
                elif entry_price and entry_price > 0:
                    profit_pct = (price - entry_price) / entry_price
                    if profit_pct >= self.profit_target_pct:
                        exit_reason = f"Profit target hit: {profit_pct:.1%} gain vs {self.profit_target_pct:.0%} target"
                    elif profit_pct <= -self.stop_loss_pct:
                        exit_reason = f"Stop-loss hit: {profit_pct:.1%} loss (limit -{self.stop_loss_pct:.0%})"
                if exit_reason is None and days_held >= self.hold_days:
                    # Let winners run: if profitable and RSI not yet extended, hold past the
                    # nominal exit up to max_hold_days (avoids cutting a working trade short).
                    if (
                        entry_price
                        and entry_price > 0
                        and days_held < self.max_hold_days
                        and (price - entry_price) / entry_price >= self.let_winners_run_pct
                        and rsi < self.rsi_exit
                    ):
                        pass  # still healthy — keep holding
                    else:
                        exit_reason = f"Held {days_held}d >= {self.hold_days}d (time-based exit)"

                if exit_reason:
                    signals.append(
                        {
                            "symbol": symbol,
                            "action": "SELL",
                            "shares": shares,
                            "price": price,
                            "value": shares * price,
                            "confidence": 1.0,
                            "reasoning": exit_reason,
                            "asof_date": latest_date,
                        }
                    )

        return signals

    def get_description(self) -> str:
        return f"Buy when RSI < {self.rsi_threshold}, sell after {self.hold_days} days"
