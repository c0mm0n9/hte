from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Chunking and limits
    chunk_seconds: int = 10
    max_chunks: int = 300
    max_video_bytes: Optional[int] = None
    max_duration_seconds: Optional[int] = None

    # Provider selection
    provider_name: str = "hive_ai"  # hive_ai | local_sample | sightengine

    # Hive AI configuration
    hive_api_key: Optional[str] = None
    hive_task_sync_url: str = "https://api.thehive.ai/api/v2/task/sync"
    hive_timeout_seconds: float = 60.0
    hive_max_concurrency: int = 4

    # Sightengine configuration
    sightengine_api_user: Optional[str] = None
    sightengine_api_secret: Optional[str] = None
    sightengine_timeout_seconds: float = 60.0
    sightengine_image_url: str = "https://api.sightengine.com/1.0/check.json"
    sightengine_video_sync_url: str = "https://api.sightengine.com/1.0/video/check-sync.json"

    # Media fetch (download) timeouts
    media_fetch_connect_timeout_seconds: float = 15.0
    media_fetch_read_timeout_seconds: Optional[float] = 120.0  # None = no read timeout for large files

    # When set, rewrite media URLs that use localhost/127.0.0.1 to this host (e.g. host.docker.internal or agent_gateway)
    media_url_rewrite_host: Optional[str] = None

    # Label thresholds
    ai_generated_threshold: float = 0.9
    deepfake_threshold: float = 0.5
    unlikely_threshold: float = 0.2

    class Config:
        env_prefix = "DEEPFAKE_"
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
