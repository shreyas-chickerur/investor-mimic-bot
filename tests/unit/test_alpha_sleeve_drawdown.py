#!/usr/bin/env python3
"""
Alpha-sleeve drawdown tests: the 5% kill switch measures strategy losses,
not the SPY cash-sweep's market beta. With ~80% of equity swept into SPY, a
routine market correction must NOT halt alpha trading; the 10%/15%
whole-portfolio halt ladder remains the catastrophe backstop.
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd
import pytest

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import src.core.execution_engine as ee  # noqa: E402


def _fake_account(pv="96000", cash="10000"):
    account = MagicMock()
    account.portfolio_value = pv
    account.cash = cash
    account.buying_power = "192000"
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


def _md(spy_price):
    dates = pd.bdate_range("2026-06-01", periods=5)
    return pd.DataFrame({"symbol": "SPY", "close": spy_price}, index=dates)


def _seed_sweep(engine, shares, avg=500.0, current=500.0):
    sid = engine._sweep_strategy_id()
    engine.db.update_position(
        strategy_id=sid, symbol="SPY", shares=shares, avg_price=avg, current_price=current
    )


class TestAlphaSleeveDrawdown:
    def test_spy_correction_does_not_count_against_alpha(self, engine):
        # Sweep: 160 sh SPY @ 500 = $80k of a $96k portfolio. Alpha = $16k.
        _seed_sweep(engine, 160.0)
        engine.portfolio_value = 96_000.0
        engine.db.set_system_state("peak_alpha_value", "16000")
        # SPY drops 6%: portfolio falls to ~$91.2k, alpha sleeve unchanged.
        engine.portfolio_value = 96_000.0 - 160.0 * 30.0  # SPY 500 → 470
        dd = engine._alpha_sleeve_drawdown(_md(470.0))
        assert dd == pytest.approx(
            0.0, abs=0.01
        ), "a pure SPY correction must not register as alpha drawdown"

    def test_alpha_losses_still_trip(self, engine):
        _seed_sweep(engine, 160.0)
        engine.db.set_system_state("peak_alpha_value", "16000")
        # SPY flat at 500 ($80k), but the portfolio lost $1.6k of ALPHA value:
        engine.portfolio_value = 94_400.0  # alpha sleeve 16000 → 14400 = -10%
        dd = engine._alpha_sleeve_drawdown(_md(500.0))
        assert dd == pytest.approx(0.10, abs=0.01)

    def test_no_sweep_equals_whole_portfolio_dd(self, engine):
        engine.portfolio_value = 90_000.0
        engine.db.set_system_state("peak_alpha_value", "100000")
        dd = engine._alpha_sleeve_drawdown(_md(500.0))
        assert dd == pytest.approx(0.10, abs=0.001)

    def test_peak_ratchets_up_and_recovery_untrips(self, engine):
        engine.portfolio_value = 100_000.0
        engine._alpha_sleeve_drawdown(_md(500.0))  # establishes peak 100k
        engine.portfolio_value = 110_000.0
        assert engine._alpha_sleeve_drawdown(_md(500.0)) == pytest.approx(0.0)
        assert float(engine.db.get_system_state("peak_alpha_value")) == pytest.approx(110_000.0)
        engine.portfolio_value = 104_500.0  # -5% from new peak
        assert engine._alpha_sleeve_drawdown(_md(500.0)) == pytest.approx(0.05, abs=0.001)

    def test_missing_spy_price_falls_back_to_position_mark(self, engine):
        _seed_sweep(engine, 160.0, current=480.0)
        engine.portfolio_value = 92_800.0  # 80k*0.96 + 16k alpha
        engine.db.set_system_state("peak_alpha_value", "16000")
        dates = pd.bdate_range("2026-06-01", periods=3)
        md = pd.DataFrame({"symbol": "AAPL", "close": 200.0}, index=dates)  # no SPY today
        dd = engine._alpha_sleeve_drawdown(md)
        assert dd == pytest.approx(0.0, abs=0.01)
