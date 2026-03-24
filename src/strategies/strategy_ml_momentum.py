#!/usr/bin/env python3
"""
Strategy 3: ML Momentum
Gradient Boosting classifier with 12 features predicting 5-day positive return.

Features span momentum (multi-timeframe), volatility, volume dynamics,
mean-reversion signals, and trend strength — all computable from OHLCV+indicators.

Training happens on the walk-forward training window; no lookahead.
"""
from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.core.strategy_base import TradingStrategy
from src.utils.config_loader import get_config
from typing import List, Dict
import pandas as pd
import numpy as np
import logging
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)

# Feature names — must match between _extract_row_features and _prepare_features
_FEATURE_NAMES = [
    'rsi',
    'rsi_slope_5d',
    'ret_5d',
    'ret_20d',
    'ret_60d',
    'vol_20d',
    'vol_ratio',
    'volume_ratio',
    'price_to_sma20',
    'price_to_sma50',
    'atr_pct',
    'adx',
]


class MLMomentumStrategy(TradingStrategy):
    """Gradient Boosting classifier predicting 5-day positive return."""

    def __init__(self, strategy_id: int, capital: float):
        super().__init__(
            strategy_id=strategy_id,
            name="ML Momentum",
            capital=capital,
        )
        config = get_config()
        self.min_confidence = config.get('strategies.ml_momentum.min_confidence', 0.55)
        self.hold_days = 5
        self.entry_dates = {}

        self.model = GradientBoostingClassifier(
            n_estimators=200,
            max_depth=3,          # shallow trees avoid overfitting on ~500 samples
            learning_rate=0.05,
            subsample=0.8,        # stochastic gradient boosting reduces variance
            min_samples_leaf=10,  # prevent fitting noise
            random_state=42,
        )
        self.scaler = StandardScaler()  # still scale for numerical stability
        self.is_trained = False
        self._train_date: str = ""  # track when model was last trained

    # ------------------------------------------------------------------
    # Feature extraction
    # ------------------------------------------------------------------
    @staticmethod
    def _safe(val, default=0.0):
        """Return default if val is NaN/None."""
        if val is None or (isinstance(val, float) and np.isnan(val)):
            return default
        return float(val)

    def _extract_row_features(self, row: pd.Series, symbol_data: pd.DataFrame) -> List[float]:
        """Extract 12 features from a single row + its history."""
        close = self._safe(row.get('close'), 1)
        rsi = self._safe(row.get('rsi'), 50)

        # RSI slope (5-day)
        if len(symbol_data) >= 6 and 'rsi' in symbol_data.columns:
            rsi_5_ago = self._safe(symbol_data['rsi'].iloc[-6], rsi)
            rsi_slope = rsi - rsi_5_ago
        else:
            rsi_slope = 0.0

        ret_5d = self._safe(row.get('returns_5d'), 0)
        ret_20d = self._safe(row.get('returns_20d'), 0)
        ret_60d = self._safe(row.get('returns_60d'), 0)
        vol_20d = self._safe(row.get('volatility_20d'), 0.15)

        # Volatility ratio (20d / 60d) — regime indicator
        vol_60d = self._safe(row.get('volatility_60d'), vol_20d)
        vol_ratio = vol_20d / vol_60d if vol_60d > 0 else 1.0

        volume_ratio = self._safe(row.get('volume_ratio'), 1.0)
        p_sma20 = self._safe(row.get('price_to_sma20'), 0)
        p_sma50 = self._safe(row.get('price_to_sma50'), 0)

        atr = self._safe(row.get('atr_20'), 0)
        atr_pct = atr / close if close > 0 else 0

        adx = self._safe(row.get('adx'), 0)

        return [
            rsi, rsi_slope, ret_5d, ret_20d, ret_60d,
            vol_20d, vol_ratio, volume_ratio,
            p_sma20, p_sma50, atr_pct, adx,
        ]

    # ------------------------------------------------------------------
    # Training
    # ------------------------------------------------------------------
    def _train_model(self, market_data: pd.DataFrame):
        """Train on historical data using pre-computed future_return_5d when available."""
        X_train = []
        y_train = []
        use_precomputed = 'future_return_5d' in market_data.columns

        sym_map = {sym: grp.copy() for sym, grp in market_data.groupby('symbol')}

        for symbol, sym in sym_map.items():
            if len(sym) < 60:
                continue

            for i in range(50, len(sym) - 5):
                row = sym.iloc[i]
                history = sym.iloc[max(0, i - 50):i + 1]

                if use_precomputed:
                    future_ret = row.get('future_return_5d', np.nan)
                    if pd.isna(future_ret):
                        continue
                    future_ret = float(future_ret)
                else:
                    future_ret = (sym.iloc[i + 5]['close'] - sym.iloc[i]['close']) / sym.iloc[i]['close']

                feats = self._extract_row_features(row, history)
                if any(np.isnan(f) or np.isinf(f) for f in feats):
                    continue

                X_train.append(feats)
                y_train.append(1 if future_ret > 0.005 else 0)  # 0.5% threshold (lower = more positives)

        if len(X_train) < 100:
            logger.warning("ML: insufficient training samples (%d), skipping", len(X_train))
            return

        X_arr = np.array(X_train)
        y_arr = np.array(y_train)
        self.scaler.fit(X_arr)
        X_scaled = self.scaler.transform(X_arr)
        self.model.fit(X_scaled, y_arr)
        self.is_trained = True
        pos_rate = y_arr.mean()
        logger.info("ML trained on %d samples (%.1f%% positive, precomputed=%s)",
                    len(y_arr), pos_rate * 100, use_precomputed)

    # ------------------------------------------------------------------
    # Signal generation
    # ------------------------------------------------------------------
    def generate_signals(self, market_data: pd.DataFrame) -> List[Dict]:
        """Generate signals using ML predictions."""
        signals = []

        # Retrain daily (model is cheap and data changes each day)
        today = str(market_data.index.max().date()) if len(market_data) > 0 else ""
        if not self.is_trained or today != self._train_date:
            self._train_model(market_data)
            self._train_date = today
        if not self.is_trained:
            return signals

        sym_map = {sym: grp for sym, grp in market_data.groupby('symbol')}

        for symbol, symbol_data in sym_map.items():
            if len(symbol_data) < 20:
                continue

            latest = symbol_data.iloc[-1]
            price = float(latest['close'])
            atr = self._safe(latest.get('atr_20'), None)

            try:
                feats = self._extract_row_features(latest, symbol_data)
                if any(np.isnan(f) or np.isinf(f) for f in feats):
                    continue

                X = self.scaler.transform([feats])
                prob_positive = float(self.model.predict_proba(X)[0][1])

                # BUY: probability above threshold. GBM produces wider probability
                # spread than LR, so 0.52 acts as a modest signal quality floor.
                if prob_positive > self.min_confidence and symbol not in self.positions:
                    shares = self.calculate_position_size(price, atr=atr, max_position_pct=0.10)
                    if shares <= 0:
                        continue
                    signals.append({
                        'symbol': symbol,
                        'action': 'BUY',
                        'shares': shares,
                        'price': price,
                        'value': shares * price,
                        'confidence': prob_positive,
                        'reasoning': f'ML prob positive 5d return: {prob_positive * 100:.1f}%',
                        'atr': atr if atr and atr > 0 else None,
                    })

                # SELL: held long enough or model flips bearish
                elif symbol in self.positions:
                    latest_date = symbol_data.index[-1]
                    days_held = self.get_days_held(symbol, latest_date)
                    if days_held >= self.hold_days or prob_positive < 0.40:
                        shares = self.positions[symbol]
                        signals.append({
                            'symbol': symbol,
                            'action': 'SELL',
                            'shares': shares,
                            'price': price,
                            'value': shares * price,
                            'confidence': 1.0 if days_held >= self.hold_days else (1.0 - prob_positive),
                            'reasoning': f'Held {days_held}d' if days_held >= self.hold_days else f'ML bearish ({prob_positive:.0%})',
                        })

            except Exception as e:
                logger.warning("ML prediction failed for %s: %s", symbol, e)
                continue

        return signals

    def get_description(self) -> str:
        return "GradientBoosting classifier (12 features) predicting 5-day positive return"
