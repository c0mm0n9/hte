import httpx
from typing import List, Optional, Tuple

from .settings import Settings


async def fact_check(fact: str, settings: Settings) -> Optional[dict]:
    """Call fact-checking service. Returns dict with truth_value, explanation, provider or None on error."""
    url = f"{settings.fact_check_base_url.rstrip('/')}/v1/fact/check"
    try:
        async with httpx.AsyncClient(timeout=settings.fact_check_timeout_seconds) as client:
            r = await client.post(url, json={"fact": fact})
            r.raise_for_status()
            return r.json()
    except Exception:
        return None


async def media_check(media_url: str, settings: Settings) -> Optional[dict]:
    """Call media-checking service by URL. Returns dict with media_type, chunks, etc."""
    url = f"{settings.media_check_base_url.rstrip('/')}/v1/media/check"
    try:
        async with httpx.AsyncClient(timeout=settings.media_check_timeout_seconds) as client:
            r = await client.post(url, json={"media_url": media_url})
            r.raise_for_status()
            return r.json()
    except Exception:
        return None


async def media_check_upload(
    settings: Settings,
    file_bytes: bytes,
    filename: str,
    content_type: str,
) -> Optional[dict]:
    """Call media-checking service with uploaded file. Returns dict with media_type, chunks, etc."""
    upload_url = f"{settings.media_check_base_url.rstrip('/')}/v1/media/check/upload"
    try:
        async with httpx.AsyncClient(timeout=settings.media_check_timeout_seconds) as client:
            r = await client.post(
                upload_url,
                files={"file": (filename, file_bytes, content_type)},
            )
            r.raise_for_status()
            return r.json()
    except Exception:
        return None


def _format_media_verdict(url_or_name: str, data: Optional[dict]) -> str:
    if not data:
        return "could not be classified"
    chunks = data.get("chunks") or []
    labels = [c.get("label") for c in chunks if c.get("label")]
    ai_scores = [c.get("ai_generated_score") for c in chunks if c.get("ai_generated_score") is not None]
    if labels:
        if any(l in ("ai_generated", "deepfake") for l in labels):
            return "likely AI-generated or synthetic"
        return "does not appear to be AI-generated"
    if ai_scores:
        avg = sum(ai_scores) / len(ai_scores)
        return "likely AI-generated" if avg >= 0.5 else "likely not AI-generated"
    return "could not be classified"


async def build_analyze_reply(
    masked_text: str,
    message: str,
    page_url: str,
    send_fact_check: bool,
    send_media_check: bool,
    uploaded_files: List[Tuple[bytes, str, str]],
    video_urls: List[str],
    settings: Settings,
    media_urls: Optional[List[str]] = None,
) -> str:
    """Build reply from masked text (fact check) and uploaded/URL media (media_check)."""
    parts = []
    media_urls = media_urls or []

    if send_fact_check:
        text = (masked_text or "").strip()
        if text:
            result = await fact_check(text, settings)
            if result:
                truth = result.get("truth_value", None)
                explanation = result.get("explanation", "") or "No explanation provided."
                if truth is True:
                    parts.append(f"**Fact check:** The content appears to be accurate or supported. {explanation}")
                elif truth is False:
                    parts.append(f"**Fact check:** The content may not be accurate. {explanation}")
                else:
                    parts.append(f"**Fact check:** {explanation}")
            else:
                parts.append("**Fact check:** The fact-checking service is temporarily unavailable.")
        else:
            parts.append("**Fact check:** No page text was received. Reload the page and try again.")

    if send_media_check:
        media_results = []
        for file_bytes, filename, content_type in uploaded_files:
            data = await media_check_upload(settings, file_bytes, filename, content_type)
            verdict = _format_media_verdict(filename, data)
            media_results.append((filename, verdict))
        seen = set()
        for url in (video_urls[:5] + list(media_urls))[:10]:
            if url in seen:
                continue
            seen.add(url)
            data = await media_check(url, settings)
            verdict = _format_media_verdict(url, data)
            label = url[:60] + "..." if len(url) > 60 else url
            media_results.append((label, verdict))
        if media_results:
            lines = ["**Media / AI-generated check:**"]
            for name, verdict in media_results:
                lines.append(f"- {name}: {verdict}")
            parts.append("\n".join(lines))
        else:
            parts.append("**Media check:** No images or videos were sent to check.")

    return "\n\n".join(parts) if parts else "Nothing to analyze. Enable fact check and/or media check and try again."


def _intent_is_fact(message: str) -> bool:
    m = message.lower().strip()
    return any(
        x in m
        for x in (
            "real",
            "true",
            "fact",
            "accurate",
            "correct",
            "trust",
            "believe",
            "fake news",
        )
    )


def _intent_is_ai_generated(message: str) -> bool:
    m = message.lower().strip()
    return any(
        x in m
        for x in (
            "ai",
            "generated",
            "deepfake",
            "fake",
            "synthetic",
            "computer",
            "real person",
        )
    )


async def build_agent_reply(
    message: str,
    page_url: str,
    media_urls: Optional[list[str]],
    settings: Settings,
    extracted_content: Optional[str] = None,
) -> str:
    parts = []
    want_fact = _intent_is_fact(message)
    want_ai = _intent_is_ai_generated(message)

    if not want_fact and not want_ai:
        want_fact = want_ai = True

    if want_fact:
        fact = (
            (extracted_content or "").strip()
            or message
            or f"Content at {page_url or 'this page'}"
        )
        if len(fact) > 20:
            result = await fact_check(fact, settings)
            if result:
                truth = result.get("truth_value", None)
                explanation = result.get("explanation", "") or "No explanation provided."
                if truth is True:
                    parts.append(f"**Fact check:** The content appears to be accurate or supported. {explanation}")
                elif truth is False:
                    parts.append(f"**Fact check:** The content may not be accurate. {explanation}")
                else:
                    parts.append(f"**Fact check:** {explanation}")
            else:
                parts.append(
                    "**Fact check:** The fact-checking service is temporarily unavailable. Try again later."
                )
        else:
            parts.append("**Fact check:** Not enough page content was extracted to check. Try opening a page with more text.")

    if want_ai and media_urls:
        ai_results = []
        for media_url in media_urls[:5]:
            data = await media_check(media_url, settings)
            if not data:
                ai_results.append((media_url, None))
                continue
            chunks = data.get("chunks") or []
            labels = [c.get("label") for c in chunks if c.get("label")]
            ai_scores = [c.get("ai_generated_score") for c in chunks if c.get("ai_generated_score") is not None]
            if labels:
                if any(l in ("ai_generated", "deepfake") for l in labels):
                    ai_results.append((media_url, "likely AI-generated or synthetic"))
                else:
                    ai_results.append((media_url, "does not appear to be AI-generated"))
            elif ai_scores:
                avg = sum(ai_scores) / len(ai_scores)
                ai_results.append(
                    (media_url, "likely AI-generated" if avg >= 0.5 else "likely not AI-generated")
                )
            else:
                ai_results.append((media_url, "could not be classified"))
        if ai_results:
            lines = ["**Media / AI-generated check:**"]
            for url, verdict in ai_results:
                short = url[:60] + "..." if len(url) > 60 else url
                lines.append(f"- {short}: {verdict}")
            parts.append("\n".join(lines))
    elif want_ai:
        parts.append(
            "**AI-generated check:** To check whether images or videos on this page are AI-generated, "
            "the extension can send their URLs. No media URLs were included for this message."
        )

    return "\n\n".join(parts) if parts else "I didn't understand. Try asking whether the content is real or whether it's AI-generated."
