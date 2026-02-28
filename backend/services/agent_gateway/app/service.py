"""
Agent gateway orchestration.

Flow:
1. LLM (Featherless) returns JSON array of actions.
2. Execute each action via API (ai_text_detector, media_checking, fact_checking; info_graph skeleton).
3. Second LLM call to get trust score 0-100.
4. Compile trust_score, fake_facts, fake_media into AgentRunResponse.
"""

import asyncio
import json
import logging
import re
from typing import Any, Optional

import httpx

from .config import Settings

logger = logging.getLogger("agent_gateway")
from .llm import chat_completions, parse_json_from_content
from .schemas import AgentRunResponse, ContentSafetyScores, FakeFact, FakeMediaChunk, FakeMediaItem, InfoGraph, InfoGraphArticle, InfoGraphEdge, InfoGraphNode, InfoGraphSource, TrueFact


ACTIONS_SYSTEM_PROMPT = """You are a safety-analysis agent. Given the user prompt, output ONLY a valid JSON array of action objects. No wrapper object (e.g. no {"actions": [...]}), no markdown, no code fences, no explanation—just the array.
Each action is an object with "type" (or "action") and type-specific fields:
- ai_text_detection: { "type": "ai_text_detection", "text": "<text to send to AI text detector>" }
- ai_media_detection: { "type": "ai_media_detection", "media_url": "<full http/https URL of image or video>" } (one object per URL; ONLY include this action if media_url is a real http/https URL — never use placeholders like [image1])
- fact_check: { "type": "fact_check", "facts": ["<fact1>", "<fact2>"] }
- information_graph: { "type": "information_graph", "website_url": "<source URL if known, else empty string>" } — website text is supplied by the system from the request; do not include website_text.
- content_safety: { "type": "content_safety" } — for checking website text for privacy leakage (PIL), harmful content, and unwanted connections. Website text is supplied by the system from the request; do not include website_text.
If the user has uploaded media files, the system will run media checks on them automatically; you may still add ai_media_detection for any http(s) URLs found in the content.
If user asks whether they can trust the website, run fact_checking as well as information_graph action.
IF user asks whether the website is safe, run content_safety action.
Run ai_media_detection and ai_text_detection every time.
Output only the JSON array of action objects."""

TRUST_SCORE_SYSTEM_PROMPT = """You are a trust evaluator. Given the results of safety checks (AI text likelihood, media deepfake scores, fact checks, information graph), produce:
- trust_score: integer 0-100 (0 = completely untrustworthy, 100 = fully trustworthy)
- explanation: 2-4 sentence human-readable explanation citing the specific evidence (AI text score, fake/true facts, media scores, information graph status)

Output ONLY a JSON object with exactly these two keys: {"trust_score": <0-100>, "explanation": "<text>"}. No markdown, no extra keys."""

FACT_EXTRACTION_SYSTEM_PROMPT = """You are a fact-extraction assistant. Given text (e.g. from a web page), extract discrete, checkable factual claims—statements that can be verified as true or false. Output ONLY a JSON array of strings, e.g. ["claim 1", "claim 2"]. No wrapper object, no markdown, no code fences, no explanation. Each array element should be one factual claim."""


def _action_type(action: dict[str, Any]) -> str:
    """Normalize action type from 'action' or 'type' field."""
    return (action.get("action") or action.get("type") or "").strip().lower()


