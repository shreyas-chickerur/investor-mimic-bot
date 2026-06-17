#!/usr/bin/env python3
"""record_fill_quality true-up regression tests.

The fill-quality loop queries Alpaca for recently CLOSED orders with an `after`
timestamp. alpaca-py 0.11.0 serializes datetimes as ``isoformat() + "Z"`` with
NO naive-check, so a tz-aware UTC value becomes the invalid ``...+00:00Z``
(offset AND Z) — which Alpaca rejects with HTTP 422. That crashed the daily
run's `record_fill_quality` step every trading day 2026-06-12..2026-06-17 and,
because the final health gate checks every non-blocking step's outcome, turned
otherwise-successful runs RED.

These tests exercise the REAL ``GetOrdersRequest`` serialization (only the
network client is mocked), so they fail on the tz-aware regression and pass on
the naive-UTC fix.
"""
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from scripts.record_fill_quality import true_up  # noqa: E402


@pytest.fixture
def serialized_after(tmp_path, monkeypatch):
    """Run true_up with a mocked broker; return the serialized `after` param
    exactly as it would be sent on the wire."""
    monkeypatch.setenv("ALPACA_API_KEY", "test_key")  # pragma: allowlist secret
    monkeypatch.setenv("ALPACA_SECRET_KEY", "test_secret")  # pragma: allowlist secret
    monkeypatch.setenv("ALPACA_PAPER", "true")

    import alpaca.trading.client as alpaca_client

    captured = {}
    fake = MagicMock()

    def _get_orders(filter=None):
        captured["request"] = filter
        return []  # empty → true_up's DB loop is a no-op

    fake.get_orders.side_effect = _get_orders
    monkeypatch.setattr(alpaca_client, "TradingClient", lambda *a, **k: fake)

    true_up(str(tmp_path / "trading.db"), days=3)
    # to_request_fields() is what alpaca-py urlencodes into the request URL.
    return captured["request"].to_request_fields()["after"]


def test_after_is_valid_rfc3339(serialized_after):
    after = serialized_after
    # The exact production defect: an offset AND a trailing Z, e.g.
    # "2026-06-14T05:46:05.843484+00:00Z" → HTTP 422.
    assert "+00:00Z" not in after, f"malformed double timezone designator: {after!r}"
    # It must parse as a real UTC instant (fromisoformat accepts +00:00, not Z).
    parsed = datetime.fromisoformat(after.replace("Z", "+00:00"))
    assert parsed.utcoffset() is not None, f"timestamp is not tz-anchored: {after!r}"


def test_after_lookback_window(serialized_after):
    # Sanity: the window is in the recent past (days=3), not the future/epoch.
    parsed = datetime.fromisoformat(serialized_after.replace("Z", "+00:00"))
    age_days = (datetime.now(parsed.tzinfo) - parsed).days
    assert 2 <= age_days <= 4, f"unexpected lookback: {age_days} days ({serialized_after!r})"
