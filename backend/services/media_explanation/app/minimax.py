"""
Minimax API integration: video generation (async poll), T2A audio (sync), and text/flashcards.
"""

import asyncio
import binascii
import io
import json
import logging
import math
import os
import re
import tempfile
from typing import Any

import httpx

from .config import Settings

logger = logging.getLogger("media_explanation")

# Video prompt hard limit imposed by Minimax
VIDEO_PROMPT_MAX_CHARS = 2000

# Flashcards system prompt
FLASHCARDS_SYSTEM_PROMPT = (
    "You are an educational content creator. "
    "Given a trust-score analysis result, produce a JSON array of flashcards "
    "that teach why the content received that score. "
    "Each card is an object with exactly two string keys: \"front\" (a concise question or concept) "
    "and \"back\" (a clear, informative answer). "
    "Aim for 5-10 cards. "
    "Output ONLY the JSON array — no markdown, no code fences, no extra explanation."
)

# System prompt for script + video fragment prompts (new pipeline).
EXPLANATION_SCRIPT_AND_FRAGMENTS_SYSTEM_PROMPT = (
    "You are a clear and authoritative media-safety narrator and video director. "
    "Given a trust-score analysis result, produce exactly two things:\n"
    "1. A spoken-word narration script (about 30–60 seconds when read aloud, roughly 70–150 words) "
    "that explains why the media content is not safe to trust. Mention the trust score and the main red flags. "
    "Use plain, conversational language — no jargon.\n"
    "2. A list of 3–8 short text-to-video prompts. Each prompt describes one visual fragment for the video "
    "(e.g. 'News anchor at desk', 'Warning sign on screen', 'Graph showing trust metrics'). "
    "Each prompt should be one short sentence, suitable for an AI video generator. "
    "You MUST respond with ONLY a valid JSON object in this exact format, nothing else — no markdown, no code fences:\n"
    '{"script": "<your full narration text here>", "video_fragment_prompts": ["prompt 1", "prompt 2", "prompt 3", ...]}'
)


def _build_script(agent_response: dict[str, Any], user_prompt: str | None) -> str:
    """Compose a human-readable explanation script from the AgentRunResponse dict."""
    trust_score = agent_response.get("trust_score", "N/A")
    explanation = (agent_response.get("trust_score_explanation") or "").strip()

    parts = [f"Trust score: {trust_score} out of 100."]

    if explanation:
        parts.append(explanation)

    fake_facts = agent_response.get("fake_facts") or []
    if fake_facts:
        fact_texts = [f.get("explanation", "") for f in fake_facts if f.get("explanation")]
        if fact_texts:
            parts.append(f"False claims detected: {'; '.join(fact_texts[:3])}.")

    fake_media = agent_response.get("fake_media") or []
    if fake_media:
        parts.append(f"{len(fake_media)} media item(s) flagged as potentially AI-generated or deepfake.")

    ai_text_score = agent_response.get("ai_text_score")
    if ai_text_score is not None:
        pct = round(ai_text_score * 100)
        parts.append(f"AI-generated text likelihood: {pct}%.")

    cs = agent_response.get("content_safety")
    if cs:
        flags = []
        if cs.get("pil", 0) >= 0.5:
            flags.append("privacy leakage")
        if cs.get("harmful", 0) >= 0.5:
            flags.append("harmful content")
        if cs.get("unwanted", 0) >= 0.5:
            flags.append("unwanted connections")
        if flags:
            parts.append(f"Content safety flags: {', '.join(flags)}.")

    if user_prompt:
        parts.append(f"Additional context: {user_prompt.strip()}")

    return " ".join(parts)


def _parse_json_from_content(content: str) -> Any:
    """
    Extract the first valid JSON object or array from an LLM response string.
    Handles reasoning-model <think>…</think> preambles, markdown fences,
    surrounding prose, and trailing text robustly.
    Raises ValueError if no valid JSON is found.
    """
    text = content.strip()
    # Reasoning models (e.g. MiniMax-M2.5) sometimes put the JSON *inside* the
    # <think> block. Remove only the tags themselves so the inner text is kept,
    # then let the bracket scanner find the JSON wherever it landed.
    text = re.sub(r"</?think>", "", text, flags=re.IGNORECASE).strip()
    # Try code-fence extraction first
    code_block = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if code_block:
        text = code_block.group(1).strip()
    # Try direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Bracket-depth scan: find the first complete JSON root in textual order.
    # Important: do not prefer '[' globally; objects often contain arrays.
    obj_i = text.find("{")
    arr_i = text.find("[")
    candidates = [idx for idx in (obj_i, arr_i) if idx != -1]
    if candidates:
        i = min(candidates)
        depth = 0
        for j in range(i, len(text)):
            if text[j] in "{[":
                depth += 1
            elif text[j] in "}]":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[i: j + 1])
                    except json.JSONDecodeError:
                        # Continue scanning for a later valid JSON root.
                        break

        for i2 in range(i + 1, len(text)):
            if text[i2] not in "{[":
                continue
            depth = 0
            for j in range(i2, len(text)):
                if text[j] in "{[":
                    depth += 1
                elif text[j] in "}]":
                    depth -= 1
                    if depth == 0:
                        try:
                            return json.loads(text[i2: j + 1])
                        except json.JSONDecodeError:
                            break
    raise ValueError(f"No valid JSON found in content (first 200 chars): {content[:200]!r}")


