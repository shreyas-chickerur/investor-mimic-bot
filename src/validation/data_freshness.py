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

# Major US market holidays (kept in sync with scripts/pre_flight_check.py,
# which imports this set).
US_MARKET_HOLIDAYS: set[str] = {
    # 2025
    "2025-01-01",
    "2025-01-20",
    "2025-02-17",
    "2025-04-18",
    "2025-05-26",
    "2025-07-04",
    "2025-09-01",
    "2025-11-27",
    "2025-12-25",
    # 2026
    "2026-01-01",
    "2026-01-19",
    "2026-02-16",
    "2026-04-03",
    "2026-05-25",
    "2026-07-03",
    "2026-09-07",
    "2026-11-26",
    "2026-12-25",
    # 2027
    "2027-01-01",
    "2027-01-18",
    "2027-02-15",
    "2027-04-02",
    "2027-05-31",
    "2027-07-05",
    "2027-09-06",
    "2027-11-25",
    "2027-12-27",
    # 2028
    "2028-01-01",
    "2028-01-17",
    "2028-02-21",
    "2028-04-14",
    "2028-05-29",
    "2028-07-04",
    "2028-09-04",
    "2028-11-23",
    "2028-12-25",
}

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
