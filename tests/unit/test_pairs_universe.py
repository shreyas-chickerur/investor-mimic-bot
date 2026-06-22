#!/usr/bin/env python3
"""
Pairs strategy now loads data-driven pairs from the screener
(EXP-2026-06-22-pairs-universe-screen). Verify the loader uses the screened
file when present (with half-life-aligned per-pair holds) and falls back to the
built-in defaults when it's absent or empty.
"""
import importlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import src.strategies.strategy_pairs_trading as pt


def _reload_with_path(monkeypatch, path):
    monkeypatch.setattr(pt, "_PAIRS_UNIVERSE_PATH", path)
    return pt


def test_missing_file_falls_back_to_defaults(monkeypatch, tmp_path):
    _reload_with_path(monkeypatch, tmp_path / "nope.json")
    pairs, holds = pt.load_screened_pairs()
    assert pairs == pt._DEFAULT_PAIRS
    assert holds == {}


def test_empty_pairs_falls_back_to_defaults(monkeypatch, tmp_path):
    f = tmp_path / "pairs_universe.json"
    f.write_text(json.dumps({"pairs": []}))
    _reload_with_path(monkeypatch, f)
    pairs, holds = pt.load_screened_pairs()
    assert pairs == pt._DEFAULT_PAIRS


def test_screened_pairs_are_used_with_per_pair_holds(monkeypatch, tmp_path):
    f = tmp_path / "pairs_universe.json"
    f.write_text(
        json.dumps(
            {
                "pairs": [
                    {"num": "COST", "den": "KO", "max_hold_days": 30},
                    {"num": "ABT", "den": "DHR", "max_hold_days": 25},
                ]
            }
        )
    )
    _reload_with_path(monkeypatch, f)
    pairs, holds = pt.load_screened_pairs()
    assert pairs == [("COST", "KO"), ("ABT", "DHR")]
    assert holds == {"COST": 30, "ABT": 25}


def test_corrupt_file_falls_back_safely(monkeypatch, tmp_path):
    f = tmp_path / "pairs_universe.json"
    f.write_text("{not valid json")
    _reload_with_path(monkeypatch, f)
    pairs, holds = pt.load_screened_pairs()
    assert pairs == pt._DEFAULT_PAIRS


def test_aligned_max_hold_scales_with_half_life():
    screen = importlib.import_module("scripts.research.screen_pairs")
    # ~3× half-life, clamped to [floor=10, cap=45].
    assert screen._aligned_max_hold(2) == screen.MAX_HOLD_FLOOR  # 3*2=6 -> floor 10
    assert screen._aligned_max_hold(5) == 15  # 3*5
    assert screen._aligned_max_hold(10) == 30  # 3*10
    assert screen._aligned_max_hold(100) == screen.MAX_HOLD_CAP  # clamped to 45
