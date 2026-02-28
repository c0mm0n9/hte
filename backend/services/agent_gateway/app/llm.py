"""
Featherless AI (OpenAI-compatible) chat completions client.
"""

import json
import logging
import re
from typing import Any

import httpx

from .config import Settings

logger = logging.getLogger("agent_gateway")


async def chat_completions(
    settings: Settings,
    *,
    system_prompt: str | None = None,
    user_message: str,
    model: str | None = None,
) -> str:
    """
    POST to Featherless chat/completions; return assistant message content.
    Uses settings.llm_base_url, settings.llm_api_key, settings.llm_timeout_seconds.
    """
    base = (settings.llm_base_url or "").rstrip("/")
    if not base:
        raise ValueError("AGENT_GATEWAY_LLM_BASE_URL is not set")
    url = f"{base}/chat/completions"
    model_name = model or settings.llm_model
    logger.info("LLM request url=%s model=%s user_message_len=%s", url, model_name, len(user_message))
    payload: dict[str, Any] = {
        "model": model_name,
        "messages": [],
        "max_tokens": 4096,
    }
    if system_prompt is not None and system_prompt:
        payload["messages"].append({"role": "system", "content": system_prompt})
    payload["messages"].append({"role": "user", "content": user_message})

    headers: dict[str, str] = {"Content-Type": "application/json"}
    if settings.llm_api_key:
        headers["Authorization"] = f"Bearer {settings.llm_api_key}"

    try:
        async with httpx.AsyncClient(timeout=settings.llm_timeout_seconds) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
        data = resp.json()
        choices = data.get("choices") or []
        if not choices:
            logger.warning("LLM response had no choices")
            return ""
        content = choices[0].get("message", {}).get("content") or ""
        logger.info("LLM response content_len=%s", len(content))
        logger.info("LLM response text:\n%s", content.strip() or "(empty)")
        return content.strip()
    except httpx.HTTPStatusError as e:
        logger.error("LLM HTTP error status=%s response=%s", e.response.status_code, e.response.text[:500])
        raise
    except Exception as e:
        logger.error("LLM request failed: %s", e)
        raise


def parse_json_from_content(content: str) -> Any:
    """
    Extract JSON from LLM response (may be wrapped in markdown or text).
    Returns parsed object or raises ValueError.
    """
    text = content.strip()
    # Try to find ```json ... ``` or ``` ... ```
    code_block = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if code_block:
        text = code_block.group(1).strip()
    # Try parse as-is
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Try to find first [ or { and parse from there
    for start_char in ("[", "{"):
        i = text.find(start_char)
        if i == -1:
            continue
        depth = 0
        for j in range(i, len(text)):
            if text[j] in "{[":
                depth += 1
            elif text[j] in "}]":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[i : j + 1])
                    except json.JSONDecodeError:
                        break
        break
    raise ValueError("No valid JSON found in LLM response")
