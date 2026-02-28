import logging

from fastapi import FastAPI

from .routers import agent

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("agent_gateway")


def create_app() -> FastAPI:
    app = FastAPI(title="Agent Gateway Service", version="1.0.0")

    @app.on_event("startup")
    async def startup() -> None:
        logger.info("Agent Gateway starting")

    @app.get("/healthz")
    async def healthz() -> dict:
        logger.debug("healthz")
        return {"status": "ok"}

    app.include_router(agent.router, prefix="/v1")
    return app


app = create_app()
