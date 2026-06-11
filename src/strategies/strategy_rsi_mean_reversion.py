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

        # Exit / hold parameters — pulled from config where available, otherwise use
        # sensible defaults that match the strategy's mean-reversion thesis.
        self.rsi_threshold = config.get("strategies.rsi_mean_reversion.rsi_entry_threshold", 35)
        self.rsi_exit = config.get("strategies.rsi_mean_reversion.rsi_exit_threshold", 55)
        self.hold_days = config.get("strategies.rsi_mean_reversion.hold_days", 20)
        self.max_hold_days = config.get("strategies.rsi_mean_reversion.max_hold_days", 40)
        self.min_hold_days = config.get("strategies.rsi_mean_reversion.min_hold_days", 0)
        self.profit_target_pct = config.get("strategies.rsi_mean_reversion.profit_target_pct", 0.05)
        self._partial_exit_done: set = set()
        self.stop_loss_pct = config.get("strategies.rsi_mean_reversion.stop_loss_pct", 0.07)
        self.let_winners_run_pct = config.get(
            "strategies.rsi_mean_reversion.let_winners_run_pct", 0.03
        )
        self.volume_spike_threshold = config.get(
            "strategies.rsi_mean_reversion.volume_spike_threshold", 1.5
        )

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

            # SELL: RSI recovered > 55  OR  5% profit target (partial)  OR  20-day time exit
            # Stop-losses are handled by StopLossManager (trailing ATR-based stops).
            elif symbol in self.positions:
                days_held = self.get_days_held(symbol, latest_date)
                shares = self.positions[symbol]
                entry_price = getattr(self, "entry_prices", {}).get(symbol)

                exit_reason = None
                exit_shares = shares
                partial_exit = False

                if rsi > self.rsi_exit:
                    exit_reason = f"RSI {rsi:.1f} > {self.rsi_exit} (mean reversion complete)"
                elif entry_price and entry_price > 0:
                    profit_pct = (price - entry_price) / entry_price
                    if (
                        profit_pct >= self.profit_target_pct
                        and symbol not in self._partial_exit_done
                    ):
                        # First tranche: sell 50% and let trailing stop manage the rest.
                        exit_shares = max(1, shares // 2)
                        exit_reason = (
                            f"Partial profit target: {profit_pct:.1%} gain → selling 50% "
                            f"({exit_shares} of {shares} shares)"
                        )
                        partial_exit = True

                # Time exit via the shared min/soft/max policy. The thesis for
                # mean reversion is "RSI has not yet reverted" (rsi < rsi_exit
                # is guaranteed here — line above exits otherwise), so a LOSING
                # position holds to the max ceiling instead of being dumped at
                # hold_days. Winners are held past the soft horizon when the
                # let-winners-run or LTCG-deferral conditions apply.
                in_profit = (
                    entry_price is not None and entry_price > 0 and price > float(entry_price)
                )
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
                        thesis_intact=rsi < self.rsi_exit,
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
                            "confidence": 1.0,
                            "reasoning": exit_reason,
                            "asof_date": latest_date,
                            "partial_exit": partial_exit,
                        }
                    )
                    if partial_exit:
                        self._partial_exit_done.add(symbol)

        return signals

    def get_description(self) -> str:
        return f"Buy when RSI < {self.rsi_threshold}, sell after {self.hold_days} days"
