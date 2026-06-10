#!/usr/bin/env python3
"""
Pairs-trading exit integrity: pair state must survive the daily restart,
the short leg must be covered with its ACTUAL size, exits must defer when
the short leg has no data, and orphaned shorts must be swept.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.strategies.strategy_pairs_trading import PairsTradingStrategy


def _make_pair_data(symbols, n=80, seed=7):
    """Stable, correlated closes so the pair z-score sits near 0 (reverted)."""
    rng = np.random.RandomState(seed)
    dates = pd.date_range("2026-03-01", periods=n, freq="D")
    frames = []
    for i, sym in enumerate(symbols):
        base = 100.0 + 20 * i
        closes = base + rng.normal(0, 0.1, n).cumsum() * 0.01
        frames.append(
            pd.DataFrame(
                {"symbol": sym, "close": closes, "atr_20": 1.0},
                index=dates,
            )
        )
    return pd.concat(frames)


@pytest.fixture
def strategy():
    s = PairsTradingStrategy(strategy_id=8, capital=12500.0)
    s.pairs = [("JPM", "BAC")]
    return s


def _held_pair(strategy, long_shares=10.0, short_shares=25.0, entry="2026-03-10"):
    strategy.positions = {"JPM": long_shares}
    strategy.short_positions = {"BAC": short_shares}
    strategy.entry_dates = {"JPM": entry}
    strategy.entry_prices = {"JPM": 100.0, "BAC": 40.0}
    # NOTE: _active_pairs deliberately left empty — it is in-memory only and a
    # fresh strategy instance (as every daily run creates) starts blank.


def test_pair_map_rebuilt_after_restart_and_exit_fires(strategy):
    """Reverted spread must exit BOTH legs even though _active_pairs started empty."""
    _held_pair(strategy)
    data = _make_pair_data(["JPM", "BAC"])

    signals = strategy.generate_signals(data)

    actions = {(s["action"], s["symbol"]) for s in signals}
    assert ("SELL", "JPM") in actions, "long leg must exit on reverted spread"
    assert ("BUY_TO_COVER", "BAC") in actions, "short leg must be covered"


def test_cover_uses_actual_short_size_not_long_size(strategy):
    _held_pair(strategy, long_shares=10.0, short_shares=25.0)
    data = _make_pair_data(["JPM", "BAC"])

    signals = strategy.generate_signals(data)

    covers = [s for s in signals if s["action"] == "BUY_TO_COVER"]
    assert len(covers) == 1
    assert covers[0]["shares"] == pytest.approx(25.0), (
        "legs are sized by equal notional — covering with the long leg's share "
        "count leaves part of the short open"
    )


def test_exit_deferred_when_short_leg_data_missing(strategy):
    """No data for the short leg → defer BOTH legs; never orphan the short."""
    _held_pair(strategy)
    data = _make_pair_data(["JPM"])  # BAC missing today

    signals = strategy.generate_signals(data)

    assert not [s for s in signals if s["symbol"] == "JPM" and s["action"] == "SELL"]
    assert strategy._active_pairs.get("JPM") == "BAC", "pair mapping must be retained for retry"


def test_orphan_short_is_swept(strategy):
    """A short with no paired long (long was stopped out) gets a forced cover."""
    strategy.positions = {}
    strategy.short_positions = {"BAC": 25.0}
    data = _make_pair_data(["JPM", "BAC"])

    signals = strategy.generate_signals(data)

    covers = [s for s in signals if s["action"] == "BUY_TO_COVER" and s["symbol"] == "BAC"]
    assert len(covers) == 1
    assert covers[0]["shares"] == pytest.approx(25.0)
    assert "rphan" in covers[0]["reasoning"]


def test_orphan_short_without_data_waits_for_next_run(strategy):
    strategy.positions = {}
    strategy.short_positions = {"BAC": 25.0}
    data = _make_pair_data(["JPM"])  # no BAC data

    signals = strategy.generate_signals(data)

    assert not signals, "cannot price the cover — must retry next run, not guess"
