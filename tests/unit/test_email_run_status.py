#!/usr/bin/env python3
"""
The daily digest must reflect the run's ACTUAL outcome, not just the static DB
markers. Regression guard for 2026-06-22: runs #218/#219 aborted at pre-flight
yet the email still rendered "All Systems Healthy" and "READY TO GO LIVE"
because the health card / go-live verdict were built only from data markers.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

import generate_daily_email as g
import pytest

from src.core.database import TradingDatabase

FAILED_STATES = ["PREFLIGHT_FAILED", "EXECUTION_FAILED", "STARTED", "UNKNOWN"]
OK_STATES = ["SUCCESS", "MARKET_CLOSED"]


@pytest.fixture()
def db_path(tmp_path):
    p = str(tmp_path / "trading.db")
    TradingDatabase(p)  # initialize schema
    return p


def _health(db_path, run_status):
    return g.build_health_card(
        recon_status="PASS",
        auto_sync_ok="",
        drift_resolved="",
        drift_remaining="0",
        fill_summary={"fill_count": 0},
        db_path=db_path,
        run_status=run_status,
    )


def _golive(db_path, run_status):
    return g.build_golive_section(
        db_path, recon_status="PASS", data_stale=False, run_status=run_status
    )


class TestHealthCardRunStatus:
    @pytest.mark.parametrize("status", FAILED_STATES)
    def test_failed_run_says_run_failed_not_healthy(self, db_path, status):
        html = _health(db_path, status)
        assert "Run Failed" in html
        assert status in html
        assert "All Systems Healthy" not in html

    @pytest.mark.parametrize("status", OK_STATES + [None, ""])
    def test_ok_or_unknown_env_does_not_inject_failure_banner(self, db_path, status):
        html = _health(db_path, status)
        assert "Run Failed" not in html
        assert "did not complete" not in html


class TestGoLiveRunStatus:
    @pytest.mark.parametrize("status", FAILED_STATES)
    def test_failed_run_is_never_ready_to_go_live(self, db_path, status):
        html = _golive(db_path, status)
        assert "READY TO GO LIVE" not in html
        assert "last run" in html

    def test_run_status_wins_over_static_checklist(self, db_path):
        # Run outcome must override the green checklist: whatever the criteria
        # say, flipping to a failed state removes the "READY TO GO LIVE" verdict
        # (the exact 2026-06-22 false-positive).
        ok_html = _golive(db_path, "SUCCESS")
        bad_html = _golive(db_path, "PREFLIGHT_FAILED")
        if "READY TO GO LIVE" in ok_html:
            assert "READY TO GO LIVE" not in bad_html
        assert "last run PREFLIGHT_FAILED" in bad_html


def test_mock_state_run_failed_preset_renders(db_path, monkeypatch):
    # The preview preset must exercise the failed-run path end-to-end.
    preset = g._MOCK_STATES["run_failed"]
    for k, v in preset.items():
        monkeypatch.setenv(k, v)
    html = g.generate_email_body(db_path=db_path, include_visuals=False)
    assert "Run Failed" in html
    assert "READY TO GO LIVE" not in html


# ---------------------------------------------------------------------------
# Live-readiness must count only POST-FIX trades, not pre-fix OPG-era phantoms.
# Regression for 2026-07-07: the go-live checklist counted all-time trades and
# days-since-inception, inflating readiness with data from an era where ~87% of
# orders expired unfilled (see execution failure 2026-07-02).
# ---------------------------------------------------------------------------


TRACK_SINCE = "2026-07-02"


def _add_closed_trade(db_path, executed_at, pnl):
    import sqlite3

    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO strategies (id, name, capital_allocation, initial_capital) "
        "VALUES (1, 'RSI', 0, 0) ON CONFLICT(id) DO NOTHING"
    )
    conn.execute(
        "INSERT INTO trades (run_id, strategy_id, symbol, action, shares, "
        "requested_price, exec_price, notional, executed_at, pnl) "
        "VALUES ('R', 1, 'AAPL', 'SELL', 1, 100, 100, 100, ?, ?)",
        (executed_at, pnl),
    )
    conn.commit()
    conn.close()


class TestLiveReadinessDateWindow:
    def test_pre_fix_trades_excluded_from_closed_count(self, db_path):
        # 25 pre-fix winners would sail past the ≥30/≥20 trade gate if counted.
        for _ in range(25):
            _add_closed_trade(db_path, "2026-05-10T10:00:00", 5.0)
        html = _golive(db_path, "SUCCESS")
        # Only post-fix trades count → 0 closed, nowhere near the threshold.
        assert "0 closed" in html
        assert "READY TO GO LIVE" not in html

    def test_days_running_measured_from_track_since_not_inception(self, db_path):
        _add_closed_trade(db_path, "2026-05-10T10:00:00", 5.0)
        html = _golive(db_path, "SUCCESS")
        # The days-running row must anchor to the track-since date, not the
        # much-earlier first pre-fix trade/run.
        assert f"since {TRACK_SINCE}" in html

    def test_post_fix_trades_are_counted(self, db_path):
        _add_closed_trade(db_path, "2026-05-10T10:00:00", 5.0)  # excluded
        _add_closed_trade(db_path, "2026-07-05T10:00:00", 5.0)  # counted
        _add_closed_trade(db_path, "2026-07-06T10:00:00", 5.0)  # counted
        html = _golive(db_path, "SUCCESS")
        assert "2 closed" in html

    def test_go_live_section_requires_statistical_edge_rows(self, db_path):
        # The unified section must surface win rate + profit factor so a reliable
        # but edge-less system can never read READY on operational criteria alone.
        html = _golive(db_path, "SUCCESS")
        assert "Win rate" in html
        assert "Profit factor" in html
