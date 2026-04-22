#!/usr/bin/env python3
"""Remediate dry-run checklist failures using scripted steps only.

This script attempts to:
1) Refresh market data
2) Re-check signal health
3) Run a DRY_RUN execution pass to produce fresh run artifacts/funnel rows
4) Re-run diagnostics + checklist

All steps are executed via subprocess and recorded to a JSON report.
"""
from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class Step:
    name: str
    command: List[str]
    env_overrides: Optional[Dict[str, str]] = None


def progress(i: int, total: int, text: str) -> None:
    width = 22
    done = int(width * i / total)
    bar = "#" * done + "-" * (width - done)
    print(f"[{i}/{total}] [{bar}] {text}", flush=True)


def run_step(step: Step, base_env: Dict[str, str]) -> Dict:
    env = dict(base_env)
    if step.env_overrides:
        env.update(step.env_overrides)

    started = datetime.now().isoformat()
    proc = subprocess.run(step.command, capture_output=True, text=True, env=env)
    ended = datetime.now().isoformat()

    return {
        "name": step.name,
        "command": " ".join(step.command),
        "exit_code": proc.returncode,
        "status": "PASS" if proc.returncode == 0 else "FAIL",
        "started_at": started,
        "ended_at": ended,
        "stdout": proc.stdout[-12000:],
        "stderr": proc.stderr[-12000:],
    }


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    report_path = root / "artifacts" / "diagnostics" / "dry_run_remediation_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)

    base_env = dict(os.environ)

    steps = [
        Step("Refresh daily market data", ["python3", "scripts/update_daily_data.py"]),
        Step("Signal health check (post-refresh)", ["python3", "scripts/monitor_signal_health.py"]),
        Step("Canonical signal dry check", ["python3", "scripts/check_signals.py"]),
        Step(
            "Run execution engine in DRY_RUN mode",
            ["python3", "src/core/execution_engine.py"],
            env_overrides={
                "DRY_RUN": "true",
                "ALPACA_PAPER": "true",
                "TRADING_DISABLED": "false",
                "DATA_VALIDATOR_MAX_AGE_HOURS": base_env.get("DATA_VALIDATOR_MAX_AGE_HOURS", "288"),
            },
        ),
        Step(
            "Monthly diagnostics refresh",
            [
                "python3",
                "scripts/diagnostics/monthly_strategy_diagnostics.py",
                "--db",
                "trading.db",
                "--window-days",
                "30",
                "--context-days",
                "120",
                "--out",
                "artifacts/diagnostics/monthly_strategy_diagnostics.json",
            ],
        ),
        Step(
            "Post-run guardrails refresh",
            [
                "python3",
                "scripts/diagnostics/post_run_guardrails.py",
                "--db",
                "trading.db",
                "--status-file",
                "/tmp/run_status.txt",
                "--out",
                "artifacts/diagnostics/post_run_guardrails.json",
            ],
        ),
        Step(
            "Dry-run verification checklist (final)",
            ["python3", "scripts/diagnostics/dry_run_verification_checklist.py"],
        ),
    ]

    print("=== DRY-RUN REMEDIATION SCRIPT ===", flush=True)
    results = []
    total = len(steps)

    for idx, step in enumerate(steps, start=1):
        progress(idx, total, step.name)
        result = run_step(step, base_env)
        results.append(result)
        print(f"  -> {result['status']} (exit {result['exit_code']})", flush=True)

    passed = sum(1 for r in results if r["status"] == "PASS")
    failed = sum(1 for r in results if r["status"] == "FAIL")

    report = {
        "generated_at": datetime.now().isoformat(),
        "passed": passed,
        "failed": failed,
        "total": total,
        "all_passed": failed == 0,
        "results": results,
    }

    report_path.write_text(json.dumps(report, indent=2))

    print("\n=== REMEDIATION SUMMARY ===", flush=True)
    print(f"Passed: {passed}", flush=True)
    print(f"Failed: {failed}", flush=True)
    print(f"Report: {report_path}", flush=True)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
