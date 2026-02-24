"""Async CRUD helpers — used by FastAPI route handlers."""

from __future__ import annotations

import datetime
import uuid
from datetime import UTC

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import (
    ExcludedIngredientModel,
    PlannedMealModel,
    RecipeModel,
    ShoppingListItemModel,
    WeeklyPlanModel,
)
from app.planner import WeeklyPlan
from app.recipes import Recipe
from app.shopping_list import ShoppingList

# ---------------------------------------------------------------------------
# Recipes
# ---------------------------------------------------------------------------


async def get_recipes(
    db: AsyncSession,
    household_id: str,
    *,
    search: str = "",
    tags: list[str] | None = None,
    page: int = 1,
    per_page: int = 24,
) -> list[Recipe]:
    from app.recipes import Recipe

    stmt = select(RecipeModel).where(
        (RecipeModel.household_id == household_id) | (RecipeModel.household_id == None)  # noqa: E711
    )
    result = await db.execute(stmt)
    orm_recipes = result.scalars().all()

    recipes = [Recipe.from_orm_model(r) for r in orm_recipes]

    if search:
        search_lower = search.lower()
        recipes = [r for r in recipes if search_lower in r.search_blob]

    if tags:
        tags_lower = [t.lower() for t in tags]
        recipes = [
            r for r in recipes
            if all(req in [t.lower() for t in r.tags] for req in tags_lower)
        ]

    return recipes


async def get_recipe_by_id(
    db: AsyncSession, recipe_id: str
) -> Recipe | None:
    from app.recipes import Recipe

    result = await db.execute(
        select(RecipeModel).where(RecipeModel.slug == recipe_id)
    )
    orm = result.scalar_one_or_none()
    return Recipe.from_orm_model(orm) if orm else None


async def upsert_recipe(
    db: AsyncSession, recipe: Recipe, household_id: str
) -> Recipe:
    """Insert or update a recipe. Returns the saved Recipe."""
    data = recipe.to_db_dict()
    data["household_id"] = household_id

    result = await db.execute(
        select(RecipeModel).where(RecipeModel.slug == recipe.id)
    )
    existing = result.scalar_one_or_none()

    if existing:
        for key, value in data.items():
            setattr(existing, key, value)
        orm_obj = existing
    else:
        orm_obj = RecipeModel(**data)
        db.add(orm_obj)

    await db.commit()
    await db.refresh(orm_obj)
    from app.recipes import Recipe
    return Recipe.from_orm_model(orm_obj)


async def delete_recipe(db: AsyncSession, recipe_id: str) -> bool:
    result = await db.execute(
        select(RecipeModel).where(RecipeModel.slug == recipe_id)
    )
    obj = result.scalar_one_or_none()
    if obj is None:
        return False
    await db.delete(obj)
    await db.commit()
    return True


# ---------------------------------------------------------------------------
# Weekly plan
# ---------------------------------------------------------------------------


def _plan_row_to_weekly_plan(plan_row) -> WeeklyPlan:
    """Convert a WeeklyPlanModel ORM row to a WeeklyPlan dataclass."""
    from app.planner import PlannedMeal, WeeklyPlan
    from app.recipes import Recipe

    meals = []
    for pm in plan_row.planned_meals:
        recipe = Recipe.from_orm_model(pm.recipe)
        meals.append(
            PlannedMeal(
                day=pm.day,
                meal_type=pm.meal_type,
                recipe=recipe,
                household_portions=pm.household_portions,
                meal_source=pm.meal_source,
                linked_meal=pm.linked_meal,
            )
        )
    return WeeklyPlan(meals=meals, daily_calorie_limit=plan_row.daily_calorie_limit)


