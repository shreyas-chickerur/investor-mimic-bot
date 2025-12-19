"""Plaid API schemas."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class PlaidLinkTokenRequest(BaseModel):
    """Request model for creating a Plaid link token."""

    user_id: str = Field(..., description="Unique identifier for the user")


class PlaidLinkTokenResponse(BaseModel):
    """Response model for Plaid link token creation."""

    link_token: str
    expiration: datetime
    request_id: str


class PlaidAccessTokenRequest(BaseModel):
    """Request model for exchanging a public token for an access token."""

    public_token: str
    metadata: Optional[Dict[str, Any]] = None


class PlaidAccessTokenResponse(BaseModel):
    """Response model for Plaid access token exchange."""

    access_token: str
    item_id: str
    request_id: str


class PaycheckEventResponse(BaseModel):
    """Response model for detected paycheck events."""

    amount: float = Field(..., description="The amount of the paycheck")
    date: datetime = Field(..., description="The date of the paycheck deposit")
    account_id: str = Field(..., description="Plaid account ID")
    transaction_id: str = Field(..., description="Plaid transaction ID")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score (0.0 to 1.0)")


class PayrollDetectionRequest(BaseModel):
    """Request model for detecting payroll deposits."""

    access_token: str = Field(..., description="Plaid access token")
    days: int = Field(30, description="Number of days of transactions to analyze")


class PayrollDetectionResponse(BaseModel):
    """Response model for payroll detection."""

    paychecks: List[PaycheckEventResponse]
    total_detected: int
    analyzed_days: int
