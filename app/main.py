"""FastAPI application entry point."""

import logging
import os
from contextlib import asynccontextmanager

import sentry_sdk
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app import config
from app.db.engine import AsyncSessionLocal, engine, ensure_default_household
from app.logging_config import configure_logging

# Configure structured JSON logging at import time
configure_logging(os.environ.get("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)

# Sentry — no-op if SENTRY_DSN is not set
sentry_sdk.init(
    dsn=os.environ.get("SENTRY_DSN"),
    traces_sample_rate=0.1,
    environment=os.environ.get("ENV", "development"),
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: validate required config + ensure DB is seeded.
    Shutdown: dispose the async engine.
    """
    # Validate required API keys
    if not config.USDA_API_KEY:
        raise RuntimeError(
            "USDA_API_KEY environment variable is required. "
            "Get your free key at https://fdc.nal.usda.gov/api-key-signup.html"
        )
    if not config.OPENAI_API_KEY:
        raise RuntimeError(
            "OPENAI_API_KEY environment variable is required. "
            "Get your key at https://platform.openai.com/api-keys"
        )

    async with AsyncSessionLocal() as db:
        await ensure_default_household(db)

    logger.info("Meal planner started", extra={"env": os.environ.get("ENV", "development")})
    yield

    await engine.dispose()
    logger.info("Meal planner shutdown")


app = FastAPI(title="Meal Planner", lifespan=lifespan)

# Rate limiting via slowapi
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Static files
_static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(_static_dir):
    app.mount("/static", StaticFiles(directory=_static_dir), name="static")

# Routers
from app.api import (  # noqa: E402
    import_routes,
    pages,
    planner,
    recipes,
    shopping,
)

app.include_router(pages.router)
app.include_router(recipes.router)
app.include_router(planner.router)
app.include_router(shopping.router)
app.include_router(import_routes.router)