async def get_actions_from_llm(
    prompt: str | None,
    website_content: str | None,
    settings: Settings,
    uploaded_file_names: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Call LLM; return parsed list of action objects."""
    names = uploaded_file_names or []
    logger.info(
        "Calling LLM for actions (prompt=%s, request_has_website_content=%s, uploaded_files=%s)",
        bool(prompt),
        bool(website_content),
        len(names),
    )
    user_parts = []
    if prompt:
        user_parts.append(f"User prompt: {prompt}")
    if website_content:
        user_parts.append(
            "The user has provided website content for this page; it will be used when running information_graph or content_safety. Do not include website_text in your action objects."
        )
    if names:
        user_parts.append(
            f"The user has also uploaded the following media file(s) for safety check (filenames): {', '.join(names)}. "
            "The system will run a media (deepfake/AI) check on each of these."
        )
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
    # Contract: actions call returns only a list; tolerate wrapper object for robustness
    if isinstance(parsed, list):
        raw_list = parsed
    elif isinstance(parsed, dict):
        raw_list = parsed.get("actions") or parsed.get("actions_list")
        if not isinstance(raw_list, list):
            logger.warning("LLM response was a dict but no list at 'actions' or 'actions_list', got %s", type(raw_list).__name__)
            return []
    else:
        logger.warning("LLM response was not a list or dict, got %s", type(parsed).__name__)
        return []
    # Accept either "action" or "type" as the action kind (LLM may return "type")
    actions = [a for a in raw_list if isinstance(a, dict) and (a.get("action") or a.get("type"))]
    logger.info("Parsed %s actions: %s", len(actions), [_action_type(a) for a in actions])
    return actions


# Max website content length to send to fact-extraction LLM (avoid token limits)
FACT_EXTRACTION_MAX_TEXT_LENGTH = 30000


async def extract_facts_from_website_text(website_content: str, settings: Settings) -> list[str]:
    """Call LLM to extract checkable factual claims from website text; return list of fact strings."""
    text = (website_content or "").strip()
    if not text:
        return []
    if len(text) > FACT_EXTRACTION_MAX_TEXT_LENGTH:
        text = text[:FACT_EXTRACTION_MAX_TEXT_LENGTH] + "\n[... truncated]"
    logger.info("Calling LLM for fact extraction (text_len=%s)", len(text))
    user_message = "Extract checkable factual claims from the following text:\n\n" + text
    try:
        content = await chat_completions(
            settings,
            system_prompt=FACT_EXTRACTION_SYSTEM_PROMPT,
            user_message=user_message,
        )
    except Exception as e:
        logger.warning("Fact extraction LLM call failed: %s", e)
        return []
    if not content:
        logger.warning("Fact extraction LLM returned empty content")
        return []
    try:
        parsed = parse_json_from_content(content)
    except (ValueError, json.JSONDecodeError) as e:
        logger.warning("Failed to parse fact extraction JSON: %s", e)
        return []
    if isinstance(parsed, list):
        raw_list = parsed
    elif isinstance(parsed, dict):
        raw_list = parsed.get("facts")
        if not isinstance(raw_list, list):
            logger.warning("Fact extraction response was dict but no list at 'facts', got %s", type(raw_list).__name__)
            return []
    else:
        logger.warning("Fact extraction response was not list or dict, got %s", type(parsed).__name__)
        return []
    facts = [str(x).strip() for x in raw_list if isinstance(x, str) and str(x).strip()]
    logger.info("Extracted %s facts from website text", len(facts))
    return facts


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


def _is_http_url(value: str) -> bool:
    return value.startswith("http://") or value.startswith("https://")


async def run_media_check(media_url: str, settings: Settings) -> dict[str, Any]:
    """POST to media_checking; return response or error stub."""
    if not _is_http_url(media_url):
        logger.info(
            "media_check skipped: media_url is not a valid HTTP URL (placeholder?) value=%r",
            media_url,
        )
        return {"skipped": True, "reason": "not a valid URL", "chunks": [], "media_url": media_url}

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


async def run_media_check_upload(
    file_bytes: bytes,
    filename: str,
    content_type: str,
    settings: Settings,
) -> dict[str, Any]:
    """POST raw file bytes to media_checking upload endpoint; return response or error stub."""
    url = (settings.media_checking_url or "").rstrip("/")
    if not url:
        logger.warning("media_check_upload skipped: MEDIA_CHECKING_URL not set")
        return {"error": "MEDIA_CHECKING_URL not set", "chunks": [], "media_url": filename}
    logger.info("Calling media_checking/upload filename=%s size=%s", filename, len(file_bytes))
    try:
        async with httpx.AsyncClient(timeout=settings.service_timeout_seconds) as client:
            r = await client.post(
                f"{url}/v1/media/check/upload",
                files={"file": (filename, file_bytes, content_type)},
            )
            r.raise_for_status()
        out = r.json()
        logger.info("media_checking upload ok chunks=%s", len(out.get("chunks") or []))
        return out
    except Exception as e:
        logger.warning("media_checking upload error: %s", e)
        return {"error": str(e), "chunks": [], "media_url": filename}


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


async def run_content_safety(website_text: str, settings: Settings) -> dict[str, Any]:
    """POST to content_safety service; return JSON with pil, harmful, unwanted or error stub."""
    url = (settings.content_safety_url or "").rstrip("/")
    if not url:
        logger.warning("content_safety skipped: CONTENT_SAFETY_URL not set")
        return {"error": "CONTENT_SAFETY_URL not set", "pil": None, "harmful": None, "unwanted": None}
    timeout = settings.content_safety_timeout_seconds
    logger.info("Calling content_safety (text_len=%s timeout=%s)", len(website_text), timeout)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.post(
                f"{url}/v1/content-safety/check",
                json={"website_text": website_text},
            )
            r.raise_for_status()
        out = r.json()
        logger.info("content_safety ok pil=%s harmful=%s unwanted=%s", out.get("pil"), out.get("harmful"), out.get("unwanted"))
        return out
    except Exception as e:
        logger.warning("content_safety error: %s", e)
        return {"error": str(e), "pil": None, "harmful": None, "unwanted": None}


async def run_info_graph(website_text: str, website_url: str, settings: Settings) -> dict[str, Any]:
    """POST to info_graph service; return JSON graph or error stub."""
    url = (settings.info_graph_url or "").rstrip("/")
    if not url:
        logger.warning("info_graph skipped: INFO_GRAPH_URL not set")
        return {"error": "INFO_GRAPH_URL not set", "nodes": [], "edges": [], "related_articles": []}
    timeout = settings.info_graph_timeout_seconds
    logger.info("Calling info_graph (website_url=%s text_len=%s timeout=%s)", website_url[:80], len(website_text), timeout)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.post(
                f"{url}/v1/info-graph/build",
                json={"website_text": website_text, "website_url": website_url},
            )
            r.raise_for_status()
        out = r.json()
        logger.info("info_graph ok nodes=%s edges=%s", len(out.get("nodes") or []), len(out.get("edges") or []))
        return out
    except Exception as e:
        logger.warning("info_graph error: %s", e)
        return {"error": str(e), "nodes": [], "edges": [], "related_articles": []}


def _is_upload_placeholder(media_url: str) -> bool:
    """True if media_url indicates an uploaded file (upload:0, upload:1, or upload:filename)."""
    s = (media_url or "").strip()
    return s.startswith("upload:")


async def execute_action(
    action: dict[str, Any],
    settings: Settings,
    request_website_url: str | None = None,
    request_website_content: str | None = None,
    uploaded_files: list[tuple[bytes, str, str]] | None = None,
) -> tuple[str, Any]:
    """
    Execute one action. Returns (action_type, result).
    request_website_url and request_website_content are used as fallbacks for information_graph when the LLM does not provide them.
    uploaded_files: used when ai_media_detection has media_url like upload:0 or upload:filename.
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
        if _is_upload_placeholder(media_url) and uploaded_files:
            suffix = media_url.strip()[7:]  # after "upload:"
            try:
                idx = int(suffix)
            except ValueError:
                idx = None
            if idx is not None and 0 <= idx < len(uploaded_files):
                file_bytes, filename, content_type = uploaded_files[idx]
                result = await run_media_check_upload(file_bytes, filename, content_type, settings)
                return (action_type, result)
            # match by filename if suffix is not an integer
            for file_bytes, filename, content_type in uploaded_files:
                if filename == suffix:
                    result = await run_media_check_upload(file_bytes, filename, content_type, settings)
                    return (action_type, result)
            return (
                action_type,
                {"error": f"uploaded file not found: {suffix!r}", "chunks": [], "media_url": media_url},
            )
        return (action_type, await run_media_check(media_url, settings))
    if action_type == "fact_check":
        facts_to_check: list[str] = []
        if request_website_content and request_website_content.strip():
            facts_to_check = await extract_facts_from_website_text(request_website_content.strip(), settings)
            if not facts_to_check:
                # Fall back to action-provided facts when extraction returns empty
                raw = action.get("facts") or []
                if not isinstance(raw, list):
                    raw = [raw] if raw else []
                facts_to_check = [f.strip() for f in raw if isinstance(f, str) and f.strip()]
        else:
            raw = action.get("facts") or []
            if not isinstance(raw, list):
                raw = [raw] if raw else []
            facts_to_check = [f.strip() for f in raw if isinstance(f, str) and f.strip()]
        # Run fact-check API calls in parallel (after extraction; no concurrent extraction + check)
        tasks = [run_fact_check(f, settings) for f in facts_to_check if f]
        results = await asyncio.gather(*tasks) if tasks else []
        return (action_type, {"facts": list(results)})
    if action_type == "information_graph":
        website_text = action.get("website_text") or action.get("text") or (request_website_content or "")
        website_url = action.get("website_url") or action.get("url") or (request_website_url or "")
        return (action_type, await run_info_graph(website_text, website_url, settings))
    if action_type == "content_safety":
        website_text = action.get("website_text") or action.get("text") or (request_website_content or "")
        if not (website_text or website_text.strip()):
            return (action_type, {"error": "missing website_text", "pil": None, "harmful": None, "unwanted": None})
        return (action_type, await run_content_safety(website_text.strip(), settings))
    logger.warning("Unknown action type=%s", action_type)
    return (action_type, {})


async def run_trust_score_llm(
    action_results: list[tuple[str, Any]],
    settings: Settings,
) -> tuple[int, str]:
    """Second LLM call: summarize results and get trust_score + explanation."""
    logger.info("Calling LLM for trust score (action_results_count=%s)", len(action_results))

    summary_parts = ["Summary of safety checks:\n"]
    for kind, data in action_results:
        if kind == "ai_text_detection":
            score = data.get("overall_score")
            summary_parts.append(
                f"[ai_text_detection]: overall_score={score} "
                f"(probability text is AI-generated; 1.0 = fully AI, 0.0 = human)"
            )
        elif kind == "ai_media_detection":
            chunks = data.get("chunks") or []
            scores = [
                f"chunk{c.get('index', i)}: ai={c.get('ai_generated_score')} deepfake={c.get('deepfake_score')}"
                for i, c in enumerate(chunks)
            ]
            summary_parts.append(
                f"[ai_media_detection]: media_url={data.get('media_url')} "
                f"media_type={data.get('media_type')} scores=[{', '.join(scores)}]"
            )
        elif kind == "fact_check":
            for item in data.get("facts") or []:
                tv = item.get("truth_value")
                exp = item.get("explanation") or ""
                summary_parts.append(f"[fact_check]: truth_value={tv} explanation={exp[:300]}")
        elif kind == "information_graph":
            nodes_count = len(data.get("nodes") or [])
            edges_count = len(data.get("edges") or [])
            articles_count = len(data.get("related_articles") or [])
            summary_parts.append(
                f"[information_graph]: nodes={nodes_count} edges={edges_count} related_articles={articles_count}"
            )
        elif kind == "content_safety":
            if data.get("error"):
                summary_parts.append(f"[content_safety]: error={data.get('error')}")
            else:
                summary_parts.append(
                    f"[content_safety]: pil={data.get('pil')} harmful={data.get('harmful')} unwanted={data.get('unwanted')}"
                )
        else:
            summary_parts.append(f"[{kind}]: {json.dumps(data, default=str)[:500]}")

    user_message = (
        "\n".join(summary_parts)
        + '\n\nOutput only a JSON object: {"trust_score": <0-100>, "explanation": "<2-4 sentences>"}'
    )

    content = await chat_completions(
        settings,
        system_prompt=TRUST_SCORE_SYSTEM_PROMPT,
        user_message=user_message,
    )
    logger.info("LLM trust_score response length=%s", len(content or ""))

    default_explanation = "Trust score estimated based on available checks."
    if not content:
        logger.warning("LLM trust score empty, using default 50")
        return 50, default_explanation

    try:
        parsed = parse_json_from_content(content)
        if isinstance(parsed, dict):
            score = parsed.get("trust_score")
            explanation = str(parsed.get("explanation") or default_explanation)
            if isinstance(score, (int, float)):
                s = max(0, min(100, int(score)))
                logger.info("Parsed trust_score=%s explanation_len=%s", s, len(explanation))
                return s, explanation
    except (ValueError, json.JSONDecodeError, TypeError) as e:
        logger.warning("Trust score parse error: %s", e)

    # Fallback: extract score from raw text
    numbers = re.findall(r"\b(100|\d{1,2})\b", content)
    for n in numbers:
        v = int(n)
        if 0 <= v <= 100:
            logger.info("Parsed trust_score=%s from fallback", v)
            return v, default_explanation

    logger.warning("Could not parse trust_score from LLM, using default 50")
    return 50, default_explanation


# Threshold above which a chunk is considered "fake" (AI-generated/deepfake)
MEDIA_FAKE_THRESHOLD = 0.5


def _media_item_from_result(data: dict[str, Any]) -> FakeMediaItem | None:
    """Build a FakeMediaItem from a media_checking result dict."""
    if data.get("error") or data.get("skipped"):
        return None
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
    return FakeMediaItem(
        media_url=str(media_url),
        media_type=data.get("media_type", ""),
        duration_seconds=float(data.get("duration_seconds", 0)),
        chunk_seconds=int(data.get("chunk_seconds", 0)),
        provider=data.get("provider", ""),
        chunks=chunks,
    )


def _media_is_fake(item: FakeMediaItem) -> bool:
    """True if any chunk has ai_generated_score or deepfake_score >= threshold."""
    for c in item.chunks:
        ag = c.ai_generated_score
        df = c.deepfake_score
        if (ag is not None and ag >= MEDIA_FAKE_THRESHOLD) or (df is not None and df >= MEDIA_FAKE_THRESHOLD):
            return True
    return False


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


def build_true_facts(action_results: list[tuple[str, Any]]) -> list[TrueFact]:
    """Collect fact_check results where truth_value is True."""
    out: list[TrueFact] = []
    for kind, data in action_results:
        if kind != "fact_check":
            continue
        facts_list = data.get("facts") or []
        for item in facts_list:
            if isinstance(item, dict) and item.get("truth_value") is True:
                out.append(
                    TrueFact(
                        truth_value=True,
                        explanation=item.get("explanation") or "",
                    )
                )
    return out


def build_ai_text_score(action_results: list[tuple[str, Any]]) -> Optional[float]:
    """Return the highest overall_score seen across all ai_text_detection results, or None."""
    scores: list[float] = []
    for kind, data in action_results:
        if kind != "ai_text_detection":
            continue
        s = data.get("overall_score")
        if isinstance(s, (int, float)):
            scores.append(float(s))
    return max(scores) if scores else None


def build_fake_media(action_results: list[tuple[str, Any]]) -> list[FakeMediaItem]:
    """Build fake_media: items where any chunk exceeds fake threshold."""
    out: list[FakeMediaItem] = []
    for kind, data in action_results:
        if kind != "ai_media_detection":
            continue
        item = _media_item_from_result(data)
        if item is not None and _media_is_fake(item):
            out.append(item)
    return out


def build_true_media(action_results: list[tuple[str, Any]]) -> list[FakeMediaItem]:
    """Build true_media: items where no chunk exceeds fake threshold."""
    out: list[FakeMediaItem] = []
    for kind, data in action_results:
        if kind != "ai_media_detection":
            continue
        item = _media_item_from_result(data)
        if item is not None and not _media_is_fake(item):
            out.append(item)
    return out


def build_info_graph_result(action_results: list[tuple[str, Any]]) -> Optional[InfoGraph]:
    """Extract and map the first successful information_graph result into an InfoGraph model."""
    for kind, data in action_results:
        if kind != "information_graph":
            continue
        if data.get("error"):
            continue
        source_raw = data.get("source") or {}
        source = InfoGraphSource(
            url=source_raw.get("url") or "",
            title=source_raw.get("title") or "",
        ) if source_raw else None

        nodes = [
            InfoGraphNode(
                id=str(n.get("id") or ""),
                type=str(n.get("type") or "entity"),
                label=str(n.get("label") or ""),
                description=str(n.get("description") or ""),
                source_url=n.get("source_url") or None,
            )
            for n in (data.get("nodes") or [])
            if isinstance(n, dict)
        ]

        def _edge_weight(e: dict) -> Optional[float]:
            w = e.get("weight")
            if w is None:
                return None
            try:
                return float(w)
            except (TypeError, ValueError):
                return None

        edges = [
            InfoGraphEdge(
                id=str(e.get("id") or ""),
                source=str(e.get("source") or ""),
                target=str(e.get("target") or ""),
                relation=str(e.get("relation") or "related_to"),
                weight=_edge_weight(e),
            )
            for e in (data.get("edges") or [])
            if isinstance(e, dict)
        ]

        articles = [
            InfoGraphArticle(
                url=str(a.get("url") or ""),
                title=str(a.get("title") or ""),
                snippet=str(a.get("snippet") or ""),
            )
            for a in (data.get("related_articles") or [])
            if isinstance(a, dict) and a.get("url")
        ]

        return InfoGraph(source=source, nodes=nodes, edges=edges, related_articles=articles)
    return None


def build_content_safety_result(action_results: list[tuple[str, Any]]) -> Optional[ContentSafetyScores]:
    """Extract the first successful content_safety result into ContentSafetyScores."""
    for kind, data in action_results:
        if kind != "content_safety":
            continue
        if data.get("error"):
            continue
        pil = data.get("pil")
        harmful = data.get("harmful")
        unwanted = data.get("unwanted")
        if pil is None and harmful is None and unwanted is None:
            continue
        return ContentSafetyScores(
            pil=float(pil) if isinstance(pil, (int, float)) else 0.0,
            harmful=float(harmful) if isinstance(harmful, (int, float)) else 0.0,
            unwanted=float(unwanted) if isinstance(unwanted, (int, float)) else 0.0,
        )
    return None


async def run_agent(
    prompt: str | None,
    website_content: str | None,
    settings: Settings,
    uploaded_files: list[tuple[bytes, str, str]] | None = None,
    website_url: str | None = None,
) -> AgentRunResponse:
    """
    Full pipeline: get actions from LLM -> execute via APIs -> trust score LLM -> compile response.

    uploaded_files: optional list of (file_bytes, filename, content_type) for direct media upload checks.
    website_url: optional URL of the page being analyzed; passed to information_graph when the LLM does not provide it.
    """
    files = uploaded_files or []
    logger.info(
        "run_agent started uploaded_files=%s website_url=%s",
        [f[1] for f in files] if files else [],
        (website_url or "")[:80] if website_url else None,
    )
    actions = await get_actions_from_llm(
        prompt, website_content, settings, uploaded_file_names=[f[1] for f in files]
    )
    injected_actions = [
        {"type": "ai_media_detection", "media_url": f"upload:{i}"}
        for i in range(len(files))
    ]
    all_actions = injected_actions + actions
    # Execute all actions in parallel (independent API/LLM calls; no shared state)
    action_results = await asyncio.gather(
        *[
            execute_action(
                act,
                settings,
                request_website_url=website_url,
                request_website_content=website_content,
                uploaded_files=files if files else None,
            )
            for act in all_actions
        ]
    )
    for i, (kind, result) in enumerate(action_results):
        if result.get("error"):
            logger.warning(
                "Action %s/%s (%s) had error: %s",
                i + 1,
                len(all_actions),
                kind,
                result.get("error"),
            )

    trust_score, trust_score_explanation = await run_trust_score_llm(action_results, settings)
    ai_text_score = build_ai_text_score(action_results)
    fake_facts = build_fake_facts(action_results)
    true_facts = build_true_facts(action_results)
    fake_media = build_fake_media(action_results)
    true_media = build_true_media(action_results)
    info_graph = build_info_graph_result(action_results)
    content_safety = build_content_safety_result(action_results)

    logger.info(
        "Compiled response: trust_score=%s ai_text_score=%s fake_facts=%s true_facts=%s fake_media=%s true_media=%s info_graph_nodes=%s content_safety=%s",
        trust_score,
        ai_text_score,
        len(fake_facts),
        len(true_facts),
        len(fake_media),
        len(true_media),
        len(info_graph.nodes) if info_graph else 0,
        content_safety,
    )

    return AgentRunResponse(
        trust_score=trust_score,
        trust_score_explanation=trust_score_explanation,
        ai_text_score=ai_text_score,
        fake_facts=fake_facts,
        fake_media=fake_media,
        true_facts=true_facts,
        true_media=true_media,
        info_graph=info_graph,
        content_safety=content_safety,
    )


async def call_media_explanation(
    agent_response: dict[str, Any],
    explanation_type: str,
    user_prompt: str | None,
    settings: Settings,
) -> httpx.Response:
    """POST to media_explanation service; return the raw httpx.Response for streaming."""
    url = (settings.media_explanation_url or "").rstrip("/")
    if not url:
        raise ValueError("MEDIA_EXPLANATION_URL not configured")
    timeout = settings.media_explanation_timeout_seconds
    logger.info(
        "Calling media_explanation: type=%s user_prompt=%s timeout=%s",
        explanation_type,
        bool(user_prompt),
        timeout,
    )
    client = httpx.AsyncClient(timeout=timeout)
    try:
        r = await client.post(
            f"{url}/v1/explain/generate",
            json={
                "response": agent_response,
                "explanation_type": explanation_type,
                "user_prompt": user_prompt,
            },
        )
        r.raise_for_status()
        logger.info(
            "media_explanation ok: status=%s content_type=%s bytes=%s",
            r.status_code,
            r.headers.get("content-type"),
            len(r.content),
        )
        return r
    except httpx.HTTPStatusError as e:
        logger.warning("media_explanation HTTP error: %s", e)
        raise
    except Exception as e:
        logger.warning("media_explanation error: %s", e)
        raise
    finally:
        await client.aclose()
