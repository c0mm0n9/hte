from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class AIDetectRequest(BaseModel):
    text: str


class SentenceScore(BaseModel):
    sentence: str
    score: float


class AIDetectResponse(BaseModel):
    overall_score: float
    sentence_scores: List[SentenceScore]
    provider: str
    provider_raw: Optional[Dict[str, Any]] = None
