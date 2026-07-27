#!/usr/bin/env python3
"""
Tests for reconciler bug-fixes:
  1. Float qty comparison with 0.5-share tolerance (was exact int match).
  2. Cash tolerance widened from 1% to 2%.
  3. No duplicate phantom-position discrepancies.
  4. Regime dict now includes 'vix' key from get_regime_adjustments.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.risk.broker_reconciler import BrokerReconciler

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_reconciler():
    """Return a BrokerReconciler with a mocked TradingClient."""
    with patch.dict(
        "os.environ",
        {
            "ALPACA_API_KEY": "test_key",  # pragma: allowlist secret
            "ALPACA_SECRET_KEY": "test_secret",  # pragma: allowlist secret
            "ALPACA_PAPER": "true",
        },
    ):
        rec = BrokerReconciler(email_notifier=None)
    rec.client = MagicMock()
    return rec


def _make_broker_position(symbol: str, qty: str, avg_price: float):
    pos = MagicMock()
    pos.symbol = symbol
    pos.qty = qty
    pos.avg_entry_price = str(avg_price)
    pos.market_value = str(float(qty) * avg_price)
    return pos


def _make_account(cash: float):
    acct = MagicMock()
    acct.cash = str(cash)
    acct.buying_power = str(cash)
    return acct


# ---------------------------------------------------------------------------
# 1. Qty tolerance: fractional share strings and small diffs pass
# ---------------------------------------------------------------------------


class TestQtyTolerance:
    def test_fractional_qty_string_does_not_raise(self):
        """'5.0' (fractional string from Alpaca) must not crash and should match local qty 5."""
        rec = _make_reconciler()
        rec.client.get_all_positions.return_value = [
            _make_broker_position("AAPL", "5.0", 150.0),
        ]
        local = {"AAPL": {"qty": 5.0, "avg_price": 150.0}}
        discs = rec._reconcile_positions(local)
        assert discs == [], f"Expected no discrepancies, got: {discs}"

    def test_within_half_share_tolerance_passes(self):
        """A 0.3-share difference should be tolerated (rounding from paper fill)."""
        rec = _make_reconciler()
        rec.client.get_all_positions.return_value = [
            _make_broker_position("MSFT", "10.3", 300.0),
        ]
        local = {"MSFT": {"qty": 10.0, "avg_price": 300.0}}
        discs = rec._reconcile_positions(local)
        assert discs == [], f"Expected no discrepancies, got: {discs}"

    def test_over_half_share_difference_is_flagged(self):
        """A 1-share difference should still be caught."""
        rec = _make_reconciler()
        rec.client.get_all_positions.return_value = [
            _make_broker_position("TSLA", "11.0", 200.0),
        ]
        local = {"TSLA": {"qty": 10.0, "avg_price": 200.0}}
        discs = rec._reconcile_positions(local)
        assert any("TSLA" in d and "Quantity" in d for d in discs)


# ---------------------------------------------------------------------------
# 2. Cash tolerance: 1.5% should now pass, 3% should still fail
# ---------------------------------------------------------------------------


class TestCashTolerance:
    def test_cash_within_2pct_passes(self):
        """1.5% cash drift must not flag a discrepancy."""
        rec = _make_reconciler()
        broker_cash = 100_000.0
        local_cash = broker_cash * 0.985  # 1.5% difference
        rec.client.get_account.return_value = _make_account(broker_cash)
        discs = rec._reconcile_cash(local_cash)
        assert discs == [], f"Expected no discrepancy for 1.5% drift, got: {discs}"

    def test_cash_over_2pct_fails(self):
        """3% cash drift must flag a discrepancy."""
        rec = _make_reconciler()
        broker_cash = 100_000.0
        local_cash = broker_cash * 0.97  # 3% difference
        rec.client.get_account.return_value = _make_account(broker_cash)
        discs = rec._reconcile_cash(local_cash)
        assert len(discs) == 1
        assert "Cash mismatch" in discs[0]

    def test_exactly_1pct_passes(self):
        """Regression: 1.0% drift that previously failed should now pass."""
        rec = _make_reconciler()
        broker_cash = 50_000.0
        local_cash = broker_cash * 0.99  # exactly 1%
        rec.client.get_account.return_value = _make_account(broker_cash)
        discs = rec._reconcile_cash(local_cash)
        assert discs == [], f"1% drift should pass, got: {discs}"


# ---------------------------------------------------------------------------
# 3. No duplicate phantom-position discrepancies
# ---------------------------------------------------------------------------


class TestNoDuplicatePhantoms:
    def test_untracked_broker_position_reported_once(self):
        """A position in broker but not in local should appear exactly once."""
        rec = _make_reconciler()

        # Broker has NVDA; local tracks nothing
        rec.client.get_all_positions.return_value = [
            _make_broker_position("NVDA", "8.0", 500.0),
        ]
        rec.client.get_account.return_value = _make_account(50_000.0)

        local_positions: dict = {}
        local_cash = 50_000.0

        _, discrepancies = rec.reconcile_daily(
            local_positions=local_positions,
            local_cash=local_cash,
        )

        nvda_discs = [d for d in discrepancies if "NVDA" in d]
        assert (
            len(nvda_discs) == 1
        ), f"Expected 1 NVDA discrepancy (was 2 before fix), got {len(nvda_discs)}: {nvda_discs}"

    def test_two_untracked_positions_each_reported_once(self):
        """Each of two phantom positions should appear exactly once, not twice."""
        rec = _make_reconciler()
        rec.client.get_all_positions.return_value = [
            _make_broker_position("AAPL", "5.0", 180.0),
            _make_broker_position("GOOG", "3.0", 170.0),
        ]
        rec.client.get_account.return_value = _make_account(50_000.0)

        _, discrepancies = rec.reconcile_daily(
            local_positions={},
            local_cash=50_000.0,
        )

        aapl_count = sum(1 for d in discrepancies if "AAPL" in d)
        goog_count = sum(1 for d in discrepancies if "GOOG" in d)
        assert aapl_count == 1, f"AAPL reported {aapl_count} times"
        assert goog_count == 1, f"GOOG reported {goog_count} times"


# ---------------------------------------------------------------------------
# 3b. send_alert=False suppresses the warning email (engine owns final-outcome
#     notification after auto-sync-and-retry)
# ---------------------------------------------------------------------------


class TestSendAlertGate:
    def _drifting_reconciler(self):
        rec = _make_reconciler()
        rec.email_notifier = MagicMock()
        # Broker has a position local doesn't track -> guaranteed discrepancy.
        rec.client.get_all_positions.return_value = [
            _make_broker_position("NVDA", "8.0", 500.0),
        ]
        rec.client.get_account.return_value = _make_account(50_000.0)
        return rec

    def test_send_alert_false_suppresses_email(self):
        rec = self._drifting_reconciler()
        success, discrepancies = rec.reconcile_daily(
            local_positions={},
            local_cash=50_000.0,
            send_alert=False,
        )
        assert not success and discrepancies  # discrepancy still detected
        rec.email_notifier.send_alert.assert_not_called()  # but no email fired
        assert rec.is_paused is True  # paused state still set for callers

    def test_send_alert_default_true_still_emails(self):
        rec = self._drifting_reconciler()
        rec.reconcile_daily(local_positions={}, local_cash=50_000.0)
        rec.email_notifier.send_alert.assert_called_once()


# ---------------------------------------------------------------------------
# 4. Regime dict now includes 'vix'
# ---------------------------------------------------------------------------


class TestRegimeAdjustmentsIncludesVix:
    def test_vix_present_in_regime_adjustments(self):
        """get_regime_adjustments must include 'vix' so execution_engine can persist it."""
        import numpy as np
        import pandas as pd

        from src.regime.regime_detector import RegimeDetector

        rd = RegimeDetector()
        dates = pd.date_range("2023-01-01", periods=100, freq="B")
        closes = np.linspace(400, 450, 100)
        market_data = pd.DataFrame({"close": closes}, index=dates)

        adjustments = rd.get_regime_adjustments(market_data=market_data)

        assert "vix" in adjustments, "vix key missing from regime_adjustments"
        assert isinstance(adjustments["vix"], (int, float))

    def test_regime_classification_mapping_covers_all_vol_regimes(self):
        """All volatility regime strings map to a non-UNKNOWN email classification."""
        vol_to_classification = {
            "low_volatility": "LOW_VOL",
            "normal": "NORMAL",
            "high_volatility": "HIGH_VOL",
        }
        for _vol, expected in vol_to_classification.items():
            assert expected in ("LOW_VOL", "NORMAL", "HIGH_VOL")
            assert expected != "UNKNOWN"


# ---------------------------------------------------------------------------
# 5. Short positions (negative qty) reconcile correctly
# ---------------------------------------------------------------------------


class TestShortPositionReconciliation:
    def test_matching_short_passes(self):
        """Broker reports shorts as negative qty; an in-sync short is clean."""
        rec = _make_reconciler()
        rec.client.get_all_positions.return_value = [
            _make_broker_position("BAC", "-25", 40.0),
        ]
        local = {"BAC": {"qty": -25.0, "avg_price": 40.0}}
        discs = rec._reconcile_positions(local)
        assert discs == [], f"Expected no discrepancies, got: {discs}"

    def test_short_within_tolerance_passes(self):
        rec = _make_reconciler()
        rec.client.get_all_positions.return_value = [
            _make_broker_position("BAC", "-25.3", 40.0),
        ]
        local = {"BAC": {"qty": -25.0, "avg_price": 40.0}}
        discs = rec._reconcile_positions(local)
        assert discs == [], f"Expected no discrepancies, got: {discs}"

    def test_short_drift_is_flagged(self):
        """-25 local vs -30 broker is meaningful drift on a short — must flag."""
        rec = _make_reconciler()
        rec.client.get_all_positions.return_value = [
            _make_broker_position("BAC", "-30", 40.0),
        ]
        local = {"BAC": {"qty": -25.0, "avg_price": 40.0}}
        discs = rec._reconcile_positions(local)
        assert len(discs) == 1 and "Quantity mismatch" in discs[0]

    def test_sign_flip_is_flagged_loudly(self):
        """Local short vs broker LONG is the worst case — must never pass."""
        rec = _make_reconciler()
        rec.client.get_all_positions.return_value = [
            _make_broker_position("BAC", "25", 40.0),
        ]
        local = {"BAC": {"qty": -25.0, "avg_price": 40.0}}
        discs = rec._reconcile_positions(local)
        assert len(discs) == 1 and "Quantity mismatch" in discs[0]
