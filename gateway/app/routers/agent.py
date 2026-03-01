import json
from typing import List, Optional

import httpx
from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Request, UploadFile, status
from fastapi.responses import Response

from ..agent_service import build_agent_reply, build_analyze_reply
from ..auth import parse_api_key
from ..schemas import AgentChatRequest, AgentChatResponse
from ..settings import Settings, get_settings

router = APIRouter(prefix="/v1/agent", tags=["agent"])


def _agent_gateway_base(settings: Settings) -> str:
    return settings.agent_gateway_url.rstrip("/")


@router.post("/run")
async def agent_run_proxy(request: Request, settings: Settings = Depends(get_settings)):
    """Proxy to backend agent_gateway (backend/services/agent_gateway)."""
    base = _agent_gateway_base(settings)
    url = f"{base}/v1/agent/run"
    body = await request.body()
    content_type = request.headers.get("content-type", "")
    timeout = settings.agent_gateway_timeout_seconds
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.post(url, content=body, headers={"Content-Type": content_type})
        return Response(
            content=r.content,
            status_code=r.status_code,
            headers={"Content-Type": r.headers.get("content-type", "application/json")},
        )
    except httpx.RequestError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Agent gateway unreachable: {e!s}",
        )


@router.post("/explain")
async def agent_explain_proxy(request: Request, settings: Settings = Depends(get_settings)):
    """Proxy to backend agent_gateway /v1/agent/explain."""
    base = _agent_gateway_base(settings)
    url = f"{base}/v1/agent/explain"
    body = await request.body()
    content_type = request.headers.get("content-type", "application/json")
    timeout = settings.agent_gateway_explain_timeout_seconds
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.post(url, content=body, headers={"Content-Type": content_type})
        return Response(
            content=r.content,
            status_code=r.status_code,
            headers={"Content-Type": r.headers.get("content-type", "application/json")},
        )
    except httpx.RequestError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Agent gateway unreachable: {e!s}",
        )


async def require_api_key(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
) -> str:
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-API-Key. Enter your API key in extension options.",
        )
    valid, mode = parse_api_key(x_api_key)
    if not valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key format.",
        )
    if mode != "agent":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This key is not for Agent mode.",
        )
    return x_api_key


@router.post("/chat", response_model=AgentChatResponse)
async def agent_chat(
    payload: AgentChatRequest,
    settings: Settings = Depends(get_settings),
    api_key: str = Depends(require_api_key),
) -> AgentChatResponse:
    reply = await build_agent_reply(
        message=payload.message,
        page_url=payload.url or "",
        media_urls=payload.media_urls,
        settings=settings,
        extracted_content=payload.extracted_content,
    )
    return AgentChatResponse(reply=reply)


@router.post("/analyze", response_model=AgentChatResponse)
async def agent_analyze(
    masked_text: str = Form(""),
    message: str = Form(""),
    page_url: str = Form(""),
    send_fact_check: str = Form("true"),
    send_media_check: str = Form("true"),
    video_urls: str = Form("[]"),
    media_urls: str = Form("[]"),
    files: List[UploadFile] = File(default=[]),
    settings: Settings = Depends(get_settings),
    api_key: str = Depends(require_api_key),
) -> AgentChatResponse:
    """Analyze page: masked text → fact_check; uploaded files + media_urls → media_check."""
    do_fact = send_fact_check.lower() in ("1", "true", "yes")
    do_media = send_media_check.lower() in ("1", "true", "yes")
    try:
        video_list = json.loads(video_urls) if video_urls else []
    except Exception:
        video_list = []
    try:
        media_list = json.loads(media_urls) if media_urls else []
    except Exception:
        media_list = []

    uploaded: List[tuple] = []
    for f in files:
        if not f.filename:
            continue
        data = await f.read()
        if data:
            uploaded.append((data, f.filename, f.content_type or "application/octet-stream"))

    reply = await build_analyze_reply(
        masked_text=masked_text,
        message=message,
        page_url=page_url,
        send_fact_check=do_fact,
        send_media_check=do_media,
        uploaded_files=uploaded,
        video_urls=video_list,
        settings=settings,
        media_urls=media_list,
    )
    return AgentChatResponse(reply=reply)
