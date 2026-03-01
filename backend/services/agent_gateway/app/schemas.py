from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class AgentRunRequest(BaseModel):
    """Request: API key (required); prompt required from body or from backend when portal validation is used."""

    api_key: str = Field(..., description="API key for authentication")
    prompt: Optional[str] = Field(
        None,
        description="User prompt for the agent. When portal backend is configured, backend may provide prompt (overrides this).",
    )
    website_content: Optional[str] = Field(
        None,
        description="Optional page text or HTML for the LLM to choose text/media for analysis",
    )


class FakeFact(BaseModel):
    """One fact that was checked and is false."""

    truth_value: bool = False
    explanation: str = ""
    fact: str = Field(default="", description="The claim that was checked (quote)")
    source: str = Field(default="", description="Fact-check source or provider name")


class TrueFact(BaseModel):
    """One fact that was checked and is true."""

    truth_value: bool = True
    explanation: str = ""
    fact: str = Field(default="", description="The claim that was checked (quote)")
    source: str = Field(default="", description="Fact-check source or provider name")


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


class InfoGraphNode(BaseModel):
    id: str
    type: str
    label: str
    description: str
    source_url: Optional[str] = None


class InfoGraphEdge(BaseModel):
    id: str
    source: str
    target: str
    relation: str
    weight: Optional[float] = None


class InfoGraphArticle(BaseModel):
    url: str
    title: str
    snippet: str


class InfoGraphSource(BaseModel):
    url: str
    title: str


class InfoGraph(BaseModel):
    source: Optional[InfoGraphSource] = None
    nodes: list[InfoGraphNode] = Field(default_factory=list)
    edges: list[InfoGraphEdge] = Field(default_factory=list)
    related_articles: list[InfoGraphArticle] = Field(default_factory=list)


class ContentSafetyScores(BaseModel):
    """Risk scores from content_safety service (PIL, harmful, unwanted)."""

    pil: float = Field(default=0.0, ge=0.0, le=1.0, description="Privacy Information Leakage risk 0-1")
    harmful: float = Field(default=0.0, ge=0.0, le=1.0, description="Harmful content risk 0-1")
    unwanted: float = Field(default=0.0, ge=0.0, le=1.0, description="Unwanted connections risk 0-1")


class AgentRunResponse(BaseModel):
    """Structured result: trust_score, explanation, ai_text_score, fake_facts, fake_media, true_facts, true_media, info_graph."""

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
    info_graph: Optional[InfoGraph] = Field(default=None, description="Information graph built from source article + related articles")
    content_safety: Optional[ContentSafetyScores] = Field(default=None, description="PIL / harmful / unwanted risk scores from content_safety check")


class ExplainRequest(BaseModel):
    """Request to generate an explanatory video, audio, or flashcards for a trust-score result."""

    api_key: Optional[str] = Field(None, description="API key (optional; no validation for explain)")
    response: AgentRunResponse = Field(..., description="The full response from /agent/run")
    explanation_type: Literal["video", "audio", "flashcards"] = Field(
        ..., description="Type of explanation to generate: video, audio, or flashcards"
    )
    user_prompt: Optional[str] = Field(
        None, description="Optional personalization prompt, e.g. 'Explain for a high-school audience'"
    )
