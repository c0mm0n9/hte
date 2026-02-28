import asyncio
import logging
import tempfile
from pathlib import Path
from typing import Optional, Literal
from urllib.parse import urlparse

import httpx

from .config import Settings

logger = logging.getLogger(__name__)
from .media import (
    VideoChunk,
    chunk_video,
    cleanup_temp_dir,
    download_media_to_temp,
    probe_video_duration,
)
from .providers import get_provider
from .schemas import MediaCheckResponse


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
VIDEO_EXTENSIONS = {".mp4", ".webm", ".avi", ".mkv", ".wmv", ".mov"}


async def detect_media_type(
    media_url: str,
    type_hint: Optional[Literal["image", "video"]] = None,
) -> Literal["image", "video"]:
    if type_hint in ("image", "video"):
        logger.debug("Media type from hint: %s url=%s", type_hint, media_url)
        return type_hint

    path = urlparse(media_url).path.lower()
    for ext in IMAGE_EXTENSIONS:
        if path.endswith(ext):
            logger.debug("Media type from extension (image) url=%s", media_url)
            return "image"
    for ext in VIDEO_EXTENSIONS:
        if path.endswith(ext):
            logger.debug("Media type from extension (video) url=%s", media_url)
            return "video"

    try:
        async with httpx.AsyncClient(timeout=5.0, follow_redirects=True) as client:
            resp = await client.head(media_url)
            ct = (resp.headers.get("Content-Type") or "").lower()
            logger.debug("Media type HEAD probe content-type=%s url=%s", ct, media_url)
            if ct.startswith("image/"):
                return "image"
            if ct.startswith("video/"):
                return "video"
    except Exception as e:
        logger.warning("Media type HEAD probe failed url=%s error=%s", media_url, e)

    logger.debug("Media type defaulting to video url=%s", media_url)
    return "video"


async def run_image_detection(
    media_url: str,
    settings: Settings,
) -> MediaCheckResponse:
    logger.info("Starting image detection url=%s provider=%s", media_url, settings.provider_name)
    temp_dir = None
    try:
        temp_dir, media_path, mime_type = await download_media_to_temp(
            media_url, settings, filename="input_image"
        )
        provider = get_provider(settings.provider_name)

        full_result = await provider.score_media_file(
            media_path, "image", "input_image", mime_type or "image/jpeg", settings
        )
        if full_result is not None:
            full_result.media_url = media_url
            logger.info("Image detection complete (full-file) url=%s chunks=%s", media_url, len(full_result.chunks))
            return full_result

        chunk = VideoChunk(
            index=0,
            path=media_path,
            start_seconds=0.0,
            end_seconds=0.0,
            mime_type=mime_type or "image/jpeg",
        )

        result = await provider.score_chunk(chunk, settings)
        logger.info("Image detection complete url=%s result=%s", media_url, result)

        return MediaCheckResponse(
            media_url=media_url,
            media_type="image",
            duration_seconds=0.0,
            chunk_seconds=0,
            provider=settings.provider_name,
            chunks=[result],
        )
    finally:
        if temp_dir is not None:
            cleanup_temp_dir(temp_dir)


async def run_video_detection(
    media_url: str,
    chunk_seconds: Optional[int],
    max_chunks: Optional[int],
    settings: Settings,
) -> MediaCheckResponse:
    temp_dir = None
    try:
        temp_dir, video_path, mime_type = await download_media_to_temp(
            media_url, settings, filename="input_video"
        )
        provider = get_provider(settings.provider_name)

        full_result = await provider.score_media_file(
            video_path, "video", "input_video", mime_type or "video/mp4", settings
        )
        if full_result is not None:
            full_result.media_url = media_url
            logger.info("Video detection complete (full-file) url=%s chunks=%s", media_url, len(full_result.chunks))
            return full_result

        duration = probe_video_duration(video_path, settings)

        chunks = chunk_video(
            video_path=video_path,
            duration_seconds=duration,
            settings=settings,
            chunk_seconds_override=chunk_seconds,
            max_chunks_override=max_chunks,
        )

        sem = asyncio.Semaphore(settings.hive_max_concurrency)

        async def _score_one(chunk: VideoChunk):
            async with sem:
                return await provider.score_chunk(chunk, settings)

        results = await asyncio.gather(*[_score_one(c) for c in chunks])

        effective_chunk_seconds = chunk_seconds or settings.chunk_seconds

        return MediaCheckResponse(
            media_url=media_url,
            media_type="video",
            duration_seconds=duration,
            chunk_seconds=effective_chunk_seconds,
            provider=settings.provider_name,
            chunks=results,
        )
    finally:
        if temp_dir is not None:
            cleanup_temp_dir(temp_dir)


