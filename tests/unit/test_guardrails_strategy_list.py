#!/usr/bin/env python3
"""
Liveness-guardrail strategy list must be derived from config, never hardcoded.

Regression: a stale 7-name hardcoded list in post_run_guardrails went RED on
the first run after the 2026-06 dispositions, flagging the absence of funnel
rows from ML Momentum / News Sentiment — both correctly disabled and never
run (run 27397185082, 2026-06-12). The trading itself had succeeded.
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from scripts.diagnostics.post_run_guardrails import expected_enabled_strategies  # noqa: E402
from src.core.execution_engine import CANONICAL_STRATEGY_SPECS  # noqa: E402
from src.utils.config_loader import get_config  # noqa: E402


def test_disabled_strategies_are_not_expected():
    expected = expected_enabled_strategies()
    config = get_config()
    for name, _desc, _cls in CANONICAL_STRATEGY_SPECS:
        key = f"strategies.{name.lower().replace(' ', '_')}.disabled"
        if config.get(key, False):
            assert name not in expected, f"{name} is disabled but the guardrail expects it"
        else:
            assert name in expected, f"{name} is enabled but the guardrail ignores it"


def test_env_disabled_strategies_excluded(monkeypatch):
    enabled = expected_enabled_strategies()
    assert enabled, "at least one strategy must be enabled"
    victim = enabled[0]
    monkeypatch.setenv("STRATEGY_DISABLED_LIST", victim)
    assert victim not in expected_enabled_strategies()


def test_no_stale_names():
    # The three evidence-disabled strategies must not be expected today
    expected = set(expected_enabled_strategies())
    assert {"ML Momentum", "News Sentiment", "Pairs Trading"} & expected == set()
