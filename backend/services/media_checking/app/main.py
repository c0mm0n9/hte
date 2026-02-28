from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .routers import media


def create_app() -> FastAPI:
    app = FastAPI(title="Media Checking Service", version="1.0.0")

    @app.get("/healthz")
    async def healthz() -> dict:
        return {"status": "ok"}

    samples_dir = Path(__file__).resolve().parent.parent / "samples"
    if samples_dir.is_dir():
        app.mount("/samples", StaticFiles(directory=str(samples_dir)), name="samples")

    app.include_router(media.router, prefix="/v1")
    return app


app = create_app()
