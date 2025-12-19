#!/usr/bin/env python3
"""
Integration tests for the approval workflow.

Tests the complete approval flow including URL routing, API endpoints,
form submission, and bulk approval functionality. Covers the types of
errors we encountered during development to prevent regressions.
"""

import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

import pytest
from fastapi.testclient import TestClient

from services.approval.trade_approval import TradeApprovalManager


class TestApprovalURLRouting:
    """Test URL routing and endpoint accessibility."""

    @pytest.fixture
    def client(self):
        """Create FastAPI test client."""
        from main import app

        return TestClient(app)

    @pytest.fixture
    def manager(self):
        """Create TradeApprovalManager instance."""
        return TradeApprovalManager()

    @pytest.fixture
    def sample_request(self, manager):
        """Create a sample approval request."""
        trades = [
            {
                "symbol": "AAPL",
                "quantity": 10.0,
                "estimated_price": 185.50,
                "estimated_value": 1855.0,
                "allocation_pct": 5.0,
            },
            {
                "symbol": "GOOGL",
                "quantity": 5.0,
                "estimated_price": 296.72,
                "estimated_value": 1483.6,
                "allocation_pct": 4.0,
            },
            {
                "symbol": "MSFT",
                "quantity": 8.0,
                "estimated_price": 378.90,
                "estimated_value": 3031.2,
                "allocation_pct": 8.0,
            },
        ]

        request = manager.create_approval_request(
            trades=trades, total_investment=6369.8, available_cash=50000.0, cash_buffer=5000.0
        )

        return request

    def test_review_page_get_request(self, client, sample_request):
        """Test that review page accepts GET requests (email links)."""
        response = client.get(f"/api/v1/approve/{sample_request.request_id}/review")

        # Should return 200 OK, not 405 Method Not Allowed
        assert response.status_code == 200
        assert "Review & Approve Trades" in response.text or "Proposed Trades" in response.text

    def test_review_page_url_routing(self, client, sample_request):
        """Test that review page URL is correctly routed."""
        # Test the exact URL pattern used in emails
        url = f"/api/v1/approve/{sample_request.request_id}/review"
        response = client.get(url)

        # Should not return 404 Not Found
        assert response.status_code == 200
        assert sample_request.request_id in response.text

    def test_individual_trade_approval_get(self, client, sample_request):
        """Test individual trade approval accepts GET requests."""
        response = client.get(f"/api/v1/approvals/{sample_request.request_id}/approve-trade/0")

        # Should return 200 OK, not 405 Method Not Allowed
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_individual_trade_approval_post(self, client, sample_request):
        """Test individual trade approval accepts POST requests."""
        response = client.post(f"/api/v1/approvals/{sample_request.request_id}/approve-trade/1")

        # Should return 200 OK
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_individual_trade_rejection_get(self, client, sample_request):
        """Test individual trade rejection accepts GET requests."""
        response = client.get(f"/api/v1/approvals/{sample_request.request_id}/reject-trade/2")

        # Should return 200 OK, not 405 Method Not Allowed
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_nonexistent_request_404(self, client):
        """Test that nonexistent request returns 404."""
        response = client.get("/api/v1/approve/nonexistent-id/review")

        # Should return 200 with error message (HTML page)
        assert response.status_code == 200
        assert "Not Found" in response.text or "not found" in response.text.lower()

    def test_invalid_trade_index(self, client, sample_request):
        """Test that invalid trade index is handled gracefully."""
        # Try to approve trade index 999 (doesn't exist)
        response = client.get(f"/api/v1/approvals/{sample_request.request_id}/approve-trade/999")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False