async def get_current_plan(
    db: AsyncSession, household_id: str
) -> tuple[WeeklyPlan | None, str | None, datetime.date | None]:
    """Return (WeeklyPlan, plan_id, week_start_date) for the most recent plan."""
    stmt = (
        select(WeeklyPlanModel)
        .where(WeeklyPlanModel.household_id == household_id)
        .order_by(WeeklyPlanModel.created_at.desc())
        .limit(1)
        .options(
            selectinload(WeeklyPlanModel.planned_meals).selectinload(
                PlannedMealModel.recipe
            )
        )
    )
    result = await db.execute(stmt)
    plan_row = result.scalar_one_or_none()

    if plan_row is None:
        return None, None, None

    return _plan_row_to_weekly_plan(plan_row), plan_row.id, plan_row.week_start_date


async def save_plan(
    db: AsyncSession,
    household_id: str,
    plan: WeeklyPlan,
    manual_overrides: dict | None = None,
    week_start_date: datetime.date | None = None,
) -> str:
    """INSERT a new weekly_plan row + its planned_meals atomically.

    Returns the new plan_id (string UUID).
    """
    if week_start_date is None:
        today = datetime.date.today()
        week_start_date = today - datetime.timedelta(days=today.weekday())

    # Enforce one plan per week — delete any existing plan for this household+week.
    old_result = await db.execute(
        select(WeeklyPlanModel).where(
            WeeklyPlanModel.household_id == household_id,
            WeeklyPlanModel.week_start_date == week_start_date,
        )
    )
    for old_plan in old_result.scalars().all():
        await db.delete(old_plan)
    await db.flush()

    plan_id = str(uuid.uuid4())
    plan_row = WeeklyPlanModel(
        id=plan_id,
        household_id=household_id,
        week_start_date=week_start_date,
        daily_calorie_limit=plan.daily_calorie_limit,
        manual_overrides=manual_overrides,
        created_at=datetime.datetime.now(UTC),
    )
    db.add(plan_row)
    await db.flush()

    # Pre-fetch slug → UUID mapping so planned_meals can store the UUID FK.
    slugs = list({meal.recipe.id for meal in plan.meals})
    slug_to_uuid: dict[str, str] = {}
    if slugs:
        rows = await db.execute(
            select(RecipeModel.slug, RecipeModel.id).where(RecipeModel.slug.in_(slugs))
        )
        slug_to_uuid = {row.slug: row.id for row in rows}

    for meal in plan.meals:
        recipe_uuid = slug_to_uuid.get(meal.recipe.id)
        if recipe_uuid is None:
            continue  # Recipe disappeared between plan generation and save — skip
        db.add(
            PlannedMealModel(
                id=str(uuid.uuid4()),
                plan_id=plan_id,
                recipe_id=recipe_uuid,
                day=meal.day,
                meal_type=meal.meal_type,
                household_portions=meal.household_portions,
                meal_source=meal.meal_source,
                linked_meal=meal.linked_meal,
            )
        )

    await db.commit()
    return plan_id


async def list_plans(
    db: AsyncSession, household_id: str
) -> list[dict]:
    """Return summary rows for all plans, newest-first."""
    from app.db.models import PlannedMealModel

    stmt = (
        select(
            WeeklyPlanModel.id,
            WeeklyPlanModel.week_start_date,
            WeeklyPlanModel.created_at,
            func.count(PlannedMealModel.id).label("meal_count"),
        )
        .outerjoin(PlannedMealModel, PlannedMealModel.plan_id == WeeklyPlanModel.id)
        .where(WeeklyPlanModel.household_id == household_id)
        .group_by(WeeklyPlanModel.id, WeeklyPlanModel.week_start_date, WeeklyPlanModel.created_at)
        .order_by(WeeklyPlanModel.week_start_date.desc())
    )
    result = await db.execute(stmt)
    rows = result.all()
    return [
        {
            "id": row.id,
            "week_start_date": row.week_start_date.isoformat(),
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "meal_count": row.meal_count,
        }
        for row in rows
    ]


