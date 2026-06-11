#!/usr/bin/env python3
"""
Shared time-exit policy tests (strategy_base.evaluate_time_exit).

The old per-strategy pattern hard-dumped positions at hold_days regardless of
P&L or thesis — ML Momentum's "Held 5d" exits realized most of its losses.
The shared policy: min-hold → signal-decay at soft horizon → hard ceiling;
a losing position with an intact thesis holds until the ceiling.
"""
import sys
from datetime import timedelta
from pathlib import Path

import pandas as pd
import pytest

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.strategies.strategy_rsi_mean_reversion import RSIMeanReversionStrategy  # noqa: E402


@pytest.fixture
def strat():
    s = RSIMeanReversionStrategy(1, 25_000)
    return s


def _held(s, symbol, days):
    asof = pd.Timestamp("2026-06-12")
    s.entry_dates[symbol] = asof - timedelta(days=days)
    return asof


class TestEvaluateTimeExit:
    def test_no_exit_before_min_hold(self, strat):
        asof = _held(strat, "X", 3)
        assert (
            strat.evaluate_time_exit(
                "X", asof, in_profit=True, thesis_intact=False, min_hold_days=5, soft_hold_days=5
            )
            is None
        )

    def test_max_ceiling_always_exits(self, strat):
        asof = _held(strat, "X", 41)
        reason = strat.evaluate_time_exit(
            "X",
            asof,
            in_profit=False,
            thesis_intact=True,  # even with an intact thesis
            soft_hold_days=20,
            max_hold_days=40,
        )
        assert reason is not None and "ceiling" in reason

    def test_losing_position_with_intact_thesis_holds_past_soft(self, strat):
        asof = _held(strat, "X", 25)
        assert (
            strat.evaluate_time_exit(
                "X",
                asof,
                in_profit=False,
                thesis_intact=True,
                soft_hold_days=20,
                max_hold_days=40,
            )
            is None
        ), "a loser with an intact thesis must NOT be dumped at the soft horizon"

    def test_thesis_gone_exits_at_soft(self, strat):
        asof = _held(strat, "X", 21)
        reason = strat.evaluate_time_exit(
            "X", asof, in_profit=False, thesis_intact=False, soft_hold_days=20, max_hold_days=40
        )
        assert reason is not None and "thesis" in reason

    def test_winner_exits_at_soft_unless_held(self, strat):
        asof = _held(strat, "X", 21)
        assert (
            strat.evaluate_time_exit(
                "X", asof, in_profit=True, thesis_intact=True, soft_hold_days=20, max_hold_days=40
            )
            is not None
        )
        assert (
            strat.evaluate_time_exit(
                "X",
                asof,
                in_profit=True,
                thesis_intact=True,
                soft_hold_days=20,
                max_hold_days=40,
                hold_winner=True,  # let-winners-run / LTCG deferral
            )
            is None
        )

    def test_no_soft_horizon_means_ceiling_only(self, strat):
        asof = _held(strat, "X", 30)
        assert (
            strat.evaluate_time_exit(
                "X", asof, in_profit=True, thesis_intact=False, max_hold_days=40
            )
            is None
        )
