import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import health, tickets
from app.api.errors import register_error_handlers
from app.api.middleware import log_requests
from app.core.config import settings
from app.core.logging import configure_logging
from app.db.session import engine

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None]:
    configure_logging(settings.log_level)
    logger.info("app.startup")
    yield
    await engine.dispose()
    logger.info("app.shutdown")


app = FastAPI(title="Multiagent PM", lifespan=lifespan)
app.middleware("http")(log_requests)
register_error_handlers(app)
app.include_router(health.router)
app.include_router(tickets.router)
