#!/usr/bin/env python3
"""
Test suite for selective trade approval system.

Tests individual trade approval/rejection functionality, ensuring that
users can approve or reject each trade independently.
"""

import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

import pytest

from services.approval.trade_approval import ApprovalStatus, TradeApprovalManager


class TestSelectiveApproval:
    """Test suite for selective trade approval functionality."""

    @pytest.fixture
    def manager(self):
        """Create a TradeApprovalManager instance."""
        return TradeApprovalManager()

    @pytest.fixture
    def sample_trades(self):
        """Sample trades for testing."""
        return [
            {
                "symbol": "GOOGL",
                "quantity": 15.2,
                "estimated_price": 296.72,
                "estimated_value": 4510.14,
                "allocation_pct": 7.8,
            },
            {
                "symbol": "UBER",
                "quantity": 45.3,
                "estimated_price": 128.50,
                "estimated_value": 5821.05,
                "allocation_pct": 6.5,
            },
            {
                "symbol": "AAPL",
                "quantity": 25.0,
                "estimated_price": 185.50,
                "estimated_value": 4637.50,
                "allocation_pct": 5.2,
            },
            {
                "symbol": "MSFT",
                "quantity": 12.5,
                "estimated_price": 378.90,
                "estimated_value": 4736.25,
                "allocation_pct": 5.0,
            },
            {
                "symbol": "AMZN",
                "quantity": 8.5,
                "estimated_price": 178.20,
                "estimated_value": 1514.70,
                "allocation_pct": 1.7,
            },
        ]

    def test_create_approval_request(self, manager, sample_trades):
        """Test creating an approval request with trades."""
        request = manager.create_approval_request(
            trades=sample_trades,
            total_investment=21219.64,
            available_cash=142825.43,
            cash_buffer=21423.81,
            expiry_hours=24,
        )

        assert request is not None
        assert request.request_id is not None
        assert request.status == ApprovalStatus.PENDING
        assert len(request.trades) == 5
        assert request.total_investment == 21219.64

        # All trades should start as pending (approved=None)
        for trade in request.trades:
            assert trade.approved is None

    def test_approve_individual_trade(self, manager, sample_trades):
        """Test approving a single trade."""
        request = manager.create_approval_request(
            trades=sample_trades,
            total_investment=21219.64,
            available_cash=142825.43,
            cash_buffer=21423.81,
        )

        # Approve first trade (GOOGL)
        success = manager.approve_trade(request.request_id, 0)
        assert success is True

        # Verify the trade is approved
        updated_request = manager.get_request(request.request_id)
        assert updated_request.trades[0].approved is True
        assert updated_request.trades[0].symbol == "GOOGL"

        # Other trades should still be pending
        for i in range(1, 5):
            assert updated_request.trades[i].approved is None

    def test_reject_individual_trade(self, manager, sample_trades):
        """Test rejecting a single trade."""
        request = manager.create_approval_request(
            trades=sample_trades,
            total_investment=21219.64,
            available_cash=142825.43,
            cash_buffer=21423.81,
        )

        # Reject second trade (UBER)
        success = manager.reject_trade(request.request_id, 1)
        assert success is True

        # Verify the trade is rejected
        updated_request = manager.get_request(request.request_id)
        assert updated_request.trades[1].approved is False
        assert updated_request.trades[1].symbol == "UBER"

        # Other trades should still be pending
        assert updated_request.trades[0].approved is None
        for i in range(2, 5):
            assert updated_request.trades[i].approved is None

    def test_mixed_approvals(self, manager, sample_trades):
        """Test approving some trades and rejecting others."""
        request = manager.create_approval_request(
            trades=sample_trades,
            total_investment=21219.64,
            available_cash=142825.43,
            cash_buffer=21423.81,
        )

        # Approve trades 0, 2, 3 (GOOGL, AAPL, MSFT)
        manager.approve_trade(request.request_id, 0)
        manager.approve_trade(request.request_id, 2)
        manager.approve_trade(request.request_id, 3)

        # Reject trades 1, 4 (UBER, AMZN)
        manager.reject_trade(request.request_id, 1)
        manager.reject_trade(request.request_id, 4)

        # Verify the status
        updated_request = manager.get_request(request.request_id)
        assert updated_request.trades[0].approved is True  # GOOGL
        assert updated_request.trades[1].approved is False  # UBER
        assert updated_request.trades[2].approved is True  # AAPL
        assert updated_request.trades[3].approved is True  # MSFT
        assert updated_request.trades[4].approved is False  # AMZN

    def test_get_approved_trades(self, manager, sample_trades):
        """Test retrieving only approved trades."""
        request = manager.create_approval_request(
            trades=sample_trades,
            total_investment=21219.64,
            available_cash=142825.43,
            cash_buffer=21423.81,
        )

        # Approve trades 0, 2, 3
        manager.approve_trade(request.request_id, 0)
        manager.approve_trade(request.request_id, 2)
        manager.approve_trade(request.request_id, 3)

        # Reject trades 1, 4
        manager.reject_trade(request.request_id, 1)
        manager.reject_trade(request.request_id, 4)

        # Get approved trades
        approved_trades = manager.get_approved_trades(request.request_id)

        assert len(approved_trades) == 3
        assert approved_trades[0].symbol == "GOOGL"
        assert approved_trades[1].symbol == "AAPL"
        assert approved_trades[2].symbol == "MSFT"

        # Verify total value of approved trades
        total_value = sum(t.estimated_value for t in approved_trades)
        expected_value = 4510.14 + 4637.50 + 4736.25  # GOOGL + AAPL + MSFT
        assert abs(total_value - expected_value) < 0.01

    def test_invalid_trade_index(self, manager, sample_trades):
        """Test approving/rejecting with invalid trade index."""
        request = manager.create_approval_request(
            trades=sample_trades,
            total_investment=21219.64,
            available_cash=142825.43,
            cash_buffer=21423.81,
        )

        # Try to approve non-existent trade
        success = manager.approve_trade(request.request_id, 10)
        assert success is False

        # Try negative index
        success = manager.reject_trade(request.request_id, -1)
        assert success is False

    def test_nonexistent_request(self, manager):
        """Test operations on non-existent request."""
        fake_id = "nonexistent-request-id"

        success = manager.approve_trade(fake_id, 0)
        assert success is False

        success = manager.reject_trade(fake_id, 0)
        assert success is False

        approved_trades = manager.get_approved_trades(fake_id)
        assert len(approved_trades) == 0

    def test_approve_all_trades(self, manager, sample_trades):
        """Test approving all trades."""
        request = manager.create_approval_request(
            trades=sample_trades,
            total_investment=21219.64,
            available_cash=142825.43,
            cash_buffer=21423.81,
        )

        # Approve all trades
        for i in range(len(sample_trades)):
            success = manager.approve_trade(request.request_id, i)
            assert success is True

        # Verify all approved
        approved_trades = manager.get_approved_trades(request.request_id)
        assert len(approved_trades) == len(sample_trades)

    def test_reject_all_trades(self, manager, sample_trades):
        """Test rejecting all trades."""
        request = manager.create_approval_request(
            trades=sample_trades,
            total_investment=21219.64,
            available_cash=142825.43,
            cash_buffer=21423.81,
        )

        # Reject all trades
        for i in range(len(sample_trades)):
            success = manager.reject_trade(request.request_id, i)
            assert success is True

        # Verify none approved
        approved_trades = manager.get_approved_trades(request.request_id)
        assert len(approved_trades) == 0

    def test_change_approval_status(self, manager, sample_trades):
        """Test changing a trade from approved to rejected and vice versa."""
        request = manager.create_approval_request(
            trades=sample_trades,
            total_investment=21219.64,
            available_cash=142825.43,
            cash_buffer=21423.81,
        )

        # Approve trade 0
        manager.approve_trade(request.request_id, 0)
        updated_request = manager.get_request(request.request_id)
        assert updated_request.trades[0].approved is True

        # Change to rejected
        manager.reject_trade(request.request_id, 0)
        updated_request = manager.get_request(request.request_id)
        assert updated_request.trades[0].approved is False

        # Change back to approved
        manager.approve_trade(request.request_id, 0)
        updated_request = manager.get_request(request.request_id)
        assert updated_request.trades[0].approved is True


