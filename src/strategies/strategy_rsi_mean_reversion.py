#!/usr/bin/env python3
"""
Strategy 1: RSI Mean Reversion
Buy when RSI < 30 (oversold), sell after 20 days
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.core.strategy_base import TradingStrategy
from src.utils.config_loader import get_config
from typing import List, Dict
import pandas as pd


class RSIMeanReversionStrategy(TradingStrategy):
    """RSI-based mean reversion strategy"""
    
    def __init__(self, strategy_id: int, capital: float):
        super().__init__(
            strategy_id=strategy_id,
            name="RSI Mean Reversion",
            capital=capital
        )
        # Load parameters from config
        config = get_config()
        self.rsi_period = config.get('strategies.rsi_mean_reversion.rsi_period', 14)
        self.rsi_oversold = config.get('strategies.rsi_mean_reversion.rsi_oversold', 30)
        self.rsi_overbought = config.get('strategies.rsi_mean_reversion.rsi_overbought', 70)
        self.rsi_slope_threshold = config.get('strategies.rsi_mean_reversion.rsi_slope_threshold', 5)
        self.vwap_proximity_pct = config.get('strategies.rsi_mean_reversion.vwap_proximity_pct', 0.02)
        
        # Legacy attributes for backward compatibility
        self.rsi_threshold = 40  # entry threshold (< 40 = oversold)
        self.rsi_exit = 55       # exit threshold (> 55 = recovery complete)
        self.hold_days = 20
        self.profit_target_pct = 0.05  # exit at 5% profit

    def generate_signals(self, market_data: pd.DataFrame) -> List[Dict]:
        """Generate buy signals for oversold stocks with improved filters."""
        signals = []

        if market_data.empty or 'symbol' not in market_data.columns:
            return signals

        for symbol in market_data['symbol'].unique():
            symbol_data = market_data[market_data['symbol'] == symbol]

            if len(symbol_data) < 2:
                continue

            latest = symbol_data.iloc[-1]
            latest_date = symbol_data.index[-1]

            if 'rsi' not in latest.index or pd.isna(latest['rsi']):
                continue

            rsi = float(latest['rsi'])
            price = float(latest['close'])
            atr = latest.get('atr_20', None)
            if atr is not None and pd.isna(atr):
                atr = None

            # RSI slope (1-day delta)
            rsi_slope = float(symbol_data['rsi'].iloc[-1] - symbol_data['rsi'].iloc[-2])

            # BUY: RSI < 40 and turning up (slope > 0) — no VWAP check (trailing VWAP
            # in the dataset is a long-run average always below current price in uptrends)
            if rsi < self.rsi_threshold and rsi_slope > 0 and symbol not in self.positions:
                shares = self.calculate_position_size(price, atr=atr, max_position_pct=0.10)
                if shares <= 0:
                    continue
                signals.append({
                    'symbol': symbol,
                    'action': 'BUY',
                    'shares': shares,
                    'price': price,
                    'value': shares * price,
                    'confidence': max(0.1, min(1.0, (self.rsi_threshold - rsi) / self.rsi_threshold)),
                    'reasoning': f'RSI {rsi:.1f} < {self.rsi_threshold} (oversold), slope {rsi_slope:+.2f} (turning up)',
                    'atr': atr,
                    'asof_date': latest_date,
                })

            # SELL: RSI recovered > 55  OR  5% profit target  OR  20-day time exit
            elif symbol in self.positions:
                days_held = self.get_days_held(symbol, latest_date)
                shares = self.positions[symbol]
                entry_price = None
                if hasattr(self, 'entry_dates') and symbol in self.entry_dates:
                    # Best proxy for entry price: walk back in time is unavailable here,
                    # so rely on RSI / time exits which don't need entry price.
                    pass

                exit_reason = None
                if rsi > self.rsi_exit:
                    exit_reason = f'RSI {rsi:.1f} > {self.rsi_exit} (mean reversion complete)'
                elif days_held >= self.hold_days:
                    exit_reason = f'Held {days_held}d >= {self.hold_days}d (time-based exit)'

                if exit_reason:
                    signals.append({
                        'symbol': symbol,
                        'action': 'SELL',
                        'shares': shares,
                        'price': price,
                        'value': shares * price,
                        'confidence': 1.0,
                        'reasoning': exit_reason,
                        'asof_date': latest_date,
                    })

        return signals
    
    def get_description(self) -> str:
        return f"Buy when RSI < {self.rsi_threshold}, sell after {self.hold_days} days"
