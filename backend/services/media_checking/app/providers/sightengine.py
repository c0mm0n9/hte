import logging
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

import httpx

from ..config import Settings
from ..media import VideoChunk
from ..schemas import ChunkResult, MediaCheckResponse
from .base import MediaProvider, label_from_scores

logger = logging.getLogger(__name__)


class SightengineMediaProvider(MediaProvider):
    """Media provider that uses the Sightengine genai model for AI-generated detection."""

    async def score_chunk(
        self,
        chunk: VideoChunk,
        settings: Settings,
    ) -> ChunkResult:
        """Send a single file chunk to Sightengine's image check endpoint."""
        if not settings.sightengine_api_user or not settings.sightengine_api_secret:
            raise RuntimeError("Sightengine API credentials are not configured")

        async with httpx.AsyncClient(timeout=settings.sightengine_timeout_seconds) as client:
            with open(chunk.path, "rb") as f:
                resp = await client.post(
                    settings.sightengine_image_url,
                    data={
                        "models": "genai",
                        "api_user": settings.sightengine_api_user,
                        "api_secret": settings.sightengine_api_secret,
                    },
                    files={"media": (chunk.path.name, f, chunk.mime_type)},
                )

        resp.raise_for_status()
        data = resp.json()

        ai_score = self._extract_image_score(data)
        label = label_from_scores(ai_score, None, settings)

        return ChunkResult(
            index=chunk.index,
            start_seconds=chunk.start_seconds,
            end_seconds=chunk.end_seconds,
            ai_generated_score=ai_score,
            deepfake_score=None,
            label=label,
            provider_raw=data,
        )

    async def score_media_file(
        self,
        path: Path,
        media_type: Literal["image", "video"],
        filename: str,
        mime_type: str,
        settings: Settings,
    ) -> Optional[MediaCheckResponse]:
        """Send the full file directly to Sightengine, bypassing ffmpeg chunking."""
        if not settings.sightengine_api_user or not settings.sightengine_api_secret:
            raise RuntimeError("Sightengine API credentials are not configured")

        if media_type == "image":
            return await self._check_image(path, filename, mime_type, settings)
        return await self._check_video(path, filename, mime_type, settings)

    async def _check_image(
        self,
        path: Path,
        filename: str,
        mime_type: str,
        settings: Settings,
    ) -> MediaCheckResponse:
        logger.info("Sightengine image check filename=%s", filename)

        async with httpx.AsyncClient(timeout=settings.sightengine_timeout_seconds) as client:
            with open(path, "rb") as f:
                resp = await client.post(
                    settings.sightengine_image_url,
                    data={
                        "models": "genai",
                        "api_user": settings.sightengine_api_user,
                        "api_secret": settings.sightengine_api_secret,
                    },
                    files={"media": (filename, f, mime_type)},
                )

        resp.raise_for_status()
        data = resp.json()
        logger.info("Sightengine image response status=%s", data.get("status"))

        ai_score = self._extract_image_score(data)
        label = label_from_scores(ai_score, None, settings)

        chunk = ChunkResult(
            index=0,
            start_seconds=0.0,
            end_seconds=0.0,
            ai_generated_score=ai_score,
            deepfake_score=None,
            label=label,
            provider_raw=data,
        )

        return MediaCheckResponse(
            media_url=filename,
            media_type="image",
            duration_seconds=0.0,
            chunk_seconds=0,
            provider="sightengine",
            chunks=[chunk],
        )

    async def _check_video(
        self,
        path: Path,
        filename: str,
        mime_type: str,
        settings: Settings,
    ) -> MediaCheckResponse:
        logger.info("Sightengine video check filename=%s", filename)

        async with httpx.AsyncClient(timeout=settings.sightengine_timeout_seconds) as client:
            with open(path, "rb") as f:
                resp = await client.post(
                    settings.sightengine_video_sync_url,
                    data={
                        "models": "genai",
                        "api_user": settings.sightengine_api_user,
                        "api_secret": settings.sightengine_api_secret,
                    },
                    files={"media": (filename, f, mime_type or "video/mp4")},
                )

        resp.raise_for_status()
        data = resp.json()
        logger.info(
            "Sightengine video response status=%s frames=%s",
            data.get("status"),
            len((data.get("data") or {}).get("frames") or []),
        )

        chunks = self._frames_to_chunks(data, settings)

        return MediaCheckResponse(
            media_url=filename,
            media_type="video",
            duration_seconds=float(len(chunks)),
            chunk_seconds=1,
            provider="sightengine",
            chunks=chunks,
        )

    def _frames_to_chunks(
        self,
        data: Dict[str, Any],
        settings: Settings,
    ) -> List[ChunkResult]:
        frames = (data.get("data") or {}).get("frames") or []
        if not frames:
            return []

        chunks: List[ChunkResult] = []
        for frame in frames:
            info = frame.get("info") or {}
            position = int(info.get("position", len(chunks)))
            ai_score = self._extract_frame_score(frame)
            label = label_from_scores(ai_score, None, settings)
            chunks.append(
                ChunkResult(
                    index=position,
                    start_seconds=float(position),
                    end_seconds=float(position) + 1.0,
                    ai_generated_score=ai_score,
                    deepfake_score=None,
                    label=label,
                    provider_raw=frame,
                )
            )
        return chunks

    @staticmethod
    def _extract_image_score(payload: Dict[str, Any]) -> Optional[float]:
        """Extract ai_generated score from Sightengine image check response."""
        type_obj = payload.get("type") or {}
        score = type_obj.get("ai_generated")
        if score is None:
            return None
        try:
            return float(score)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _extract_frame_score(frame: Dict[str, Any]) -> Optional[float]:
        """Extract ai_generated score from a single Sightengine video frame."""
        type_obj = frame.get("type") or {}
        score = type_obj.get("ai_generated")
        if score is None:
            return None
        try:
            return float(score)
        except (TypeError, ValueError):
            return None
