from typing import Literal, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from .. import schemas
from ..config import get_settings, Settings
from ..media import MediaUnreachableError
from ..service import run_media_detection, run_media_detection_from_upload


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

    try:
        return await run_media_detection(
            media_url=str(payload.media_url),
            chunk_seconds=payload.chunk_seconds,
            max_chunks=payload.max_chunks,
            type_hint=payload.type_hint,
            settings=settings,
        )
    except MediaUnreachableError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(e),
        ) from e


@router.post("/media/check/upload", response_model=schemas.MediaCheckResponse)
@router.post("/deepfake/check/upload", response_model=schemas.MediaCheckResponse)
async def check_media_upload(
    file: UploadFile = File(..., description="Image or video file to analyse"),
    chunk_seconds: Optional[int] = Form(None),
    max_chunks: Optional[int] = Form(None),
    type_hint: Optional[Literal["image", "video"]] = Form(None),
    settings: Settings = Depends(get_settings),
) -> schemas.MediaCheckResponse:
    data = await file.read()
    if not data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty",
        )

    return await run_media_detection_from_upload(
        file_bytes=data,
        filename=file.filename or "upload",
        content_type=file.content_type or "application/octet-stream",
        chunk_seconds=chunk_seconds,
        max_chunks=max_chunks,
        type_hint=type_hint,
        settings=settings,
    )
