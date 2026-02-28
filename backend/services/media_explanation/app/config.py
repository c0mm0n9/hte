from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Minimax API credentials
    minimax_base_url: str = "https://api.minimax.io"
    minimax_api_key: Optional[str] = None

    # Minimax model names (can be overridden via env)
    minimax_video_model: str = "MiniMax-Hailuo-02"
    minimax_audio_model: str = "speech-02-turbo"
    minimax_text_model: str = "MiniMax-M2.5"
    minimax_audio_voice_id: str = "male-qn-qingse"  # 300+ system voices available

    # Timeouts (seconds)
    audio_timeout_seconds: float = 120.0
    video_poll_timeout_seconds: float = 600.0
    video_poll_interval_seconds: float = 5.0
    flashcards_timeout_seconds: float = 60.0
    explanation_script_timeout_seconds: float = 60.0

    # Video explanation pipeline: optional background music (file path or URL), max fragment clips
    background_music_path: Optional[str] = None
    max_video_fragments: int = 10
    max_parallel_video_generations: int = 3

    class Config:
        env_prefix = "MEDIA_EXPLANATION_"
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
