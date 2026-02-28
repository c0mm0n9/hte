from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # LLM for content safety (MiniMax M2.5 by default; or OpenAI-compatible)
    llm_base_url: str = "https://api.minimax.io/v1"
    llm_api_key: Optional[str] = None
    llm_model: str = "MiniMax-M2.5"
    llm_path: str = "/text/chatcompletion_v2"  # MiniMax path; use "/chat/completions" for OpenAI-compatible
    llm_timeout_seconds: float = 120.0

    class Config:
        env_prefix = "CONTENT_SAFETY_"
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
