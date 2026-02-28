from fastapi import FastAPI

from .routers import media


def create_app() -> FastAPI:
    app = FastAPI(title="Media Checking Service", version="1.0.0")

    @app.get("/healthz")
    async def healthz() -> dict:
        return {"status": "ok"}

    app.include_router(media.router, prefix="/v1")
    return app


app = create_app()
