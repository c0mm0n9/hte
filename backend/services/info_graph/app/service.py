"""
Info graph builder.

Flow:
1. Use Exa search to find related articles for the website URL.
2. Build an LLM prompt combining the original website text + article snippets.
3. Call Featherless LLM (gpt-oss-120b) to produce a JSON information graph.
4. Parse and return as InfoGraphResponse.
"""

import logging
from typing import Any

import httpx

from .config import Settings
from .llm import chat_completions, parse_json_from_content
from .schemas import (
    GraphEdge,
    GraphNode,
    GraphSource,
    InfoGraphRequest,
    InfoGraphResponse,
    RelatedArticle,
)

logger = logging.getLogger("info_graph")


GRAPH_SYSTEM_PROMPT = """You are an information graph analyst. Given a source article and related articles from the web, produce ONLY a valid JSON object representing the information graph. No markdown, no code fences, no explanation.

The JSON object must have these keys:
- "source": { "url": "<source URL>", "title": "<title extracted from text or URL>" }
- "nodes": array of node objects, each with:
    { "id": "<unique short id like n1, n2...>", "type": "<one of: claim, entity, topic, person, organization, event, article>", "label": "<short name>", "description": "<1-2 sentence description>", "source_url": "<URL where this node originates, or null>" }
- "edges": array of edge objects, each with:
    { "id": "<unique short id like e1, e2...>", "source": "<node id>", "target": "<node id>", "relation": "<one of: supports, contradicts, related_to, mentions, authored_by, published_by, occurred_at, is_a, part_of>", "weight": <float 0.0-1.0 indicating strength of connection> }
- "related_articles" (optional): array of { "url": "<article URL>", "title": "<article title>", "snippet": "<short excerpt>" } for key articles referenced in the graph.

Rules:
- Include 8-20 nodes covering key claims, entities, topics, people, and organizations from all articles.
- Include edges that reflect meaningful relationships between nodes.
- Nodes from related articles should have source_url set to the article URL.
- Output ONLY the JSON object."""


async def search_exa(website_url: str, website_text: str, settings: Settings) -> list[dict[str, Any]]:
    """
    Call Exa search API to find related articles.
    Returns list of result dicts with url, title, text snippet.
    """
    if not (settings.exa_api_key and settings.exa_api_key.strip()):
        logger.warning("Exa API key not configured; skipping web search")
        return []

    query = website_url
    payload: dict[str, Any] = {
        "query": query,
        "numResults": settings.exa_num_results,
        "contents": {
            "text": {"maxCharacters": 1500},
        },
        "excludeDomains": [_extract_domain(website_url)],
    }
    headers = {
        "Content-Type": "application/json",
        "x-api-key": settings.exa_api_key,
    }
    url = settings.exa_base_url.rstrip("/") + "/search"

    logger.info("Exa search query=%s num_results=%s", query[:100], settings.exa_num_results)
    try:
        async with httpx.AsyncClient(timeout=settings.exa_timeout_seconds) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
        data = resp.json()
        results = data.get("results") or []
        logger.info("Exa returned %s results", len(results))
        return results
    except Exception as e:
        logger.warning("Exa search failed: %s", e)
        return []


def _extract_domain(url: str) -> str:
    """Extract bare domain from URL for Exa excludeDomains."""
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        return parsed.netloc or url
    except Exception:
        return url


def _build_llm_prompt(request: InfoGraphRequest, exa_results: list[dict[str, Any]]) -> str:
    parts: list[str] = []

    parts.append(f"SOURCE ARTICLE\nURL: {request.website_url}\n\n{request.website_text[:3000]}")

    if exa_results:
        parts.append("\n\nRELATED ARTICLES FROM THE WEB")
        for i, result in enumerate(exa_results, 1):
            title = result.get("title") or "Untitled"
            url = result.get("url") or ""
            text = ""
            content = result.get("text")
            if isinstance(content, str):
                text = content[:1200]
            elif isinstance(content, dict):
                text = (content.get("text") or "")[:1200]
            parts.append(f"\n[Article {i}]\nTitle: {title}\nURL: {url}\n{text}")

    parts.append(
        "\n\nBuild the information graph JSON as specified. Output ONLY the JSON object."
    )
    return "\n".join(parts)


