from fastapi import APIRouter, Depends, HTTPException, status

from .. import schemas
from ..config import Settings, get_settings
from ..providers.base import get_fact_checker


router = APIRouter(tags=["fact-check"])


@router.post("/fact/check", response_model=schemas.FactCheckResponse)
async def check_fact(
    payload: schemas.FactCheckRequest,
    settings: Settings = Depends(get_settings),
) -> schemas.FactCheckResponse:
    try:
        provider = get_fact_checker(settings)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    try:
        return await provider.check_fact(payload.fact, settings)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Fact checking provider error: {exc}",
        ) from exc

