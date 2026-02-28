import math
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple
from urllib.parse import urlparse, urlunparse

import httpx

from .config import Settings


def _rewrite_media_url_if_local(url: str, settings: Settings) -> str:
    """If URL points to localhost/127.0.0.1 and rewrite host is set, rewrite for Docker access."""
    if not settings.media_url_rewrite_host:
        return url
    try:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
        if host in ("localhost", "127.0.0.1", "::1"):
            new_netloc = f"{settings.media_url_rewrite_host}:{parsed.port}" if parsed.port else settings.media_url_rewrite_host
            return urlunparse(parsed._replace(netloc=new_netloc))
    except Exception:
        pass
    return url


class MediaUnreachableError(Exception):
    """Raised when the media URL cannot be fetched (connection failed, timeout, etc.)."""
    pass


@dataclass
class VideoChunk:
    index: int
    path: Path
    start_seconds: float
    end_seconds: float
    mime_type: str = "video/mp4"


async def download_media_to_temp(
    url: str,
    settings: Settings,
    filename: str = "input_media",
) -> Tuple[Path, Path, str]:
    """
    Download media at `url` to a temporary directory.

    Returns (temp_dir, media_path, mime_type).
    """
    url = _rewrite_media_url_if_local(url, settings)
    temp_dir = Path(tempfile.mkdtemp(prefix="ai_media_"))
    media_path = temp_dir / filename

    max_bytes: Optional[int] = settings.max_video_bytes
    connect_timeout = settings.media_fetch_connect_timeout_seconds
    read_timeout = settings.media_fetch_read_timeout_seconds
    timeout = httpx.Timeout(connect=connect_timeout, read=read_timeout)

    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            async with client.stream("GET", url) as resp:
                resp.raise_for_status()
                mime_type = resp.headers.get("Content-Type", "application/octet-stream")
                with open(media_path, "wb") as f:
                    total = 0
                    async for chunk in resp.aiter_bytes():
                        if not chunk:
                            continue
                        total += len(chunk)
                        if max_bytes is not None and total > max_bytes:
                            resp.close()
                            raise ValueError("Media exceeds configured max_video_bytes limit")
                        f.write(chunk)
    except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout) as e:
        if temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)
        raise MediaUnreachableError(
            f"Could not fetch media from URL (connection failed or timeout). "
            f"Ensure the URL is reachable from this service (e.g. from Docker use host.docker.internal or service names, not localhost). Original: {e!s}"
        ) from e
    except httpx.HTTPStatusError as e:
        if temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)
        raise MediaUnreachableError(
            f"Media URL returned HTTP {e.response.status_code}. "
            f"Ensure the URL is accessible. Original: {e!s}"
        ) from e

    return temp_dir, media_path, mime_type


def _run_ffprobe_duration(path: Path) -> float:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(path),
    ]
    proc = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {proc.stderr.strip()}")

    try:
        return float(proc.stdout.strip())
    except (TypeError, ValueError):
        raise RuntimeError("Unable to parse video duration from ffprobe output")


def probe_video_duration(path: Path, settings: Settings) -> float:
    duration = _run_ffprobe_duration(path)

    if settings.max_duration_seconds is not None and duration > settings.max_duration_seconds:
        raise ValueError("Video duration exceeds configured max_duration_seconds limit")

    return duration


def chunk_video(
    video_path: Path,
    duration_seconds: float,
    settings: Settings,
    chunk_seconds_override: Optional[int] = None,
    max_chunks_override: Optional[int] = None,
) -> List[VideoChunk]:
    chunk_seconds = chunk_seconds_override or settings.chunk_seconds
    max_chunks = max_chunks_override or settings.max_chunks

    chunk_seconds = max(1, int(chunk_seconds))
    max_chunks = max(1, int(max_chunks))

    effective_duration = duration_seconds
    if settings.max_duration_seconds is not None:
        effective_duration = min(effective_duration, settings.max_duration_seconds)

    total_time = min(effective_duration, chunk_seconds * max_chunks)
    num_chunks = max(1, min(math.ceil(effective_duration / chunk_seconds), max_chunks))

    out_dir = video_path.parent / "chunks"
    out_dir.mkdir(exist_ok=True)
    pattern = out_dir / "chunk_%05d.mp4"

    base_cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(video_path),
        "-f",
        "segment",
        "-segment_time",
        str(chunk_seconds),
        "-reset_timestamps",
        "1",
        "-t",
        str(total_time),
        str(pattern),
    ]

    proc = subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(video_path), "-c", "copy"]
        + base_cmd[8:],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        text=True,
    )

    if proc.returncode != 0:
        # Fallback without stream copy (re-encode)
        proc = subprocess.run(
            base_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            text=True,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"ffmpeg chunking failed: {proc.stderr.strip()}")

    chunk_files = sorted(out_dir.glob("chunk_*.mp4"))
    if not chunk_files:
        raise RuntimeError("ffmpeg did not produce any chunks")

    chunk_files = chunk_files[:num_chunks]

    chunks: List[VideoChunk] = []
    for idx, path in enumerate(chunk_files):
        start = idx * chunk_seconds
        end = min(start + chunk_seconds, effective_duration)
        chunks.append(
            VideoChunk(
                index=idx,
                path=path,
                start_seconds=float(start),
                end_seconds=float(end),
            )
        )

    return chunks


def cleanup_temp_dir(temp_dir: Path) -> None:
    if temp_dir.exists():
        shutil.rmtree(temp_dir, ignore_errors=True)
