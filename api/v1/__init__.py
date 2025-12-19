from fastapi import APIRouter

api_router = APIRouter(prefix="/api/v1")

# Import routers
from .endpoints import approvals as approvals_router
from .endpoints import approval_page as approval_page_router

# Include routers
api_router.include_router(approvals_router.router, prefix="/approvals", tags=["approvals"])
api_router.include_router(approval_page_router.router, prefix="/approve", tags=["approval-pages"])
