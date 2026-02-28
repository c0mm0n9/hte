from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # API key validation (allowed keys for incoming requests; optional in dev)
    allowed_api_keys: Optional[str] = None  # comma-separated, or empty to skip validation

    # LLM (Featherless: openai/gpt-oss-120b)
    llm_system_prompt: str = ""
    llm_base_url: str = "https://api.featherless.ai/v1"
    llm_api_key: Optional[str] = None
    llm_timeout_seconds: float = 60.0
    llm_model: str = "openai/gpt-oss-120b"

    # Service endpoints (called via API). Defaults use Docker Compose service names.
    # For local dev (agent_gateway run on host), set in .env to http://localhost:8000 etc.
    ai_text_detector_url: str = "http://ai_text_detector:8002"
    media_checking_url: str = "http://media_checking:8000"
    fact_checking_url: str = "http://fact_checking:8001"
    info_graph_url: Optional[str] = None

    service_timeout_seconds: float = 30.0
    info_graph_timeout_seconds: float = 180.0

    class Config:
        env_prefix = "AGENT_GATEWAY_"
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
