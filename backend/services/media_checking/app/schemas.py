from typing import List, Optional, Literal

from pydantic import BaseModel, HttpUrl


class MediaCheckRequest(BaseModel):
    media_url: HttpUrl
    chunk_seconds: Optional[int] = None
    max_chunks: Optional[int] = None
    type_hint: Optional[Literal["image", "video"]] = None


class ChunkResult(BaseModel):
    index: int
    start_seconds: float
    end_seconds: float
    ai_generated_score: Optional[float] = None
    deepfake_score: Optional[float] = None
    label: str
    provider_raw: Optional[dict] = None


class MediaCheckResponse(BaseModel):
    media_url: HttpUrl
    media_type: Literal["image", "video"]
    duration_seconds: float
    chunk_seconds: int
    provider: str
    chunks: List[ChunkResult]
