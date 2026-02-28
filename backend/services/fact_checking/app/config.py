import os
from functools import lru_cache
from typing import Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    provider: str = "exa"

    exa_api_key: Optional[str] = None
    exa_base_url: str = "https://api.exa.ai"
    exa_timeout_seconds: float = 30.0
    # Optional: include full text in Answer API search results (default compact)
    exa_answer_include_text: bool = False

    class Config:
        env_prefix = "FACTCHECK_"
        env_file = ".env"
        env_file_encoding = "utf-8"

    @field_validator("exa_api_key", mode="after")
    @classmethod
    def resolve_exa_api_key(cls, v: Optional[str]) -> str:
        if v and getattr(v, "strip", None) and v.strip():
            return v.strip()
        key = (os.environ.get("EXA_API_KEY") or "").strip()
        return key


@lru_cache()
def get_settings() -> Settings:
    return Settings()