def _check_base_resp(data: dict[str, Any], label: str) -> None:
    """Raise ValueError if Minimax base_resp.status_code is non-zero."""
    base_resp = data.get("base_resp") or {}
    code = base_resp.get("status_code", 0)
    if code != 0:
        raise ValueError(
            f"Minimax {label} API error: status_code={code} status_msg={base_resp.get('status_msg')!r}"
        )


def _coerce_llm_content_to_text(content: Any) -> str:
    """
    Normalize LLM message content into plain text.
    Supports:
    - direct string content
    - list content blocks like [{"type":"text","text":"..."}]
    - any scalar fallback via str()
    """
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        chunks: list[str] = []
        for item in content:
            if isinstance(item, dict):
                text_val = item.get("text") or item.get("content") or item.get("value")
                if text_val:
                    chunks.append(str(text_val))
            elif item:
                chunks.append(str(item))
        return "\n".join(chunks).strip()
    return str(content)


def _normalize_video_fragment_prompts(raw_prompts: Any) -> list[str]:
    """Accept list/str prompt shapes and normalize to a cleaned string list."""
    if raw_prompts is None:
        return []

    if isinstance(raw_prompts, list):
        return [str(p).strip() for p in raw_prompts if str(p).strip()]

    if isinstance(raw_prompts, str):
        # Accept multiline/numbered prompt lists from imperfect LLM outputs.
        lines = [ln.strip() for ln in raw_prompts.splitlines() if ln.strip()]
        cleaned = []
        for ln in lines:
            ln = re.sub(r"^\s*(?:[-*]|\d+[.)])\s*", "", ln).strip()
            if ln:
                cleaned.append(ln)
        if cleaned:
            return cleaned
        as_one = raw_prompts.strip()
        return [as_one] if as_one else []

    raise ValueError(f"video_fragment_prompts must be an array or string, got {type(raw_prompts).__name__}")


def _is_known_minimax_music_prepare_error(err: Exception) -> bool:
    """
    Minimax status_code=2151 means backend music generation not ready/transient.
    This path is optional, so treat it as soft-skip without warning noise.
    """
    msg = str(err)
    return "status_code=2151" in msg or "音乐生成准备失败" in msg


# ---------------------------------------------------------------------------
# LLM explanation script and fragment prompts
# ---------------------------------------------------------------------------


