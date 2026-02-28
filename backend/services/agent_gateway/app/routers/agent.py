import logging

from fastapi import APIRouter, Depends, HTTPException, status

from .. import schemas
from ..config import get_settings, Settings
from ..service import run_agent

router = APIRouter(tags=["agent"])
logger = logging.getLogger("agent_gateway")


def validate_api_key(api_key: str, settings: Settings) -> None:
    """Reject request if api_key is not allowed (when allowed_api_keys is set)."""
    if not settings.allowed_api_keys:
        return
    allowed = {k.strip() for k in settings.allowed_api_keys.split(",") if k.strip()}
    if allowed and api_key not in allowed:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )


@router.post("/agent/run", response_model=schemas.AgentRunResponse)
async def agent_run(
    payload: schemas.AgentRunRequest,
    settings: Settings = Depends(get_settings),
) -> schemas.AgentRunResponse:
    """
    Receives API key, optional prompt, optional website_content.
    LLM generates actions -> execute via ai_text_detector, media_checking, fact_checking -> trust score LLM -> return trust_score, fake_facts, fake_media.
    """
    validate_api_key(payload.api_key, settings)

    logger.info(
        "agent/run request: prompt=%s website_content_len=%s",
        "yes" if payload.prompt else "no",
        len(payload.website_content or ""),
    )
    result = await run_agent(
        prompt=payload.prompt,
        website_content=payload.website_content,
        settings=settings,
    )
    logger.info(
        "agent/run done: trust_score=%s fake_facts=%s fake_media=%s",
        result.trust_score,
        len(result.fake_facts),
        len(result.fake_media),
    )
    return result
