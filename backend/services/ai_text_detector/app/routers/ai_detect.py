from fastapi import APIRouter, Depends, HTTPException, status

from .. import schemas
from ..config import Settings, get_settings
from ..service import run_detection

router = APIRouter(tags=["ai-detect"])


@router.post("/ai-detect", response_model=schemas.AIDetectResponse)
async def ai_detect(
    payload: schemas.AIDetectRequest,
    settings: Settings = Depends(get_settings),
) -> schemas.AIDetectResponse:
    if not (payload.text and payload.text.strip()):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="text is required and must be non-empty",
        )

    try:
        return await run_detection(payload.text.strip(), settings)
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AI detection provider error: {exc}",
        ) from exc
