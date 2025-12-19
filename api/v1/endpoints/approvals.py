"""
API endpoints for trade approval management.
"""

from typing import Optional, Dict
from fastapi import APIRouter, HTTPException, Form
from pydantic import BaseModel

from services.approval.trade_approval import TradeApprovalManager, ApprovalRequest

router = APIRouter()

# Initialize approval manager
approval_manager = TradeApprovalManager()


class ApprovalResponse(BaseModel):
    """Response for approval actions."""
    success: bool
    message: str
    request: Optional[ApprovalRequest] = None


@router.get("/{request_id}")
async def get_approval_request(request_id: str) -> ApprovalRequest:
    """
    Get an approval request by ID.
    
    Args:
        request_id: The approval request ID
        
    Returns:
        ApprovalRequest details
    """
    request = approval_manager.get_request(request_id)
    
    if not request:
        raise HTTPException(status_code=404, detail="Approval request not found")
    
    return request


@router.post("/{request_id}/approve")
async def approve_request(
    request_id: str,
    notes: Optional[str] = None
) -> ApprovalResponse:
    """
    Approve a trade request.
    
    Args:
        request_id: The approval request ID
        notes: Optional approval notes
        
    Returns:
        ApprovalResponse with success status
    """
    success = approval_manager.approve_request(
        request_id=request_id,
        approved_by="web",
        notes=notes
    )
    
    if not success:
        request = approval_manager.get_request(request_id)
        if not request:
            raise HTTPException(status_code=404, detail="Approval request not found")
        
        return ApprovalResponse(
            success=False,
            message=f"Could not approve request (status: {request.status})",
            request=request
        )
    
    request = approval_manager.get_request(request_id)
    
    return ApprovalResponse(
        success=True,
        message="Trade request approved successfully",
        request=request
    )


@router.post("/{request_id}/reject")
async def reject_request(
    request_id: str,
    notes: Optional[str] = None
) -> ApprovalResponse:
    """
    Reject a trade request.
    
    Args:
        request_id: The approval request ID
        notes: Optional rejection notes
        
    Returns:
        ApprovalResponse with success status
    """
    success = approval_manager.reject_request(
        request_id=request_id,
        notes=notes
    )
    
    if not success:
        request = approval_manager.get_request(request_id)
        if not request:
            raise HTTPException(status_code=404, detail="Approval request not found")
        
        return ApprovalResponse(
            success=False,
            message=f"Could not reject request (status: {request.status})",
            request=request
        )
    
    request = approval_manager.get_request(request_id)
    
    return ApprovalResponse(
        success=True,
        message="Trade request rejected",
        request=request
    )


@router.api_route("/{request_id}/approve-trade/{trade_index}", methods=["GET", "POST"])
async def approve_trade(
    request_id: str,
    trade_index: int
) -> ApprovalResponse:
    """
    Approve a specific trade within a request.
    
    Args:
        request_id: The approval request ID
        trade_index: Index of the trade to approve
        
    Returns:
        ApprovalResponse with success status
    """
    success = approval_manager.approve_trade(
        request_id=request_id,
        trade_index=trade_index
    )
    
    if not success:
        request = approval_manager.get_request(request_id)
        if not request:
            raise HTTPException(status_code=404, detail="Approval request not found")
        
        return ApprovalResponse(
            success=False,
            message=f"Could not approve trade {trade_index}",
            request=request
        )
    
    request = approval_manager.get_request(request_id)
    
    return ApprovalResponse(
        success=True,
        message=f"Trade {trade_index} approved successfully",
        request=request
    )


@router.api_route("/{request_id}/reject-trade/{trade_index}", methods=["GET", "POST"])
async def reject_trade(
    request_id: str,
    trade_index: int
) -> ApprovalResponse:
    """
    Reject a specific trade within a request.
    
    Args:
        request_id: The approval request ID
        trade_index: Index of the trade to reject
        
    Returns:
        ApprovalResponse with success status
    """
    success = approval_manager.reject_trade(
        request_id=request_id,
        trade_index=trade_index
    )
    
    if not success:
        request = approval_manager.get_request(request_id)
        if not request:
            raise HTTPException(status_code=404, detail="Approval request not found")
        
        return ApprovalResponse(
            success=False,
            message=f"Could not reject trade {trade_index}",
            request=request
        )
    
    request = approval_manager.get_request(request_id)
    
    return ApprovalResponse(
        success=True,
        message=f"Trade {trade_index} rejected successfully",
        request=request
    )


@router.post("/{request_id}/submit-bulk")
async def submit_bulk_approval(
    request_id: str,
    decisions: Dict[str, str]
) -> ApprovalResponse:
    """
    Submit bulk approval/rejection decisions for all trades.
    
    Args:
        request_id: The approval request ID
        decisions: Dictionary mapping trade indices to 'approve' or 'reject'
        
    Returns:
        ApprovalResponse with success status
    """
    request = approval_manager.get_request(request_id)
    
    if not request:
        raise HTTPException(status_code=404, detail="Approval request not found")
    
    if request.status != ApprovalStatus.PENDING:
        return ApprovalResponse(
            success=False,
            message=f"Request is not pending (status: {request.status})",
            request=request
        )
    
    # Process each decision
    approved_count = 0
    rejected_count = 0
    
    for trade_key, decision in decisions.items():
        if not trade_key.startswith('trade_'):
            continue
            
        try:
            trade_index = int(trade_key.replace('trade_', ''))
            
            if decision == 'approve':
                approval_manager.approve_trade(request_id, trade_index)
                approved_count += 1
            elif decision == 'reject':
                approval_manager.reject_trade(request_id, trade_index)
                rejected_count += 1
        except (ValueError, IndexError):
            continue
    
    # Get updated request
    updated_request = approval_manager.get_request(request_id)
    
    return ApprovalResponse(
        success=True,
        message=f"Processed {approved_count} approvals and {rejected_count} rejections",
        request=updated_request
    )


@router.get("/")
async def list_pending_requests():
    """
    List all pending approval requests.
    
    Returns:
        List of pending ApprovalRequests
    """
    pending = approval_manager.get_pending_requests()
    return {"pending_requests": pending, "count": len(pending)}
