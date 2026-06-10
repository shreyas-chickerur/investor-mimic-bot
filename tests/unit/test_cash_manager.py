#!/usr/bin/env python3
"""
CashManager release clamp: a double release must never hand one strategy more
than its own allocation (previously the clamp was the WHOLE portfolio).
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.integration.cash_manager import CashManager


class TestReleaseClamp:
    def test_release_restores_reserved_amount(self):
        cm = CashManager(total_cash=100_000, num_strategies=5)  # $20k each
        assert cm.reserve_cash(1, 5_000)
        cm.release_cash(1, 5_000)
        assert cm.allocated_cash[1] == pytest.approx(20_000)

    def test_double_release_clamps_to_strategy_allocation(self):
        cm = CashManager(total_cash=100_000, num_strategies=5)
        assert cm.reserve_cash(1, 5_000)
        cm.release_cash(1, 5_000)
        cm.release_cash(1, 5_000)  # erroneous second release
        assert cm.allocated_cash[1] == pytest.approx(20_000), (
            "double release must clamp to the strategy's $20k allocation, "
            "not the $100k portfolio"
        )

    def test_double_release_logs_warning(self, caplog):
        cm = CashManager(total_cash=100_000, num_strategies=5)
        assert cm.reserve_cash(1, 5_000)
        cm.release_cash(1, 5_000)
        with caplog.at_level("WARNING"):
            cm.release_cash(1, 5_000)
        assert any("clamp" in r.message for r in caplog.records)

    def test_invariant_holds_after_double_release(self):
        cm = CashManager(total_cash=100_000, num_strategies=5)
        assert cm.reserve_cash(1, 5_000)
        cm.release_cash(1, 5_000)
        cm.release_cash(1, 5_000)
        assert cm.validate_invariants() is True

    def test_set_allocations_updates_ceilings(self):
        cm = CashManager(total_cash=100_000, num_strategies=5)
        cm.set_allocations({1: 30_000, 2: 70_000})
        cm.release_cash(1, 50_000)  # bogus huge release
        assert cm.allocated_cash[1] == pytest.approx(30_000)

    def test_sync_from_broker_scales_ceilings(self):
        cm = CashManager(total_cash=100_000, num_strategies=5)
        cm.sync_from_broker(50_000)  # broker says half the cash
        cm.release_cash(1, 100_000)  # bogus release
        assert cm.allocated_cash[1] == pytest.approx(10_000)  # 20k ceiling scaled by 0.5
