from fastapi import FastAPI

from .routers import ai_detect


def create_app() -> FastAPI:
    app = FastAPI(title="AI Text Detector Service", version="1.0.0")

    @app.get("/healthz")
    async def healthz() -> dict:
        return {"status": "ok"}

    app.include_router(ai_detect.router, prefix="/v1")
    return app


app = create_app()
