from typing import Optional

from ..config import Settings
from ..media import VideoChunk
from ..schemas import ChunkResult
from .base import MediaProvider, label_from_scores


class LocalSampleMediaProvider(MediaProvider):
    """
    Example provider stub showing how to plug in a local
    model for AI media / deepfake detection.
    """

    async def score_chunk(
        self,
        chunk: VideoChunk,
        settings: Settings,
    ) -> ChunkResult:
        # Placeholder heuristic: no real model here.
        ai_score: Optional[float] = None
        df_score: Optional[float] = None

        label = label_from_scores(ai_score, df_score, settings)

        return ChunkResult(
            index=chunk.index,
            start_seconds=chunk.start_seconds,
            end_seconds=chunk.end_seconds,
            ai_generated_score=ai_score,
            deepfake_score=df_score,
            label=label,
            provider_raw={"note": "local_sample provider placeholder; plug in your own model"},
        )
