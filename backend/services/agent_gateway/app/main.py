import base64
import logging
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .routers import agent

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("agent_gateway")


def _safe_encode(obj: Any) -> Any:
    """Recursively encode validation error details, replacing bytes with base64 strings."""
    if isinstance(obj, bytes):
        try:
            return obj.decode("utf-8")
        except UnicodeDecodeError:
            return base64.b64encode(obj).decode("ascii")
    if isinstance(obj, dict):
        return {k: _safe_encode(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_safe_encode(i) for i in obj]
    return obj


def create_app() -> FastAPI:
    app = FastAPI(title="Agent Gateway Service", version="1.0.0")

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"detail": _safe_encode(exc.errors())},
        )

    @app.on_event("startup")
    async def startup() -> None:
        logger.info("Agent Gateway starting")
        for route in app.routes:
            if hasattr(route, "methods") and hasattr(route, "path"):
                for method in route.methods:
                    if method != "HEAD":
                        logger.info("Route: %s %s", method, route.path)

    @app.get("/healthz")
    async def healthz() -> dict:
        logger.debug("healthz")
        return {"status": "ok"}

    app.include_router(agent.router, prefix="/v1")
    return app


app = create_app()
