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
    US_MARKET_HOLIDAYS,
    is_fresh,
    is_trading_day,
    last_completed_session,
    nyse_holidays,
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


class TestMarketHolidays:
    """Guards against the 2026-06-22 PREFLIGHT_FAILED outage: the hand-typed
    holiday list had dropped Juneteenth (2026-06-19) and mis-dated Good
    Friday/Christmas 2027, so a Monday-after-holiday treated correct
    last-session data as stale. The set is now computed; these lock it down."""

    def test_juneteenth_observed_every_year(self):
        # NYSE has observed Juneteenth since 2022. Each year must include it,
        # with weekend observance (2027-06-19 is a Saturday -> Fri 06-18).
        assert "2025-06-19" in US_MARKET_HOLIDAYS  # Thursday
        assert "2026-06-19" in US_MARKET_HOLIDAYS  # Friday (the missing one)
        assert "2027-06-18" in US_MARKET_HOLIDAYS  # Sat -> observed Friday
        assert "2028-06-19" in US_MARKET_HOLIDAYS  # Monday

    def test_good_friday_and_christmas_2027_correct(self):
        # Easter 2027 is Mar 28 -> Good Friday Mar 26 (was wrongly 04-02).
        assert "2027-03-26" in US_MARKET_HOLIDAYS
        assert "2027-04-02" not in US_MARKET_HOLIDAYS
        # Dec 25 2027 is a Saturday -> observed Friday Dec 24 (was wrongly 12-27).
        assert "2027-12-24" in US_MARKET_HOLIDAYS
        assert "2027-12-27" not in US_MARKET_HOLIDAYS

    def test_ten_full_closures_per_year(self):
        # Ten NYSE full-day closures, minus any that fall on a Saturday with no
        # observance (New Year on Sat) — so 9 or 10 per year, never fewer.
        for year in (2025, 2026, 2027, 2028):
            assert 9 <= len(nyse_holidays(year)) <= 10

    def test_monday_after_juneteenth_data_is_fresh(self):
        # The exact outage: Thursday 2026-06-18 data checked Monday 2026-06-22
        # pre-open. Friday 06-19 was Juneteenth (closed), so 06-18 IS the last
        # session — must be fresh even though it is ~82h old (> 80h knob).
        latest = datetime(2026, 6, 18, 16, 0)
        now = datetime(2026, 6, 22, 1, 45)
        assert last_completed_session(now) == date(2026, 6, 18)
        fresh, reason = is_fresh(latest, now, max_age_hours=80)
        assert fresh
        assert "session" in reason

    def test_juneteenth_is_not_a_trading_day(self):
        assert is_trading_day(date(2026, 6, 19)) is False