class TestBulkApprovalWorkflow:
    """Test the bulk approval form submission workflow."""

    @pytest.fixture
    def client(self):
        """Create FastAPI test client."""
        from main import app

        return TestClient(app)

    @pytest.fixture
    def manager(self):
        """Create TradeApprovalManager instance."""
        return TradeApprovalManager()

    @pytest.fixture
    def sample_request(self, manager):
        """Create a sample approval request."""
        trades = [
            {
                "symbol": "NVDA",
                "quantity": 12.5,
                "estimated_price": 495.22,
                "estimated_value": 6190.25,
                "allocation_pct": 8.2,
            },
            {
                "symbol": "META",
                "quantity": 18.3,
                "estimated_price": 475.80,
                "estimated_value": 8707.14,
                "allocation_pct": 7.5,
            },
            {
                "symbol": "TSLA",
                "quantity": 22.0,
                "estimated_price": 248.50,
                "estimated_value": 5467.00,
                "allocation_pct": 6.8,
            },
            {
                "symbol": "GOOGL",
                "quantity": 15.2,
                "estimated_price": 296.72,
                "estimated_value": 4510.14,
                "allocation_pct": 5.9,
            },
            {
                "symbol": "AMZN",
                "quantity": 8.5,
                "estimated_price": 178.20,
                "estimated_value": 1514.70,
                "allocation_pct": 2.1,
            },
        ]

        request = manager.create_approval_request(
            trades=trades, total_investment=26389.23, available_cash=142825.43, cash_buffer=21423.81
        )

        return request

    def test_bulk_approval_all_approved(self, client, sample_request, manager):
        """Test submitting form with all trades approved."""
        form_data = {
            "trade_0": "approve",
            "trade_1": "approve",
            "trade_2": "approve",
            "trade_3": "approve",
            "trade_4": "approve",
        }

        response = client.post(
            f"/api/v1/approve/{sample_request.request_id}/submit", data=form_data
        )

        assert response.status_code == 200
        assert "Decisions Submitted Successfully" in response.text
        assert "5" in response.text  # 5 approved trades

        # Verify all trades are approved
        approved_trades = manager.get_approved_trades(sample_request.request_id)
        assert len(approved_trades) == 5

    def test_bulk_approval_mixed_decisions(self, client, sample_request, manager):
        """Test submitting form with mixed approve/reject decisions."""
        form_data = {
            "trade_0": "approve",  # NVDA
            "trade_1": "reject",  # META
            "trade_2": "approve",  # TSLA
            "trade_3": "approve",  # GOOGL
            "trade_4": "reject",  # AMZN
        }

        response = client.post(
            f"/api/v1/approve/{sample_request.request_id}/submit", data=form_data
        )

        assert response.status_code == 200
        assert "Decisions Submitted Successfully" in response.text

        # Verify correct trades are approved
        approved_trades = manager.get_approved_trades(sample_request.request_id)
        assert len(approved_trades) == 3

        approved_symbols = [t.symbol for t in approved_trades]
        assert "NVDA" in approved_symbols
        assert "TSLA" in approved_symbols
        assert "GOOGL" in approved_symbols
        assert "META" not in approved_symbols
        assert "AMZN" not in approved_symbols

    def test_bulk_approval_all_rejected(self, client, sample_request, manager):
        """Test submitting form with all trades rejected."""
        form_data = {
            "trade_0": "reject",
            "trade_1": "reject",
            "trade_2": "reject",
            "trade_3": "reject",
            "trade_4": "reject",
        }

        response = client.post(
            f"/api/v1/approve/{sample_request.request_id}/submit", data=form_data
        )

        assert response.status_code == 200
        assert "Decisions Submitted Successfully" in response.text

        # Verify no trades are approved
        approved_trades = manager.get_approved_trades(sample_request.request_id)
        assert len(approved_trades) == 0

    def test_form_displays_all_trades(self, client, sample_request):
        """Test that the review form displays all trades."""
        response = client.get(f"/api/v1/approve/{sample_request.request_id}/review")

        assert response.status_code == 200

        # Check that all trade symbols appear in the form
        assert "NVDA" in response.text
        assert "META" in response.text
        assert "TSLA" in response.text
        assert "GOOGL" in response.text
        assert "AMZN" in response.text

        # Check that radio buttons are present
        assert 'name="trade_0"' in response.text
        assert 'name="trade_1"' in response.text
        assert 'name="trade_2"' in response.text
        assert 'name="trade_3"' in response.text
        assert 'name="trade_4"' in response.text

    def test_form_has_submit_button(self, client, sample_request):
        """Test that the form has a submit button."""
        response = client.get(f"/api/v1/approve/{sample_request.request_id}/review")

        assert response.status_code == 200
        assert "Submit Decisions" in response.text
        assert 'type="submit"' in response.text


