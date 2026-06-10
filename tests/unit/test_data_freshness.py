#!/usr/bin/env python3
"""
data_freshness: the single staleness knob + last-completed-session calendar
check (the workflow previously had three disagreeing thresholds: 48/72/144h).
"""
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.validation.data_freshness import (
    is_fresh,
    is_trading_day,
    last_completed_session,
)


class TestLastCompletedSession:
    def test_monday_pre_open_resolves_to_friday(self):
        # Mon 2026-06-08 00:45 ET (the daily run time) — Friday is last complete
        now = datetime(2026, 6, 8, 0, 45)
        assert last_completed_session(now) == date(2026, 6, 5)

    def test_tuesday_pre_open_resolves_to_monday(self):
        now = datetime(2026, 6, 9, 0, 45)
        assert last_completed_session(now) == date(2026, 6, 8)

    def test_after_close_resolves_to_same_day(self):
        now = datetime(2026, 6, 9, 17, 0)
        assert last_completed_session(now) == date(2026, 6, 9)

    def test_holiday_monday_skipped(self):
        # Memorial Day 2026-05-25 (Mon, in holiday set): Tue pre-open → prior Friday
        now = datetime(2026, 5, 26, 0, 45)
        assert last_completed_session(now) == date(2026, 5, 22)

    def test_is_trading_day(self):
        assert is_trading_day(date(2026, 6, 9)) is True  # Tuesday
        assert is_trading_day(date(2026, 6, 7)) is False  # Sunday
        assert is_trading_day(date(2026, 5, 25)) is False  # Memorial Day


class TestIsFresh:
    def test_normal_daily_data_is_fresh(self):
        latest = datetime(2026, 6, 8, 16, 0)
        now = datetime(2026, 6, 9, 0, 45)
        fresh, reason = is_fresh(latest, now, max_age_hours=80)
        assert fresh

    def test_monday_after_weekend_is_fresh(self):
        # Friday's data, checked Monday pre-open: ~57h old, within 80h
        latest = datetime(2026, 6, 5, 16, 0)
        now = datetime(2026, 6, 8, 0, 45)
        fresh, _ = is_fresh(latest, now, max_age_hours=80)
        assert fresh

    def test_tuesday_after_holiday_monday_passes_via_calendar(self):
        # Friday 5/22 data checked Tue 5/26 pre-open after Memorial Day:
        # ~81h old (over the 80h knob) but covers the last completed session.
        latest = datetime(2026, 5, 22, 16, 0)
        now = datetime(2026, 5, 26, 0, 45)
        fresh, reason = is_fresh(latest, now, max_age_hours=80)
        assert fresh
        assert "session" in reason

    def test_genuinely_stale_data_fails(self):
        # Data ends Monday 6/8 but it's Thursday 6/11 pre-open: missed
        # Tuesday AND Wednesday sessions.
        latest = datetime(2026, 6, 8, 16, 0)
        now = datetime(2026, 6, 11, 0, 45)
        fresh, reason = is_fresh(latest, now, max_age_hours=48)
        assert not fresh
        assert "misses the last" in reason

    def test_date_input_accepted(self):
        fresh, _ = is_fresh(date(2026, 6, 8), datetime(2026, 6, 9, 0, 45), max_age_hours=80)
        assert fresh
