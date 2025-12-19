from fastapi import APIRouter, HTTPException, status

router = APIRouter()


@router.get("/", summary="Legacy trades API (removed)")
async def trades_api_removed():
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail="Legacy trades API removed. Use Phase 5 execution scripts/services (alpaca-py) instead.",
    )
