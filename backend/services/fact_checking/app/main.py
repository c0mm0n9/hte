from fastapi import FastAPI

from .routers import fact_check


def create_app() -> FastAPI:
    app = FastAPI(title="Fact Checking Service", version="1.0.0")

    @app.get("/healthz")
    async def healthz() -> dict:
        return {"status": "ok"}

    app.include_router(fact_check.router, prefix="/v1")
    return app


app = create_app()

