#!/usr/bin/env python3
"""
Universe expansion + rolling backfill tests (2026-06).

The universe grew from 43 to 120+ symbols; new symbols must onboard via
capped, deterministic backfill so a single run never blows the API budget.
"""
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from scripts.update_daily_data import select_backfill_symbols  # noqa: E402
from src.data.universe_provider import UniverseProvider  # noqa: E402


class TestExpandedUniverse:
    def test_no_duplicate_symbols(self):
        universe = UniverseProvider.DEFAULT_UNIVERSE
        assert len(universe) == len(
            set(universe)
        ), f"duplicates: {[s for s in set(universe) if universe.count(s) > 1]}"

    def test_universe_is_meaningfully_wider(self):
        assert len(UniverseProvider.DEFAULT_UNIVERSE) >= 120

    def test_all_symbols_pass_validation(self):
        provider = UniverseProvider()
        validated = provider.validate_universe(UniverseProvider.DEFAULT_UNIVERSE)
        assert validated == [s.strip().upper() for s in UniverseProvider.DEFAULT_UNIVERSE]

    def test_benchmarks_still_present(self):
        universe = set(UniverseProvider.DEFAULT_UNIVERSE)
        assert UniverseProvider.BENCHMARK_SYMBOLS <= universe


def _df(symbol_rows: dict, latest="2026-06-10"):
    """Build an existing_df with N rows per symbol ending at `latest`."""
    frames = []
    end = datetime.fromisoformat(latest)
    for sym, n in symbol_rows.items():
        dates = pd.bdate_range(end=end, periods=n)
        frames.append(pd.DataFrame({"date": dates, "symbol": sym, "close": 100.0}))
    return pd.concat(frames, ignore_index=True)


class TestSelectBackfillSymbols:
    def test_cold_start_backfills_everything_up_to_cap(self):
        backfill, deferred = select_backfill_symbols(
            None, ["C", "A", "B", "D"], None, max_backfills=2
        )
        assert backfill == {"A", "B"}  # alphabetical determinism
        assert deferred == {"C", "D"}

    def test_established_symbols_not_backfilled(self):
        df = _df({"AAPL": 500, "MSFT": 500})
        backfill, deferred = select_backfill_symbols(
            df, ["AAPL", "MSFT"], df["date"].max(), max_backfills=25
        )
        assert backfill == set()
        assert deferred == set()

    def test_new_symbols_selected_and_capped(self):
        df = _df({"AAPL": 500})
        universe = ["AAPL", "ORCL", "CSCO", "BAC"]
        backfill, deferred = select_backfill_symbols(
            df, universe, df["date"].max(), max_backfills=2
        )
        assert backfill == {"BAC", "CSCO"}
        assert deferred == {"ORCL"}

    def test_stale_symbol_triggers_backfill(self):
        # symbol with deep history but no recent rows must re-backfill
        frames = _df({"AAPL": 500})
        old = _df({"OLD": 400}, latest="2025-06-01")
        df = pd.concat([frames, old], ignore_index=True)
        backfill, _ = select_backfill_symbols(
            df, ["AAPL", "OLD"], frames["date"].max(), max_backfills=25
        )
        assert "OLD" in backfill

    def test_no_cap_returns_all(self):
        backfill, deferred = select_backfill_symbols(
            None, ["A", "B", "C"], None, max_backfills=None
        )
        assert backfill == {"A", "B", "C"}
        assert deferred == set()
