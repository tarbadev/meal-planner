"""Async SQLAlchemy engine, session factory, and startup helpers."""

from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app import config

engine = create_async_engine(
    config.DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: yield an AsyncSession, close it when done."""
    async with AsyncSessionLocal() as session:
        yield session


async def ensure_default_household(db: AsyncSession) -> None:
    """Create the default household row if it doesn't exist yet.

    Called once during the FastAPI lifespan so every subsequent request
    can safely assume household_id=DEFAULT_HOUSEHOLD_ID exists.
    """
    await db.execute(
        text("""
            INSERT INTO households (id, name)
            VALUES (:id, 'Default')
            ON CONFLICT (id) DO NOTHING
        """),
        {"id": config.DEFAULT_HOUSEHOLD_ID},
    )
    await db.commit()
