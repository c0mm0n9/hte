from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status

from ..agent_service import build_agent_reply
from ..auth import parse_api_key
from ..schemas import AgentChatRequest, AgentChatResponse
from ..settings import Settings, get_settings

router = APIRouter(prefix="/v1/agent", tags=["agent"])


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
