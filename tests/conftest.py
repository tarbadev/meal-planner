"""Pytest configuration and shared fixtures.

Unit tests (test_planner, test_recipes, test_cook_once, etc.) use the
create_test_recipe() helper directly.

Integration tests (tests/integration/) use the async db_session and client
fixtures defined here.
"""

import os

# Set dummy API keys before any app module is imported so the lifespan startup
# check passes in the same way as production (no _is_testing() bypass needed).
os.environ.setdefault("USDA_API_KEY", "test-key")
os.environ.setdefault("OPENAI_API_KEY", "test-key")

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.models import Base
from app.recipes import Recipe

# ---------------------------------------------------------------------------
# Shared helper (used by unit tests)
# ---------------------------------------------------------------------------


def create_test_recipe(
    recipe_id: str,
    name: str,
    servings: int = 4,
    prep_time_minutes: int = 10,
    cook_time_minutes: int = 20,
    calories: int = 400,
    protein: float = 20.0,
    carbs: float = 40.0,
    fat: float = 15.0,
    tags: list | None = None,
    ingredients: list | None = None,
    instructions: list | None = None,
) -> Recipe:
    """Helper to create test Recipe with nested nutrition structure."""
    return Recipe(
        id=recipe_id,
        name=name,
        servings=servings,
        prep_time_minutes=prep_time_minutes,
        cook_time_minutes=cook_time_minutes,
        nutrition_per_serving={
            "calories": calories,
            "protein": protein,
            "carbs": carbs,
            "fat": fat,
        },
        tags=tags or [],
        ingredients=ingredients or [],
        instructions=instructions or [],
    )


# ---------------------------------------------------------------------------
# Integration test fixtures
# ---------------------------------------------------------------------------

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"
TEST_HOUSEHOLD_ID = "00000000-0000-0000-0000-000000000001"


@pytest.fixture
async def db_session():
    """Fresh in-memory SQLite DB for each test function."""
    # SQLite doesn't support gen_random_uuid() or ARRAY — the models use
    # Python-side defaults and JSON columns, so SQLite works fine for testing.
    engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})

    async with engine.begin() as conn:
        # Create tables — use SQLAlchemy metadata, not raw Postgres DDL
        await conn.run_sync(Base.metadata.create_all)

    async with async_sessionmaker(engine, expire_on_commit=False)() as session:
        # Seed the default household row
        from app.db.models import Household
        session.add(Household(id=TEST_HOUSEHOLD_ID, name="Default"))
        await session.commit()
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def client(db_session: AsyncSession):
    """HTTP test client wired to the FastAPI app with the test DB injected."""
    from app.db.engine import get_db
    from app.main import app

    async def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c
    app.dependency_overrides.clear()
