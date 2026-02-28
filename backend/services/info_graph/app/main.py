import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .routers import info_graph

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("info_graph")


def create_app() -> FastAPI:
    app = FastAPI(title="Info Graph Service", version="1.0.0")

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        """Log validation errors and request body to diagnose 422s."""
        body = b""
        try:
            body = await request.body()
        except Exception:
            pass
        body_preview = body[:500].decode("utf-8", errors="replace") if body else "(none)"
        logger.warning(
            "Request validation failed: path=%s errors=%s body_preview=%s",
            request.url.path,
            exc.errors(),
            body_preview,
        )
        return JSONResponse(
            status_code=422,
            content={"detail": exc.errors()},
        )

    @app.get("/healthz")
    async def healthz() -> dict:
        return {"status": "ok"}

    app.include_router(info_graph.router, prefix="/v1")
    return app


app = create_app()
