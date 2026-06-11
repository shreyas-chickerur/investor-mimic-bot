#!/usr/bin/env python3
"""
ML Momentum leakage-prevention tests.

Two leaks existed: (1) a pre-computed future_return_5d column could feed
training with unverifiable forward-looking data; (2) the walk-forward OOS
accuracy used a naive 2/3 split where 5-day labels straddled the boundary,
inflating the accuracy number that gates LIVE confidence scaling.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.strategies.strategy_ml_momentum import MLMomentumStrategy  # noqa: E402


def _synthetic_frame(n_days=400, n_symbols=3, seed=7, with_future_col=False):
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2024-01-02", periods=n_days)
    frames = []
    for k in range(n_symbols):
        closes = 100 * np.cumprod(1 + rng.normal(0.0005, 0.015, n_days))
        df = pd.DataFrame(
            {
                "symbol": f"SYM{k}",
                "close": closes,
                "rsi": rng.uniform(30, 70, n_days),
                "returns_5d": rng.normal(0, 0.02, n_days),
                "returns_20d": rng.normal(0, 0.04, n_days),
                "volume_ratio": rng.uniform(0.5, 2.0, n_days),
            },
            index=dates,
        )
        frames.append(df)
    out = pd.concat(frames).sort_index()
    if with_future_col:
        out["future_return_5d"] = 0.01
    return out


@pytest.fixture
def strategy(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # keep ml_model.pkl writes out of the repo
    return MLMomentumStrategy(strategy_id=2, capital=20_000)


class TestFutureColumnRejection:
    def test_train_raises_on_future_column(self, strategy):
        with pytest.raises(ValueError, match="forward-looking"):
            strategy._train_model(_synthetic_frame(with_future_col=True))

    def test_walk_forward_rejects_future_column_silently_but_sets_no_accuracy(self, strategy):
        # The accuracy path catches exceptions (non-fatal) but must NOT
        # produce an accuracy number from leaky data.
        strategy._compute_walk_forward_accuracy(_synthetic_frame(with_future_col=True))
        assert strategy.last_oos_accuracy is None

    def test_train_accepts_clean_frame(self, strategy):
        strategy._train_model(_synthetic_frame())
        assert strategy.is_trained


class TestTrainCutoff:
    def test_no_label_window_extends_past_data_end(self, strategy):
        df = _synthetic_frame()
        strategy._train_model(df)
        data_end = df.index.max()
        assert strategy.last_train_max_label_date is not None
        # The last label window must close ON or BEFORE the final date —
        # never beyond what was knowable at asof.
        assert strategy.last_train_max_label_date <= data_end


class TestPurgedWalkForward:
    def test_purge_and_embargo_remove_boundary_samples(self, strategy):
        df = _synthetic_frame(n_days=400)
        strategy._compute_walk_forward_accuracy(df)
        assert strategy.last_oos_accuracy is not None
        # 2 * horizon dates × n_symbols of samples sit in the purged gap
        assert strategy.last_purged_count > 0

    def test_synthetic_noise_scores_near_random_with_purge(self, strategy):
        # Pure noise: an honest (purged) estimate must hover near 50%,
        # not drift upward via boundary leakage.
        df = _synthetic_frame(n_days=500, seed=11)
        strategy._compute_walk_forward_accuracy(df)
        assert strategy.last_oos_accuracy is not None
        assert 35.0 <= strategy.last_oos_accuracy <= 65.0

    def test_too_few_dates_skips_cleanly(self, strategy):
        df = _synthetic_frame(n_days=70)
        strategy._compute_walk_forward_accuracy(df)
        assert strategy.last_oos_accuracy is None