async def run_media_detection(
    media_url: str,
    chunk_seconds: Optional[int],
    max_chunks: Optional[int],
    type_hint: Optional[Literal["image", "video"]],
    settings: Settings,
) -> MediaCheckResponse:
    logger.info(
        "run_media_detection url=%s type_hint=%s provider=%s",
        media_url,
        type_hint,
        settings.provider_name,
    )
    media_type = await detect_media_type(media_url, type_hint)
    logger.info("Detected media_type=%s url=%s", media_type, media_url)
    if media_type == "image":
        return await run_image_detection(media_url, settings)
    return await run_video_detection(media_url, chunk_seconds, max_chunks, settings)


# ---------------------------------------------------------------------------
# Upload helpers (no download step – caller saves the file to temp_path first)
# ---------------------------------------------------------------------------

def detect_media_type_from_upload(
    filename: str,
    content_type: str,
    type_hint: Optional[Literal["image", "video"]] = None,
) -> Literal["image", "video"]:
    if type_hint in ("image", "video"):
        return type_hint
    name = filename.lower()
    for ext in IMAGE_EXTENSIONS:
        if name.endswith(ext):
            return "image"
    for ext in VIDEO_EXTENSIONS:
        if name.endswith(ext):
            return "video"
    ct = (content_type or "").lower()
    if ct.startswith("image/"):
        return "image"
    if ct.startswith("video/"):
        return "video"
    return "video"


async def run_image_detection_from_path(
    media_path: Path,
    mime_type: str,
    filename: str,
    settings: Settings,
) -> MediaCheckResponse:
    provider = get_provider(settings.provider_name)

    full_result = await provider.score_media_file(
        media_path, "image", filename, mime_type or "image/jpeg", settings
    )
    if full_result is not None:
        logger.info("Image detection from path complete (full-file) filename=%s chunks=%s", filename, len(full_result.chunks))
        return full_result

    chunk = VideoChunk(
        index=0,
        path=media_path,
        start_seconds=0.0,
        end_seconds=0.0,
        mime_type=mime_type or "image/jpeg",
    )
    result = await provider.score_chunk(chunk, settings)
    return MediaCheckResponse(
        media_url=filename,
        media_type="image",
        duration_seconds=0.0,
        chunk_seconds=0,
        provider=settings.provider_name,
        chunks=[result],
    )


async def run_video_detection_from_path(
    video_path: Path,
    filename: str,
    chunk_seconds: Optional[int],
    max_chunks: Optional[int],
    settings: Settings,
) -> MediaCheckResponse:
    provider = get_provider(settings.provider_name)

    full_result = await provider.score_media_file(
        video_path, "video", filename, "video/mp4", settings
    )
    if full_result is not None:
        logger.info("Video detection from path complete (full-file) filename=%s chunks=%s", filename, len(full_result.chunks))
        return full_result

    duration = probe_video_duration(video_path, settings)
    chunks = chunk_video(
        video_path=video_path,
        duration_seconds=duration,
        settings=settings,
        chunk_seconds_override=chunk_seconds,
        max_chunks_override=max_chunks,
    )
    sem = asyncio.Semaphore(settings.hive_max_concurrency)

    async def _score_one(chunk: VideoChunk):
        async with sem:
            return await provider.score_chunk(chunk, settings)

    results = await asyncio.gather(*[_score_one(c) for c in chunks])
    effective_chunk_seconds = chunk_seconds or settings.chunk_seconds
    return MediaCheckResponse(
        media_url=filename,
        media_type="video",
        duration_seconds=duration,
        chunk_seconds=effective_chunk_seconds,
        provider=settings.provider_name,
        chunks=results,
    )


async def run_media_detection_from_upload(
    file_bytes: bytes,
    filename: str,
    content_type: str,
    chunk_seconds: Optional[int],
    max_chunks: Optional[int],
    type_hint: Optional[Literal["image", "video"]],
    settings: Settings,
) -> MediaCheckResponse:
    media_type = detect_media_type_from_upload(filename, content_type, type_hint)
    temp_dir = Path(tempfile.mkdtemp(prefix="ai_upload_"))
    try:
        suffix = Path(filename).suffix or (".jpg" if media_type == "image" else ".mp4")
        media_path = temp_dir / f"upload{suffix}"
        media_path.write_bytes(file_bytes)
        if media_type == "image":
            return await run_image_detection_from_path(
                media_path, content_type, filename, settings
            )
        return await run_video_detection_from_path(
            media_path, filename, chunk_seconds, max_chunks, settings
        )
    finally:
        cleanup_temp_dir(temp_dir)
