#!/usr/bin/env python3
"""
End-to-end DRY_RUN smoke test: the full daily pipeline (data load → regime →
all strategies → funnel → execution paths) against the real committed
training data, with the broker patched out and DRY_RUN=true.

This is the test that catches "the engine itself is broken" BEFORE the next
production run does — it runs in CI's slow suite and a weekly schedule.
"""
import os
import sqlite3
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import src.core.execution_engine as ee  # noqa: E402


def _fake_account():
    account = MagicMock()
    account.portfolio_value = "100000"
    account.cash = "100000"
    account.buying_power = "100000"
    return account


def _fake_order():
    order = MagicMock()
    order.id = "dryrun-order"
    order.status = "accepted"
    order.filled_qty = None
    order.filled_avg_price = None
    return order


@pytest.mark.timeout(600)  # full pipeline on 22k rows; overrides the 120s default
def test_full_pipeline_dry_run(tmp_path, monkeypatch):
    data_file = project_root / "data" / "training_data.csv"
    if not data_file.exists():
        pytest.skip("training_data.csv not available")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ALPACA_API_KEY", "test_key")  # pragma: allowlist secret
    monkeypatch.setenv("ALPACA_SECRET_KEY", "test_secret")  # pragma: allowlist secret
    monkeypatch.setenv("ALPACA_PAPER", "true")
    monkeypatch.setenv("DRY_RUN", "true")
    # The committed CSV is a point-in-time snapshot — never fail on its age here
    monkeypatch.setenv("DATA_MAX_AGE_HOURS", "1000000")
    monkeypatch.setenv("DATA_VALIDATOR_MAX_AGE_HOURS", "1000000")
    # Keep CI hermetic-ish and fast: news fetching and ML training are
    # exercised by their own unit suites.
    monkeypatch.setenv("STRATEGY_DISABLED_LIST", "News Sentiment,ML Momentum")

    # The committed CSV is a snapshot, so the "covers the last trading session"
    # calendar requirement can't hold — relax it (age/quality checks still run).
    from datetime import date

    monkeypatch.setattr(
        "src.data.data_validator.DataValidator._expected_latest_date",
        lambda self, market_now: date(2000, 1, 1),
    )

    fake_client = MagicMock()
    fake_client.get_account.return_value = _fake_account()
    fake_client.get_all_positions.return_value = []
    fake_client.get_orders.return_value = []
    fake_client.submit_order.return_value = _fake_order()
    fake_client.get_order_by_id.return_value = _fake_order()
    monkeypatch.setattr(ee, "TradingClient", lambda *a, **k: fake_client)
    monkeypatch.setattr(
        "src.risk.broker_reconciler.TradingClient", lambda *a, **k: fake_client, raising=False
    )

    runner = ee.MultiStrategyRunner()
    market_data = runner.load_market_data()
    assert market_data is not None, "committed training data must load and validate"

    signals, pnl_metrics = runner.execute_pipeline(market_data)

    # The pipeline completed without raising; now verify it actually DID things.
    assert not runner.kill_switch.is_killed, f"kill switch fired: {runner.kill_switch.kill_reasons}"

    with sqlite3.connect("trading.db") as conn:
        conn.row_factory = sqlite3.Row
        funnel_strategies = {
            r["strategy_id"]
            for r in conn.execute(
                "SELECT DISTINCT strategy_id FROM signal_funnel WHERE run_id=?",
                (runner.run_id,),
            ).fetchall()
        }
        run_state = conn.execute(
            "SELECT stage, status FROM run_state ORDER BY updated_at DESC LIMIT 1"
        ).fetchone()

    # All enabled strategies must report a funnel row (liveness). The expected
    # count is derived from the canonical spec list minus config-disabled and
    # env-disabled strategies — never hardcoded, so flipping a `disabled` flag
    # in trading_config.yaml doesn't silently weaken or break this canary.
    from src.utils.config_loader import get_config

    _config = get_config()
    _env_disabled = {
        s.strip() for s in os.environ.get("STRATEGY_DISABLED_LIST", "").split(",") if s.strip()
    }
    _enabled = [
        name
        for name, _desc, _cls in ee.CANONICAL_STRATEGY_SPECS
        if not _config.get(f"strategies.{name.lower().replace(' ', '_')}.disabled", False)
        and name not in _env_disabled
    ]
    assert len(funnel_strategies) >= len(_enabled), (
        f"expected funnel rows from all {len(_enabled)} enabled strategies "
        f"({_enabled}), got {len(funnel_strategies)} — "
        "a strategy crashed or was silently skipped"
    )
    assert run_state is not None and run_state["status"] != "FAILED"

    # DRY_RUN guarantee: zero real order submissions reached the broker
    fake_client.submit_order.assert_not_called()
