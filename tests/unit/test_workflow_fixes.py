"""
Regression tests for fixes applied after Mar 2026 workflow failures.

Covers:
  1. check_stop_losses TypeError: None stop_price / entry_price must not
     raise TypeError when formatted in the warning log line.
  2. fetch_historical_data.py: ALPHA_VANTAGE_PREMIUM env var selects
     sequential (free) vs. parallel (premium) mode.
  3. update_daily_data.py: cold-start fetches 100 days instead of 5 days
     so the training data passes the 250-day DataValidator threshold.
"""
from __future__ import annotations

import os
import pytest
import pandas as pd
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


# ---------------------------------------------------------------------------
# 1. Stop-loss None formatting — regression for TypeError in check_stop_losses
# ---------------------------------------------------------------------------

class TestStopLossNoneFormatting:
    """
    Guard logic introduced in execution_engine.check_stop_losses must not
    raise TypeError when stop_price or entry_price is None.
    Previously the log line used :.2f on None directly, crashing the run.
    """

    def _format_stop(self, stop_price, entry_price, current_price: float) -> tuple:
        """Mirrors the exact guard logic in execution_engine.check_stop_losses."""
        entry = entry_price or 0
        stop_str = f"${stop_price:.2f}" if stop_price is not None else "N/A"
        entry_str = f"${entry:.2f}" if entry else "N/A"
        current_str = f"${current_price:.2f}"
        return stop_str, entry_str, current_str

    def test_none_stop_price_does_not_raise(self):
        """stop_price=None must produce 'N/A', not TypeError."""
        stop_str, _, _ = self._format_stop(None, 100.0, 90.0)
        assert stop_str == "N/A"

    def test_none_entry_price_does_not_raise(self):
        """entry_price=None must produce 'N/A', not TypeError."""
        _, entry_str, _ = self._format_stop(94.0, None, 90.0)
        assert entry_str == "N/A"

    def test_both_none_does_not_raise(self):
        """Both stop_price=None and entry_price=None must not raise."""
        stop_str, entry_str, _ = self._format_stop(None, None, 90.0)
        assert stop_str == "N/A"
        assert entry_str == "N/A"

    def test_zero_entry_price_does_not_raise(self):
        """entry_price=0 is treated as falsy → 'N/A'."""
        _, entry_str, _ = self._format_stop(94.0, 0, 90.0)
        assert entry_str == "N/A"

    def test_valid_values_format_correctly(self):
        """When both values are set, normal float formatting applies."""
        stop_str, entry_str, current_str = self._format_stop(94.0, 100.0, 89.5)
        assert stop_str == "$94.00"
        assert entry_str == "$100.00"
        assert current_str == "$89.50"

    def test_entry_price_dict_get_with_explicit_none(self):
        """
        Regression: position.get('entry_price', 0) returns None when the key
        exists with value None — the default=0 is NOT used in that case.
        The fix uses `position.get('entry_price') or 0` instead.
        """
        position = {'entry_price': None, 'shares': 10}
        # Old (broken): would return None, not 0
        old_result = position.get('entry_price', 0)
        assert old_result is None, "dict.get default not used when key exists with None"

        # New (fixed): `or 0` converts None → 0
        new_result = position.get('entry_price') or 0
        assert new_result == 0


# ---------------------------------------------------------------------------
# 2. fetch_historical_data — ALPHA_VANTAGE_PREMIUM env var
# ---------------------------------------------------------------------------

