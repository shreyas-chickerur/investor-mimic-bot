#!/usr/bin/env python3
"""
Workflow-file tripwires. An invalid daily_trading.yml took the platform down
for a full day in June 2026 (GitHub rejected the whole file; the scheduled
dispatch silently stopped firing, with 0-second failure runs named after the
file path). These tests catch that class of error on `make test`, before a
push — actionlint in CI is the second line of defense.
"""
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

WORKFLOWS_DIR = Path(__file__).parent.parent.parent / ".github" / "workflows"
WORKFLOW_FILES = sorted(WORKFLOWS_DIR.glob("*.yml"))

# Keys GitHub Actions accepts on a STEP. A stray key here (e.g. `permissions`,
# which is job/workflow-level only) makes GitHub reject the entire file.
VALID_STEP_KEYS = {
    "name",
    "id",
    "if",
    "uses",
    "with",
    "run",
    "env",
    "shell",
    "continue-on-error",
    "timeout-minutes",
    "working-directory",
}


@pytest.mark.parametrize("path", WORKFLOW_FILES, ids=lambda p: p.name)
def test_workflow_yaml_parses(path):
    yaml.safe_load(path.read_text())


@pytest.mark.parametrize("path", WORKFLOW_FILES, ids=lambda p: p.name)
def test_workflow_steps_use_only_valid_keys(path):
    doc = yaml.safe_load(path.read_text())
    for job_name, job in (doc.get("jobs") or {}).items():
        for i, step in enumerate(job.get("steps") or []):
            bad = set(step) - VALID_STEP_KEYS
            assert not bad, (
                f"{path.name} job '{job_name}' step {i} "
                f"({step.get('name', '?')}) has invalid step-level keys: {bad} — "
                "GitHub will reject the whole workflow file"
            )


class TestDailyTradingInvariants:
    @pytest.fixture
    def text(self):
        return (WORKFLOWS_DIR / "daily_trading.yml").read_text()

    @pytest.fixture
    def doc(self, text):
        return yaml.safe_load(text)

    def test_single_staleness_threshold(self, doc):
        """DATA_MAX_AGE_HOURS is defined exactly once, at workflow level."""
        assert "DATA_MAX_AGE_HOURS" in (doc.get("env") or {})
        for job in doc["jobs"].values():
            for step in job.get("steps", []):
                step_env = step.get("env") or {}
                assert "DATA_MAX_AGE_HOURS" not in step_env, (
                    f"step '{step.get('name')}' redefines DATA_MAX_AGE_HOURS — "
                    "the workflow-level value is the single source of truth"
                )

    def test_health_gate_is_allow_list(self, text):
        """Only SUCCESS/MARKET_CLOSED may pass; UNKNOWN must not slip through."""
        assert '"$STATUS" != "SUCCESS"' in text, (
            "final health gate must allow-list SUCCESS (a deny-list let "
            "UNKNOWN/STARTED/EXECUTING pass silently — June 2026 outage class)"
        )

    def test_gate_verdict_is_propagated(self, doc):
        steps = doc["jobs"]["daily-execution"]["steps"]
        names = [s.get("name") for s in steps]
        assert names[-1] == "Propagate health gate result", (
            "the gate runs with continue-on-error so the failure email can "
            "send; the LAST step must re-assert its verdict as the job status"
        )

    def test_snapshot_export_runs_after_reconciliation(self, doc):
        steps = doc["jobs"]["daily-execution"]["steps"]
        order = {s.get("name"): i for i, s in enumerate(steps)}
        assert (
            order["Check reconciliation status"]
            < order["Export dashboard snapshot"]
            < order["Generate daily email digest"]
        ), "snapshot export reads reconciliation step outputs — order matters"

    def test_outbox_processor_runs_after_expectation_check(self, doc):
        steps = doc["jobs"]["daily-execution"]["steps"]
        order = {s.get("name"): i for i, s in enumerate(steps)}
        assert order["Post-run expectation check"] < order["Process notification outbox"], (
            "the expectation check queues alerts to the outbox; the processor "
            "must run after it or alerts wait a full day"
        )

    def test_run_status_values_match_shell_script(self, text):
        """Every status run_trading.sh can write is handled by the workflow."""
        script = (Path(__file__).parent.parent.parent / "scripts" / "run_trading.sh").read_text()
        written = {
            "STARTED",
            "MARKET_CLOSED",
            "PREFLIGHT_FAILED",
            "EXECUTING",
            "SUCCESS",
            "EXECUTION_FAILED",
        }
        for status in written:
            assert f'"{status}"' in script, f"run_trading.sh no longer writes {status}?"
        # The gate handles them via the allow-list: explicit mentions required
        # only for the two passing values.
        assert "MARKET_CLOSED" in text and "SUCCESS" in text
