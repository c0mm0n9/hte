from pydantic import BaseModel, Field


class ContentSafetyRequest(BaseModel):
    website_text: str = Field(..., description="Website or page text to analyze for safety")


class ContentSafetyResponse(BaseModel):
    pil: float = Field(..., ge=0.0, le=1.0, description="Privacy Information Leakage risk score 0-1")
    harmful: float = Field(..., ge=0.0, le=1.0, description="Harmful content risk score 0-1")
    unwanted: float = Field(..., ge=0.0, le=1.0, description="Unwanted connections risk score 0-1")
