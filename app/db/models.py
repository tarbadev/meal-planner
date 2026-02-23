"""SQLAlchemy 2.0 ORM models.

Uses `JSON` as the portable base type so the same model definitions work
with both PostgreSQL (production) and SQLite (integration tests).  The
Alembic migration uses Postgres-native DDL (JSONB, ARRAY, GIN indexes)
for production; in tests SQLAlchemy's create_all emits plain JSON/TEXT.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Float,
    ForeignKey,
    Integer,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    pass


class Household(Base):
    __tablename__ = "households"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    recipes: Mapped[list["RecipeModel"]] = relationship(
        back_populates="household", cascade="all, delete-orphan"
    )
    weekly_plans: Mapped[list["WeeklyPlanModel"]] = relationship(
        back_populates="household", cascade="all, delete-orphan"
    )
    excluded_ingredients: Mapped[list["ExcludedIngredientModel"]] = relationship(
        back_populates="household", cascade="all, delete-orphan"
    )


class RecipeModel(Base):
    __tablename__ = "recipes"

    id: Mapped[str] = mapped_column(Text, primary_key=True)  # slug
    household_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("households.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    servings: Mapped[int] = mapped_column(Integer, nullable=False, default=4)
    prep_time_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cook_time_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # JSON in SQLite, JSONB in Postgres (migration handles DDL)
    nutrition: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    tags: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    ingredients: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    instructions: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    source_url: Mapped[str | None] = mapped_column(Text)
    image_url: Mapped[str | None] = mapped_column(Text)
    reheats_well: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    stores_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    packs_well_as_lunch: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )

    household: Mapped["Household | None"] = relationship(back_populates="recipes")
    planned_meals: Mapped[list["PlannedMealModel"]] = relationship(
        back_populates="recipe"
    )


class WeeklyPlanModel(Base):
    __tablename__ = "weekly_plans"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=lambda: str(uuid.uuid4()))
    household_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("households.id", ondelete="CASCADE"),
        index=True,
    )
    daily_calorie_limit: Mapped[float | None] = mapped_column(Float)
    manual_overrides: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    household: Mapped["Household"] = relationship(back_populates="weekly_plans")
    planned_meals: Mapped[list["PlannedMealModel"]] = relationship(
        back_populates="plan", cascade="all, delete-orphan"
    )
    shopping_list_items: Mapped[list["ShoppingListItemModel"]] = relationship(
        back_populates="plan", cascade="all, delete-orphan"
    )


class PlannedMealModel(Base):
    __tablename__ = "planned_meals"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=lambda: str(uuid.uuid4()))
    plan_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("weekly_plans.id", ondelete="CASCADE"),
        index=True,
    )
    recipe_id: Mapped[str] = mapped_column(
        Text, ForeignKey("recipes.id", ondelete="RESTRICT")
    )
    day: Mapped[str] = mapped_column(Text, nullable=False)
    meal_type: Mapped[str] = mapped_column(Text, nullable=False)
    household_portions: Mapped[float] = mapped_column(Float, nullable=False)
    meal_source: Mapped[str] = mapped_column(Text, nullable=False, default="fresh")
    linked_meal: Mapped[str | None] = mapped_column(Text)

    plan: Mapped["WeeklyPlanModel"] = relationship(back_populates="planned_meals")
    recipe: Mapped["RecipeModel"] = relationship(back_populates="planned_meals")


class ShoppingListItemModel(Base):
    __tablename__ = "shopping_list_items"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=lambda: str(uuid.uuid4()))
    plan_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("weekly_plans.id", ondelete="CASCADE"),
        index=True,
    )
    item: Mapped[str] = mapped_column(Text, nullable=False)
    quantity: Mapped[float | None] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(Text, nullable=False, default="")
    category: Mapped[str] = mapped_column(Text, nullable=False, default="other")
    sources: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    checked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    plan: Mapped["WeeklyPlanModel"] = relationship(back_populates="shopping_list_items")


class ExcludedIngredientModel(Base):
    __tablename__ = "excluded_ingredients"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=lambda: str(uuid.uuid4()))
    household_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("households.id", ondelete="CASCADE"),
    )
    ingredient: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (UniqueConstraint("household_id", "ingredient"),)

    household: Mapped["Household"] = relationship(
        back_populates="excluded_ingredients"
    )
