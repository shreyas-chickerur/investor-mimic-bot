#!/usr/bin/env python3
"""Verbose remediation runner with heartbeat progress updates.

Runs remediation steps sequentially, streaming child output when available,
and printing heartbeat messages when a child step is quiet.
"""
from __future__ import annotations

import json
import os
import select
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class Step:
    name: str
    command: List[str]
    env_overrides: Optional[Dict[str, str]] = None


def stage(i: int, total: int, msg: str) -> None:
    width = 24
    done = int(width * i / total)
    bar = "#" * done + "-" * (width - done)
    print(f"[{i}/{total}] [{bar}] {msg}", flush=True)


def run_step(step: Step, base_env: Dict[str, str], heartbeat_seconds: int = 20) -> Dict:
    env = dict(base_env)
    if step.env_overrides:
        env.update(step.env_overrides)

    started = datetime.now().isoformat()
    started_t = time.time()
    print(f"  command: {' '.join(step.command)}", flush=True)

    proc = subprocess.Popen(
        step.command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        env=env,
    )

    log_lines: List[str] = []
    last_emit = time.time()

    assert proc.stdout is not None
    while True:
        if proc.poll() is not None:
            # Drain remaining buffered lines
            remainder = proc.stdout.read() or ""
            if remainder:
                for ln in remainder.splitlines():
                    print(f"    {ln}", flush=True)
                    log_lines.append(ln)
            break

        ready, _, _ = select.select([proc.stdout], [], [], 1.0)
        if ready:
            line = proc.stdout.readline()
            if line:
                line = line.rstrip("\n")
                print(f"    {line}", flush=True)
                log_lines.append(line)
                last_emit = time.time()
        else:
            now = time.time()
            if now - last_emit >= heartbeat_seconds:
                elapsed = int(now - started_t)
                print(f"    [heartbeat] '{step.name}' still running ({elapsed}s elapsed)", flush=True)
                last_emit = now

    ended = datetime.now().isoformat()
    code = proc.returncode if proc.returncode is not None else 1

    return {
        "name": step.name,
        "command": " ".join(step.command),
        "status": "PASS" if code == 0 else "FAIL",
        "exit_code": code,
        "started_at": started,
        "ended_at": ended,
        "log_tail": log_lines[-300:],
    }


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    report_path = root / "artifacts" / "diagnostics" / "dry_run_remediation_verbose_report.json"
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
        Step("Dry-run verification checklist (final)", ["python3", "scripts/diagnostics/dry_run_verification_checklist.py"]),
    ]

    print("=== VERBOSE DRY-RUN REMEDIATION ===", flush=True)
    results = []

    for idx, s in enumerate(steps, start=1):
        stage(idx, len(steps), s.name)
        result = run_step(s, base_env, heartbeat_seconds=20)
        results.append(result)
        print(f"  -> {result['status']} (exit {result['exit_code']})", flush=True)

    passed = sum(1 for r in results if r["status"] == "PASS")
    failed = sum(1 for r in results if r["status"] == "FAIL")

    report = {
        "generated_at": datetime.now().isoformat(),
        "passed": passed,
        "failed": failed,
        "total": len(steps),
        "all_passed": failed == 0,
        "results": results,
    }

    report_path.write_text(json.dumps(report, indent=2))

    print("\n=== VERBOSE REMEDIATION SUMMARY ===", flush=True)
    print(f"Passed: {passed}", flush=True)
    print(f"Failed: {failed}", flush=True)
    print(f"Report: {report_path}", flush=True)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
