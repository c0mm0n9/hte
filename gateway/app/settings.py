"""Gateway settings from environment only. Extension holds its own config (gateway URL, etc.)."""
from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    fact_check_base_url: str = "http://localhost:8001"
    media_check_base_url: str = "http://localhost:8002"
    fact_check_timeout_seconds: float = 30.0
    media_check_timeout_seconds: float = 60.0
    # Backend agent_gateway (extension /v1/agent/run and /v1/agent/explain are proxied here)
    agent_gateway_url: str = "http://127.0.0.1:8003"
    agent_gateway_timeout_seconds: float = 300.0
    agent_gateway_explain_timeout_seconds: float = 600.0

    class Config:
        env_prefix = "GATEWAY_"
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
