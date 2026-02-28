"""
Agent gateway orchestration.

Flow:
1. LLM (Featherless) returns JSON array of actions.
2. Execute each action via API (ai_text_detector, media_checking, fact_checking; info_graph skeleton).
3. Second LLM call to get trust score 0-100.
4. Compile trust_score, fake_facts, fake_media into AgentRunResponse.
"""

import json
import logging
import re
from typing import Any

import httpx

from .config import Settings

logger = logging.getLogger("agent_gateway")
from .llm import chat_completions, parse_json_from_content
from .schemas import AgentRunResponse, FakeFact, FakeMediaChunk, FakeMediaItem


ACTIONS_SYSTEM_PROMPT = """You are a safety-analysis agent. Given the user prompt and optional website content, output ONLY a valid JSON array of actions. No markdown, no code fences, no explanation.
Each action is an object with "type" (or "action") and type-specific fields:
- ai_text_detection: { "type": "ai_text_detection", "text": "<text to send to AI text detector>" }
- ai_media_detection: { "type": "ai_media_detection", "media_url": "<url of image or video>" } (one object per URL)
- fact_check: { "type": "fact_check", "facts": ["<fact1>", "<fact2>"] }
- information_graph: { "type": "information_graph" }
Output only the JSON array."""

TRUST_SCORE_SYSTEM_PROMPT = """You are a trust evaluator. Given the results of safety checks (AI text scores, media checks, fact checks), output a single integer trust score from 0 to 100. Output only a JSON object: {"trust_score": <0-100>}. No other text."""


def _action_type(action: dict[str, Any]) -> str:
    """Normalize action type from 'action' or 'type' field."""
    return (action.get("action") or action.get("type") or "").strip().lower()


async def get_actions_from_llm(
    prompt: str | None,
    website_content: str | None,
    settings: Settings,
) -> list[dict[str, Any]]:
    """Call LLM; return parsed list of action objects."""
    logger.info("Calling LLM for actions (prompt=%s, website_content_len=%s)", bool(prompt), len(website_content or ""))
    user_parts = []
    if prompt:
        user_parts.append(f"User prompt: {prompt}")
    if website_content:
        user_parts.append(f"Website content:\n{website_content}")
    user_message = "\n\n".join(user_parts) if user_parts else "Analyze for safety and output the JSON array of actions."
    system = settings.llm_system_prompt.strip() or ACTIONS_SYSTEM_PROMPT
    content = await chat_completions(
        settings,
        system_prompt=system,
        user_message=user_message,
    )
    logger.info("LLM actions response length=%s", len(content or ""))
    if not content:
        logger.warning("LLM returned empty content")
        return []
    try:
        parsed = parse_json_from_content(content)
    except (ValueError, json.JSONDecodeError) as e:
        logger.warning("Failed to parse LLM actions JSON: %s", e)
        return []
    if isinstance(parsed, list):
        # Accept either "action" or "type" as the action kind (LLM may return "type")
        actions = [a for a in parsed if isinstance(a, dict) and (a.get("action") or a.get("type"))]
        logger.info("Parsed %s actions: %s", len(actions), [_action_type(a) for a in actions])
        return actions
    logger.warning("LLM response was not a list, got %s", type(parsed).__name__)
    return []


async def run_ai_text_detection(text: str, settings: Settings) -> dict[str, Any]:
    """POST to ai_text_detector; return response or error stub."""
    url = (settings.ai_text_detector_url or "").rstrip("/")
    if not url:
        logger.warning("ai_text_detection skipped: AI_TEXT_DETECTOR_URL not set")
        return {"error": "AI_TEXT_DETECTOR_URL not set", "overall_score": None, "sentence_scores": []}
    logger.info("Calling ai_text_detector (text_len=%s)", len(text))
    try:
        async with httpx.AsyncClient(timeout=settings.service_timeout_seconds) as client:
            r = await client.post(f"{url}/v1/ai-detect", json={"text": text})
            r.raise_for_status()
        out = r.json()
        logger.info("ai_text_detector ok overall_score=%s", out.get("overall_score"))
        return out
    except Exception as e:
        logger.warning("ai_text_detector error: %s", e)
        return {"error": str(e), "overall_score": None, "sentence_scores": []}


