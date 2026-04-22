#!/usr/bin/env python3
"""Run a dry-run style verification checklist with progress output.

This script executes non-trading checks in sequence, records pass/fail,
and writes a JSON report to artifacts/diagnostics.
"""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List


@dataclass
class Step:
    name: str
    command: List[str]


def progress(i: int, total: int, text: str) -> None:
    width = 20
    done = int(width * i / total)
    bar = "#" * done + "-" * (width - done)
    print(f"[{i}/{total}] [{bar}] {text}", flush=True)


def run_step(step: Step) -> dict:
    started = datetime.now().isoformat()
    proc = subprocess.run(step.command, capture_output=True, text=True)
    ended = datetime.now().isoformat()
    return {
        "name": step.name,
        "command": " ".join(step.command),
        "exit_code": proc.returncode,
        "status": "PASS" if proc.returncode == 0 else "FAIL",
        "started_at": started,
        "ended_at": ended,
        "stdout": proc.stdout[-8000:],
        "stderr": proc.stderr[-8000:],
    }


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    report_path = root / "artifacts" / "diagnostics" / "dry_run_verification_checklist.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)

    steps = [
        Step("Import check", ["python3", "scripts/import_check.py"]),
        Step("Signal health check", ["python3", "scripts/monitor_signal_health.py"]),
        Step("Canonical signal dry check", ["python3", "scripts/check_signals.py"]),
        Step(
            "Monthly diagnostics",
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
            "Post-run guardrails",
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
        Step("Daily email generation", ["python3", "scripts/generate_daily_email.py"]),
        Step(
            "Python compile sanity",
            [
                "python3",
                "-m",
                "py_compile",
                "scripts/generate_daily_email.py",
                "scripts/diagnostics/monthly_strategy_diagnostics.py",
                "scripts/diagnostics/post_run_guardrails.py",
                "scripts/diagnostics/dry_run_verification_checklist.py",
                "src/core/execution_engine.py",
                "src/strategies/strategy_ml_momentum.py",
            ],
        ),
    ]

    print("=== DRY-RUN VERIFICATION CHECKLIST ===", flush=True)
    results = []

    total = len(steps)
    for idx, step in enumerate(steps, start=1):
        progress(idx, total, step.name)
        result = run_step(step)
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

    print("\n=== CHECKLIST SUMMARY ===", flush=True)
    print(f"Passed: {passed}", flush=True)
    print(f"Failed: {failed}", flush=True)
    print(f"Report: {report_path}", flush=True)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
