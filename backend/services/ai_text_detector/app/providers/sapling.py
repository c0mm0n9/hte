from typing import Any, Dict, List

import httpx

from ..config import Settings
from ..schemas import AIDetectResponse, SentenceScore
from .base import TextAIProvider


class SaplingTextAIProvider(TextAIProvider):
    async def detect(self, text: str, settings: Settings) -> AIDetectResponse:
        if not (settings.sapling_api_key and settings.sapling_api_key.strip()):
            raise RuntimeError(
                "Sapling API key is not configured. Set AIDETECT_SAPLING_API_KEY or SAPLING_API_KEY."
            )

        url = settings.sapling_base_url.rstrip("/") + "/api/v1/aidetect"
        payload: Dict[str, Any] = {
            "key": settings.sapling_api_key,
            "text": text,
            "sent_scores": True,
            "version": "20251027",  # pin detector version; avoid routing/502 issues
        }

        async with httpx.AsyncClient(timeout=settings.sapling_timeout_seconds) as client:
            resp = await client.post(url, json=payload)

        resp.raise_for_status()
        data = resp.json()

        overall_score = float(data.get("score", 0.0))
        sentence_scores_raw: List[Dict[str, Any]] = data.get("sentence_scores") or []
        sentence_scores = [
            SentenceScore(
                sentence=item.get("sentence", ""),
                score=float(item.get("score", 0.0)),
            )
            for item in sentence_scores_raw
        ]

        return AIDetectResponse(
            overall_score=overall_score,
            sentence_scores=sentence_scores,
            provider="sapling",
            provider_raw=data,
        )