async def run_media_check(media_url: str, settings: Settings) -> dict[str, Any]:
    """POST to media_checking; return response or error stub."""
    url = (settings.media_checking_url or "").rstrip("/")
    if not url:
        logger.warning("media_check skipped: MEDIA_CHECKING_URL not set")
        return {"error": "MEDIA_CHECKING_URL not set", "chunks": [], "media_url": media_url}
    logger.info("Calling media_checking for url=%s", media_url[:80] + "..." if len(media_url) > 80 else media_url)
    try:
        async with httpx.AsyncClient(timeout=settings.service_timeout_seconds) as client:
            r = await client.post(f"{url}/v1/media/check", json={"media_url": media_url})
            r.raise_for_status()
        out = r.json()
        logger.info("media_checking ok chunks=%s", len(out.get("chunks") or []))
        return out
    except Exception as e:
        logger.warning("media_checking error: %s", e)
        return {"error": str(e), "chunks": [], "media_url": media_url}


async def run_fact_check(fact: str, settings: Settings) -> dict[str, Any]:
    """POST to fact_checking for one fact; return response or error stub."""
    url = (settings.fact_checking_url or "").rstrip("/")
    if not url:
        logger.warning("fact_check skipped: FACT_CHECKING_URL not set")
        return {"error": "FACT_CHECKING_URL not set", "truth_value": True, "explanation": ""}
    logger.info("Calling fact_checking for fact=%s", (fact[:60] + "..." if len(fact) > 60 else fact))
    try:
        async with httpx.AsyncClient(timeout=settings.service_timeout_seconds) as client:
            r = await client.post(f"{url}/v1/fact/check", json={"fact": fact})
            r.raise_for_status()
        out = r.json()
        logger.info("fact_checking ok truth_value=%s", out.get("truth_value"))
        return out
    except Exception as e:
        logger.warning("fact_checking error: %s", e)
        return {"error": str(e), "truth_value": True, "explanation": str(e)}


async def execute_action(
    action: dict[str, Any],
    settings: Settings,
) -> tuple[str, Any]:
    """
    Execute one action. Returns (action_type, result).
    Accepts "action" or "type" field. For information_graph, returns ("information_graph", stub).
    """
    action_type = _action_type(action)
    logger.info("Executing action type=%s", action_type)
    if action_type == "ai_text_detection":
        text = action.get("text") or ""
        if not text.strip():
            return (action_type, {"error": "missing text", "overall_score": None, "sentence_scores": []})
        return (action_type, await run_ai_text_detection(text, settings))
    if action_type == "ai_media_detection":
        media_url = action.get("media_url") or ""
        if not media_url.strip():
            return (action_type, {"error": "missing media_url", "chunks": [], "media_url": ""})
        return (action_type, await run_media_check(media_url, settings))
    if action_type == "fact_check":
        facts = action.get("facts") or []
        if not isinstance(facts, list):
            facts = [facts] if facts else []
        results = []
        for f in facts:
            if isinstance(f, str) and f.strip():
                results.append(await run_fact_check(f.strip(), settings))
        return (action_type, {"facts": results})
    if action_type == "information_graph":
        logger.info("information_graph: skeleton (no external call)")
        return (action_type, {"status": "skeleton", "message": "Service in development"})
    logger.warning("Unknown action type=%s", action_type)
    return (action_type, {})


