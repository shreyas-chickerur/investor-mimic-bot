#!/usr/bin/env python3
"""
Signal contract: every signal a strategy emits must carry an ``asof_date``.

The execution engine uses asof_date for point-in-time entry dates and audit
trails; a missing field silently falls back to datetime.now(), corrupting
hold-day and tax-treatment math. This regressed once (earnings_drift SELL,
fixed 2026-06-11) — this source-level tripwire covers every append site in
every strategy, including branches that only fire on rare market conditions
and therefore can't be reliably exercised with synthetic data.
"""
import ast
from pathlib import Path

import pytest

STRATEGY_DIR = Path(__file__).parent.parent.parent / "src" / "strategies"
STRATEGY_FILES = sorted(STRATEGY_DIR.glob("strategy_*.py"))


def _signal_append_dicts(tree: ast.AST):
    """Yield (lineno, dict_node) for every ``signals.append({...})`` call."""
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "append"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "signals"
            and node.args
            and isinstance(node.args[0], ast.Dict)
        ):
            yield node.lineno, node.args[0]


@pytest.mark.parametrize("path", STRATEGY_FILES, ids=lambda p: p.name)
def test_every_emitted_signal_has_asof_date(path):
    tree = ast.parse(path.read_text())
    appends = list(_signal_append_dicts(tree))
    assert appends, f"{path.name}: no signals.append(dict) found — pattern changed?"
    for lineno, dict_node in appends:
        keys = {k.value for k in dict_node.keys if isinstance(k, ast.Constant)}
        assert "asof_date" in keys, (
            f"{path.name}:{lineno} emits a signal without 'asof_date' — the engine "
            "will fall back to datetime.now() and corrupt entry dates / hold days"
        )


@pytest.mark.parametrize("path", STRATEGY_FILES, ids=lambda p: p.name)
def test_every_emitted_signal_has_core_fields(path):
    """Symbol/action/shares/price/confidence are required by the funnel."""
    tree = ast.parse(path.read_text())
    for lineno, dict_node in _signal_append_dicts(tree):
        keys = {k.value for k in dict_node.keys if isinstance(k, ast.Constant)}
        missing = {"symbol", "action", "shares", "price", "confidence"} - keys
        assert not missing, f"{path.name}:{lineno} signal missing required fields: {missing}"
