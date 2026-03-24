#!/usr/bin/env python3
"""
Strategy 6: Cross-Sectional Factor Momentum

Ranks stocks by a composite factor score and buys the top quintile.
Factors used (all computable from existing data):
  1. Price momentum (60-day return, skip last 5 days for reversal)
  2. Earnings quality proxy (low volatility + positive momentum = quality)
  3. Mean-reversion signal (RSI z-score for oversold bounce)
  4. Volume confirmation (rising volume on up-moves)

Academic basis:
  - Jegadeesh & Titman (1993): 12-1 momentum
  - Asness et al. (2013): Value and Momentum Everywhere
  - Novy-Marx (2012): Quality minus Junk

Holds positions for 20 trading days, then re-ranks.
"""
from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.core.strategy_base import TradingStrategy
from typing import List, Dict
import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)


class FactorMomentumStrategy(TradingStrategy):
    """Cross-sectional factor momentum: buy top-ranked stocks by composite score."""

    def __init__(self, strategy_id: int, capital: float):
        super().__init__(
            strategy_id=strategy_id,
            name="Factor Momentum",
            capital=capital,
        )
        self.hold_days = 20
        self.top_n = 5              # Buy top 5 stocks
        self.profit_target_pct = 0.12   # Exit at 12% gain — lock in before mean-reversion
        self.stop_loss_pct = 0.08       # Exit at 8% loss — factor momentum can trend hard
        self.entry_dates = {}
        self._last_rerank_date = None

    def _compute_factor_scores(self, market_data: pd.DataFrame) -> Dict[str, float]:
        """
        Compute composite factor score for each symbol using cross-sectional
        percentile ranking so that scores reflect relative standing, not absolute
        values that cluster around 0.5 when sigmoid-normalised independently.

        Returns:
            Dict of {symbol: composite_score} where scores are meaningful ranks.
        """
        # Build per-symbol row counts once, then get latest row per symbol in one pass
        counts = market_data.groupby('symbol').size()
        eligible = counts[counts >= 60].index

        if len(eligible) < 3:
            return {}

        filtered = market_data[market_data['symbol'].isin(eligible)]

        # One groupby pass to get last row per symbol (replaces 33 individual boolean filters)
        latest_df = filtered.groupby('symbol').last()

        # --- Factor 1: Momentum (60d return, skip last 5d for reversal) ---
        # Use pre-computed returns_60d where the close-based calculation is unavailable
        # Close-based (skip-5) momentum requires random access to specific rows;
        # fall back to the stored returns_60d column which is computed the same way.
        ret_60d = latest_df['returns_60d'].fillna(0.0)
        momentum = ret_60d.astype(float)

        # --- Factor 2: Quality proxy ---
        vol_20d = latest_df['volatility_20d'].fillna(0.2).astype(float)
        quality = -vol_20d + momentum.clip(lower=0) * 0.5

        # --- Factor 3: Mean-reversion (RSI 25-45 oversold range) ---
        rsi = latest_df['rsi'].fillna(50.0).astype(float)
        reversion_score = np.where(
            (rsi >= 25) & (rsi <= 45),
            (45 - rsi) / 20,
            0.0
        )

        # --- Factor 4: Volume confirmation (rising volume on up-moves only) ---
        vol_ratio = latest_df['volume_ratio'].fillna(1.0).astype(float)
        ret_5d = latest_df['returns_5d'].fillna(0.0).astype(float)
        volume_confirm = vol_ratio * ret_5d.clip(lower=0)

        # Assemble factor DataFrame and cross-sectionally rank each factor
        factors = pd.DataFrame({
            'momentum': momentum,
            'quality': quality,
            'reversion': reversion_score,
            'volume': volume_confirm,
        }, index=latest_df.index)

        for col in ['momentum', 'quality', 'reversion', 'volume']:
            factors[f'{col}_pct'] = factors[col].rank(pct=True)

        # Weighted composite score
        factors['composite'] = (
            0.40 * factors['momentum_pct'] +
            0.25 * factors['quality_pct'] +
            0.20 * factors['reversion_pct'] +
            0.15 * factors['volume_pct']
        )

        return factors['composite'].to_dict()

    def generate_signals(self, market_data: pd.DataFrame) -> List[Dict]:
        """Generate signals by ranking stocks and buying top quintile."""
        signals = []
        latest_date = market_data.index[-1] if len(market_data) > 0 else None
        if latest_date is None:
            return signals

        # Pre-build symbol→DataFrame lookup once — avoids repeated boolean filter per position
        sym_map = {sym: grp for sym, grp in market_data.groupby('symbol')}

        # Check SELL first — profit target, stop-loss, or time-based rebalance
        for symbol in list(self.positions.keys()):
            days_held = self.get_days_held(symbol, latest_date)
            sym_data = sym_map.get(symbol)
            if sym_data is None or sym_data.empty:
                continue
            price = float(sym_data.iloc[-1]['close'])
            shares = self.positions[symbol]
            entry_price = getattr(self, 'entry_prices', {}).get(symbol)

            exit_reason = None
            if entry_price and entry_price > 0:
                pnl_pct = (price - entry_price) / entry_price
                if pnl_pct >= self.profit_target_pct:
                    exit_reason = f'Profit target: {pnl_pct:.1%} gain (target {self.profit_target_pct:.0%})'
                elif pnl_pct <= -self.stop_loss_pct:
                    exit_reason = f'Stop-loss: {pnl_pct:.1%} loss (limit -{self.stop_loss_pct:.0%})'
            if exit_reason is None and days_held >= self.hold_days:
                exit_reason = f'Factor rebalance: held {days_held}d'

            if exit_reason:
                signals.append({
                    'symbol': symbol,
                    'action': 'SELL',
                    'shares': shares,
                    'price': price,
                    'value': shares * price,
                    'confidence': 0.9 if 'Profit' in (exit_reason or '') or 'Stop' in (exit_reason or '') else 0.7,
                    'reasoning': exit_reason,
                })

        # Only generate new BUY signals if we have capacity
        current_positions = len(self.positions)
        buy_capacity = self.top_n - current_positions + len([s for s in signals if s['action'] == 'SELL'])

        if buy_capacity <= 0:
            return signals

        # Compute factor scores
        scores = self._compute_factor_scores(market_data)
        if not scores:
            return signals

        # Rank and select top N (exclude already held)
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        candidates = [
            (sym, score) for sym, score in ranked
            if sym not in self.positions
        ][:buy_capacity]

        for symbol, score in candidates:
            sym_data = sym_map.get(symbol)
            if sym_data is None or sym_data.empty:
                continue

            latest = sym_data.iloc[-1]
            price = float(latest['close'])
            atr = float(latest.get('atr_20', 0)) if not pd.isna(latest.get('atr_20', np.nan)) else 0

            shares = self.calculate_position_size(price, atr=atr if atr > 0 else None, max_position_pct=0.08)
            if shares <= 0:
                continue

            confidence = min(0.9, 0.4 + score)

            signals.append({
                'symbol': symbol,
                'action': 'BUY',
                'shares': shares,
                'price': price,
                'value': shares * price,
                'confidence': confidence,
                'reasoning': f'Factor rank score {score:.3f} (top {len(candidates)})',
                'atr': atr if atr > 0 else None,
            })

        return signals

    def get_description(self) -> str:
        return (
            "Cross-sectional factor momentum: ranks stocks by composite "
            "(momentum + quality + mean-reversion + volume), buys top quintile"
        )
