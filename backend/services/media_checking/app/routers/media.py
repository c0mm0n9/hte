from fastapi import APIRouter, Depends, HTTPException, status

from .. import schemas
from ..config import get_settings, Settings
from ..service import run_media_detection


router = APIRouter(tags=["media-check"])


@router.post("/media/check", response_model=schemas.MediaCheckResponse)
@router.post("/deepfake/check", response_model=schemas.MediaCheckResponse)
async def check_media(
    payload: schemas.MediaCheckRequest,
    settings: Settings = Depends(get_settings),
) -> schemas.MediaCheckResponse:
    if not payload.media_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="media_url is required",
        )

    return await run_media_detection(
        media_url=str(payload.media_url),
        chunk_seconds=payload.chunk_seconds,
        max_chunks=payload.max_chunks,
        type_hint=payload.type_hint,
        settings=settings,
    )
