from abc import ABC, abstractmethod
from typing import Optional

from ..config import Settings
from ..media import VideoChunk
from ..schemas import ChunkResult


class MediaProvider(ABC):
    @abstractmethod
    async def score_chunk(
        self,
        chunk: VideoChunk,
        settings: Settings,
    ) -> ChunkResult:
        ...


def label_from_scores(
    ai_generated_score: Optional[float],
    deepfake_score: Optional[float],
    settings: Settings,
) -> str:
    if ai_generated_score is None and deepfake_score is None:
        return "unknown"

    ai_score = ai_generated_score or 0.0
    df_score = deepfake_score or 0.0

    if df_score >= settings.deepfake_threshold:
        return "deepfake"

    if ai_score >= settings.ai_generated_threshold:
        return "ai_generated"

    if ai_score <= settings.unlikely_threshold and df_score <= settings.unlikely_threshold:
        return "not_ai_generated"

    return "unknown"
