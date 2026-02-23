"""Synchronous CRUD helpers — used by standalone scripts (not FastAPI routes).

These mirror the async CRUD functions in crud.py but use a regular
synchronous SQLAlchemy Session so scripts don't need an event loop.
"""

from __future__ import annotations

import uuid as _uuid_mod

from sqlalchemy import create_engine, delete, select
from sqlalchemy.orm import Session, sessionmaker

from app import config
from app.db.models import ExcludedIngredientModel, RecipeModel
from app.recipes import Recipe


def _sync_engine():
    """Return a synchronous psycopg3 engine derived from DATABASE_URL."""
    url = config.DATABASE_URL
    # Strip async driver aliases if present
    url = url.replace("+aiosqlite", "").replace("+asyncpg", "")
    return create_engine(url, pool_pre_ping=True)


def get_session() -> Session:
    """Return a new synchronous session (caller must close/commit)."""
    engine = _sync_engine()
    SessionLocal = sessionmaker(engine)
    return SessionLocal()


# ---------------------------------------------------------------------------
# Recipes
# ---------------------------------------------------------------------------


def get_recipes(
    db: Session,
    household_id: str,
) -> list[Recipe]:
    from app.recipes import Recipe

    stmt = select(RecipeModel).where(
        (RecipeModel.household_id == household_id) | (RecipeModel.household_id == None)  # noqa: E711
    )
    orm_recipes = db.execute(stmt).scalars().all()
    return [Recipe.from_orm_model(r) for r in orm_recipes]


def get_recipe_by_id(db: Session, recipe_id: str) -> Recipe | None:
    from app.recipes import Recipe

    result = db.execute(select(RecipeModel).where(RecipeModel.slug == recipe_id))
    orm = result.scalar_one_or_none()
    return Recipe.from_orm_model(orm) if orm else None


def upsert_recipe(db: Session, recipe: Recipe, household_id: str) -> Recipe:
    from app.recipes import Recipe

    data = recipe.to_db_dict()
    data["household_id"] = household_id

    existing = db.execute(
        select(RecipeModel).where(RecipeModel.slug == recipe.id)
    ).scalar_one_or_none()

    if existing:
        for key, value in data.items():
            setattr(existing, key, value)
        orm_obj = existing
    else:
        orm_obj = RecipeModel(**data)
        db.add(orm_obj)

    db.commit()
    db.refresh(orm_obj)
    return Recipe.from_orm_model(orm_obj)


# ---------------------------------------------------------------------------
# Excluded ingredients
# ---------------------------------------------------------------------------

_DEFAULT_EXCLUDED = ["water", "salt", "ice"]


def get_excluded_ingredients(db: Session, household_id: str) -> list[str]:
    stmt = select(ExcludedIngredientModel.ingredient).where(
        ExcludedIngredientModel.household_id == household_id
    )
    rows = db.execute(stmt).scalars().all()
    return list(rows) if rows else list(_DEFAULT_EXCLUDED)


def save_excluded_ingredients(
    db: Session, household_id: str, items: list[str]
) -> None:
    db.execute(
        delete(ExcludedIngredientModel).where(
            ExcludedIngredientModel.household_id == household_id
        )
    )
    for ingredient in items:
        stripped = ingredient.strip()
        if stripped:
            db.add(ExcludedIngredientModel(
                id=str(_uuid_mod.uuid4()),
                household_id=household_id,
                ingredient=stripped,
            ))
    db.commit()
