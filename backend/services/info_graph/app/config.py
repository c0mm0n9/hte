import os
from functools import lru_cache
from typing import Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Exa search
    exa_api_key: Optional[str] = None
    exa_base_url: str = "https://api.exa.ai"
    exa_timeout_seconds: float = 30.0
    exa_num_results: int = 10

    # LLM for graph building (MiniMax M2.5 by default; or Featherless/OpenAI-compatible)
    llm_base_url: str = "https://api.minimax.io/v1"
    llm_api_key: Optional[str] = None
    llm_model: str = "MiniMax-M2.5"
    llm_path: str = "/text/chatcompletion_v2"  # MiniMax path; use "/chat/completions" for OpenAI-compatible
    llm_timeout_seconds: float = 120.0

    class Config:
        env_prefix = "INFOGRAPH_"
        env_file = ".env"
        env_file_encoding = "utf-8"

    @field_validator("exa_api_key", mode="after")
    @classmethod
    def resolve_exa_api_key(cls, v: Optional[str]) -> Optional[str]:
        if v and v.strip():
            return v.strip()
        return (os.environ.get("EXA_API_KEY") or "").strip() or None


@lru_cache()
def get_settings() -> Settings:
    return Settings()
