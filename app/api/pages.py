"""Page and health-check routes."""

import logging

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app import config
from app.db.engine import get_db

logger = logging.getLogger(__name__)

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/")
async def index(request: Request):
    """Render the web UI."""
    logger.debug("Rendering index page")
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "current_plan": None,
            "current_shopping_list": None,
            "household_portions": config.TOTAL_PORTIONS,
            "config": config,
        },
    )


@router.get("/health")
async def health(db: AsyncSession = Depends(get_db)):
    """Health check — verifies the app is running and the DB is reachable."""
    try:
        await db.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception:
        logger.exception("Health check DB ping failed")
        db_status = "error"

    status = "ok" if db_status == "ok" else "degraded"
    return {"status": status, "db": db_status}


@router.post("/share-recipe")
async def share_recipe(request: Request):
    """Handle PWA share target for recipe URLs and text."""
    from urllib.parse import quote

    form = await request.form()
    url = form.get("url", "").strip()
    title = form.get("title", "").strip()
    text_val = form.get("text", "").strip()

    if url:
        return RedirectResponse(url=f"/?import_url={url}", status_code=303)
    if text_val:
        return RedirectResponse(url=f"/?import_text={quote(text_val)}", status_code=303)
    if title:
        return RedirectResponse(url=f"/?import_text={quote(title)}", status_code=303)
    return RedirectResponse(url="/", status_code=303)
