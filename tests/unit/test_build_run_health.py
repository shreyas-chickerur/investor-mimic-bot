#!/usr/bin/env python3
"""
build_run_health: consolidated GREEN/YELLOW/RED verdict, run_history
persistence, and recurring-failure escalation.
"""
import json
import sqlite3
import sys
from pathlib import Path

import pytest

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "scripts" / "diagnostics"))

import build_run_health as brh  # noqa: E402

from src.core.database import TradingDatabase  # noqa: E402


@pytest.fixture
def db_path(tmp_path):
    db = TradingDatabase(db_path=str(tmp_path / "trading.db"))
    return db.db_path


def _expectations(failures=()):
    """failures: iterable of (label, severity) tuples."""
    failed = {label for label, _ in failures}
    sev = dict(failures)
    labels = ["Run completed (not HALTED/FAILED)", "Kill switch did not fire", "Signals generated"]
    results = [
        {
            "label": lbl,
            "passed": lbl not in failed,
            "severity": sev.get(lbl, "medium"),
            "detail": "x",
        }
        for lbl in labels
    ]
    return {"results": results}


class TestVerdict:
    def test_green_happy_path(self, db_path):
        checks = brh.build_checks(
            "SUCCESS",
            _expectations(),
            {"critical_failures": []},
            {"reconciliation_status": "PASS"},
            "PASS",
            "",
        )
        assert brh.compute_overall(checks) == "GREEN"

    def test_market_closed_is_green_without_reports(self, db_path):
        checks = brh.build_checks("MARKET_CLOSED", None, None, {}, "", "")
        assert brh.compute_overall(checks) == "GREEN"

    def test_guardrail_critical_is_red(self, db_path):
        checks = brh.build_checks(
            "SUCCESS",
            _expectations(),
            {"critical_failures": ["funnel went backwards"]},
            {"reconciliation_status": "PASS"},
            "PASS",
            "",
        )
        assert brh.compute_overall(checks) == "RED"

    def test_missing_guardrails_on_success_is_red(self, db_path):
        checks = brh.build_checks(
            "SUCCESS", _expectations(), None, {"reconciliation_status": "PASS"}, "PASS", ""
        )
        assert brh.compute_overall(checks) == "RED"

    def test_medium_expectation_failure_is_yellow(self, db_path):
        checks = brh.build_checks(
            "SUCCESS",
            _expectations(failures=[("Signals generated", "medium")]),
            {"critical_failures": []},
            {"reconciliation_status": "PASS"},
            "PASS",
            "",
        )
        assert brh.compute_overall(checks) == "YELLOW"

    def test_unresolved_recon_drift_is_red(self, db_path):
        checks = brh.build_checks(
            "SUCCESS", _expectations(), {"critical_failures": []}, {}, "FAIL", "false"
        )
        assert brh.compute_overall(checks) == "RED"

    def test_auto_resolved_recon_drift_passes(self, db_path):
        checks = brh.build_checks(
            "SUCCESS", _expectations(), {"critical_failures": []}, {}, "FAIL", "true"
        )
        recon = [c for c in checks if c["name"] == "reconciliation"][0]
        assert recon["passed"] is True

    def test_unknown_status_is_red(self, db_path):
        checks = brh.build_checks(
            "UNKNOWN", _expectations(), {"critical_failures": []}, {}, "PASS", ""
        )
        assert brh.compute_overall(checks) == "RED"


class TestRunHistoryAndRecurrence:
    def _persist(self, db_path, run_id, failed, overall="RED"):
        report = {
            "run_id": run_id,
            "date": "2026-06-11",
            "overall": overall,
            "status": "SUCCESS",
            "checks": [{"name": n, "passed": False} for n in failed],
            "portfolio_value": 96000.0,
            "orders": {"FILLED": 2},
            "data_freshness_hours": 12.0,
        }
        brh.persist_run_history(db_path, report)

    def test_row_persisted(self, db_path):
        self._persist(db_path, "run1", ["reconciliation"])
        with sqlite3.connect(db_path) as conn:
            row = conn.execute(
                "SELECT run_id, overall, failed_checks_json FROM run_history"
            ).fetchone()
        assert row[0] == "run1" and row[1] == "RED"
        assert json.loads(row[2]) == ["reconciliation"]

    def test_recurrence_fires_on_third_consecutive_failure(self, db_path):
        self._persist(db_path, "run1", ["reconciliation"])
        self._persist(db_path, "run2", ["reconciliation"])
        recurring = brh.detect_recurrences(db_path, ["reconciliation"])
        assert recurring == ["reconciliation"]

    def test_no_recurrence_when_prior_run_clean(self, db_path):
        self._persist(db_path, "run1", ["reconciliation"])
        self._persist(db_path, "run2", [], overall="GREEN")
        recurring = brh.detect_recurrences(db_path, ["reconciliation"])
        assert recurring == []

    def test_no_recurrence_without_history(self, db_path):
        assert brh.detect_recurrences(db_path, ["reconciliation"]) == []

    def test_upsert_same_run_id_no_duplicate(self, db_path):
        self._persist(db_path, "run1", ["a"])
        self._persist(db_path, "run1", ["a", "b"])
        with sqlite3.connect(db_path) as conn:
            n = conn.execute("SELECT COUNT(*) FROM run_history").fetchone()[0]
        assert n == 1
