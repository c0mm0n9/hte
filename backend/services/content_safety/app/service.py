"""
Content safety classifier: PIL, harmful, unwanted connection risk scores via MiniMax 2.5.
"""

import logging
from typing import Any

from .config import Settings
from .llm import chat_completions, parse_json_from_content
from .schemas import ContentSafetyResponse

logger = logging.getLogger("content_safety")

# Truncate website text to stay within context (e.g. ~12k chars)
MAX_TEXT_LENGTH = 12_000

CONTENT_SAFETY_SYSTEM_PROMPT = """You are a content-safety classifier. Given website or page text, output ONLY a valid JSON object with exactly these three keys and no other keys:
- "pil": risk score 0.0 to 1.0 for Privacy Information Leakage (PII, personal data, sensitive identifiers exposed in the text)
- "harmful": risk score 0.0 to 1.0 for harmful content (violence, hate speech, illegal content, self-harm, dangerous advice)
- "unwanted": risk score 0.0 to 1.0 for unwanted connection types (predators, scammers, fraud, grooming, exploitation, deceptive contact)

Use 0.0 for no risk, 1.0 for high/clear risk. Use decimals (e.g. 0.3, 0.7) for partial risk.
Output ONLY the JSON object. No markdown, no code fences, no explanation."""


def _clamp_score(value: Any) -> float:
    """Return float in [0, 1]; invalid values become 0.0."""
    if value is None:
        return 0.0
    try:
        f = float(value)
        return max(0.0, min(1.0, f))
    except (TypeError, ValueError):
        return 0.0


async def check_content_safety(website_text: str, settings: Settings) -> ContentSafetyResponse:
    """
    Call MiniMax to get pil/harmful/unwanted scores; parse, validate, and return.
    """
    text = (website_text or "").strip()
    if not text:
        raise ValueError("website_text must not be empty")
    if len(text) > MAX_TEXT_LENGTH:
        text = text[:MAX_TEXT_LENGTH] + "\n[... truncated]"
    logger.info("Checking content safety for text_len=%s", len(text))

    content = await chat_completions(
        settings,
        system_prompt=CONTENT_SAFETY_SYSTEM_PROMPT,
        user_message=text,
    )
    if not content:
        logger.warning("LLM returned empty content")
        return ContentSafetyResponse(pil=0.0, harmful=0.0, unwanted=0.0)

    try:
        parsed = parse_json_from_content(content)
    except ValueError as e:
        logger.warning("Failed to parse LLM JSON: %s", e)
        return ContentSafetyResponse(pil=0.0, harmful=0.0, unwanted=0.0)

    if not isinstance(parsed, dict):
        logger.warning("Parsed response was not a dict: %s", type(parsed).__name__)
        return ContentSafetyResponse(pil=0.0, harmful=0.0, unwanted=0.0)

    pil = _clamp_score(parsed.get("pil"))
    harmful = _clamp_score(parsed.get("harmful"))
    unwanted = _clamp_score(parsed.get("unwanted"))
    logger.info("Content safety scores: pil=%s harmful=%s unwanted=%s", pil, harmful, unwanted)
    return ContentSafetyResponse(pil=pil, harmful=harmful, unwanted=unwanted)
