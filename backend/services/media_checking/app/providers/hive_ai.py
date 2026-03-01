import logging
from typing import Any, Dict, Optional

import httpx

from ..config import Settings
from ..media import VideoChunk
from ..schemas import ChunkResult
from .base import MediaProvider, label_from_scores

logger = logging.getLogger(__name__)


class HiveAIMediaProvider(MediaProvider):
    async def score_chunk(
        self,
        chunk: VideoChunk,
        settings: Settings,
    ) -> ChunkResult:
        if not settings.hive_api_key:
            logger.warning("Hive AI API key is not configured")
            return self._error_chunk(chunk, "Hive AI API key is not configured")

        headers = {
            "Authorization": f"Token {settings.hive_api_key}",
            "Accept": "application/json",
        }

        try:
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
        except httpx.HTTPStatusError as e:
            logger.warning(
                "Hive AI API error: %s %s - %s. Check HIVE_API_KEY and account access.",
                e.response.status_code,
                e.response.reason_phrase,
                (e.response.text or "")[:200],
            )
            return self._error_chunk(
                chunk,
                f"Hive AI API returned {e.response.status_code}: {e.response.reason_phrase}",
                status=e.response.status_code,
                body=(e.response.text or "")[:500],
            )
        except (httpx.RequestError, OSError, ValueError) as e:
            logger.warning("Hive AI request failed: %s", e)
            return self._error_chunk(chunk, str(e))

    @staticmethod
    def _error_chunk(
        chunk: VideoChunk,
        message: str,
        status: Optional[int] = None,
        body: Optional[str] = None,
    ) -> ChunkResult:
        return ChunkResult(
            index=chunk.index,
            start_seconds=chunk.start_seconds,
            end_seconds=chunk.end_seconds,
            ai_generated_score=None,
            deepfake_score=None,
            label="error",
            provider_raw={"error": message, "status": status, "body": body},
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