def run_manual_tests():
    """Run manual tests without pytest."""
    print("=" * 80)
    print("SELECTIVE APPROVAL SYSTEM TESTS")
    print("=" * 80)
    print()

    manager = TradeApprovalManager()

    sample_trades = [
        {
            "symbol": "GOOGL",
            "quantity": 15.2,
            "estimated_price": 296.72,
            "estimated_value": 4510.14,
            "allocation_pct": 7.8,
        },
        {
            "symbol": "UBER",
            "quantity": 45.3,
            "estimated_price": 128.50,
            "estimated_value": 5821.05,
            "allocation_pct": 6.5,
        },
        {
            "symbol": "AAPL",
            "quantity": 25.0,
            "estimated_price": 185.50,
            "estimated_value": 4637.50,
            "allocation_pct": 5.2,
        },
        {
            "symbol": "MSFT",
            "quantity": 12.5,
            "estimated_price": 378.90,
            "estimated_value": 4736.25,
            "allocation_pct": 5.0,
        },
        {
            "symbol": "AMZN",
            "quantity": 8.5,
            "estimated_price": 178.20,
            "estimated_value": 1514.70,
            "allocation_pct": 1.7,
        },
    ]

    # Test 1: Create request
    print("Test 1: Creating approval request...")
    request = manager.create_approval_request(
        trades=sample_trades,
        total_investment=21219.64,
        available_cash=142825.43,
        cash_buffer=21423.81,
    )
    print(f"✓ Created request {request.request_id}")
    print(f"  - {len(request.trades)} trades")
    print(f"  - All trades pending: {all(t.approved is None for t in request.trades)}")
    print()

    # Test 2: Approve individual trades
    print("Test 2: Approving individual trades...")
    manager.approve_trade(request.request_id, 0)  # GOOGL
    manager.approve_trade(request.request_id, 2)  # AAPL
    manager.approve_trade(request.request_id, 3)  # MSFT
    print("✓ Approved GOOGL, AAPL, MSFT")
    print()

    # Test 3: Reject individual trades
    print("Test 3: Rejecting individual trades...")
    manager.reject_trade(request.request_id, 1)  # UBER
    manager.reject_trade(request.request_id, 4)  # AMZN
    print("✓ Rejected UBER, AMZN")
    print()

    # Test 4: Get approved trades
    print("Test 4: Retrieving approved trades...")
    approved_trades = manager.get_approved_trades(request.request_id)
    print(f"✓ Found {len(approved_trades)} approved trades:")
    for trade in approved_trades:
        print(
            f"  - {trade.symbol}: {trade.quantity} shares @ ${trade.estimated_price:.2f} = ${trade.estimated_value:,.2f}"
        )
    total_value = sum(t.estimated_value for t in approved_trades)
    print(f"  - Total value: ${total_value:,.2f}")
    print()

    # Test 5: Verify status
    print("Test 5: Verifying trade status...")
    updated_request = manager.get_request(request.request_id)
    print("Trade status:")
    for i, trade in enumerate(updated_request.trades):
        status = (
            "✅ APPROVED"
            if trade.approved is True
            else "❌ REJECTED"
            if trade.approved is False
            else "⏳ PENDING"
        )
        print(f"  {i}. {trade.symbol:6s} - {status}")
    print()

    print("=" * 80)
    print("✅ ALL TESTS PASSED!")
    print("=" * 80)
    print()
    print("Summary:")
    print(f"  - Approved: {sum(1 for t in updated_request.trades if t.approved is True)}")
    print(f"  - Rejected: {sum(1 for t in updated_request.trades if t.approved is False)}")
    print(f"  - Pending:  {sum(1 for t in updated_request.trades if t.approved is None)}")
    print()


if __name__ == "__main__":
    # Run manual tests if executed directly
    run_manual_tests()