async def generate_explanation_script_and_fragments(
    agent_response: dict[str, Any],
    user_prompt: str | None,
    settings: Settings,
) -> tuple[str, list[str]]:
    """
    Call Minimax chatcompletion_v2 to produce script + video_fragment_prompts.

    Returns (script, video_fragment_prompts). Raises ValueError on API/parse/invalid shape.
    """
    api_key = settings.minimax_api_key or ""
    base = settings.minimax_base_url.rstrip("/")
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    trust_score = agent_response.get("trust_score", "N/A")
    trust_explanation = (agent_response.get("trust_score_explanation") or "").strip()
    fake_facts = agent_response.get("fake_facts") or []
    fact_texts = [f.get("explanation", "") for f in fake_facts if f.get("explanation")]
    fake_media = agent_response.get("fake_media") or []
    ai_text_score = agent_response.get("ai_text_score")
    ai_pct = round(ai_text_score * 100) if ai_text_score is not None else None
    cs = agent_response.get("content_safety") or {}
    safety_flags = []
    if cs.get("pil", 0) >= 0.5:
        safety_flags.append("privacy leakage")
    if cs.get("harmful", 0) >= 0.5:
        safety_flags.append("harmful content")
    if cs.get("unwanted", 0) >= 0.5:
        safety_flags.append("unwanted connections")

    lines = [f"Trust score: {trust_score}/100."]
    if trust_explanation:
        lines.append(f"Analysis summary: {trust_explanation}")
    if fact_texts:
        lines.append(f"False claims detected: {'; '.join(fact_texts[:3])}.")
    if fake_media:
        lines.append(f"{len(fake_media)} media item(s) flagged as AI-generated or deepfake.")
    if ai_pct is not None:
        lines.append(f"AI-generated text likelihood: {ai_pct}%.")
    if safety_flags:
        lines.append(f"Content safety issues: {', '.join(safety_flags)}.")
    if user_prompt:
        lines.append(f"Additional context: {user_prompt.strip()}")

    user_message = "\n".join(lines)
    logger.info(
        "explain/video: Generating script+fragments via LLM (data_len=%s model=%s)",
        len(user_message), settings.minimax_text_model,
    )

    payload = {
        "model": settings.minimax_text_model,
        "messages": [
            {"role": "system", "content": EXPLANATION_SCRIPT_AND_FRAGMENTS_SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        "temperature": 0.5,
        "max_tokens": 1024,
    }

    async with httpx.AsyncClient(timeout=settings.explanation_script_timeout_seconds) as client:
        resp = await client.post(
            f"{base}/v1/text/chatcompletion_v2",
            headers=headers,
            json=payload,
        )
        if not resp.is_success:
            logger.error(
                "explain/video: LLM HTTP error status=%s body=%s",
                resp.status_code, resp.text[:500],
            )
            resp.raise_for_status()
        data = resp.json()

    _check_base_resp(data, "chatcompletion_v2 (script+fragments)")
    choices = data.get("choices") or []
    if not choices:
        raise ValueError("Minimax text returned no choices for script+fragments.")
    first_choice = choices[0]
    if "message" in first_choice:
        raw = (first_choice.get("message") or {}).get("content")
    else:
        raw = first_choice.get("text")
    raw_content = _coerce_llm_content_to_text(raw)
    if not raw_content:
        raise ValueError("Minimax text returned empty content for script+fragments.")

    message_content = re.sub(r"</?think>", "", raw_content, flags=re.IGNORECASE).strip()
    logger.info(
        "explain/video: LLM raw content len=%s first_200=%s",
        len(message_content), message_content[:200],
    )

    try:
        parsed = _parse_json_from_content(message_content)
    except (json.JSONDecodeError, ValueError) as exc:
        logger.error(
            "explain/video: Explanation script+fragments JSON parse failed. content_preview=%s",
            message_content[:300],
        )
        raise ValueError(
            f"LLM response did not contain valid JSON. Preview: {message_content[:200]!r}"
        ) from exc

    # LLM may return a single object or an array; extract the first usable object.
    if isinstance(parsed, list) and len(parsed) == 1 and isinstance(parsed[0], dict):
        parsed = parsed[0]
        logger.info("explain/video: LLM returned array with one object, using that object")
    elif isinstance(parsed, list):
        picked = None
        for item in parsed:
            if not isinstance(item, dict):
                continue
            if any(k in item for k in ("script", "narration_script", "narration", "voiceover_script")):
                picked = item
                break
        if picked is not None:
            parsed = picked
            logger.info("explain/video: LLM returned array; selected first object containing script keys")
    if not isinstance(parsed, dict):
        raise ValueError(f"Expected JSON object for script+fragments, got {type(parsed).__name__}")

    script = (
        parsed.get("script")
        or parsed.get("narration_script")
        or parsed.get("narration")
        or parsed.get("voiceover_script")
        or ""
    )
    script = str(script).strip()
    if not script:
        raise ValueError("LLM JSON missing or empty 'script' field.")

    raw_prompts = (
        parsed.get("video_fragment_prompts")
        or parsed.get("fragment_prompts")
        or parsed.get("video_prompts")
        or parsed.get("visual_prompts")
        or parsed.get("prompts")
        or []
    )
    video_fragment_prompts = _normalize_video_fragment_prompts(raw_prompts)

    logger.info(
        "explain/video: script word_count=%s chars=%s first_100=%s",
        len(script.split()), len(script), script[:100],
    )
    logger.info(
        "explain/video: video_fragment_prompts count=%s prompts=%s",
        len(video_fragment_prompts),
        [p[:50] + ("..." if len(p) > 50 else "") for p in video_fragment_prompts],
    )
    return script, video_fragment_prompts


# ---------------------------------------------------------------------------
# Static frame for the explanation video
# ---------------------------------------------------------------------------

def _create_explanation_frame(trust_score: int | None = None) -> bytes:
    """
    Generate a 1280x720 PNG frame used as the visual background for the explanation video.
    Uses Pillow to draw a branded safety-warning card with optional trust-score meter.
    """
    from PIL import Image, ImageDraw, ImageFont  # type: ignore[import]

    W, H = 1280, 720
    img = Image.new("RGB", (W, H), color=(13, 17, 35))
    draw = ImageDraw.Draw(img)

    # Gradient-like header band (solid dark red)
    draw.rectangle([(0, 0), (W, 90)], fill=(160, 25, 25))
    # Thin accent line under header
    draw.rectangle([(0, 90), (W, 96)], fill=(220, 50, 50))

    # Load scalable fonts; fall back gracefully for older Pillow versions
    try:
        font_title = ImageFont.load_default(size=52)
        font_sub = ImageFont.load_default(size=30)
        font_body = ImageFont.load_default(size=22)
        font_small = ImageFont.load_default(size=18)
    except TypeError:
        font_title = ImageFont.load_default()
        font_sub = font_title
        font_body = font_title
        font_small = font_title

    # Header label
    draw.text((40, 24), "\u26a0  MEDIA SAFETY WARNING", fill=(255, 255, 255), font=font_sub)

    # Main title
    draw.text((40, 120), "Why This Content Is Not Safe", fill=(255, 80, 80), font=font_title)

    # Divider
    draw.rectangle([(40, 192), (W - 40, 196)], fill=(80, 30, 30))

    # Trust score section
    if trust_score is not None:
        score_color = (
            (220, 60, 60) if trust_score < 40
            else (220, 170, 50) if trust_score < 65
            else (80, 200, 80)
        )
        draw.text((40, 218), f"Trust Score: {trust_score} / 100", fill=score_color, font=font_sub)

        # Background track
        track_x0, track_y0, track_x1, track_y1 = 40, 268, W - 40, 298
        draw.rectangle([(track_x0, track_y0), (track_x1, track_y1)], fill=(40, 40, 60))
        # Filled portion
        fill_x1 = int(track_x0 + (track_x1 - track_x0) * (trust_score / 100))
        draw.rectangle([(track_x0, track_y0), (fill_x1, track_y1)], fill=score_color)
        draw.text((40, 312), "Low trust — content may be misleading or fabricated.", fill=(180, 180, 200), font=font_body)
    else:
        draw.text((40, 218), "Trust score unavailable.", fill=(180, 180, 200), font=font_sub)

    # Body copy
    body_y = 370 if trust_score is not None else 280
    draw.text(
        (40, body_y),
        "Our AI analysis detected red flags in this content.",
        fill=(210, 210, 225),
        font=font_body,
    )
    draw.text(
        (40, body_y + 36),
        "It may contain false facts, AI-generated media, or harmful material.",
        fill=(210, 210, 225),
        font=font_body,
    )
    draw.text(
        (40, body_y + 72),
        "Always verify information from trusted sources before sharing.",
        fill=(160, 160, 180),
        font=font_body,
    )

    # Footer band
    draw.rectangle([(0, H - 56), (W, H)], fill=(22, 26, 50))
    draw.rectangle([(0, H - 56), (W, H - 52)], fill=(50, 55, 90))
    draw.text((40, H - 36), "Powered by HTE Trust Analysis", fill=(130, 135, 165), font=font_small)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf.read()


# ---------------------------------------------------------------------------
# Helpers for pipeline
# ---------------------------------------------------------------------------

async def _ffprobe_duration(audio_path: str) -> float:
    """Return duration in seconds of an audio file. Raises ValueError on failure."""
    probe_cmd = [
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", audio_path,
    ]
    proc = await asyncio.create_subprocess_exec(
        *probe_cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        err_msg = (stderr or stdout).decode("utf-8", errors="replace")[:300]
        logger.error("explain/video: ffprobe failed (exit %s): %s", proc.returncode, err_msg)
        raise ValueError(f"ffprobe failed (exit {proc.returncode}): {err_msg[:200]}")
    duration_str = stdout.decode("utf-8", errors="replace").strip()
    try:
        return float(duration_str)
    except (ValueError, TypeError) as e:
        raise ValueError(f"Could not parse audio duration from ffprobe: {duration_str!r}") from e


async def _run_ffmpeg(args: list[str], timeout: float = 120.0) -> None:
    """Run ffmpeg with given args (without the 'ffmpeg' binary name). Raises ValueError on failure."""
    cmd = ["ffmpeg", "-y"] + args
    logger.info("explain/video: ffmpeg args: %s", " ".join(cmd[:12]) + ("..." if len(cmd) > 12 else ""))
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        _, stderr_bytes = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        raise ValueError(f"ffmpeg timed out after {timeout}s")
    if proc.returncode != 0:
        err_msg = stderr_bytes.decode("utf-8", errors="replace")[:500]
        logger.error("explain/video: ffmpeg failed (exit %s): %s", proc.returncode, err_msg)
        raise ValueError(f"ffmpeg failed (exit {proc.returncode}): {err_msg[:300]}")


# ---------------------------------------------------------------------------
# Pipeline: script + fragments + music -> final MP4
# ---------------------------------------------------------------------------

async def generate_video_with_audio_and_fragments(
    script: str,
    fragment_prompts: list[str],
    settings: Settings,
    trust_score: int | None = None,
) -> bytes:
    """
    Generate narration audio first, then video fragments (or static frame if no prompts),
    optional background music, then assemble into one MP4.
    """
    logger.info(
        "explain/video: pipeline start script_words=%s fragment_prompts=%s",
        len(script.split()), len(fragment_prompts),
    )
    audio_bytes = await generate_audio(script, settings)
    logger.info("explain/video: narration audio ready (%s bytes)", len(audio_bytes))

    with tempfile.TemporaryDirectory() as tmpdir:
        audio_path = os.path.join(tmpdir, "audio.mp3")
        with open(audio_path, "wb") as fh:
            fh.write(audio_bytes)
        audio_duration_sec = await _ffprobe_duration(audio_path)
        if audio_duration_sec <= 0:
            raise ValueError(f"Invalid audio duration: {audio_duration_sec}")
        logger.info("explain/video: audio_duration_sec=%.2f", audio_duration_sec)

        # Step B: background music (optional)
        music_path: str | None = None
        if settings.background_music_path:
            raw = settings.background_music_path.strip()
            try:
                if raw.startswith(("http://", "https://")):
                    async with httpx.AsyncClient(timeout=30.0) as c:
                        r = await c.get(raw)
                    r.raise_for_status()
                    music_bytes = r.content
                else:
                    with open(raw, "rb") as fh:
                        music_bytes = fh.read()
                raw_music_path = os.path.join(tmpdir, "music_raw.mp3")
                with open(raw_music_path, "wb") as fh:
                    fh.write(music_bytes)
                music_path = os.path.join(tmpdir, "music.mp3")
                await _run_ffmpeg([
                    "-i", raw_music_path, "-t", str(audio_duration_sec),
                    "-af", "volume=0.2", music_path,
                ], timeout=60.0)
                logger.info("explain/video: background music ready (duration=%.2fs volume=0.2)", audio_duration_sec)
            except Exception as e:
                logger.warning("explain/video: background music load failed, skipping: %s", e)
                music_path = None
        else:
            # Generate background music via Minimax music-2.5
            try:
                music_bytes = await generate_background_music(settings)
                raw_music_path = os.path.join(tmpdir, "music_raw.mp3")
                with open(raw_music_path, "wb") as fh:
                    fh.write(music_bytes)
                music_path = os.path.join(tmpdir, "music.mp3")
                await _run_ffmpeg([
                    "-i", raw_music_path, "-t", str(audio_duration_sec),
                    "-af", "volume=0.2", music_path,
                ], timeout=60.0)
                logger.info("explain/video: Minimax background music ready (duration=%.2fs volume=0.2)", audio_duration_sec)
            except Exception as e:
                if _is_known_minimax_music_prepare_error(e):
                    logger.info(
                        "explain/video: Minimax background music temporarily unavailable, continuing without it: %s",
                        e,
                    )
                else:
                    logger.warning("explain/video: Minimax background music generation failed, skipping: %s", e)
                music_path = None

        # Step C: video (fragments or single static frame)
        clip_duration_sec = 6
        video_only_path = os.path.join(tmpdir, "video_only.mp4")

        if fragment_prompts:
            n_clips = min(
                math.ceil(audio_duration_sec / clip_duration_sec),
                len(fragment_prompts),
                getattr(settings, "max_video_fragments", 10),
            )
            n_clips = max(1, n_clips)
            max_parallel = max(1, min(getattr(settings, "max_parallel_video_generations", 3), n_clips))
            logger.info(
                "explain/video: generating %s video clips in parallel=%s (audio_duration=%.2fs)",
                n_clips,
                max_parallel,
                audio_duration_sec,
            )

            clip_paths: list[str] = ["" for _ in range(n_clips)]
            sem = asyncio.Semaphore(max_parallel)

            async def _generate_one_clip(i: int) -> None:
                prompt = fragment_prompts[i] if i < len(fragment_prompts) else fragment_prompts[-1]
                prompt = (prompt or "neutral broadcast background")[:VIDEO_PROMPT_MAX_CHARS]
                logger.info("explain/video: clip %s/%s prompt=%s", i + 1, n_clips, prompt[:60])
                async with sem:
                    clip_bytes = await generate_video_clip(prompt, clip_duration_sec, settings)
                clip_path = os.path.join(tmpdir, f"clip_{i}.mp4")
                with open(clip_path, "wb") as fh:
                    fh.write(clip_bytes)
                clip_paths[i] = clip_path

            await asyncio.gather(*(_generate_one_clip(i) for i in range(n_clips)))
            last_duration = audio_duration_sec - (n_clips - 1) * clip_duration_sec
            if last_duration < clip_duration_sec and last_duration > 0 and n_clips > 0:
                last_path = clip_paths[-1]
                trimmed_path = os.path.join(tmpdir, "clip_last_trimmed.mp4")
                await _run_ffmpeg(["-i", last_path, "-t", str(last_duration), "-c", "copy", trimmed_path], timeout=30.0)
                clip_paths[-1] = trimmed_path
            concat_list_path = os.path.join(tmpdir, "concat_list.txt")
            with open(concat_list_path, "w", encoding="utf-8") as fh:
                for p in clip_paths:
                    # FFmpeg concat: file 'path' (use forward slashes; escape single quotes)
                    p_esc = p.replace("\\", "/").replace("'", "'\\''")
                    fh.write(f"file '{p_esc}'\n")
            await _run_ffmpeg([
                "-f", "concat", "-safe", "0", "-i", concat_list_path,
                "-c", "copy", video_only_path,
            ], timeout=90.0)
            logger.info("explain/video: video_only assembled (%s clips)", n_clips)
        else:
            frame_bytes = _create_explanation_frame(trust_score=trust_score)
            frame_path = os.path.join(tmpdir, "frame.png")
            with open(frame_path, "wb") as fh:
                fh.write(frame_bytes)
            await _run_ffmpeg([
                "-loop", "1", "-framerate", "1", "-t", str(audio_duration_sec),
                "-i", frame_path, "-c:v", "libx264", "-tune", "stillimage",
                "-pix_fmt", "yuv420p", video_only_path,
            ], timeout=60.0)
            logger.info("explain/video: static frame video_only (duration=%.2fs)", audio_duration_sec)

        # Step D: mix voice + music (if any), then mux video + mixed audio
        mixed_path = os.path.join(tmpdir, "mixed.mp3")
        if music_path:
            await _run_ffmpeg([
                "-i", audio_path, "-i", music_path,
                "-filter_complex", "[0:a]volume=1[a0];[1:a]volume=0.2[a1];[a0][a1]amix=inputs=2:duration=first",
                "-ac", "1", mixed_path,
            ], timeout=60.0)
        else:
            mixed_path = audio_path
        final_path = os.path.join(tmpdir, "final.mp4")
        await _run_ffmpeg([
            "-i", video_only_path, "-i", mixed_path,
            "-c:v", "copy", "-c:a", "aac", "-b:a", "128k", "-shortest", final_path,
        ], timeout=60.0)
        with open(final_path, "rb") as fh:
            mp4_bytes = fh.read()
    logger.info("explain/video: pipeline done MP4 size=%s bytes", len(mp4_bytes))
    return mp4_bytes


# ---------------------------------------------------------------------------
# Video (Minimax text-to-video, kept for reference / future use)
# ---------------------------------------------------------------------------

async def generate_video_clip(prompt: str, duration_sec: int, settings: Settings) -> bytes:
    """
    Generate a single video clip from a text prompt. duration_sec should be 6 or 10 (10 only for some models at 768P).
    Raises ValueError on Minimax API errors; asyncio.TimeoutError if the task does not finish.
    """
    return await generate_video(prompt, settings, duration_sec=duration_sec)


async def generate_video(script: str, settings: Settings, duration_sec: int = 6) -> bytes:
    """
    Submit a text-to-video task to Minimax, poll until complete, then download and return the video bytes.
    duration_sec: 6 or 10 (10 supported for Hailuo models at 768P).
    Raises ValueError on Minimax API errors.
    Raises asyncio.TimeoutError if the task does not finish within the poll timeout.
    """
    api_key = settings.minimax_api_key or ""
    base = settings.minimax_base_url.rstrip("/")
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    prompt = script[:VIDEO_PROMPT_MAX_CHARS]
    duration_sec = 6 if duration_sec not in (6, 10) else duration_sec

    # Resolution rules (Minimax):
    #   MiniMax-Hailuo-2.3 / MiniMax-Hailuo-02  → 768P (default) or 1080P
    #   T2V-01-Director / T2V-01                 → 720P (default)
    hailuo_models = {"minimax-hailuo-2.3", "minimax-hailuo-02"}
    resolution = "768P" if settings.minimax_video_model.lower() in hailuo_models else "720P"

    logger.info(
        "explain/video: Submitting video clip task (prompt_len=%s duration=%s model=%s resolution=%s)",
        len(prompt), duration_sec, settings.minimax_video_model, resolution,
    )
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            f"{base}/v1/video_generation",
            headers=headers,
            json={
                "model": settings.minimax_video_model,
                "prompt": prompt,
                "duration": duration_sec,
                "resolution": resolution,
            },
        )
        if not resp.is_success:
            logger.error("Minimax video_generation HTTP error: status=%s body=%s", resp.status_code, resp.text[:500])
            resp.raise_for_status()
        data = resp.json()

    logger.info("Minimax video_generation response: base_resp=%s task_id=%s", data.get("base_resp"), data.get("task_id"))
    _check_base_resp(data, "video_generation")
    task_id = data.get("task_id")
    if not task_id:
        raise ValueError(f"Minimax video_generation returned no task_id. Full response: {data}")

    logger.info("Video task submitted: task_id=%s", task_id)

    # Poll for completion
    deadline = asyncio.get_event_loop().time() + settings.video_poll_timeout_seconds
    interval = settings.video_poll_interval_seconds
    file_id: str | None = None
    qdata: dict = {}

    async with httpx.AsyncClient(timeout=30.0) as client:
        while True:
            remaining = deadline - asyncio.get_event_loop().time()
            if remaining <= 0:
                raise asyncio.TimeoutError(
                    f"Video task {task_id} did not complete within {settings.video_poll_timeout_seconds}s"
                )

            await asyncio.sleep(min(interval, remaining))

            query_resp = await client.get(
                f"{base}/v1/query/video_generation",
                headers=headers,
                params={"task_id": task_id},
            )
            if not query_resp.is_success:
                logger.error("Minimax query HTTP error: status=%s body=%s", query_resp.status_code, query_resp.text[:300])
                query_resp.raise_for_status()
            qdata = query_resp.json()
            status = qdata.get("status", "")
            logger.info("Video task status: task_id=%s status=%s", task_id, status)

            if status == "Success":
                file_id = qdata.get("file_id")
                break
            elif status in ("Fail", "Failed"):
                raise ValueError(f"Minimax video task failed: task_id={task_id} response={qdata}")
            # else: Preparing / Queueing / Processing — keep polling

    if not file_id:
        raise ValueError(f"Video task succeeded but no file_id returned: {qdata}")

    logger.info("Video task complete: task_id=%s file_id=%s", task_id, file_id)

    # Retrieve download URL
    async with httpx.AsyncClient(timeout=30.0) as client:
        file_resp = await client.get(
            f"{base}/v1/files/retrieve",
            headers=headers,
            params={"file_id": file_id},
        )
        if not file_resp.is_success:
            logger.error("Minimax files/retrieve HTTP error: status=%s body=%s", file_resp.status_code, file_resp.text[:300])
            file_resp.raise_for_status()
        fdata = file_resp.json()

    # Minimax returns: {"file": {"download_url": "..."}} or flat {"download_url": "..."}
    download_url = (fdata.get("file") or {}).get("download_url") or fdata.get("download_url")
    if not download_url:
        raise ValueError(f"Minimax files/retrieve returned no download_url. Full response: {fdata}")

    logger.info("Downloading video from: %s", download_url[:80])
    async with httpx.AsyncClient(timeout=120.0) as client:
        video_resp = await client.get(download_url)
        if not video_resp.is_success:
            logger.error("Video download HTTP error: status=%s", video_resp.status_code)
            video_resp.raise_for_status()
        return video_resp.content


# ---------------------------------------------------------------------------
# Audio
# ---------------------------------------------------------------------------

async def generate_audio(script: str, settings: Settings) -> bytes:
    """
    Call Minimax T2A v2 HTTP API; return mp3 audio bytes.
    Minimax T2A v2 response: {"data": {"audio": "<hex>", "status": 2}, "base_resp": {...}}
    Raises ValueError on Minimax API errors.
    """
    api_key = settings.minimax_api_key or ""
    base = settings.minimax_base_url.rstrip("/")
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    logger.info(
        "explain/audio: Generating TTS script_len=%s words=%s first_80=%s model=%s voice=%s",
        len(script), len(script.split()), script[:80] if script else "",
        settings.minimax_audio_model, settings.minimax_audio_voice_id,
    )

    payload = {
        "model": settings.minimax_audio_model,
        "text": script,
        "stream": False,
        "voice_setting": {
            "voice_id": settings.minimax_audio_voice_id,
            "speed": 1.0,
            "vol": 1.0,
            "pitch": 0,
        },
        "audio_setting": {
            "sample_rate": 32000,
            "bitrate": 128000,
            "format": "mp3",
        },
    }

    async with httpx.AsyncClient(timeout=settings.audio_timeout_seconds) as client:
        resp = await client.post(f"{base}/v1/t2a_v2", headers=headers, json=payload)
        if not resp.is_success:
            logger.error("Minimax T2A HTTP error: status=%s body=%s", resp.status_code, resp.text[:500])
            resp.raise_for_status()
        data = resp.json()

    logger.debug("Minimax T2A raw response keys: %s", list(data.keys()))
    _check_base_resp(data, "T2A")

    # Response: {"data": {"audio": "<hex_string>", "status": 2}, ...}
    inner = data.get("data") or {}
    audio_hex: str = inner.get("audio", "")
    if not audio_hex:
        logger.error("Minimax T2A response missing audio field. data keys=%s inner keys=%s", list(data.keys()), list(inner.keys()))
        raise ValueError(
            f"Minimax T2A returned no audio data. Top-level keys: {list(data.keys())}, "
            f"data keys: {list(inner.keys())}"
        )

    logger.info("explain/audio: TTS response received hex_len=%s", len(audio_hex))
    try:
        decoded = binascii.unhexlify(audio_hex)
        logger.info("explain/audio: decoded bytes=%s", len(decoded))
        return decoded
    except (binascii.Error, ValueError) as e:
        raise ValueError(f"Failed to decode Minimax T2A audio hex: {e}") from e


# ---------------------------------------------------------------------------
# Background music (Minimax music-2.5)
# ---------------------------------------------------------------------------

async def generate_background_music(settings: Settings) -> bytes:
    """
    Call Minimax music_generation API (music-2.5) to generate instrumental background music.
    Returns mp3 bytes. Raises ValueError on API errors.
    """
    api_key = settings.minimax_api_key or ""
    base = settings.minimax_base_url.rstrip("/")
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    payload = {
        "model": "music-2.5",
        "prompt": "Calm instrumental background music, no vocals, soft and low volume for narration underlay.",
        "lyrics": "[Inst]\n[Instrumental]",
        "stream": False,
        "output_format": "hex",
        "audio_setting": {
            "sample_rate": 32000,
            "bitrate": 128000,
            "format": "mp3",
        },
    }

    logger.info("explain/video: Generating background music via Minimax music-2.5")
    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(f"{base}/v1/music_generation", headers=headers, json=payload)
        if not resp.is_success:
            logger.error(
                "explain/video: Minimax music_generation HTTP error: status=%s body=%s",
                resp.status_code, resp.text[:500],
            )
            resp.raise_for_status()
        data = resp.json()

    _check_base_resp(data, "music_generation")
    inner = data.get("data") or {}
    status = inner.get("status", 0)
    if status != 2:
        raise ValueError(f"Minimax music_generation not completed: status={status}")
    audio_hex: str = inner.get("audio", "")
    if not audio_hex:
        raise ValueError("Minimax music_generation returned no audio data.")
    try:
        decoded = binascii.unhexlify(audio_hex)
        logger.info("explain/video: background music generated (%s bytes)", len(decoded))
        return decoded
    except (binascii.Error, ValueError) as e:
        raise ValueError(f"Failed to decode Minimax music hex: {e}") from e


# ---------------------------------------------------------------------------
# Flashcards
# ---------------------------------------------------------------------------

async def generate_flashcards(script: str, user_prompt: str | None, settings: Settings) -> list[dict]:
    """
    Call Minimax text/chatcompletion_v2 to generate flashcards as [{front, back}].
    Raises ValueError on Minimax API or parse errors.
    """
    api_key = settings.minimax_api_key or ""
    base = settings.minimax_base_url.rstrip("/")
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    user_message = script
    if user_prompt:
        user_message += f"\n\nAdditional user request: {user_prompt.strip()}"

    logger.info("Generating flashcards (text_len=%s model=%s)", len(user_message), settings.minimax_text_model)

    payload = {
        "model": settings.minimax_text_model,
        "messages": [
            {"role": "system", "content": FLASHCARDS_SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        "temperature": 0.3,
        "max_tokens": 2048,
    }

    async with httpx.AsyncClient(timeout=settings.flashcards_timeout_seconds) as client:
        resp = await client.post(
            f"{base}/v1/text/chatcompletion_v2",
            headers=headers,
            json=payload,
        )
        if not resp.is_success:
            logger.error("Minimax flashcards HTTP error: status=%s body=%s", resp.status_code, resp.text[:500])
            resp.raise_for_status()
        data = resp.json()

    logger.debug("Minimax flashcards raw response keys: %s", list(data.keys()))
    _check_base_resp(data, "chatcompletion_v2")

    choices = data.get("choices") or []
    if not choices:
        logger.error("Minimax flashcards: no choices. Full response: %s", str(data)[:500])
        raise ValueError(f"Minimax text returned no choices. Response keys: {list(data.keys())}")

    first_choice = choices[0]
    # Handle both {message: {content: "..."}} and {text: "..."} shapes
    if "message" in first_choice:
        content = (first_choice.get("message") or {}).get("content") or ""
    else:
        content = first_choice.get("text") or ""

    if not content:
        logger.error("Minimax flashcards: empty content. choice=%s", first_choice)
        raise ValueError(f"Minimax text returned empty content. Choice keys: {list(first_choice.keys())}")

    logger.info("Flashcards raw content received (len=%s)", len(content))

    try:
        parsed = _parse_json_from_content(content)
    except (json.JSONDecodeError, ValueError) as e:
        logger.error("Flashcards JSON parse failed. content=%s", content[:300])
        raise ValueError(f"Failed to parse flashcards JSON: {e}") from e

    if not isinstance(parsed, list):
        raise ValueError(f"Expected JSON array for flashcards, got {type(parsed).__name__}: {str(parsed)[:200]}")

    cards = []
    for item in parsed:
        if isinstance(item, dict) and "front" in item and "back" in item:
            cards.append({"front": str(item["front"]), "back": str(item["back"])})

    logger.info("Flashcards generated: count=%s", len(cards))
    return cards
