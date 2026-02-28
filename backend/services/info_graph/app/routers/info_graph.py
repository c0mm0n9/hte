import logging

from fastapi import APIRouter, Depends, HTTPException, status

from ..config import Settings, get_settings
from ..schemas import InfoGraphRequest, InfoGraphResponse
from ..service import build_info_graph

router = APIRouter(tags=["info-graph"])
logger = logging.getLogger("info_graph")


@router.post("/info-graph/build", response_model=InfoGraphResponse)
async def build_graph(
    payload: InfoGraphRequest,
    settings: Settings = Depends(get_settings),
) -> InfoGraphResponse:
    logger.info(
        "POST /info-graph/build: website_url=%s website_text_len=%s",
        payload.website_url[:80] if payload.website_url else "(empty)",
        len(payload.website_text or ""),
    )
    if not payload.website_text.strip():
        logger.warning("Rejecting request: website_text is empty")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="website_text must not be empty",
        )
    if not payload.website_url.strip():
        logger.warning("Rejecting request: website_url is empty")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="website_url must not be empty",
        )
    try:
        result = await build_info_graph(payload, settings)
        logger.info(
            "info-graph/build done: nodes=%s edges=%s related_articles=%s",
            len(result.nodes),
            len(result.edges),
            len(result.related_articles),
        )
        return result
    except Exception as exc:
        logger.exception("Info graph build failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Info graph build failed: {exc}",
        ) from exc
