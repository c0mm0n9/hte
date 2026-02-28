from typing import Any, Dict, Optional

import httpx

from ..config import Settings
from ..media import VideoChunk
from ..schemas import ChunkResult
from .base import MediaProvider, label_from_scores


class HiveAIMediaProvider(MediaProvider):
    async def score_chunk(
        self,
        chunk: VideoChunk,
        settings: Settings,
    ) -> ChunkResult:
        if not settings.hive_api_key:
            raise RuntimeError("Hive AI API key is not configured")

        headers = {
            "Authorization": f"Token {settings.hive_api_key}",
            "Accept": "application/json",
        }

        async with httpx.AsyncClient(timeout=settings.hive_timeout_seconds) as client:
            with open(chunk.path, "rb") as f:
                files = {"media": (chunk.path.name, f, chunk.mime_type)}
                resp = await client.post(
                    settings.hive_task_sync_url,
                    headers=headers,
                    files=files,
                    data={},
                )

        resp.raise_for_status()
        data = resp.json()

        ai_score, df_score = self._extract_scores(data)
        label = label_from_scores(ai_score, df_score, settings)

        return ChunkResult(
            index=chunk.index,
            start_seconds=chunk.start_seconds,
            end_seconds=chunk.end_seconds,
            ai_generated_score=ai_score,
            deepfake_score=df_score,
            label=label,
            provider_raw=data,
        )

    @staticmethod
    def _extract_scores(payload: Dict[str, Any]) -> tuple[Optional[float], Optional[float]]:
        """
        Extract ai_generated and deepfake scores from Hive AI unified
        image/video detection response.
        """
        status_list = payload.get("status") or []
        if not status_list:
            return None, None

        response = status_list[0].get("response") or {}
        output = response.get("output") or []
        if not output:
            return None, None

        classes = output[0].get("classes") or []

        ai_score: Optional[float] = None
        df_score: Optional[float] = None

        for item in classes:
            cls = item.get("class")
            score = item.get("score")
            if cls == "ai_generated":
                ai_score = float(score)
            elif cls == "deepfake":
                df_score = float(score)

        return ai_score, df_score
