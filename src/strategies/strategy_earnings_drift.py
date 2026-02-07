#!/usr/bin/env python3
"""
Strategy 5: Post-Earnings Announcement Drift (PEAD)

Exploits the most persistent market anomaly: stocks that report positive
earnings surprises continue drifting upward for 60+ days.

Since we lack actual earnings dates/estimates, we detect earnings events
via a price-based proxy:
  - Abnormal volume spike (>2x 20-day avg)
  - Combined with abnormal return (|return| > 2x 20-day vol)
  - On a single day (earnings are point events)

Buy after positive surprise, sell after negative or after drift window.

Academic reference:
  Bernard & Thomas (1989), Garfinkel et al. (2024) — ~20% annual return
  from top SUE decile long portfolio.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.core.strategy_base import TradingStrategy
from typing import List, Dict
import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)


class EarningsDriftStrategy(TradingStrategy):
    """Post-Earnings Announcement Drift strategy using price-based surprise proxy."""

    def __init__(self, strategy_id: int, capital: float):
        super().__init__(
            strategy_id=strategy_id,
            name="Earnings Drift",
            capital=capital,
        )
        self.volume_spike_threshold = 2.0   # Volume must be 2x 20-day avg
        self.return_threshold_mult = 2.0    # Return must be 2x 20-day vol
        self.drift_hold_days = 40           # Hold for drift period (academic: 60-90d, we use 40 for safety)
        self.min_surprise_return = 0.02     # Minimum 2% absolute return on event day
        self.entry_dates = {}
        self.event_returns = {}             # Track the surprise magnitude per position

    def _detect_earnings_events(self, symbol_data: pd.DataFrame) -> Dict:
        """
        Detect likely earnings announcement events in recent data.

        Returns dict with event info if detected in last 3 trading days,
        None otherwise.
        """
        if len(symbol_data) < 25:
            return None

        # Need volume and close columns
        if 'volume' not in symbol_data.columns or 'close' not in symbol_data.columns:
            return None

        # Calculate rolling stats for detection
        vol_sma20 = symbol_data['volume'].rolling(20).mean()
        daily_returns = symbol_data['close'].pct_change()
        return_vol_20 = daily_returns.rolling(20).std()

        # Check last 3 trading days for an earnings event
        for lookback in range(1, 4):
            if lookback >= len(symbol_data):
                continue

            idx = -lookback
            day_volume = symbol_data['volume'].iloc[idx]
            day_return = daily_returns.iloc[idx]
            avg_volume = vol_sma20.iloc[idx - 1] if abs(idx - 1) < len(vol_sma20) else vol_sma20.iloc[-5]
            avg_vol = return_vol_20.iloc[idx - 1] if abs(idx - 1) < len(return_vol_20) else return_vol_20.iloc[-5]

            if pd.isna(day_volume) or pd.isna(avg_volume) or pd.isna(day_return) or pd.isna(avg_vol):
                continue
            if avg_volume <= 0 or avg_vol <= 0:
                continue

            volume_ratio = day_volume / avg_volume
            return_magnitude = abs(day_return)

            # Earnings event detection criteria
            is_volume_spike = volume_ratio >= self.volume_spike_threshold
            is_abnormal_return = return_magnitude >= self.return_threshold_mult * avg_vol
            is_significant = return_magnitude >= self.min_surprise_return

            if is_volume_spike and is_abnormal_return and is_significant:
                return {
                    'days_ago': lookback,
                    'event_return': float(day_return),
                    'volume_ratio': float(volume_ratio),
                    'return_vs_vol': float(return_magnitude / avg_vol),
                    'direction': 'positive' if day_return > 0 else 'negative',
                    'event_date': symbol_data.index[idx],
                }

        return None

    def generate_signals(self, market_data: pd.DataFrame) -> List[Dict]:
        """Generate signals based on detected earnings surprises."""
        signals = []

        for symbol in market_data['symbol'].unique():
            symbol_data = market_data[market_data['symbol'] == symbol]
            if len(symbol_data) < 25:
                continue

            latest = symbol_data.iloc[-1]
            price = float(latest['close'])
            atr = float(latest.get('atr_20', 0)) if not pd.isna(latest.get('atr_20', np.nan)) else 0
            latest_date = symbol_data.index[-1]

            # Check for SELL first (existing positions)
            if symbol in self.positions:
                days_held = self.get_days_held(symbol, latest_date)

                # Exit after drift window
                if days_held >= self.drift_hold_days:
                    shares = self.positions[symbol]
                    signals.append({
                        'symbol': symbol,
                        'action': 'SELL',
                        'shares': shares,
                        'price': price,
                        'value': shares * price,
                        'confidence': 0.8,
                        'reasoning': f'Drift window expired ({days_held}d held)',
                    })
                    continue

                # Exit if a NEW negative surprise detected while holding
                event = self._detect_earnings_events(symbol_data)
                if event and event['direction'] == 'negative':
                    shares = self.positions[symbol]
                    signals.append({
                        'symbol': symbol,
                        'action': 'SELL',
                        'shares': shares,
                        'price': price,
                        'value': shares * price,
                        'confidence': 0.9,
                        'reasoning': f'Negative surprise detected ({event["event_return"]:.1%}), exiting',
                    })
                continue

            # Check for BUY (new positions only)
            event = self._detect_earnings_events(symbol_data)
            if event is None:
                continue

            # Only buy on POSITIVE surprises
            if event['direction'] != 'positive':
                continue

            # Confidence scales with surprise magnitude
            surprise_mag = abs(event['event_return'])
            confidence = min(0.95, 0.5 + surprise_mag * 5)  # 2% surprise → 0.6, 5% → 0.75, 9% → 0.95

            shares = self.calculate_position_size(price, atr=atr if atr > 0 else None, max_position_pct=0.10)
            if shares <= 0:
                continue

            signals.append({
                'symbol': symbol,
                'action': 'BUY',
                'shares': shares,
                'price': price,
                'value': shares * price,
                'confidence': confidence,
                'reasoning': (
                    f'PEAD: +{event["event_return"]:.1%} surprise {event["days_ago"]}d ago, '
                    f'vol spike {event["volume_ratio"]:.1f}x'
                ),
                'atr': atr if atr > 0 else None,
            })

        return signals

    def get_description(self) -> str:
        return (
            "Post-Earnings Announcement Drift: buys after positive earnings surprises "
            "(detected via volume spike + abnormal return), holds for drift period"
        )