async def run_trust_score_llm(
    action_results: list[tuple[str, Any]],
    settings: Settings,
) -> int:
    """Second LLM call: summarize results and get trust_score 0-100."""
    logger.info("Calling LLM for trust score (action_results_count=%s)", len(action_results))
    summary_parts = ["Summary of safety checks:\n"]
    for kind, data in action_results:
        summary_parts.append(f"[{kind}]: {json.dumps(data, default=str)[:2000]}")
    user_message = "\n".join(summary_parts) + "\n\nOutput only a JSON object with key trust_score (integer 0-100)."
    system = TRUST_SCORE_SYSTEM_PROMPT
    content = await chat_completions(
        settings,
        system_prompt=system,
        user_message=user_message,
    )
    logger.info("LLM trust_score response length=%s", len(content or ""))
    if not content:
        logger.warning("LLM trust score empty, using default 50")
        return 50
    try:
        parsed = parse_json_from_content(content)
        if isinstance(parsed, dict):
            score = parsed.get("trust_score")
            if isinstance(score, (int, float)):
                s = max(0, min(100, int(score)))
                logger.info("Parsed trust_score=%s from JSON", s)
                return s
        if isinstance(parsed, int):
            s = max(0, min(100, parsed))
            logger.info("Parsed trust_score=%s from JSON", s)
            return s
    except (ValueError, json.JSONDecodeError, TypeError) as e:
        logger.warning("Trust score parse error: %s", e)
    # Fallback: try to find a number 0-100 in text
    numbers = re.findall(r"\b(100|\d{1,2})\b", content)
    for n in numbers:
        v = int(n)
        if 0 <= v <= 100:
            logger.info("Parsed trust_score=%s from fallback", v)
            return v
    logger.warning("Could not parse trust_score from LLM, using default 50")
    return 50


def build_fake_facts(action_results: list[tuple[str, Any]]) -> list[FakeFact]:
    """Collect fact_check results where truth_value is False."""
    out: list[FakeFact] = []
    for kind, data in action_results:
        if kind != "fact_check":
            continue
        facts_list = data.get("facts") or []
        for item in facts_list:
            if isinstance(item, dict) and item.get("truth_value") is False:
                out.append(
                    FakeFact(
                        truth_value=False,
                        explanation=item.get("explanation") or "",
                    )
                )
    return out


def build_fake_media(action_results: list[tuple[str, Any]]) -> list[FakeMediaItem]:
    """Build fake_media from media_checking responses."""
    out: list[FakeMediaItem] = []
    for kind, data in action_results:
        if kind != "ai_media_detection":
            continue
        if data.get("error"):
            continue
        media_url = data.get("media_url") or ""
        chunks_raw = data.get("chunks") or []
        chunks = []
        for c in chunks_raw:
            if isinstance(c, dict):
                chunks.append(
                    FakeMediaChunk(
                        index=c.get("index", 0),
                        start_seconds=c.get("start_seconds", 0.0),
                        end_seconds=c.get("end_seconds", 0.0),
                        ai_generated_score=c.get("ai_generated_score"),
                        deepfake_score=c.get("deepfake_score"),
                        label=c.get("label", ""),
                        provider_raw=c.get("provider_raw"),
                    )
                )
        out.append(
            FakeMediaItem(
                media_url=str(media_url),
                media_type=data.get("media_type", ""),
                duration_seconds=float(data.get("duration_seconds", 0)),
                chunk_seconds=int(data.get("chunk_seconds", 0)),
                provider=data.get("provider", ""),
                chunks=chunks,
            )
        )
    return out


async def run_agent(
    prompt: str | None,
    website_content: str | None,
    settings: Settings,
) -> AgentRunResponse:
    """
    Full pipeline: get actions from LLM -> execute via APIs -> trust score LLM -> compile response.
    """
    logger.info("run_agent started")
    actions = await get_actions_from_llm(prompt, website_content, settings)
    action_results: list[tuple[str, Any]] = []
    for i, act in enumerate(actions):
        kind, result = await execute_action(act, settings)
        action_results.append((kind, result))
        if result.get("error"):
            logger.warning("Action %s/%s (%s) had error: %s", i + 1, len(actions), kind, result.get("error"))

    trust_score = await run_trust_score_llm(action_results, settings)
    fake_facts = build_fake_facts(action_results)
    fake_media = build_fake_media(action_results)

    return AgentRunResponse(
        trust_score=trust_score,
        fake_facts=fake_facts,
        fake_media=fake_media,
    )
