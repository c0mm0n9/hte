from typing import Literal, Optional

from pydantic import BaseModel


class AgentChatRequest(BaseModel):
    url: str = ""
    message: str
    device_token: Optional[str] = None
    media_urls: Optional[list[str]] = None  # image/video URLs from page (for AI-generated check)
    extracted_content: Optional[str] = None  # LLM-extracted important page content (text summary)


class AgentChatResponse(BaseModel):
    reply: str


class AuthValidateResponse(BaseModel):
    valid: bool
    mode: Optional[Literal["agent", "control"]] = None
