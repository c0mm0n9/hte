import os
from functools import lru_cache
from typing import Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    provider: str = "sapling"

    sapling_api_key: Optional[str] = None
    sapling_base_url: str = "https://api.sapling.ai"
    sapling_timeout_seconds: float = 30.0

    class Config:
        env_prefix = "AIDETECT_"
        env_file = ".env"
        env_file_encoding = "utf-8"

    @field_validator("sapling_api_key", mode="after")
    @classmethod
    def resolve_sapling_api_key(cls, v: Optional[str]) -> str:
        if v and getattr(v, "strip", None) and v.strip():
            return v.strip()
        key = (os.environ.get("SAPLING_API_KEY") or "").strip()
        return key


@lru_cache()
def get_settings() -> Settings:
    return Settings()
