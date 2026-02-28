import logging
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status

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
        logger.warning("Agent run rejected: invalid API key")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )


@router.post("/agent/run", response_model=schemas.AgentRunResponse)
async def agent_run(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> schemas.AgentRunResponse:
    """
    Accepts either JSON body or multipart/form-data (with optional file upload).

    JSON body fields:  api_key, prompt, website_content
    Form-data fields:  api_key, prompt, website_content, file (optional image/video)
    """
    content_type = request.headers.get("content-type", "")
    uploaded_file: Optional[tuple[bytes, str, str]] = None

    if "multipart/form-data" in content_type or "application/x-www-form-urlencoded" in content_type:
        form = await request.form()
        api_key: str = form.get("api_key") or ""
        prompt: Optional[str] = form.get("prompt") or None
        website_content: Optional[str] = form.get("website_content") or None

        file_field = form.get("file")
        if isinstance(file_field, UploadFile):
            file_bytes = await file_field.read()
            if file_bytes:
                uploaded_file = (
                    file_bytes,
                    file_field.filename or "upload",
                    file_field.content_type or "application/octet-stream",
                )
                logger.info(
                    "agent/run multipart: file=%s size=%s",
                    file_field.filename,
                    len(file_bytes),
                )
    else:
        body = await request.json()
        api_key = body.get("api_key") or ""
        prompt = body.get("prompt") or None
        website_content = body.get("website_content") or None

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="api_key is required",
        )

    validate_api_key(api_key, settings)

    logger.info(
        "agent/run request: prompt=%s website_content_len=%s file=%s",
        "yes" if prompt else "no",
        len(website_content or ""),
        uploaded_file[1] if uploaded_file else None,
    )

    result = await run_agent(
        prompt=prompt,
        website_content=website_content,
        settings=settings,
        uploaded_file=uploaded_file,
    )
    logger.info(
        "agent/run done: trust_score=%s fake_facts=%s fake_media=%s true_facts=%s true_media=%s",
        result.trust_score,
        len(result.fake_facts),
        len(result.fake_media),
        len(result.true_facts),
        len(result.true_media),
    )
    return result
