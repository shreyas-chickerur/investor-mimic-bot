"""
Trade Approval System

Manages approval requests for trades, allowing manual confirmation before execution.
"""

import logging
import json
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
from enum import Enum

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ApprovalStatus(str, Enum):
    """Status of an approval request."""
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class TradeProposal(BaseModel):
    """A proposed trade for approval."""
    symbol: str
    quantity: float
    estimated_price: Optional[float] = None
    estimated_value: Optional[float] = None
    allocation_pct: Optional[float] = None
    approved: Optional[bool] = None  # None=pending, True=approved, False=rejected


class ApprovalRequest(BaseModel):
    """An approval request for a set of trades."""
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime
    status: ApprovalStatus = ApprovalStatus.PENDING
    
    # Trade details
    total_investment: float
    cash_buffer: float
    available_cash: float
    trades: List[TradeProposal]
    
    # Strategy details
    strategy_name: str = "Conviction Strategy"
    max_positions: int = 10
    
    # Approval details
    approved_at: Optional[datetime] = None
    approved_by: Optional[str] = None
    notes: Optional[str] = None


class TradeApprovalManager:
    """
    Manages trade approval requests.
    
    Example usage:
        manager = TradeApprovalManager()
        
        # Create approval request
        request = manager.create_approval_request(
            trades=[...],
            total_investment=5000.0,
            available_cash=10000.0
        )
        
        # Send email notification
        await manager.send_approval_email(request)
        
        # Check status later
        if manager.is_approved(request.request_id):
            # Execute trades
            pass
    """
    
    def __init__(self, storage_dir: str = "data/approvals"):
        """
        Initialize the approval manager.
        
        Args:
            storage_dir: Directory to store approval requests
        """
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
    
    def create_approval_request(
        self,
        trades: List[Dict],
        total_investment: float,
        available_cash: float,
        cash_buffer: float = 0.0,
        expiry_hours: int = 24
    ) -> ApprovalRequest:
        """
        Create a new approval request.
        
        Args:
            trades: List of proposed trades
            total_investment: Total amount to invest
            available_cash: Available cash in account
            cash_buffer: Cash buffer amount
            expiry_hours: Hours until request expires
            
        Returns:
            ApprovalRequest object
        """
        # Convert trades to TradeProposal objects
        trade_proposals = []
        for trade in trades:
            proposal = TradeProposal(
                symbol=trade.get("symbol"),
                quantity=trade.get("quantity", 0),
                estimated_price=trade.get("estimated_price"),
                estimated_value=trade.get("estimated_value"),
                allocation_pct=trade.get("allocation_pct")
            )
            trade_proposals.append(proposal)
        
        # Create request
        request = ApprovalRequest(
            expires_at=datetime.utcnow() + timedelta(hours=expiry_hours),
            total_investment=total_investment,
            cash_buffer=cash_buffer,
            available_cash=available_cash,
            trades=trade_proposals
        )
        
        # Save to disk
        self._save_request(request)
        
        logger.info(f"Created approval request {request.request_id}")
        return request
    
    def get_request(self, request_id: str) -> Optional[ApprovalRequest]:
        """Get an approval request by ID."""
        request_file = self.storage_dir / f"{request_id}.json"
        
        if not request_file.exists():
            return None
        
        try:
            data = json.loads(request_file.read_text())
            return ApprovalRequest(**data)
        except Exception as e:
            logger.error(f"Failed to load request {request_id}: {e}")
            return None
    
    def approve_request(
        self,
        request_id: str,
        approved_by: str = "user",
        notes: Optional[str] = None
    ) -> bool:
        """
        Approve a request.
        
        Args:
            request_id: Request ID to approve
            approved_by: Who approved it
            notes: Optional approval notes
            
        Returns:
            True if approved successfully
        """
        request = self.get_request(request_id)
        
        if not request:
            logger.error(f"Request {request_id} not found")
            return False
        
        if request.status != ApprovalStatus.PENDING:
            logger.warning(f"Request {request_id} is not pending (status: {request.status})")
            return False
        
        if datetime.utcnow() > request.expires_at:
            logger.warning(f"Request {request_id} has expired")
            request.status = ApprovalStatus.EXPIRED
            self._save_request(request)
            return False
        
        # Approve the request
        request.status = ApprovalStatus.APPROVED
        request.approved_at = datetime.utcnow()
        request.approved_by = approved_by
        request.notes = notes
        
        self._save_request(request)
        logger.info(f"Approved request {request_id}")
        
        return True
    
    def reject_request(
        self,
        request_id: str,
        notes: Optional[str] = None
    ) -> bool:
        """
        Reject a request.
        
        Args:
            request_id: Request ID to reject
            notes: Optional rejection notes
            
        Returns:
            True if rejected successfully
        """
        request = self.get_request(request_id)
        
        if not request:
            logger.error(f"Request {request_id} not found")
            return False
        
        if request.status != ApprovalStatus.PENDING:
            logger.warning(f"Request {request_id} is not pending")
            return False
        
        # Reject the request
        request.status = ApprovalStatus.REJECTED
        request.notes = notes
        
        self._save_request(request)
        logger.info(f"Rejected request {request_id}")
        
        return True
    
    def is_approved(self, request_id: str) -> bool:
        """Check if a request is approved."""
        request = self.get_request(request_id)
        
        if not request:
            return False
        
        return request.status == ApprovalStatus.APPROVED
    
    def is_pending(self, request_id: str) -> bool:
        """Check if a request is still pending."""
        request = self.get_request(request_id)
        
        if not request:
            return False
        
        if request.status != ApprovalStatus.PENDING:
            return False
        
        # Check if expired
        if datetime.utcnow() > request.expires_at:
            request.status = ApprovalStatus.EXPIRED
            self._save_request(request)
            return False
        
        return True
    
    def approve_trade(self, request_id: str, trade_index: int) -> bool:
        """Approve a specific trade within a request."""
        request = self.get_request(request_id)
        
        if not request:
            logger.error(f"Request {request_id} not found")
            return False
        
        if request.status != ApprovalStatus.PENDING:
            logger.warning(f"Request {request_id} is not pending")
            return False
        
        if trade_index < 0 or trade_index >= len(request.trades):
            logger.error(f"Invalid trade index {trade_index}")
            return False
        
        # Approve the specific trade
        request.trades[trade_index].approved = True
        self._save_request(request)
        logger.info(f"Approved trade {trade_index} in request {request_id}")
        
        return True
    
    def reject_trade(self, request_id: str, trade_index: int) -> bool:
        """Reject a specific trade within a request."""
        request = self.get_request(request_id)
        
        if not request:
            logger.error(f"Request {request_id} not found")
            return False
        
        if request.status != ApprovalStatus.PENDING:
            logger.warning(f"Request {request_id} is not pending")
            return False
        
        if trade_index < 0 or trade_index >= len(request.trades):
            logger.error(f"Invalid trade index {trade_index}")
            return False
        
        # Reject the specific trade
        request.trades[trade_index].approved = False
        self._save_request(request)
        logger.info(f"Rejected trade {trade_index} in request {request_id}")
        
        return True
    
    def get_approved_trades(self, request_id: str) -> List[TradeProposal]:
        """Get list of approved trades from a request."""
        request = self.get_request(request_id)
        
        if not request:
            return []
        
        return [trade for trade in request.trades if trade.approved is True]
    
    def get_pending_requests(self) -> List[ApprovalRequest]:
        """Get all pending approval requests."""
        pending = []
        
        for request_file in self.storage_dir.glob("*.json"):
            try:
                data = json.loads(request_file.read_text())
                request = ApprovalRequest(**data)
                
                if request.status == ApprovalStatus.PENDING:
                    # Check if expired
                    if datetime.utcnow() > request.expires_at:
                        request.status = ApprovalStatus.EXPIRED
                        self._save_request(request)
                    else:
                        pending.append(request)
            except Exception as e:
                logger.error(f"Failed to load {request_file}: {e}")
        
        return pending
    
    def _save_request(self, request: ApprovalRequest):
        """Save a request to disk."""
        request_file = self.storage_dir / f"{request.request_id}.json"
        request_file.write_text(request.model_dump_json(indent=2))
    
    async def send_approval_email(self, request: ApprovalRequest, recipient_email: str) -> bool:
        """
        Send an approval request email.
        
        Args:
            request: Approval request to send
            recipient_email: Email address to send to
            
        Returns:
            True if email sent successfully
        """
        try:
            from config.settings import get_notification_config
            from services.monitoring.notification_manager import NotificationManager
            
            config = get_notification_config()
            if not config or not config.email_config:
                logger.warning("Email not configured, cannot send approval request")
                return False
            
            manager = NotificationManager(config)
            
            # Build email content
            subject = f"Trade Approval Required: ${request.total_investment:,.2f}"
            
            # Build trade summary
            trade_summary = "\n".join([
                f"  • {t.symbol}: {t.quantity} shares @ ${t.estimated_price:.2f} = ${t.estimated_value:,.2f}"
                for t in request.trades
            ])
            
            # Get approval URL (assumes API is running on localhost:8000)
            approve_url = f"http://localhost:8000/api/v1/approvals/{request.request_id}/approve"
            reject_url = f"http://localhost:8000/api/v1/approvals/{request.request_id}/reject"
            
            message = f"""
Investment Approval Required

The bot has identified an investment opportunity and is requesting your approval.

SUMMARY:
--------
Total Investment: ${request.total_investment:,.2f}
Available Cash: ${request.available_cash:,.2f}
Cash Buffer: ${request.cash_buffer:,.2f}
Number of Trades: {len(request.trades)}
Strategy: {request.strategy_name}

PROPOSED TRADES:
---------------
{trade_summary}

APPROVAL:
---------
This request will expire at: {request.expires_at.strftime('%Y-%m-%d %H:%M:%S UTC')}

To approve these trades, click:
{approve_url}

To reject these trades, click:
{reject_url}

Or respond to this email with "APPROVE" or "REJECT".

Request ID: {request.request_id}
"""
            
            # Send email
            success = manager.email_notifier.send_alert(
                to_emails=[recipient_email],
                subject=subject,
                message=message,
                level="INFO"
            )
            
            if success:
                logger.info(f"Sent approval email for request {request.request_id}")
            else:
                logger.error(f"Failed to send approval email for request {request.request_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to send approval email: {e}")
            return False
