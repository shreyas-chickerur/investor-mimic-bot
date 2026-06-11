#!/usr/bin/env python3
"""
Capital allocation single-source-of-truth + health gating tests.

Regression context (2026-06-11): the allocator's total_capital was set to
max(portfolio_value, buying_power) — the ~4x day-trade margin ceiling — so
strategies.capital_allocation summed to ~$380k on a $96k account, position
sizing ran on phantom capital, and the cash manager (which trusts
sum(allocations) as its total) believed it too.
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import src.core.execution_engine as ee  # noqa: E402
from src.monitoring.strategy_health_scorer import StrategyHealthScorer  # noqa: E402


def _fake_account(pv="100000", cash="100000", buying_power="400000"):
    account = MagicMock()
    account.portfolio_value = pv
    account.cash = cash
    account.buying_power = buying_power
    return account


@pytest.fixture
def engine(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ALPACA_API_KEY", "test_key")  # pragma: allowlist secret
    monkeypatch.setenv("ALPACA_SECRET_KEY", "test_secret")  # pragma: allowlist secret
    monkeypatch.setenv("ALPACA_PAPER", "true")
    monkeypatch.setenv("DRY_RUN", "false")

    fake_client = MagicMock()
    fake_client.get_account.return_value = _fake_account()
    fake_client.get_all_positions.return_value = []
    fake_client.get_orders.return_value = []

    monkeypatch.setattr(ee, "TradingClient", lambda *a, **k: fake_client)
    monkeypatch.setattr(
        "src.risk.broker_reconciler.TradingClient", lambda *a, **k: fake_client, raising=False
    )
    return ee.MultiStrategyRunner()


def _strategy_stub(strategy_id=1, name="Test Strategy"):
    s = MagicMock()
    s.strategy_id = strategy_id
    s.name = name
    return s


class TestAllocatorCapitalBase:
    def test_base_is_deployed_pct_of_equity_not_buying_power(self, engine):
        engine.portfolio_value = 96_000.0
        engine.buying_power = 384_000.0  # 4x margin — must be ignored
        base = engine._allocator_capital_base()
        deployed_pct = engine.config.get("strategies.deployed_capital_pct", 0.85)
        assert base == pytest.approx(96_000.0 * deployed_pct)
        assert base < 96_000.0  # never exceeds equity, let alone margin

    def test_allocations_sum_to_capital_base(self, engine):
        engine.portfolio_value = 96_000.0
        engine.buying_power = 384_000.0
        engine.dynamic_allocator.total_capital = engine._allocator_capital_base()
        allocations = engine.dynamic_allocator.calculate_allocations([1, 2, 3, 4, 5, 6, 7, 8])
        assert sum(allocations.values()) == pytest.approx(
            engine._allocator_capital_base(), rel=0.01
        )


class TestAllocationMultiplier:
    """Profitability-only gating: inactivity must never starve a strategy."""

    def test_proven_loser_is_quartered(self):
        metrics = {"trade_count_30d": 17, "expectancy_30d": -28.8, "win_rate_30d": 0.29}
        assert StrategyHealthScorer.allocation_multiplier(metrics) == 0.25

    def test_negative_expectancy_decent_winrate_is_halved(self):
        metrics = {"trade_count_30d": 8, "expectancy_30d": -5.0, "win_rate_30d": 0.50}
        assert StrategyHealthScorer.allocation_multiplier(metrics) == 0.5

    def test_sparse_winner_keeps_full_allocation(self):
        # Factor Momentum case: 2 trades, +$714 — unproven is not unhealthy
        metrics = {"trade_count_30d": 2, "expectancy_30d": 357.0, "win_rate_30d": 0.5}
        assert StrategyHealthScorer.allocation_multiplier(metrics) == 1.0

    def test_sparse_loser_keeps_full_allocation_until_proven(self):
        metrics = {"trade_count_30d": 3, "expectancy_30d": -50.0, "win_rate_30d": 0.0}
        assert StrategyHealthScorer.allocation_multiplier(metrics) == 1.0

    def test_profitable_active_strategy_full(self):
        metrics = {"trade_count_30d": 20, "expectancy_30d": 12.0, "win_rate_30d": 0.55}
        assert StrategyHealthScorer.allocation_multiplier(metrics) == 1.0

    def test_missing_metrics_neutral(self):
        assert StrategyHealthScorer.allocation_multiplier({}) == 1.0


class TestHealthGating:
    def _patch_scorer(self, monkeypatch, multipliers: dict):
        class _StubScorer:
            def __init__(self, db):
                pass

            def calculate_strategy_health(self, strategy_id, name):
                return {"strategy_id": strategy_id}

            @staticmethod
            def allocation_multiplier(metrics):
                return multipliers.get(metrics["strategy_id"], 1.0)

        monkeypatch.setattr(
            "src.monitoring.strategy_health_scorer.StrategyHealthScorer", _StubScorer
        )

    def test_loser_gated_and_capital_redistributed(self, engine, monkeypatch):
        self._patch_scorer(monkeypatch, {2: 0.25})
        engine.dynamic_allocator.total_capital = 80_000.0
        engine.dynamic_allocator.max_allocation = 0.35
        strategies = [_strategy_stub(1, "Winner"), _strategy_stub(2, "Loser")]
        allocations = {1: 20_000.0, 2: 20_000.0}

        gated = engine._apply_health_gating(allocations, strategies)

        assert gated[2] == pytest.approx(5_000.0)  # 20k x 0.25
        # Freed 15k flows to the winner, capped at 35% of 80k = 28k
        assert gated[1] == pytest.approx(28_000.0)
        # Total never exceeds the original pool
        assert sum(gated.values()) <= sum(allocations.values()) + 1e-6

    def test_leftover_stays_unallocated_when_winners_at_cap(self, engine, monkeypatch):
        self._patch_scorer(monkeypatch, {2: 0.25})
        engine.dynamic_allocator.total_capital = 50_000.0
        engine.dynamic_allocator.max_allocation = 0.35  # cap = 17.5k
        strategies = [_strategy_stub(1, "Winner"), _strategy_stub(2, "Loser")]
        allocations = {1: 17_500.0, 2: 20_000.0}

        gated = engine._apply_health_gating(allocations, strategies)

        assert gated[1] == pytest.approx(17_500.0)  # already at cap
        assert gated[2] == pytest.approx(5_000.0)
        # 15k freed has nowhere to go — stays out (flows to cash sweep)
        assert sum(gated.values()) == pytest.approx(22_500.0)

    def test_all_healthy_passthrough(self, engine, monkeypatch):
        self._patch_scorer(monkeypatch, {})
        strategies = [_strategy_stub(1), _strategy_stub(2)]
        allocations = {1: 10_000.0, 2: 12_000.0}
        assert engine._apply_health_gating(allocations, strategies) == allocations

    def test_gating_disabled_by_config(self, engine, monkeypatch):
        self._patch_scorer(monkeypatch, {1: 0.25})
        monkeypatch.setattr(
            engine.config,
            "get",
            lambda key, default=None: (
                False if key == "strategies.health_gating_enabled" else default
            ),
        )
        strategies = [_strategy_stub(1)]
        allocations = {1: 10_000.0}
        assert engine._apply_health_gating(allocations, strategies) == allocations

    def test_scorer_failure_is_nonfatal(self, engine, monkeypatch):
        class _Boom:
            def __init__(self, db):
                raise RuntimeError("db locked")

        monkeypatch.setattr("src.monitoring.strategy_health_scorer.StrategyHealthScorer", _Boom)
        strategies = [_strategy_stub(1)]
        allocations = {1: 10_000.0}
        assert engine._apply_health_gating(allocations, strategies) == allocations
