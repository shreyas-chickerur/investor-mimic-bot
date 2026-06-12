#!/usr/bin/env python3
"""
Shared sector map coverage tests: every tradeable universe symbol must be
mapped to a sector ETF (the old partial maps made the universe expansion
invisible to Factor Momentum and Sector Rotation), and benchmarks must
never appear as constituents.
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.data.sector_map import SYMBOL_SECTOR, constituents_by_sector, sector_of  # noqa: E402
from src.data.universe_provider import UniverseProvider  # noqa: E402


def test_every_tradeable_universe_symbol_is_mapped():
    tradeable = set(UniverseProvider.DEFAULT_UNIVERSE) - UniverseProvider.BENCHMARK_SYMBOLS
    unmapped = sorted(s for s in tradeable if s not in SYMBOL_SECTOR)
    assert unmapped == [], f"unmapped tradeable symbols: {unmapped}"


def test_no_benchmark_is_a_constituent():
    overlap = UniverseProvider.BENCHMARK_SYMBOLS & set(SYMBOL_SECTOR)
    assert overlap == set(), f"benchmarks mapped as constituents: {overlap}"


def test_all_sectors_have_universe_etfs():
    # Every sector ETF used in the map must be fetchable (in the universe)
    sectors = set(SYMBOL_SECTOR.values())
    missing = sorted(sectors - set(UniverseProvider.DEFAULT_UNIVERSE))
    assert missing == [], f"sector ETFs not in the data universe: {missing}"


def test_inverted_map_round_trips():
    by_sector = constituents_by_sector()
    assert sum(len(v) for v in by_sector.values()) == len(SYMBOL_SECTOR)
    assert sector_of("aapl") == "XLK"  # case-insensitive
    assert sector_of("UNKNOWN") is None  # never silently SPY
