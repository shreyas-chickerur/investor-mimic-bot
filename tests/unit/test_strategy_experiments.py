#!/usr/bin/env python3
"""
Strategy-experiment framework: registry well-formedness + reviewer verdict
logic. Guards the changelog backbone that tracks attempts to revive the
disabled strategies (docs/research/STRATEGY_CHANGELOG.md).
"""
import json
import sqlite3
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "research"))

import review_experiments as rx
import yaml

REGISTRY = Path(__file__).parent.parent.parent / "config" / "strategy_experiments.yaml"
VALID_OPS = {">=", ">", "<=", "<", "=="}
VALID_STATUS = {"pending", "validated", "rejected", "inconclusive"}


class TestRegistryWellFormed:
    def test_registry_parses_and_has_experiments(self):
        reg = yaml.safe_load(REGISTRY.read_text())
        assert reg.get("experiments"), "registry must list experiments"

    def test_every_experiment_has_required_fields(self):
        reg = yaml.safe_load(REGISTRY.read_text())
        seen_ids = set()
        for e in reg["experiments"]:
            for field in (
                "id",
                "strategy",
                "hypothesis",
                "success_criteria",
                "review_date",
                "status",
            ):
                assert field in e, f"{e.get('id')} missing {field}"
            assert e["id"] not in seen_ids, f"duplicate id {e['id']}"
            seen_ids.add(e["id"])
            assert e["status"] in VALID_STATUS
            date.fromisoformat(e["review_date"])  # raises if malformed
            assert e["success_criteria"], f"{e['id']} has no criteria"
            for c in e["success_criteria"]:
                assert c["op"] in VALID_OPS
                assert isinstance(c["threshold"], (int, float))

    def test_three_disabled_strategies_are_tracked(self):
        reg = yaml.safe_load(REGISTRY.read_text())
        tracked = {e["strategy"] for e in reg["experiments"]}
        assert {"pairs_trading", "ml_momentum", "news_sentiment"} <= tracked


class TestReviewerVerdicts:
    def _exp(self, tmp_path, criteria, result=None, review_date="2020-01-01"):
        rf = None
        if result is not None:
            rf = tmp_path / "r.json"
            rf.write_text(json.dumps(result))
        return {
            "id": "EXP-test",
            "strategy": "x",
            "date_started": "2026-01-01",
            "hypothesis": "h",
            "success_criteria": criteria,
            "result_file": str(rf.relative_to(rx.PROJECT_ROOT)) if rf else None,
            "review_date": review_date,
            "status": "pending",
        }

    def test_validated_when_all_criteria_pass(self, tmp_path, monkeypatch):
        monkeypatch.setattr(rx, "PROJECT_ROOT", tmp_path)
        exp = self._exp(
            tmp_path,
            [{"metric": "enriched.mean_acc", "op": ">=", "threshold": 0.54}],
            {"enriched": {"mean_acc": 0.56}},
        )
        ev = rx.evaluate(exp, db_path=None)
        assert ev["verdict"] == "validated"

    def test_rejected_when_a_criterion_fails(self, tmp_path, monkeypatch):
        monkeypatch.setattr(rx, "PROJECT_ROOT", tmp_path)
        exp = self._exp(
            tmp_path,
            [{"metric": "enriched.mean_acc", "op": ">=", "threshold": 0.54}],
            {"enriched": {"mean_acc": 0.50}},
        )
        ev = rx.evaluate(exp, db_path=None)
        assert ev["verdict"] == "rejected"
        assert ev["criteria"][0]["value"] == 0.50

    def test_inconclusive_when_result_missing(self, tmp_path, monkeypatch):
        monkeypatch.setattr(rx, "PROJECT_ROOT", tmp_path)
        exp = self._exp(
            tmp_path, [{"metric": "enriched.mean_acc", "op": ">=", "threshold": 0.54}], result=None
        )
        ev = rx.evaluate(exp, db_path=None)
        assert ev["verdict"] == "inconclusive"

    def test_pairs_passing_count_metric(self, tmp_path, monkeypatch):
        monkeypatch.setattr(rx, "PROJECT_ROOT", tmp_path)
        (tmp_path / "data").mkdir()
        (tmp_path / "data" / "pairs_universe.json").write_text(
            json.dumps({"pairs": [{"num": "A", "den": "B"}, {"num": "C", "den": "D"}]})
        )
        exp = {
            "id": "p",
            "strategy": "pairs_trading",
            "success_criteria": [{"metric": "pairs.passing_count", "op": ">=", "threshold": 2}],
            "result_file": None,
            "review_date": "2020-01-01",
            "status": "pending",
            "date_started": "2026-01-01",
            "hypothesis": "h",
        }
        ev = rx.evaluate(exp, db_path=None)
        assert ev["verdict"] == "validated"
        assert ev["criteria"][0]["value"] == 2

    def test_news_distinct_dates_metric(self, tmp_path):
        db = str(tmp_path / "t.db")
        con = sqlite3.connect(db)
        con.execute(
            "CREATE TABLE sentiment_history (asof_date TEXT, symbol TEXT, "
            "score REAL, PRIMARY KEY(asof_date, symbol))"
        )
        con.executemany(
            "INSERT INTO sentiment_history VALUES (?,?,?)",
            [("2026-06-20", "AAPL", 0.5), ("2026-06-21", "AAPL", 0.5)],
        )
        con.commit()
        con.close()
        assert rx.resolve_metric("news.distinct_dates", {}, db) == 2

    def test_due_respects_review_date(self):
        future = (date.today() + timedelta(days=30)).isoformat()
        past = (date.today() - timedelta(days=1)).isoformat()
        assert rx._due({"status": "pending", "review_date": past}, force_all=False)
        assert not rx._due({"status": "pending", "review_date": future}, force_all=False)
        assert rx._due({"status": "pending", "review_date": future}, force_all=True)
        assert not rx._due({"status": "validated", "review_date": past}, force_all=True)