async def get_plan_by_id(
    db: AsyncSession, plan_id: str, household_id: str
) -> tuple[WeeklyPlan | None, str | None, datetime.date | None]:
    """Return (WeeklyPlan, plan_id, week_start_date) for a specific plan UUID."""
    stmt = (
        select(WeeklyPlanModel)
        .where(
            WeeklyPlanModel.id == plan_id,
            WeeklyPlanModel.household_id == household_id,
        )
        .options(
            selectinload(WeeklyPlanModel.planned_meals).selectinload(
                PlannedMealModel.recipe
            )
        )
    )
    result = await db.execute(stmt)
    plan_row = result.scalar_one_or_none()

    if plan_row is None:
        return None, None, None

    return _plan_row_to_weekly_plan(plan_row), plan_row.id, plan_row.week_start_date


async def get_plan_by_week_start(
    db: AsyncSession, household_id: str, week_start: datetime.date
) -> tuple[WeeklyPlan | None, str | None]:
    """Return (WeeklyPlan, plan_id) for the plan anchored to week_start, or (None, None)."""
    stmt = (
        select(WeeklyPlanModel)
        .where(
            WeeklyPlanModel.household_id == household_id,
            WeeklyPlanModel.week_start_date == week_start,
        )
        .order_by(WeeklyPlanModel.created_at.desc())
        .limit(1)
        .options(
            selectinload(WeeklyPlanModel.planned_meals).selectinload(
                PlannedMealModel.recipe
            )
        )
    )
    result = await db.execute(stmt)
    plan_row = result.scalar_one_or_none()

    if plan_row is None:
        return None, None

    return _plan_row_to_weekly_plan(plan_row), plan_row.id


# ---------------------------------------------------------------------------
# Shopping list
# ---------------------------------------------------------------------------


async def get_shopping_list(
    db: AsyncSession, plan_id: str
) -> ShoppingList:
    from app.shopping_list import ShoppingList, ShoppingListItem

    stmt = (
        select(ShoppingListItemModel)
        .where(ShoppingListItemModel.plan_id == plan_id)
        .order_by(ShoppingListItemModel.sort_order)
    )
    result = await db.execute(stmt)
    rows = result.scalars().all()

    items = [
        ShoppingListItem(
            item=r.item,
            quantity=r.quantity,
            unit=r.unit,
            category=r.category,
            sources=r.sources or [],
            checked=r.checked,
        )
        for r in rows
    ]
    return ShoppingList(items=items)


async def save_shopping_list(
    db: AsyncSession, plan_id: str, sl: ShoppingList
) -> None:
    """Replace all shopping list items for plan_id atomically."""
    await db.execute(
        delete(ShoppingListItemModel).where(
            ShoppingListItemModel.plan_id == plan_id
        )
    )
    for i, item in enumerate(sl.items):
        db.add(
            ShoppingListItemModel(
                id=str(uuid.uuid4()),
                plan_id=plan_id,
                item=item.item,
                quantity=item.quantity,
                unit=item.unit,
                category=item.category,
                sources=item.sources if item.sources else [],
                checked=getattr(item, "checked", False),
                sort_order=i,
            )
        )
    await db.commit()


# ---------------------------------------------------------------------------
# Excluded ingredients
# ---------------------------------------------------------------------------

_DEFAULT_EXCLUDED = ["water", "salt", "ice"]


async def get_excluded_ingredients(
    db: AsyncSession, household_id: str
) -> list[str]:
    stmt = select(ExcludedIngredientModel.ingredient).where(
        ExcludedIngredientModel.household_id == household_id
    )
    result = await db.execute(stmt)
    rows = result.scalars().all()
    return list(rows) if rows else list(_DEFAULT_EXCLUDED)


async def save_excluded_ingredients(
    db: AsyncSession, household_id: str, items: list[str]
) -> None:
    await db.execute(
        delete(ExcludedIngredientModel).where(
            ExcludedIngredientModel.household_id == household_id
        )
    )
    for ingredient in items:
        stripped = ingredient.strip()
        if stripped:
            db.add(ExcludedIngredientModel(
                id=str(uuid.uuid4()),
                household_id=household_id,
                ingredient=stripped,
            ))
    await db.commit()
