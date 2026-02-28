from pydantic import BaseModel
from typing import Optional, Dict, Any


class FactCheckRequest(BaseModel):
    fact: str


class FactCheckResponse(BaseModel):
    truth_value: bool
    explanation: str
    provider: str
    raw_provider_response: Optional[Dict[str, Any]] = None

