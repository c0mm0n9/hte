from typing import Any, Optional

from pydantic import BaseModel, Field


class AgentRunRequest(BaseModel):
    """Request: API key (required), optional prompt, optional website content."""

    api_key: str = Field(..., description="API key for authentication")
    prompt: Optional[str] = Field(None, description="Optional user prompt, e.g. 'I need to analyze this website for safety'")
    website_content: Optional[str] = Field(
        None,
        description="Optional page text or HTML for the LLM to choose text/media for analysis",
    )


class FakeFact(BaseModel):
    """One fact that was checked and is false."""

    truth_value: bool = False
    explanation: str = ""


class TrueFact(BaseModel):
    """One fact that was checked and is true."""

    truth_value: bool = True
    explanation: str = ""


class FakeMediaChunk(BaseModel):
    """Per-chunk media result (mirrors media_checking ChunkResult)."""

    index: int = 0
    start_seconds: float = 0.0
    end_seconds: float = 0.0
    ai_generated_score: Optional[float] = None
    deepfake_score: Optional[float] = None
    label: str = ""
    provider_raw: Optional[dict[str, Any]] = None


class FakeMediaItem(BaseModel):
    """One media resource with chunks (from media_checking)."""

    media_url: str = ""
    media_type: str = ""  # image | video
    duration_seconds: float = 0.0
    chunk_seconds: int = 0
    provider: str = ""
    chunks: list[FakeMediaChunk] = Field(default_factory=list)


class AgentRunResponse(BaseModel):
    """Structured result: trust_score, explanation, ai_text_score, fake_facts, fake_media, true_facts, true_media."""

    trust_score: int = Field(..., ge=0, le=100, description="Trust score 0-100 from LLM")
    trust_score_explanation: str = Field(
        default="",
        description="Human-readable explanation of the trust score based on all checks performed",
    )
    ai_text_score: Optional[float] = Field(
        default=None,
        description="Overall AI-generated text likelihood (0.0–1.0) from ai_text_detector, or null if not run",
    )
    fake_facts: list[FakeFact] = Field(default_factory=list, description="Facts with truth_value false from fact_checking")
    fake_media: list[FakeMediaItem] = Field(default_factory=list, description="Media flagged as AI-generated/deepfake (high scores)")
    true_facts: list[TrueFact] = Field(default_factory=list, description="Facts with truth_value true from fact_checking")
    true_media: list[FakeMediaItem] = Field(default_factory=list, description="Media not flagged as fake (low scores)")
