#!/usr/bin/env python3
"""
Strategy 5: Post-Earnings Announcement Drift (PEAD)

Exploits the most persistent market anomaly: stocks that report positive
earnings surprises continue drifting upward for 60+ days.

Primary signal source: data/earnings_calendar.csv (fetched by
scripts/update_earnings_calendar.py via Alpha Vantage EARNINGS_CALENDAR).
Fallback: price-based proxy (volume spike + abnormal return) when the
calendar file is absent or stale.

Buy after positive surprise within the drift entry window, sell after
profit target, stop-loss, drift window expiry, or negative re-surprise.

Academic reference:
  Bernard & Thomas (1989), Garfinkel et al. (2024) — ~20% annual return
  from top SUE decile long portfolio.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import logging

import numpy as np
import pandas as pd

from src.core.strategy_base import TradingStrategy

_PROJECT_ROOT = Path(__file__).parent.parent.parent
_EARNINGS_CALENDAR_PATH = _PROJECT_ROOT / "data" / "earnings_calendar.csv"

logger = logging.getLogger(__name__)


class EarningsDriftStrategy(TradingStrategy):
    """Post-Earnings Announcement Drift strategy.

    Uses actual earnings calendar (data/earnings_calendar.csv) as the primary
    event trigger.  Falls back to volume-spike proxy when the file is absent.
    """

    def __init__(self, strategy_id: int, capital: float):
        super().__init__(
            strategy_id=strategy_id,
            name="Earnings Drift",
            capital=capital,
        )
        from src.utils.config_loader import get_config as _gc

        _cfg = _gc()
        self.volume_spike_threshold = _cfg.get(
            "strategies.earnings_drift.volume_spike_threshold", 1.3
        )
        self.return_threshold_mult = 2.0
        self.drift_hold_days = _cfg.get("strategies.earnings_drift.drift_hold_days", 40)
        self.min_surprise_return = _cfg.get("strategies.earnings_drift.min_surprise_return", 0.02)
        self.profit_target_pct = _cfg.get("strategies.earnings_drift.profit_target_pct", 0.20)
        self.stop_loss_pct = _cfg.get("strategies.earnings_drift.stop_loss_pct", 0.10)
        self.entry_dates: dict = {}
        self.event_returns: dict = {}
        self._partial_exit_done: set = set()
        # Entry window: buy up to N trading days after the earnings date
        self.calendar_entry_window_days = _cfg.get(
            "strategies.earnings_drift.calendar_entry_window_days", 5
        )

    def _spy_above_sma50(self, market_data: pd.DataFrame) -> bool:
        """Return True if SPY is above its 50-day SMA (broad market uptrend gate)."""
        spy_rows = (
            market_data[market_data["symbol"] == "SPY"]
            if "symbol" in market_data.columns
            else pd.DataFrame()
        )
        if len(spy_rows) < 50:
            return True
        prices = spy_rows["close"].values
        sma50 = float(np.mean(prices[-50:]))
        above = float(prices[-1]) > sma50
        if not above:
            logger.info("Earnings Drift: SPY below 50-day SMA — BUY suppressed")
        return above

    def _load_earnings_calendar(self) -> pd.DataFrame:
        """Load earnings calendar from disk. Returns empty DataFrame if unavailable."""
        try:
            if not _EARNINGS_CALENDAR_PATH.exists():
                return pd.DataFrame()
            df = pd.read_csv(_EARNINGS_CALENDAR_PATH, parse_dates=["reportDate"])
            return df
        except Exception as exc:
            logger.warning("Could not load earnings calendar: %s", exc)
            return pd.DataFrame()

    def _symbols_with_recent_earnings(
        self, as_of_date: pd.Timestamp, symbols: set[str]
    ) -> set[str]:
        """Return symbols that reported earnings in the last calendar_entry_window_days."""
        cal = self._load_earnings_calendar()
        if cal.empty:
            return set()
        window_start = as_of_date - pd.Timedelta(days=self.calendar_entry_window_days)
        recent = cal[
            (cal["symbol"].isin(symbols))
            & (cal["reportDate"] >= window_start)
            & (cal["reportDate"] <= as_of_date)
        ]
        result = set(recent["symbol"].unique())
        if result:
            logger.info(
                "Earnings calendar: %d symbols reported in last %dd: %s",
                len(result),
                self.calendar_entry_window_days,
                sorted(result),
            )
        return result

    def _detect_earnings_events(self, symbol_data: pd.DataFrame) -> dict | None:
        """
        Detect likely earnings announcement events in recent data.

        Returns dict with event info if detected in last 3 trading days,
        None otherwise.
        """
        if len(symbol_data) < 25:
            return None

        # Need volume and close columns
        if "volume" not in symbol_data.columns or "close" not in symbol_data.columns:
            return None

        # Calculate rolling stats for detection
        vol_sma20 = symbol_data["volume"].rolling(20).mean()
        daily_returns = symbol_data["close"].pct_change()
        return_vol_20 = daily_returns.rolling(20).std()

        # Check last 3 trading days for an earnings event
        for lookback in range(1, 4):
            if lookback >= len(symbol_data):
                continue

            idx = -lookback
            day_volume = symbol_data["volume"].iloc[idx]
            day_return = daily_returns.iloc[idx]
            avg_volume = (
                vol_sma20.iloc[idx - 1] if abs(idx - 1) < len(vol_sma20) else vol_sma20.iloc[-5]
            )
            avg_vol = (
                return_vol_20.iloc[idx - 1]
                if abs(idx - 1) < len(return_vol_20)
                else return_vol_20.iloc[-5]
            )

            if (
                pd.isna(day_volume)
                or pd.isna(avg_volume)
                or pd.isna(day_return)
                or pd.isna(avg_vol)
            ):
                continue
            if avg_volume <= 0 or avg_vol <= 0:
                continue

            volume_ratio = day_volume / avg_volume
            return_magnitude = abs(day_return)

            # Earnings event detection criteria.
            # The absolute return threshold is set higher than min_surprise_return (2%) to
            # avoid triggering on ex-dividend dates: quarterly dividends typically produce
            # 0.5–2.5% price moves with a volume spike, which matches the proxy pattern.
            # Genuine post-earnings surprises are typically ≥3–4%. Using 3.5% here gives
            # meaningful separation. Calendar-based signals (primary path) are unaffected.
            _proxy_min_return = max(self.min_surprise_return, 0.035)
            is_volume_spike = volume_ratio >= self.volume_spike_threshold
            is_abnormal_return = return_magnitude >= self.return_threshold_mult * avg_vol
            is_significant = return_magnitude >= _proxy_min_return

            if is_volume_spike and is_abnormal_return and is_significant:
                return {
                    "days_ago": lookback,
                    "event_return": float(day_return),
                    "volume_ratio": float(volume_ratio),
                    "return_vs_vol": float(return_magnitude / avg_vol),
                    "direction": "positive" if day_return > 0 else "negative",
                    "event_date": symbol_data.index[idx],
                }

        return None

    def generate_signals(self, market_data: pd.DataFrame) -> list[dict]:
        """Generate signals based on actual earnings calendar (primary) or volume proxy (fallback)."""
        signals = []
        sym_map: dict = {}
        for _ed_key, _ed_grp in market_data.groupby("symbol"):
            sym_map[_ed_key] = _ed_grp
        latest_date = market_data.index.max()
        market_uptrend = self._spy_above_sma50(market_data)

        # --- Primary: actual earnings calendar ---
        calendar_symbols = self._symbols_with_recent_earnings(
            as_of_date=latest_date,
            symbols=set(sym_map.keys()),
        )
        using_calendar = bool(calendar_symbols)
        if not using_calendar:
            logger.info(
                "Earnings calendar empty or no recent events — falling back to volume proxy"
            )

        for symbol, symbol_data in sym_map.items():
            if len(symbol_data) < 25:
                continue

            latest = symbol_data.iloc[-1]
            price = float(latest["close"])
            atr_raw = latest.get("atr_20", None)
            atr = float(atr_raw) if atr_raw is not None and not pd.isna(atr_raw) else 0
            sym_latest_date = symbol_data.index[-1]

            # --- SELL: check existing positions first ---
            if symbol in self.positions:
                days_held = self.get_days_held(symbol, sym_latest_date)
                entry_price = getattr(self, "entry_prices", {}).get(symbol)
                shares = self.positions[symbol]

                exit_reason = None
                exit_confidence = 0.8
                exit_shares = shares
                partial_exit = False

                if entry_price and entry_price > 0:
                    pnl_pct = (price - entry_price) / entry_price
                    # Partial exit at profit target — sell 50%, let trailing stop run the rest.
                    # Stop-losses handled by StopLossManager (trailing ATR ratchet).
                    if pnl_pct >= self.profit_target_pct and symbol not in self._partial_exit_done:
                        exit_shares = max(1, shares // 2)
                        exit_reason = (
                            f"PEAD partial profit target: {pnl_pct:.1%} gain → selling 50% "
                            f"({exit_shares} of {shares} shares)"
                        )
                        exit_confidence = 0.95
                        partial_exit = True

                # Tax-aware: extend drift hold to cross 1-year mark if close.
                if exit_reason is None and days_held >= self.drift_hold_days:
                    if 365 <= days_held < 370:
                        pass  # extend hold for long-term capital gains treatment
                    else:
                        exit_reason = f"Drift window expired ({days_held}d held)"

                if exit_reason is None:
                    event = self._detect_earnings_events(symbol_data)
                    if event and event["direction"] == "negative":
                        exit_reason = f'Negative re-surprise ({event["event_return"]:.1%}), exiting'
                        exit_confidence = 0.9

                if exit_reason:
                    signals.append(
                        {
                            "symbol": symbol,
                            "action": "SELL",
                            "shares": exit_shares,
                            "price": price,
                            "value": exit_shares * price,
                            "confidence": exit_confidence,
                            "reasoning": exit_reason,
                            "partial_exit": partial_exit,
                        }
                    )
                    if partial_exit:
                        self._partial_exit_done.add(symbol)
                continue

            # Market regime gate: suppress new BUY entries when SPY is below 50-day SMA.
            if not market_uptrend:
                continue

            # --- BUY: calendar path ---
            if using_calendar:
                if symbol not in calendar_symbols:
                    continue
                # Confirm the post-earnings price action is positive
                event = self._detect_earnings_events(symbol_data)
                if event and event["direction"] == "negative":
                    logger.info(
                        "Skipping %s: negative post-earnings move despite calendar trigger", symbol
                    )
                    continue
                surprise_mag = abs(event["event_return"]) if event else self.min_surprise_return
                confidence = min(0.90, 0.55 + surprise_mag * 4)
                reasoning = f"PEAD (calendar): earnings reported, entry within {self.calendar_entry_window_days}d window"
                if event:
                    reasoning += f', {event["event_return"]:+.1%} day-of move'

            # --- BUY: volume-proxy fallback ---
            else:
                event = self._detect_earnings_events(symbol_data)
                if event is None or event["direction"] != "positive":
                    continue
                surprise_mag = abs(event["event_return"])
                confidence = min(0.95, 0.5 + surprise_mag * 5)
                reasoning = (
                    f'PEAD (proxy): +{event["event_return"]:.1%} surprise {event["days_ago"]}d ago, '
                    f'vol spike {event["volume_ratio"]:.1f}x'
                )

            shares = self.calculate_position_size(
                price, atr=atr if atr > 0 else None, max_position_pct=0.10
            )
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
                    "reasoning": reasoning,
                    "atr": atr if atr > 0 else None,
                    "asof_date": sym_latest_date,
                }
            )

        return signals

    def get_description(self) -> str:
        return (
            "Post-Earnings Announcement Drift: buys after positive earnings surprises "
            "(detected via volume spike + abnormal return), holds for drift period"
        )