def _parse_related_articles(
    raw: dict[str, Any],
    exa_results: list[dict[str, Any]],
) -> list[RelatedArticle]:
    """Build related_articles from graph JSON when present (url/title/snippet), else from Exa results."""
    raw_articles = raw.get("related_articles")
    if isinstance(raw_articles, list) and raw_articles:
        out: list[RelatedArticle] = []
        for a in raw_articles:
            if not isinstance(a, dict):
                continue
            url = a.get("url") or ""
            if not url:
                continue
            title = str(a.get("title") or "Untitled")
            snippet = str(a.get("snippet") or "")
            out.append(RelatedArticle(url=url, title=title, snippet=snippet))
        if out:
            return out
    return _exa_to_related_articles(exa_results)


def _exa_to_related_articles(exa_results: list[dict[str, Any]]) -> list[RelatedArticle]:
    """Build RelatedArticle list from Exa search results."""
    out: list[RelatedArticle] = []
    for result in exa_results:
        url = result.get("url") or ""
        title = result.get("title") or "Untitled"
        content = result.get("text")
        if isinstance(content, str):
            snippet = content[:300]
        elif isinstance(content, dict):
            snippet = (content.get("text") or "")[:300]
        else:
            snippet = ""
        if url:
            out.append(RelatedArticle(url=url, title=title, snippet=snippet))
    return out


def _parse_graph_response(
    raw: dict[str, Any],
    exa_results: list[dict[str, Any]],
    website_url: str,
) -> InfoGraphResponse:
    """Convert raw LLM dict into a validated InfoGraphResponse."""
    source_raw = raw.get("source") or {}
    source = GraphSource(
        url=source_raw.get("url") or website_url,
        title=source_raw.get("title") or "",
    )

    nodes: list[GraphNode] = []
    for n in raw.get("nodes") or []:
        if not isinstance(n, dict):
            continue
        nodes.append(
            GraphNode(
                id=str(n.get("id") or ""),
                type=str(n.get("type") or "entity"),
                label=str(n.get("label") or ""),
                description=str(n.get("description") or ""),
                source_url=n.get("source_url") or None,
            )
        )

    edges: list[GraphEdge] = []
    for e in raw.get("edges") or []:
        if not isinstance(e, dict):
            continue
        weight = e.get("weight")
        try:
            weight_val = float(weight) if weight is not None else None
        except (TypeError, ValueError):
            weight_val = None
        edges.append(
            GraphEdge(
                id=str(e.get("id") or ""),
                source=str(e.get("source") or ""),
                target=str(e.get("target") or ""),
                relation=str(e.get("relation") or "related_to"),
                weight=weight_val,
            )
        )

    related_articles = _parse_related_articles(raw, exa_results)

    return InfoGraphResponse(
        source=source,
        nodes=nodes,
        edges=edges,
        related_articles=related_articles,
    )


async def build_info_graph(request: InfoGraphRequest, settings: Settings) -> InfoGraphResponse:
    """
    Main pipeline: Exa search -> LLM graph build -> parse response.
    """
    logger.info("build_info_graph started url=%s text_len=%s", request.website_url, len(request.website_text))

    exa_results = await search_exa(request.website_url, request.website_text, settings)

    user_message = _build_llm_prompt(request, exa_results)
    logger.info("LLM prompt len=%s", len(user_message))

    content = await chat_completions(
        settings,
        system_prompt=GRAPH_SYSTEM_PROMPT,
        user_message=user_message,
    )

    if not content:
        logger.warning("LLM returned empty content; returning empty graph")
        return InfoGraphResponse(
            source=GraphSource(url=request.website_url, title=""),
            nodes=[],
            edges=[],
            related_articles=[],
        )

    try:
        raw = parse_json_from_content(content)
    except ValueError as e:
        logger.warning("Failed to parse LLM graph JSON: %s", e)
        return InfoGraphResponse(
            source=GraphSource(url=request.website_url, title=""),
            nodes=[],
            edges=[],
            related_articles=[_to_related(r) for r in exa_results if r.get("url")],
        )

    if not isinstance(raw, dict):
        logger.warning("LLM graph response was not a dict, got %s", type(raw).__name__)
        return InfoGraphResponse(
            source=GraphSource(url=request.website_url, title=""),
            nodes=[],
            edges=[],
            related_articles=[_to_related(r) for r in exa_results if r.get("url")],
        )

    return _parse_graph_response(raw, exa_results, request.website_url)


def _to_related(result: dict[str, Any]) -> RelatedArticle:
    url = result.get("url") or ""
    title = result.get("title") or "Untitled"
    content = result.get("text")
    if isinstance(content, str):
        snippet = content[:300]
    elif isinstance(content, dict):
        snippet = (content.get("text") or "")[:300]
    else:
        snippet = ""
    return RelatedArticle(url=url, title=title, snippet=snippet)
