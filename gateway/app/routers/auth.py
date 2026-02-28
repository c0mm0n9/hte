from typing import Optional

from fastapi import APIRouter, Header, HTTPException, status

from ..auth import parse_api_key
from ..schemas import AuthValidateResponse

router = APIRouter(prefix="/v1/auth", tags=["auth"])


@router.get("/validate", response_model=AuthValidateResponse)
async def validate_api_key(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
) -> AuthValidateResponse:
    """Validate portal-generated API key. Returns mode from key suffix (-agent or -control)."""
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-API-Key header",
        )
    valid, mode = parse_api_key(x_api_key)
    if not valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key format",
        )
    return AuthValidateResponse(valid=True, mode=mode)
