from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class ExplainRequest(BaseModel):
    """Internal request from agent_gateway to generate explanatory media."""

    response: dict[str, Any] = Field(..., description="Full AgentRunResponse dict from /agent/run")
    explanation_type: Literal["video", "audio", "flashcards"] = Field(
        ..., description="Type of explanation to generate"
    )
    user_prompt: Optional[str] = Field(
        None, description="Optional personalisation hint for Minimax generation"
    )


class Flashcard(BaseModel):
    front: str = Field(..., description="Question or concept on the front of the card")
    back: str = Field(..., description="Answer or explanation on the back of the card")


class FlashcardsResponse(BaseModel):
    flashcards: list[Flashcard] = Field(default_factory=list)
