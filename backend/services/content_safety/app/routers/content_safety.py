import logging

from fastapi import APIRouter, Depends, HTTPException, status

from ..config import Settings, get_settings
from ..schemas import ContentSafetyRequest, ContentSafetyResponse
from ..service import check_content_safety

router = APIRouter(tags=["content-safety"])
logger = logging.getLogger("content_safety")


@router.post("/content-safety/check", response_model=ContentSafetyResponse)
async def content_safety_check(
    payload: ContentSafetyRequest,
    settings: Settings = Depends(get_settings),
) -> ContentSafetyResponse:
    logger.info("POST /content-safety/check: website_text_len=%s", len(payload.website_text or ""))
    if not (payload.website_text or payload.website_text.strip()):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="website_text must not be empty",
        )
    try:
        result = await check_content_safety(payload.website_text, settings)
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        ) from e
    except Exception as exc:
        logger.exception("Content safety check failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Content safety check failed: {exc}",
        ) from exc
