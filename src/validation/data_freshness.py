#!/usr/bin/env python3
"""
Single source of truth for "is the market data fresh enough to trade on?".

History: the daily workflow once had THREE different staleness thresholds
(48h alert, 72h gate, 144h validator) that could disagree — trading proceeded
on data another step had just flagged stale. Everything now reads the one
DATA_MAX_AGE_HOURS knob and, for gaps that hour-counting can't classify
(three-day weekends, market holidays), falls back to a calendar check: data
is fresh if it covers the last COMPLETED trading session, regardless of age.
"""
from __future__ import annotations

import logging
import os
from datetime import date, datetime, time, timedelta

logger = logging.getLogger(__name__)

DEFAULT_MAX_AGE_HOURS = 80  # Fri close -> Mon 05:45 UTC ≈ 57h, with margin

# US market holidays are COMPUTED, not hand-maintained. A hand-typed list
# silently dropped Juneteenth (2026-06-19) and mis-dated Good Friday/Christmas
# 2027, which made the Monday-after-holiday freshness check declare correct
# last-session data "stale" and fail pre-flight (PREFLIGHT_FAILED outage,
# 2026-06-22). Deriving the dates removes the whole class of bug.
#
# Covers the ten NYSE full-closure holidays with NYSE observance rules
# (Sat -> preceding Fri, Sun -> following Mon; New Year on Sat is NOT
# observed). It does NOT capture ad-hoc closures (national mourning, weather)
# — those are rare, unpredictable, and were never in the manual list either.


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    """The ``n``-th ``weekday`` (Mon=0) of ``month`` in ``year``."""
    first = date(year, month, 1)
    first += timedelta(days=(weekday - first.weekday()) % 7)
    return first + timedelta(weeks=n - 1)


def _last_weekday(year: int, month: int, weekday: int) -> date:
    """The last ``weekday`` (Mon=0) of ``month`` in ``year``."""
    nxt = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    d = nxt - timedelta(days=1)
    return d - timedelta(days=(d.weekday() - weekday) % 7)


def _easter(year: int) -> date:
    """Easter Sunday (Anonymous Gregorian algorithm) — anchors Good Friday."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    m = (a + 11 * h + 22 * ((32 + 2 * e + 2 * i - h - k) % 7)) // 451
    month = (h + ((32 + 2 * e + 2 * i - h - k) % 7) - 7 * m + 114) // 31
    day = ((h + ((32 + 2 * e + 2 * i - h - k) % 7) - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def _observed(d: date, is_new_year: bool = False) -> date | None:
    """Apply NYSE weekend-observance: Sat -> Fri, Sun -> Mon.

    New Year's Day falling on a Saturday is NOT observed (the market is open
    the preceding Friday, Dec 31), so this returns None for that case.
    """
    if d.weekday() == 5:  # Saturday
        return None if is_new_year else d - timedelta(days=1)
    if d.weekday() == 6:  # Sunday
        return d + timedelta(days=1)
    return d


def nyse_holidays(year: int) -> set[str]:
    """ISO dates of NYSE full-day closures in ``year`` (observance applied)."""
    candidates = [
        _observed(date(year, 1, 1), is_new_year=True),  # New Year's Day
        _nth_weekday(year, 1, 0, 3),  # MLK Day (3rd Mon Jan)
        _nth_weekday(year, 2, 0, 3),  # Washington's Birthday (3rd Mon Feb)
        _easter(year) - timedelta(days=2),  # Good Friday
        _last_weekday(year, 5, 0),  # Memorial Day (last Mon May)
        _observed(date(year, 6, 19)),  # Juneteenth
        _observed(date(year, 7, 4)),  # Independence Day
        _nth_weekday(year, 9, 0, 1),  # Labor Day (1st Mon Sep)
        _nth_weekday(year, 11, 3, 4),  # Thanksgiving (4th Thu Nov)
        _observed(date(year, 12, 25)),  # Christmas
    ]
    return {d.isoformat() for d in candidates if d is not None}


# Generated over a wide range so the calendar never silently runs out. Kept in
# sync with scripts/pre_flight_check.py, which imports this set.
_HOLIDAY_YEAR_RANGE = range(2020, 2041)
US_MARKET_HOLIDAYS: set[str] = {iso for year in _HOLIDAY_YEAR_RANGE for iso in nyse_holidays(year)}

_MARKET_CLOSE_ET = time(16, 0)


def configured_max_age_hours() -> int:
    """The one staleness knob (workflow-level env DATA_MAX_AGE_HOURS)."""
    return int(os.getenv("DATA_MAX_AGE_HOURS", str(DEFAULT_MAX_AGE_HOURS)))


def is_trading_day(d: date) -> bool:
    return d.weekday() < 5 and d.isoformat() not in US_MARKET_HOLIDAYS


def last_completed_session(now: datetime | None = None) -> date:
    """Most recent trading day whose 16:00 ET close has already happened.

    ``now`` is interpreted as US/Eastern when naive (callers in GHA pass
    Eastern-converted datetimes; the daily run at 05:45 UTC = 00:45/01:45 ET
    resolves to the PREVIOUS day's session, which is correct).
    """
    if now is None:
        try:
            import pytz  # type: ignore[import-untyped]

            now = datetime.now(pytz.timezone("America/New_York")).replace(tzinfo=None)
        except Exception:
            now = datetime.now()

    d = now.date()
    if not is_trading_day(d) or now.time() < _MARKET_CLOSE_ET:
        d -= timedelta(days=1)
    while not is_trading_day(d):
        d -= timedelta(days=1)
    return d


def is_fresh(
    latest_data_date: datetime | date,
    now: datetime | None = None,
    max_age_hours: int | None = None,
) -> tuple[bool, str]:
    """Whether data dated ``latest_data_date`` is tradeable.

    Fresh when EITHER:
      * its age is within max_age_hours (the normal daily case), OR
      * it covers the last completed trading session (holiday/weekend gaps
        where wall-clock age legitimately exceeds the threshold).
    """
    if max_age_hours is None:
        max_age_hours = configured_max_age_hours()
    if now is None:
        now = datetime.now()

    if isinstance(latest_data_date, datetime):
        latest_dt = latest_data_date
        latest_d = latest_data_date.date()
    else:
        latest_dt = datetime.combine(latest_data_date, _MARKET_CLOSE_ET)
        latest_d = latest_data_date

    age_hours = (now - latest_dt).total_seconds() / 3600
    if age_hours <= max_age_hours:
        return True, f"data is {age_hours:.1f}h old (≤ {max_age_hours}h)"

    session = last_completed_session(now)
    if latest_d >= session:
        return True, (
            f"data is {age_hours:.0f}h old but covers the last completed "
            f"session ({session.isoformat()}) — holiday/weekend gap"
        )

    return False, (
        f"data is {age_hours:.0f}h old (> {max_age_hours}h) and misses the last "
        f"completed session ({session.isoformat()}, data ends {latest_d.isoformat()})"
    )