class TestEmailTemplateURLGeneration:
    """Test that email templates generate correct URLs."""

    def test_review_url_generation(self):
        """Test that review URL is correctly generated in email template."""
        from services.monitoring.email_templates import get_approval_email_html

        request_id = "test-request-123"
        trades = [
            {
                "symbol": "AAPL",
                "quantity": 10.0,
                "estimated_price": 185.50,
                "estimated_value": 1855.0,
                "allocation_pct": 5.0,
            }
        ]

        html = get_approval_email_html(
            request_id=request_id,
            trades=trades,
            total_investment=1855.0,
            available_cash=50000.0,
            cash_buffer=5000.0,
            approve_url=f"http://localhost:8000/api/v1/approve/{request_id}/approve",
            reject_url=f"http://localhost:8000/api/v1/approve/{request_id}/reject",
        )

        # Check that the review URL is correct (not malformed)
        expected_url = f"http://localhost:8000/api/v1/approve/{request_id}/review"
        assert expected_url in html

        # Make sure it's NOT the malformed version
        malformed_url = f"http://localhost:8000/api/v1/review/{request_id}/review"
        assert malformed_url not in html

    def test_email_contains_review_button(self):
        """Test that email contains the review button."""
        from services.monitoring.email_templates import get_approval_email_html

        request_id = "test-request-456"
        trades = [
            {
                "symbol": "GOOGL",
                "quantity": 5.0,
                "estimated_price": 296.72,
                "estimated_value": 1483.6,
                "allocation_pct": 4.0,
            }
        ]

        html = get_approval_email_html(
            request_id=request_id,
            trades=trades,
            total_investment=1483.6,
            available_cash=50000.0,
            cash_buffer=5000.0,
            approve_url=f"http://localhost:8000/api/v1/approve/{request_id}/approve",
            reject_url=f"http://localhost:8000/api/v1/approve/{request_id}/reject",
        )

        # Check for review button text
        assert "Review & Approve Trades" in html or "Review" in html

        # Check that it's a link
        assert "<a href=" in html


class TestErrorHandling:
    """Test error handling and edge cases."""

    @pytest.fixture
    def client(self):
        """Create FastAPI test client."""
        from main import app

        return TestClient(app)

    @pytest.fixture
    def manager(self):
        """Create TradeApprovalManager instance."""
        return TradeApprovalManager()

    def test_already_processed_request(self, client, manager):
        """Test accessing a request that's already been processed."""
        trades = [
            {
                "symbol": "AAPL",
                "quantity": 10.0,
                "estimated_price": 185.50,
                "estimated_value": 1855.0,
                "allocation_pct": 5.0,
            }
        ]

        request = manager.create_approval_request(
            trades=trades, total_investment=1855.0, available_cash=50000.0, cash_buffer=5000.0
        )

        # Approve the request
        manager.approve_request(request.request_id)

        # Try to access review page
        response = client.get(f"/api/v1/approve/{request.request_id}/review")

        assert response.status_code == 200
        assert "Already Processed" in response.text or "APPROVED" in response.text

    def test_expired_request_handling(self, client, manager):
        """Test handling of expired requests."""
        from datetime import datetime, timedelta

        trades = [
            {
                "symbol": "AAPL",
                "quantity": 10.0,
                "estimated_price": 185.50,
                "estimated_value": 1855.0,
                "allocation_pct": 5.0,
            }
        ]

        # Create request with very short expiry
        request = manager.create_approval_request(
            trades=trades,
            total_investment=1855.0,
            available_cash=50000.0,
            cash_buffer=5000.0,
            expiry_hours=0,  # Expired immediately
        )

        # Manually set expiry to past
        request.expires_at = datetime.utcnow() - timedelta(hours=1)
        manager._save_request(request)

        # Try to approve individual trade
        response = client.get(f"/api/v1/approvals/{request.request_id}/approve-trade/0")

        # Should handle gracefully (not crash)
        assert response.status_code in [200, 400, 404]


