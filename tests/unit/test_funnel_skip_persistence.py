#!/usr/bin/env python3
"""Every strategy-skip path must PERSIST its zero-count funnel row.

The post-run guardrail (scripts/diagnostics/post_run_guardrails.py) treats a
missing signal_funnel row for a canonical strategy as a critical failure.
Skip paths that only record_* in memory without save_to_database() therefore
turn a legitimate skip into a RED run — this happened on 2026-07-17 when the
regime detector disabled Sector Rotation and no funnel row was written.
"""
import re
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import src.core.execution_engine as ee  # noqa: E402


def test_every_funnel_recording_skip_path_persists_row():
    import inspect

    src = inspect.getsource(ee.MultiStrategyRunner.run_all_strategies)

    # Each block that records zero raw signals for a skipped strategy and then
    # `continue`s must call save_to_database in between — otherwise the run
    # produces no signal_funnel row and the guardrail flags it critical.
    pattern = re.compile(
        r"record_raw_signals\(strategy\.strategy_id, 0\)(?P<block>.*?)\n\s*continue\b",
        re.DOTALL,
    )
    blocks = list(pattern.finditer(src))
    assert blocks, "no funnel-recording skip paths found — did the loop change shape?"
    for m in blocks:
        assert "save_to_database" in m.group("block"), (
            "A strategy-skip path records funnel counts but never persists them "
            "(save_to_database missing before `continue`): a legitimately skipped "
            "strategy would have no signal_funnel row and the post-run guardrail "
            f"turns the run RED. Offending block:\n{m.group(0)[:400]}"
        )
