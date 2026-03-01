"""
Dummy API key and validate service for local/testing use.
- GET /api_key  -> returns a dummy API key
- GET /validate/?api_key=... -> validates key (same response shape as portal)
"""
import logging
import os
from typing import Optional

from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("dummy_validate")

# Default dummy key; accept comma-separated list via env for multiple valid keys
DUMMY_KEYS_ENV = os.environ.get("DUMMY_VALIDATE_KEYS", "dummy-00000000-0000-0000-0000-000000000001-control")
VALID_KEYS = {k.strip() for k in DUMMY_KEYS_ENV.split(",") if k.strip()}
DEFAULT_KEY = next(iter(VALID_KEYS), "dummy-00000000-0000-0000-0000-000000000001-control")

# Mode for default key: "control" -> may include prompt; "agentic" -> no prompt
DEFAULT_MODE = os.environ.get("DUMMY_VALIDATE_MODE", "control").strip().lower()
if DEFAULT_MODE not in ("control", "agentic"):
    DEFAULT_MODE = "control"
DUMMY_PROMPT = os.environ.get("DUMMY_VALIDATE_PROMPT", "You are a helpful assistant.").strip()

app = FastAPI(title="Dummy Validate Service", version="1.0.0")


@app.get("/healthz")
async def healthz() -> dict:
    return {"status": "ok"}


@app.get("/api_key")
async def get_api_key() -> dict:
    """Return a dummy API key for testing."""
    return {"api_key": DEFAULT_KEY}


@app.get("/api/portal/validate/")
async def validate(
    api_key: Optional[str] = Query(None, alias="api_key"),
):
    """
    Validate API key. Same response shape as portal: { valid, mode [, prompt] }.
    Accepts any key that matches DUMMY_VALIDATE_KEYS (env) or the default dummy key.
    Returns 400 when api_key missing, 401 when invalid, 200 when valid.
    """
    key = (api_key or "").strip()
    if not key:
        return JSONResponse(
            status_code=400,
            content={"valid": False, "error": "api_key required"},
        )
    if key not in VALID_KEYS:
        return JSONResponse(
            status_code=401,
            content={"valid": False, "error": "Invalid API key"},
        )
    payload: dict = {"valid": True, "mode": DEFAULT_MODE}
    if DEFAULT_MODE == "control":
        payload["prompt"] = DUMMY_PROMPT
    return payload
