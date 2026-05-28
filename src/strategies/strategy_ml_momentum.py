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

import logging
import pickle  # nosec B403
from datetime import datetime

import numpy as np
import pandas as pd

from src.core.strategy_base import TradingStrategy
from src.utils.config_loader import get_config

try:
    import lightgbm as lgb

    _LGBM_AVAILABLE = True
except (ImportError, OSError):  # OSError covers missing libomp.dylib on macOS
    from sklearn.ensemble import GradientBoostingClassifier as _FallbackGBT

    _LGBM_AVAILABLE = False

logger = logging.getLogger(__name__)

# Feature names — must match between _extract_row_features and _prepare_features
_FEATURE_NAMES = [
    "rsi",
    "rsi_slope_5d",
    "ret_5d",
    "ret_20d",
    "ret_60d",
    "vol_20d",
    "vol_ratio",
    "volume_ratio",
    "price_to_sma20",
    "price_to_sma50",
    "atr_pct",
    "adx",
]

_MODEL_PATH = Path("data/ml_model.pkl")
_MODEL_MAX_AGE_DAYS = 7


class MLMomentumStrategy(TradingStrategy):
    """Gradient Boosting classifier predicting 5-day outperformance vs SPY."""

    def __init__(self, strategy_id: int, capital: float):
        super().__init__(
            strategy_id=strategy_id,
            name="ML Momentum",
            capital=capital,
        )
        config = get_config()
        self.min_confidence = config.get("strategies.ml_momentum.min_confidence", 0.55)
        self.max_new_positions_per_day = config.get(
            "strategies.ml_momentum.max_new_positions_per_day", 3
        )
        self.buy_quantile_threshold = config.get(
            "strategies.ml_momentum.buy_quantile_threshold", 0.65
        )
        self.hold_days = 5
        self.entry_dates = {}

        if _LGBM_AVAILABLE:
            self.model = lgb.LGBMClassifier(
                n_estimators=500,
                learning_rate=0.03,
                num_leaves=15,  # shallow — prevents overfitting on ~500 train samples
                min_child_samples=20,  # equivalent to min_samples_leaf
                subsample=0.8,
                colsample_bytree=0.8,
                class_weight="balanced",
                random_state=42,
                verbose=-1,  # suppress LightGBM training output
            )
        else:
            self.model = _FallbackGBT(
                n_estimators=200,
                max_depth=3,
                learning_rate=0.05,
                subsample=0.8,
                min_samples_leaf=10,
                random_state=42,
            )
        self.is_trained = False
        self._train_date: str = ""  # track when model was last trained
        self.last_feature_importances: dict = {}
        self.last_oos_accuracy: float | None = None
        self.last_train_accuracy: float | None = None

    # ------------------------------------------------------------------
    # Model persistence
    # ------------------------------------------------------------------
    def _save_model(self) -> None:
        try:
            _MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "model": self.model,
                "is_trained": self.is_trained,
                "train_date": self._train_date,
                "feature_importances": self.last_feature_importances,
                "oos_accuracy": self.last_oos_accuracy,
                "train_accuracy": self.last_train_accuracy,
                "saved_at": datetime.utcnow().isoformat(),
            }
            with open(_MODEL_PATH, "wb") as f:
                pickle.dump(payload, f)
            logger.info("ML model saved to %s", _MODEL_PATH)
        except Exception as exc:
            logger.warning("ML model save failed: %s", exc)

    def _load_model(self) -> bool:
        """Return True if a fresh-enough saved model was loaded."""
        if not _MODEL_PATH.exists():
            return False
        try:
            age_days = (
                datetime.utcnow() - datetime.utcfromtimestamp(_MODEL_PATH.stat().st_mtime)
            ).days
            if age_days > _MODEL_MAX_AGE_DAYS:
                logger.info("ML model on disk is %d days old — will retrain", age_days)
                return False
            with open(_MODEL_PATH, "rb") as f:
                payload = pickle.load(f)  # nosec B301
            self.model = payload["model"]
            self.is_trained = payload.get("is_trained", True)
            self._train_date = payload.get("train_date", "")
            self.last_feature_importances = payload.get("feature_importances", {})
            self.last_oos_accuracy = payload.get("oos_accuracy")
            self.last_train_accuracy = payload.get("train_accuracy")
            logger.info(
                "ML model loaded from disk (trained %s, OOS acc=%.1f%%)",
                self._train_date,
                self.last_oos_accuracy or 0,
            )
            return True
        except Exception as exc:
            logger.warning("ML model load failed: %s — will retrain", exc)
            return False

    # ------------------------------------------------------------------
    # Feature extraction
    # ------------------------------------------------------------------
    @staticmethod
    def _safe(val, default=0.0):
        """Return default if val is NaN/None."""
        if val is None or (isinstance(val, float) and np.isnan(val)):
            return default
        return float(val)

    def _extract_row_features(self, row: pd.Series, symbol_data: pd.DataFrame) -> list[float]:
        """Extract 12 features from a single row + its history."""
        close = self._safe(row.get("close"), 1)
        rsi = self._safe(row.get("rsi"), 50)

        # RSI slope (5-day)
        if len(symbol_data) >= 6 and "rsi" in symbol_data.columns:
            rsi_5_ago = self._safe(symbol_data["rsi"].iloc[-6], rsi)
            rsi_slope = rsi - rsi_5_ago
        else:
            rsi_slope = 0.0

        ret_5d = self._safe(row.get("returns_5d"), 0)
        ret_20d = self._safe(row.get("returns_20d"), 0)
        ret_60d = self._safe(row.get("returns_60d"), 0)
        vol_20d = self._safe(row.get("volatility_20d"), 0.15)

        # Volatility ratio (20d / 60d) — regime indicator
        vol_60d = self._safe(row.get("volatility_60d"), vol_20d)
        vol_ratio = vol_20d / vol_60d if vol_60d > 0 else 1.0

        volume_ratio = self._safe(row.get("volume_ratio"), 1.0)
        p_sma20 = self._safe(row.get("price_to_sma20"), 0)
        p_sma50 = self._safe(row.get("price_to_sma50"), 0)

        atr = self._safe(row.get("atr_20"), 0)
        atr_pct = atr / close if close > 0 else 0

        adx = self._safe(row.get("adx"), 0)

        return [
            rsi,
            rsi_slope,
            ret_5d,
            ret_20d,
            ret_60d,
            vol_20d,
            vol_ratio,
            volume_ratio,
            p_sma20,
            p_sma50,
            atr_pct,
            adx,
        ]

    # ------------------------------------------------------------------
    # Training
    # ------------------------------------------------------------------
    def _build_spy_return_index(self, market_data: pd.DataFrame) -> dict:
        """Build a date -> 5-day SPY return lookup for beta-adjusted labeling."""
        spy_rows = (
            market_data[market_data["symbol"] == "SPY"]
            if "symbol" in market_data.columns
            else pd.DataFrame()
        )
        if len(spy_rows) < 6:
            return {}
        spy_close = spy_rows["close"].sort_index()
        spy_ret_idx = {}
        arr = spy_close.values
        dates = spy_close.index
        for i in range(len(arr) - 5):
            if arr[i] > 0:
                spy_ret_idx[dates[i]] = (arr[i + 5] - arr[i]) / arr[i]
        return spy_ret_idx

    def _train_model(self, market_data: pd.DataFrame):
        """Train on historical data using pre-computed future_return_5d when available."""
        X_train = []
        y_train = []
        use_precomputed = "future_return_5d" in market_data.columns

        spy_ret_idx = self._build_spy_return_index(market_data)
        spy_available = len(spy_ret_idx) > 0
        if not spy_available:
            logger.warning("ML: SPY data unavailable — falling back to raw return label")

        sym_map: dict = {}
        for _sym_key, _sym_grp in market_data.groupby("symbol"):
            sym_map[_sym_key] = _sym_grp

        for _symbol, sym in sym_map.items():
            if _symbol == "SPY":
                continue
            if len(sym) < 60:
                continue

            for i in range(50, len(sym) - 5):
                row = sym.iloc[i]
                history = sym.iloc[max(0, i - 50) : i + 1]

                if use_precomputed:
                    future_ret = row.get("future_return_5d", np.nan)
                    if pd.isna(future_ret):
                        continue
                    future_ret = float(future_ret)
                else:
                    future_ret = (sym.iloc[i + 5]["close"] - sym.iloc[i]["close"]) / sym.iloc[i][
                        "close"
                    ]

                feats = self._extract_row_features(row, history)
                if any(np.isnan(f) or np.isinf(f) for f in feats):
                    continue

                row_date = sym.index[i]
                if spy_available and row_date in spy_ret_idx:
                    spy_ret = spy_ret_idx[row_date]
                    label = 1 if future_ret > spy_ret else 0
                else:
                    label = 1 if future_ret > 0.005 else 0

                X_train.append(feats)
                y_train.append(label)

        if len(X_train) < 100:
            logger.warning("ML: insufficient training samples (%d), skipping", len(X_train))
            return

        X_arr = np.array(X_train)
        y_arr = np.array(y_train)
        self.model.fit(X_arr, y_arr)  # LightGBM is scale-invariant; no scaler needed
        self.is_trained = True
        pos_rate = y_arr.mean()
        logger.info(
            "ML trained on %d samples (%.1f%% positive, precomputed=%s, beta_adjusted=%s)",
            len(y_arr),
            pos_rate * 100,
            use_precomputed,
            spy_available,
        )

        self._save_model()

        if hasattr(self.model, "feature_importances_"):
            importances = self.model.feature_importances_
            self.last_feature_importances = dict(
                sorted(
                    zip(_FEATURE_NAMES, importances),
                    key=lambda kv: kv[1],
                    reverse=True,
                )
            )
            logger.info(
                "ML feature importances: %s",
                ", ".join(f"{k}={v:.4f}" for k, v in self.last_feature_importances.items()),
            )

    def _compute_walk_forward_accuracy(self, market_data: pd.DataFrame) -> None:
        """Estimate out-of-sample accuracy via a single walk-forward split."""
        try:
            spy_ret_idx = self._build_spy_return_index(market_data)
            spy_available = len(spy_ret_idx) > 0
            use_precomputed = "future_return_5d" in market_data.columns

            all_rows: list[tuple] = []  # (date, features, label)

            sym_map: dict = {}
            for _sym_key, _sym_grp in market_data.groupby("symbol"):
                sym_map[_sym_key] = _sym_grp

            for _symbol, sym in sym_map.items():
                if _symbol == "SPY":
                    continue
                if len(sym) < 60:
                    continue

                for i in range(50, len(sym) - 5):
                    row = sym.iloc[i]
                    history = sym.iloc[max(0, i - 50) : i + 1]

                    if use_precomputed:
                        future_ret = row.get("future_return_5d", np.nan)
                        if pd.isna(future_ret):
                            continue
                        future_ret = float(future_ret)
                    else:
                        future_ret = (sym.iloc[i + 5]["close"] - sym.iloc[i]["close"]) / sym.iloc[
                            i
                        ]["close"]

                    feats = self._extract_row_features(row, history)
                    if any(np.isnan(f) or np.isinf(f) for f in feats):
                        continue

                    row_date = sym.index[i]
                    if spy_available and row_date in spy_ret_idx:
                        label = 1 if future_ret > spy_ret_idx[row_date] else 0
                    else:
                        label = 1 if future_ret > 0.005 else 0

                    all_rows.append((row_date, feats, label))

            if len(all_rows) < 200:
                logger.debug("ML walk-forward skipped: only %d samples", len(all_rows))
                return

            all_rows.sort(key=lambda r: r[0])
            split = int(len(all_rows) * 2 / 3)

            train_rows = all_rows[:split]
            val_rows = all_rows[split:]

            X_tr = np.array([r[1] for r in train_rows])
            y_tr = np.array([r[2] for r in train_rows])
            X_val = np.array([r[1] for r in val_rows])
            y_val = np.array([r[2] for r in val_rows])

            if _LGBM_AVAILABLE:
                fold_model = lgb.LGBMClassifier(
                    n_estimators=500,
                    learning_rate=0.03,
                    num_leaves=15,
                    min_child_samples=20,
                    subsample=0.8,
                    colsample_bytree=0.8,
                    class_weight="balanced",
                    random_state=42,
                    verbose=-1,
                )
            else:
                fold_model = _FallbackGBT(
                    n_estimators=200,
                    max_depth=3,
                    learning_rate=0.05,
                    subsample=0.8,
                    min_samples_leaf=10,
                    random_state=42,
                )

            fold_model.fit(X_tr, y_tr)
            train_preds = fold_model.predict(X_tr)
            val_preds = fold_model.predict(X_val)

            self.last_train_accuracy = float(np.mean(train_preds == y_tr)) * 100
            self.last_oos_accuracy = float(np.mean(val_preds == y_val)) * 100

            logger.info(
                "ML walk-forward OOS accuracy: %.1f%% (train: %.1f%%) — %d samples validated",
                self.last_oos_accuracy,
                self.last_train_accuracy,
                len(val_rows),
            )

            if self.last_oos_accuracy < 52.0:
                logger.warning("ML model near-random on OOS data — signals unreliable")

        except Exception as exc:
            logger.warning("ML walk-forward accuracy computation failed: %s", exc)
            self.last_oos_accuracy = None
            self.last_train_accuracy = None

    # ------------------------------------------------------------------
    # Signal generation
    # ------------------------------------------------------------------
    def _spy_above_sma50(self, market_data: pd.DataFrame) -> bool:
        """Return True if SPY is above its 50-day SMA (broad market uptrend gate)."""
        spy_rows = (
            market_data[market_data["symbol"] == "SPY"]
            if "symbol" in market_data.columns
            else pd.DataFrame()
        )
        if len(spy_rows) < 50:
            return True  # not enough data — allow signals
        spy_rows = spy_rows.sort_index()
        prices = spy_rows["close"].values
        sma50 = float(np.mean(prices[-50:]))
        above = float(prices[-1]) > sma50
        if not above:
            logger.info(
                "ML: SPY below 50-day SMA (%.2f < %.2f) — BUY suppressed", prices[-1], sma50
            )
        return above

    def generate_signals(self, market_data: pd.DataFrame) -> list[dict]:
        """Generate signals using ML predictions."""
        signals: list[dict] = []
        buy_candidates: list[dict] = []

        # Load persisted model on first call; retrain if stale or not trained
        today = str(market_data.index.max().date()) if len(market_data) > 0 else ""
        if not self.is_trained:
            self._load_model()
        if not self.is_trained or today != self._train_date:
            # Run walk-forward accuracy check before committing to new signals
            all_sym_rows = sum(
                max(0, len(g) - 55)
                for sym, g in market_data.groupby("symbol")
                if sym != "SPY" and len(g) >= 60
            )
            if all_sym_rows >= 200:
                self._compute_walk_forward_accuracy(market_data)
            else:
                logger.debug("ML walk-forward skipped: estimated %d samples < 200", all_sym_rows)
            self._train_model(market_data)
            self._train_date = today
        if not self.is_trained:
            return signals

        # Market regime gate: suppress all BUY signals when SPY is below its 50-day SMA.
        market_uptrend = self._spy_above_sma50(market_data)

        sym_map: dict = {}
        for _sg_key, _sg_grp in market_data.groupby("symbol"):
            sym_map[_sg_key] = _sg_grp

        for symbol, symbol_data in sym_map.items():
            if len(symbol_data) < 20:
                continue

            latest = symbol_data.iloc[-1]
            price = float(latest["close"])
            atr = self._safe(latest.get("atr_20"), None)

            try:
                feats = self._extract_row_features(latest, symbol_data)
                if any(np.isnan(f) or np.isinf(f) for f in feats):
                    continue

                prob_positive = float(self.model.predict_proba([feats])[0][1])

                # BUY: probability above threshold, and SPY above 50-day SMA.
                if (
                    prob_positive > self.min_confidence
                    and symbol not in self.positions
                    and market_uptrend
                ):
                    shares = self.calculate_position_size(price, atr=atr, max_position_pct=0.10)
                    if shares <= 0:
                        continue
                    sym_latest_date = str(symbol_data.index[-1])[:10]
                    buy_candidates.append(
                        {
                            "symbol": symbol,
                            "action": "BUY",
                            "shares": shares,
                            "price": price,
                            "value": shares * price,
                            "confidence": prob_positive,
                            "reasoning": f"ML prob positive 5d return: {prob_positive * 100:.1f}%",
                            "atr": atr if atr and atr > 0 else None,
                            "asof_date": sym_latest_date,
                        }
                    )

                # SELL: held long enough or model flips bearish
                elif symbol in self.positions:
                    latest_date = symbol_data.index[-1]
                    days_held = self.get_days_held(symbol, latest_date)
                    if days_held >= self.hold_days or prob_positive < 0.40:
                        shares = int(self.positions[symbol])
                        signals.append(
                            {
                                "symbol": symbol,
                                "action": "SELL",
                                "shares": shares,
                                "price": price,
                                "value": shares * price,
                                "confidence": 1.0
                                if days_held >= self.hold_days
                                else (1.0 - prob_positive),
                                "reasoning": f"Held {days_held}d"
                                if days_held >= self.hold_days
                                else f"ML bearish ({prob_positive:.0%})",
                                "asof_date": str(latest_date)[:10],
                            }
                        )

            except Exception as e:
                logger.warning("ML prediction failed for %s: %s", symbol, e)
                continue

        # Calibrated top-k BUY selection: avoid over-trading weak-probability names
        # by keeping only the strongest daily candidates above an adaptive floor.
        if buy_candidates:
            probs = np.array([float(c["confidence"]) for c in buy_candidates], dtype=float)
            quantile = float(np.quantile(probs, self.buy_quantile_threshold))
            adaptive_floor = max(float(self.min_confidence), quantile)

            filtered = [c for c in buy_candidates if float(c["confidence"]) >= adaptive_floor]
            filtered.sort(key=lambda x: float(x["confidence"]), reverse=True)

            selected = filtered[: max(0, int(self.max_new_positions_per_day))]
            logger.info(
                "ML BUY selection: %d candidates -> %d selected (adaptive_floor=%.3f)",
                len(buy_candidates),
                len(selected),
                adaptive_floor,
            )
            signals.extend(selected)

        return signals

    def get_description(self) -> str:
        backend = "LightGBM" if _LGBM_AVAILABLE else "GradientBoosting (fallback)"
        return f"{backend} classifier (12 features) predicting 5-day positive return"