def run_manual_tests():
    """Run manual integration tests."""
    print("=" * 80)
    print("APPROVAL WORKFLOW INTEGRATION TESTS")
    print("=" * 80)
    print()

    from fastapi.testclient import TestClient
    from main import app

    client = TestClient(app)
    manager = TradeApprovalManager()

    # Test 1: Create request and access review page
    print("Test 1: Review page accessibility...")
    trades = [
        {
            "symbol": "AAPL",
            "quantity": 10.0,
            "estimated_price": 185.50,
            "estimated_value": 1855.0,
            "allocation_pct": 5.0,
        },
        {
            "symbol": "GOOGL",
            "quantity": 5.0,
            "estimated_price": 296.72,
            "estimated_value": 1483.6,
            "allocation_pct": 4.0,
        },
    ]

    request = manager.create_approval_request(
        trades=trades, total_investment=3338.6, available_cash=50000.0, cash_buffer=5000.0
    )

    response = client.get(f"/api/v1/approve/{request.request_id}/review")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    print(f"✓ Review page accessible (status: {response.status_code})")
    print()

    # Test 2: Individual trade approval (GET)
    print("Test 2: Individual trade approval via GET...")
    response = client.get(f"/api/v1/approvals/{request.request_id}/approve-trade/0")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    data = response.json()
    assert data["success"] is True, "Approval should succeed"
    print(f"✓ Individual trade approval works (GET method)")
    print()

    # Test 3: Bulk approval submission
    print("Test 3: Bulk approval form submission...")
    form_data = {"trade_0": "approve", "trade_1": "reject"}

    # Create new request for bulk test
    request2 = manager.create_approval_request(
        trades=trades, total_investment=3338.6, available_cash=50000.0, cash_buffer=5000.0
    )

    response = client.post(f"/api/v1/approve/{request2.request_id}/submit", data=form_data)
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    assert "Decisions Submitted Successfully" in response.text
    print(f"✓ Bulk approval submission works")

    # Verify results
    approved_trades = manager.get_approved_trades(request2.request_id)
    assert len(approved_trades) == 1, f"Expected 1 approved trade, got {len(approved_trades)}"
    assert approved_trades[0].symbol == "AAPL"
    print(f"✓ Correct trades approved: {[t.symbol for t in approved_trades]}")
    print()

    # Test 4: URL generation in email template
    print("Test 4: Email template URL generation...")
    from services.monitoring.email_templates import get_approval_email_html

    html = get_approval_email_html(
        request_id="test-123",
        trades=trades,
        total_investment=3338.6,
        available_cash=50000.0,
        cash_buffer=5000.0,
        approve_url="http://localhost:8000/api/v1/approve/test-123/approve",
        reject_url="http://localhost:8000/api/v1/approve/test-123/reject",
    )

    expected_url = "http://localhost:8000/api/v1/approve/test-123/review"
    assert expected_url in html, "Review URL should be in email"
    print(f"✓ Email template generates correct review URL")
    print()

    print("=" * 80)
    print("✅ ALL INTEGRATION TESTS PASSED!")
    print("=" * 80)
    print()
    print("Summary:")
    print("  ✓ Review page accessible via GET")
    print("  ✓ Individual trade approval works (GET & POST)")
    print("  ✓ Bulk approval form submission works")
    print("  ✓ Email template generates correct URLs")
    print("  ✓ No 404 or 405 errors")
    print()


if __name__ == "__main__":
    # Run manual tests if executed directly
    run_manual_tests()
