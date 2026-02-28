import logging
from typing import Optional
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import Response
from starlette.datastructures import UploadFile as StarletteUploadFile

from .. import schemas
from ..config import get_settings, Settings
from ..service import call_media_explanation, run_agent

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


async def validate_api_key_with_portal(api_key: str, settings: Settings) -> Optional[str]:
    """
    Validate API key via portal backend (GET .../api/portal/validate/?api_key=...).
    Returns backend-provided prompt when valid and present; None when valid but no prompt.
    Raises HTTPException: 401 invalid key, 502/503 upstream error or malformed response.
    """
    base = (settings.portal_base_url or "").strip().rstrip("/")
    if not base:
        return None
    path = (settings.portal_validate_path or "api/portal/validate/").strip().lstrip("/")
    url = f"{base}/{path}?{urlencode({'api_key': api_key})}"
    timeout = settings.portal_validate_timeout_seconds
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.get(url)
    except (httpx.TimeoutException, httpx.ConnectError) as e:
        logger.warning("Portal validate request failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="API key validation service unavailable",
        ) from e
    except Exception as e:
        logger.exception("Portal validate error: %s", e)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="API key validation error",
        ) from e

    if r.status_code in (400, 401, 404):
        logger.warning("Portal validate rejected key: status=%s", r.status_code)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )
    if r.status_code != 200:
        logger.warning("Portal validate unexpected status: %s", r.status_code)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="API key validation returned an error",
        )

    try:
        data = r.json()
    except Exception as e:
        logger.warning("Portal validate invalid JSON: %s", e)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="API key validation returned invalid response",
        ) from e
    if not isinstance(data, dict):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="API key validation returned invalid response",
        )
    if data.get("valid") is not True:
        logger.warning("Portal validate returned valid=false")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )
    prompt = data.get("prompt")
    if isinstance(prompt, str) and prompt.strip():
        return prompt.strip()
    return None


@router.post("/agent/run", response_model=schemas.AgentRunResponse)
async def agent_run(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> schemas.AgentRunResponse:
    """
    Accepts either JSON body or multipart/form-data (with optional file uploads).

    Request must include api_key. When AGENT_GATEWAY_PORTAL_BASE_URL is set, the key is validated
    via the portal backend (GET api/portal/validate/?api_key=...); the backend may return a prompt,
    which overrides any prompt in the request body. When portal is not configured, api_key is
    checked against AGENT_GATEWAY_ALLOWED_API_KEYS (if set). A non-empty prompt is required:
    either from the backend (when available) or from the request.

    JSON body fields:  api_key (required), prompt (required if backend does not provide one), website_content, website_url
    Form-data fields:  api_key, prompt, website_content, website_url,
                       and any key for file(s), e.g. uploaded_file, file (one or more image/video files).
    In Postman: use Body -> form-data; add rows for api_key, prompt, etc., and set type to File for uploads.
    Do not set Content-Type header manually—let Postman send multipart/form-data.
    """
    content_type = request.headers.get("content-type", "")
    uploaded_files: list[tuple[bytes, str, str]] = []
    website_url: Optional[str] = None

    send_fact_check = False
    send_media_check = False
    if "multipart/form-data" in content_type or "application/x-www-form-urlencoded" in content_type:
        form = await request.form()
        api_key = (form.get("api_key") or "").strip().strip('"')
        prompt_raw = form.get("prompt")
        prompt = prompt_raw.strip().strip('"') if isinstance(prompt_raw, str) else None
        website_content_raw = form.get("website_content")
        website_content = website_content_raw.strip().strip('"') if isinstance(website_content_raw, str) else None
        website_url_raw = form.get("website_url")
        website_url = website_url_raw.strip().strip('"') if isinstance(website_url_raw, str) else None
        send_fact_check = str(form.get("send_fact_check") or "").strip().lower() in ("true", "1", "yes")
        send_media_check = str(form.get("send_media_check") or "").strip().lower() in ("true", "1", "yes")

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
        send_fact_check = bool(body.get("send_fact_check"))
        send_media_check = bool(body.get("send_media_check"))

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="api_key is required",
        )

    backend_prompt: Optional[str] = None
    if settings.portal_base_url:
        backend_prompt = await validate_api_key_with_portal(api_key, settings)
    else:
        validate_api_key(api_key, settings)

    effective_prompt = (backend_prompt if (backend_prompt is not None and backend_prompt) else prompt) or None
    if not (effective_prompt and effective_prompt.strip()):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="prompt is required (provide in request body or via backend for this API key)",
        )

    logger.info(
        "agent/run request: prompt=%s website_content_len=%s website_url=%s files=%s",
        "yes" if effective_prompt else "no",
        len(website_content or ""),
        (website_url or "")[:80] if website_url else None,
        [f[1] for f in uploaded_files] if uploaded_files else [],
    )

    result = await run_agent(
        prompt=effective_prompt,
        website_content=website_content,
        website_url=website_url,
        settings=settings,
        uploaded_files=uploaded_files,
        send_fact_check=send_fact_check,
        send_media_check=send_media_check,
    )
    logger.info(
        "agent/run done: trust_score=%s fake_facts=%s fake_media=%s true_facts=%s true_media=%s info_graph_nodes=%s content_safety=%s",
        result.trust_score,
        len(result.fake_facts),
        len(result.fake_media),
        len(result.true_facts),
        len(result.true_media),
        len(result.info_graph.nodes) if result.info_graph else 0,
        result.content_safety,
    )
    return result


@router.post("/agent/explain")
async def agent_explain(
    payload: schemas.ExplainRequest,
    settings: Settings = Depends(get_settings),
) -> Response:
    """
    Generate an explanatory video, audio, or flashcards for a trust-score result.

    Body fields:
      - api_key (required): API key for authentication
      - response (required): full JSON object from /agent/run
      - explanation_type (required): "video" | "audio" | "flashcards"
      - user_prompt (optional): personalisation hint passed to Minimax

    Returns:
      - video/audio: binary file with appropriate Content-Type and Content-Disposition
      - flashcards: JSON object {"flashcards": [...]}
    """
    validate_api_key(payload.api_key, settings)

    if not settings.media_explanation_url:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Media explanation service is not configured (AGENT_GATEWAY_MEDIA_EXPLANATION_URL not set)",
        )

    logger.info(
        "agent/explain request: type=%s user_prompt=%s trust_score=%s",
        payload.explanation_type,
        bool(payload.user_prompt),
        payload.response.trust_score,
    )

    try:
        svc_response = await call_media_explanation(
            agent_response=payload.response.model_dump(),
            explanation_type=payload.explanation_type,
            user_prompt=payload.user_prompt,
            settings=settings,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))
    except Exception as e:
        logger.exception("media_explanation call failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Media explanation service error: {e}",
        )

    content_type = svc_response.headers.get("content-type", "application/octet-stream")
    content_disposition = svc_response.headers.get("content-disposition", "")

    logger.info(
        "agent/explain done: type=%s content_type=%s bytes=%s",
        payload.explanation_type,
        content_type,
        len(svc_response.content),
    )

    headers: dict[str, str] = {}
    if content_disposition:
        headers["Content-Disposition"] = content_disposition
    elif payload.explanation_type == "video":
        headers["Content-Disposition"] = 'attachment; filename="explanation.mp4"'
    elif payload.explanation_type == "audio":
        headers["Content-Disposition"] = 'attachment; filename="explanation.mp3"'

    return Response(content=svc_response.content, media_type=content_type, headers=headers)