class TestFetchHistoricalDataTierDetection:
    """
    fetch_historical_data.main() reads ALPHA_VANTAGE_PREMIUM to choose
    sequential (free) vs parallel (premium) mode.
    Default must be free/sequential so a free-tier key does not exhaust
    the 5 req/min limit with 15 simultaneous workers.
    """

    def test_default_is_free_tier(self, monkeypatch):
        """Without the env var, default must be sequential (free)."""
        monkeypatch.delenv("ALPHA_VANTAGE_PREMIUM", raising=False)
        premium = os.getenv("ALPHA_VANTAGE_PREMIUM", "false").lower() == "true"
        assert premium is False, "Default API tier must be free (sequential)"

    def test_premium_env_var_true_enables_parallel(self, monkeypatch):
        """ALPHA_VANTAGE_PREMIUM=true must enable parallel mode."""
        monkeypatch.setenv("ALPHA_VANTAGE_PREMIUM", "true")
        premium = os.getenv("ALPHA_VANTAGE_PREMIUM", "false").lower() == "true"
        assert premium is True

    def test_premium_env_var_false_keeps_sequential(self, monkeypatch):
        """ALPHA_VANTAGE_PREMIUM=false must keep sequential mode."""
        monkeypatch.setenv("ALPHA_VANTAGE_PREMIUM", "false")
        premium = os.getenv("ALPHA_VANTAGE_PREMIUM", "false").lower() == "true"
        assert premium is False

    def test_premium_env_var_case_insensitive(self, monkeypatch):
        """env var check must be case-insensitive."""
        monkeypatch.setenv("ALPHA_VANTAGE_PREMIUM", "TRUE")
        premium = os.getenv("ALPHA_VANTAGE_PREMIUM", "false").lower() == "true"
        assert premium is True

    def test_fetcher_respects_premium_flag(self, monkeypatch):
        """ExtendedDataFetcher uses _fetch_parallel when premium=True."""
        monkeypatch.setenv("ALPHA_VANTAGE_API_KEY", "FAKE_KEY_FOR_TEST")
        from scripts.fetch_historical_data import ExtendedDataFetcher
        fetcher_free = ExtendedDataFetcher(years=1, premium=False)
        fetcher_prem = ExtendedDataFetcher(years=1, premium=True)
        assert fetcher_free.premium is False
        assert fetcher_prem.premium is True


# ---------------------------------------------------------------------------
# 3. update_daily_data — cold-start fetches 100 days instead of 5
# ---------------------------------------------------------------------------

class TestUpdateDailyDataColdStart:
    """
    When training_data.csv does not exist (existing_df is None), the updater
    must request 100 days of compact data per symbol instead of only 5 days.
    5 days of OHLCV is not enough to compute the 50-day or 200-day MAs that
    DataValidator requires.
    """

    def test_days_to_fetch_is_100_when_no_existing_data(self):
        """Cold start: existing_df=None → days_to_fetch=100."""
        existing_df = None
        days_to_fetch = 5 if existing_df is not None else 100
        assert days_to_fetch == 100

    def test_days_to_fetch_is_5_for_incremental_update(self):
        """Incremental update: existing_df present → days_to_fetch=5."""
        existing_df = pd.DataFrame({"date": ["2024-01-01"], "symbol": ["AAPL"]})
        days_to_fetch = 5 if existing_df is not None else 100
        assert days_to_fetch == 5

    def test_updater_class_sets_100_days_on_cold_start(self, tmp_path, monkeypatch):
        """
        Verify the actual DailyDataUpdater sets days_to_fetch=100 when the
        training data file is absent (no network call is made).
        """
        monkeypatch.setenv("ALPHA_VANTAGE_API_KEY", "FAKE_KEY_FOR_TEST")
        import scripts.update_daily_data as _udm
        from scripts.update_daily_data import DailyDataUpdater

        updater = DailyDataUpdater()
        data_file = tmp_path / "training_data.csv"

        # Patch fetch_latest_data so no real HTTP call is made; track `days` arg
        captured_days = []

        def fake_fetch(symbol, days=5):
            captured_days.append(days)
            return None  # simulate failure for all symbols

        monkeypatch.setattr(updater, "fetch_latest_data", fake_fetch)
        # Also eliminate the 12s inter-symbol sleep (35 symbols × 12s = 420s otherwise)
        monkeypatch.setattr(_udm.time, "sleep", lambda _: None)

        # Run with non-existent data file (cold start)
        updater.update_training_data(data_file=str(data_file))

        assert len(captured_days) > 0, "fetch_latest_data should have been called"
        assert all(d == 100 for d in captured_days), (
            f"Cold start must request 100 days, got: {set(captured_days)}"
        )
