#!/usr/bin/env python3
"""
Lightweight import check for core modules and workflow scripts.
"""
import importlib
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))


MODULES = [
    "execution_engine",
    "data_validator",
    "broker_reconciler",
    "database",
    "artifact_writer",
    "scripts.generate_email_chart",
    "scripts.check_broker_state",
    "scripts.generate_daily_email",
    "scripts.generate_strategy_performance",
    "scripts.generate_strategy_chart",
]


def main() -> int:
    failures = []
    for module in MODULES:
        try:
            importlib.import_module(module)
        except Exception as exc:  # pragma: no cover - diagnostics only
            failures.append((module, exc))

    if failures:
        for module, exc in failures:
            print(f"❌ Failed to import {module}: {exc}")
        return 1

    print("✅ Import check passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
