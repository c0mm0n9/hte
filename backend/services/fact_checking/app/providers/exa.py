import json
from typing import Any, Dict

import httpx

from ..config import Settings
from ..schemas import FactCheckResponse


# Query sent to Exa Answer API: search + LLM return structured fact-check result.
QUERY_TEMPLATE = (
    'You need to analyze this fact whether it is true or false.\n'
    'Input: fact "{fact}"\n'
    "Output: JSON with truth_value (boolean) and explanation (string)."
)

# JSON Schema for Answer API structured output (Draft 7).
OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "truth_value": {"type": "boolean", "description": "True if the fact holds, false otherwise"},
        "explanation": {"type": "string", "description": "Why this truth_value was assigned"},
    },
    "required": ["truth_value", "explanation"],
    "additionalProperties": False,
}


class ExaFactChecker:
    """Uses Exa Answer API: web search + LLM with structured output."""

    async def _call_exa_answer(self, fact: str, settings: Settings) -> Dict[str, Any]:
        if not (settings.exa_api_key and settings.exa_api_key.strip()):
            raise RuntimeError(
                "Exa API key is not configured. Set FACTCHECK_EXA_API_KEY or EXA_API_KEY."
            )

        query = QUERY_TEMPLATE.format(fact=fact)
        headers = {
            "Content-Type": "application/json",
            "x-api-key": settings.exa_api_key,
        }
        payload: Dict[str, Any] = {
            "query": query,
            "text": settings.exa_answer_include_text,
            "outputSchema": OUTPUT_SCHEMA,
        }
        url = settings.exa_base_url.rstrip("/") + "/answer"

        async with httpx.AsyncClient(timeout=settings.exa_timeout_seconds) as client:
            resp = await client.post(url, headers=headers, json=payload)

        resp.raise_for_status()
        return resp.json()

    @staticmethod
    def _answer_to_parsed(raw: Dict[str, Any]) -> Dict[str, Any]:
        """Extract and normalize structured answer from Exa Answer API response."""
        answer = raw.get("answer")
        if isinstance(answer, dict):
            return answer
        if isinstance(answer, str):
            text = answer.strip()
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1 and end > start:
                text = text[start : end + 1]
            try:
                return json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Failed to parse JSON from Exa answer: {exc}") from exc
        raise ValueError("Exa Answer API did not return a valid answer")

    async def check_fact(
        self,
        fact: str,
        settings: Settings,
    ) -> FactCheckResponse:
        raw = await self._call_exa_answer(fact, settings)
        parsed = self._answer_to_parsed(raw)

        truth_value = parsed.get("truth_value")
        explanation = parsed.get("explanation")

        if isinstance(truth_value, str):
            lowered = truth_value.strip().lower()
            if lowered in {"true", "yes", "1"}:
                truth_value = True
            elif lowered in {"false", "no", "0"}:
                truth_value = False

        if not isinstance(truth_value, bool):
            raise ValueError("Exa response truth_value is not a boolean")
        if not isinstance(explanation, str):
            explanation = str(explanation) if explanation is not None else ""

        return FactCheckResponse(
            truth_value=truth_value,
            explanation=explanation,
            provider="exa",
            raw_provider_response=raw,
        )

