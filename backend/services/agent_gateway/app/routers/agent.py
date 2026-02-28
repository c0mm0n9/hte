import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, status
from starlette.datastructures import UploadFile as StarletteUploadFile

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
    Accepts either JSON body or multipart/form-data (with optional file uploads).

    JSON body fields:  api_key, prompt, website_content, website_url
    Form-data fields:  api_key, prompt, website_content, website_url,
                       and any key for file(s), e.g. uploaded_file, file (one or more image/video files).
    In Postman: use Body -> form-data; add rows for api_key, prompt, etc., and set type to File for uploads.
    Do not set Content-Type header manually—let Postman send multipart/form-data.
    """
    content_type = request.headers.get("content-type", "")
    uploaded_files: list[tuple[bytes, str, str]] = []
    website_url: Optional[str] = None

    if "multipart/form-data" in content_type or "application/x-www-form-urlencoded" in content_type:
        form = await request.form()
        api_key = (form.get("api_key") or "").strip().strip('"')
        prompt_raw = form.get("prompt")
        prompt = prompt_raw.strip().strip('"') if isinstance(prompt_raw, str) else None
        website_content_raw = form.get("website_content")
        website_content = website_content_raw.strip().strip('"') if isinstance(website_content_raw, str) else None
        website_url_raw = form.get("website_url")
        website_url = website_url_raw.strip().strip('"') if isinstance(website_url_raw, str) else None

        # Collect all uploaded files from any form field (Postman/curl may use uploaded_file, file, etc.).
        # Deduplicate keys first (dict.fromkeys preserves order), then use getlist() to retrieve
        # ALL values per key — this correctly handles multiple files under the same field name.
        # Check against StarletteUploadFile (parent class) because request.form() returns
        # Starlette's UploadFile instances, not FastAPI's subclass.
        for key in dict.fromkeys(form.keys()):
            for field_value in form.getlist(key):
                if isinstance(field_value, StarletteUploadFile):
                    file_bytes = await field_value.read()
                    if file_bytes:
                        uploaded_files.append((
                            file_bytes,
                            field_value.filename or "upload",
                            field_value.content_type or "application/octet-stream",
                        ))
                        logger.info(
                            "agent/run multipart: key=%s file=%s size=%s",
                            key,
                            field_value.filename,
                            len(file_bytes),
                        )
    else:
        body = await request.json()
        api_key = body.get("api_key") or ""
        prompt = body.get("prompt") or None
        website_content = body.get("website_content") or None
        website_url = body.get("website_url") or None

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="api_key is required",
        )

    validate_api_key(api_key, settings)

    logger.info(
        "agent/run request: prompt=%s website_content_len=%s website_url=%s files=%s",
        "yes" if prompt else "no",
        len(website_content or ""),
        (website_url or "")[:80] if website_url else None,
        [f[1] for f in uploaded_files] if uploaded_files else [],
    )

    result = await run_agent(
        prompt=prompt,
        website_content=website_content,
        website_url=website_url,
        settings=settings,
        uploaded_files=uploaded_files,
    )
    logger.info(
        "agent/run done: trust_score=%s fake_facts=%s fake_media=%s true_facts=%s true_media=%s info_graph_nodes=%s",
        result.trust_score,
        len(result.fake_facts),
        len(result.fake_media),
        len(result.true_facts),
        len(result.true_media),
        len(result.info_graph.nodes) if result.info_graph else 0,
    )
    return result
