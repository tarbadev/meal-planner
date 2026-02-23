"""Planner routes — plan generation, current plan, manual plan edits."""

import logging
import random
import threading
import time
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app import config
from app.db import crud
from app.db.engine import get_db
from app.planner import MealPlanner, PlannedMeal, WeeklyPlan, add_cook_once_slots
from app.recipes import Recipe
from app.shopping_list import generate_shopping_list
from app.shopping_normalizer import apply_exclusions, llm_normalize

logger = logging.getLogger(__name__)
router = APIRouter()

# ---------------------------------------------------------------------------
# Background normalization task tracking (in-memory; ephemeral by design)
# ---------------------------------------------------------------------------
_norm_tasks: dict[str, dict] = {}
_norm_lock = threading.Lock()
_NORM_TASK_TTL = 3600


def _norm_task_run(task_id: str, snapshot, plan_id: str, db_url: str) -> None:
    """Background thread: LLM-normalize snapshot and persist to DB."""
    import asyncio

    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    async def _run():
        engine = create_async_engine(db_url, echo=False)
        SessionLocal = async_sessionmaker(engine, expire_on_commit=False)
        try:
            result = llm_normalize(snapshot)
            async with SessionLocal() as db:
                await crud.save_shopping_list(db, plan_id, result)
            with _norm_lock:
                _norm_tasks[task_id] = {
                    "status": "done",
                    "created_at": _norm_tasks.get(task_id, {}).get("created_at", time.time()),
                    "items": [
                        {
                            "item": i.item,
                            "quantity": i.quantity,
                            "unit": i.unit,
                            "category": i.category,
                            "sources": i.sources,
                        }
                        for i in result.items
                    ],
                }
        except Exception:
            logger.exception("Background normalization failed", extra={"task_id": task_id})
            with _norm_lock:
                _norm_tasks[task_id] = {
                    "status": "failed",
                    "created_at": _norm_tasks.get(task_id, {}).get("created_at", time.time()),
                    "items": None,
                }
        finally:
            await engine.dispose()

    asyncio.run(_run())


def _start_normalization(snapshot, plan_id: str) -> str:
    task_id = str(uuid.uuid4())
    now = time.time()
    with _norm_lock:
        stale = [k for k, v in _norm_tasks.items() if now - v.get("created_at", now) > _NORM_TASK_TTL]
        for k in stale:
            del _norm_tasks[k]
        _norm_tasks[task_id] = {"status": "pending", "items": None, "created_at": now}
    t = threading.Thread(
        target=_norm_task_run,
        args=(task_id, snapshot, plan_id, config.DATABASE_URL),
        daemon=True,
    )
    t.start()
    return task_id


def _serialize_plan(plan: WeeklyPlan | None) -> dict | None:
    if plan is None:
        return None
    return {
        "meals": [
            {
                "day": meal.day,
                "meal_type": meal.meal_type,
                "recipe_id": meal.recipe.id,
                "recipe_name": meal.recipe.name,
                "portions": meal.portions,
                "calories": meal.calories,
                "protein": meal.protein,
                "carbs": meal.carbs,
                "fat": meal.fat,
                "saturated_fat": meal.saturated_fat,
                "polyunsaturated_fat": meal.polyunsaturated_fat,
                "monounsaturated_fat": meal.monounsaturated_fat,
                "sodium": meal.sodium,
                "potassium": meal.potassium,
                "fiber": meal.fiber,
                "sugar": meal.sugar,
                "vitamin_a": meal.vitamin_a,
                "vitamin_c": meal.vitamin_c,
                "calcium": meal.calcium,
                "iron": meal.iron,
                "prep_time": meal.recipe.prep_time_minutes,
                "cook_time": meal.recipe.cook_time_minutes,
                "total_time": meal.recipe.total_time_minutes,
                "meal_source": meal.meal_source,
                "linked_meal": meal.linked_meal,
                "image_url": meal.recipe.image_url,
            }
            for meal in plan.meals
        ],
        "totals": {
            "calories": plan.total_calories,
            "protein": plan.total_protein,
            "carbs": plan.total_carbs,
            "fat": plan.total_fat,
            "saturated_fat": plan.total_saturated_fat,
            "polyunsaturated_fat": plan.total_polyunsaturated_fat,
            "monounsaturated_fat": plan.total_monounsaturated_fat,
            "sodium": plan.total_sodium,
            "potassium": plan.total_potassium,
            "fiber": plan.total_fiber,
            "sugar": plan.total_sugar,
            "vitamin_a": plan.total_vitamin_a,
            "vitamin_c": plan.total_vitamin_c,
            "calcium": plan.total_calcium,
            "iron": plan.total_iron,
        },
        "daily_averages": {
            "calories": plan.avg_daily_calories,
            "protein": plan.avg_daily_protein,
            "carbs": plan.avg_daily_carbs,
            "fat": plan.avg_daily_fat,
            "saturated_fat": plan.avg_daily_saturated_fat,
            "polyunsaturated_fat": plan.avg_daily_polyunsaturated_fat,
            "monounsaturated_fat": plan.avg_daily_monounsaturated_fat,
            "sodium": plan.avg_daily_sodium,
            "potassium": plan.avg_daily_potassium,
            "fiber": plan.avg_daily_fiber,
            "sugar": plan.avg_daily_sugar,
            "vitamin_a": plan.avg_daily_vitamin_a,
            "vitamin_c": plan.avg_daily_vitamin_c,
            "calcium": plan.avg_daily_calcium,
            "iron": plan.avg_daily_iron,
        },
        "daily_nutrition": plan.get_daily_nutrition(),
        "daily_calorie_limit": plan.daily_calorie_limit,
    }


def _convert_plan_to_manual_overrides(plan: WeeklyPlan) -> dict:
    result: dict = {}
    for meal in plan.meals:
        result.setdefault(meal.day, {})[meal.meal_type] = {
            "recipe_id": meal.recipe.id,
            "servings": meal.household_portions,
            "meal_source": meal.meal_source,
            "linked_meal": meal.linked_meal,
        }
    return result


async def _rebuild_plan_from_overrides(
    db: AsyncSession,
    overrides: dict,
    recipes: list[Recipe],
    calorie_limit: float | None = None,
) -> tuple[WeeklyPlan, str]:
    """Rebuild WeeklyPlan from overrides dict and persist it."""
    effective_limit = calorie_limit if calorie_limit is not None else config.DAILY_CALORIE_LIMIT
    meals = []
    for day, day_meals in overrides.items():
        for meal_type, meal_data in day_meals.items():
            recipe = next((r for r in recipes if r.id == meal_data["recipe_id"]), None)
            if recipe:
                meals.append(
                    PlannedMeal(
                        day=day,
                        meal_type=meal_type,
                        recipe=recipe,
                        household_portions=meal_data["servings"],
                        meal_source=meal_data.get("meal_source", "fresh"),
                        linked_meal=meal_data.get("linked_meal"),
                    )
                )
    plan = WeeklyPlan(meals=meals, daily_calorie_limit=effective_limit)
    plan_id = await crud.save_plan(db, config.DEFAULT_HOUSEHOLD_ID, plan, overrides)

    raw_list = generate_shopping_list(plan)
    excluded = await crud.get_excluded_ingredients(db, config.DEFAULT_HOUSEHOLD_ID)
    sl = apply_exclusions(raw_list, excluded)
    await crud.save_shopping_list(db, plan_id, sl)

    return plan, plan_id


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post("/generate")
async def generate(db: AsyncSession = Depends(get_db)):
    """Generate a new weekly meal plan."""
    logger.info("Generating weekly meal plan")

    recipes = await crud.get_recipes(db, config.DEFAULT_HOUSEHOLD_ID)
    planner = MealPlanner(
        household_portions=config.TOTAL_PORTIONS,
        meal_schedule=config.MEAL_SCHEDULE,
        daily_calorie_limit=config.DAILY_CALORIE_LIMIT,
        meal_calorie_splits=config.MEAL_CALORIE_SPLITS,
    )
    plan = planner.generate_weekly_plan(recipes)
    if config.COOK_ONCE_PLANNING:
        plan = add_cook_once_slots(plan, adult_portions=config.PACKED_LUNCH_PORTIONS)

    overrides = _convert_plan_to_manual_overrides(plan)
    plan_id = await crud.save_plan(db, config.DEFAULT_HOUSEHOLD_ID, plan, overrides)

    raw_list = generate_shopping_list(plan)
    excluded = await crud.get_excluded_ingredients(db, config.DEFAULT_HOUSEHOLD_ID)
    sl = apply_exclusions(raw_list, excluded)
    await crud.save_shopping_list(db, plan_id, sl)

    norm_task_id = _start_normalization(sl, plan_id)

    return {
        "success": True,
        "message": "Weekly plan generated successfully",
        "normalization_task_id": norm_task_id,
    }


@router.post("/generate-with-schedule")
async def generate_with_schedule(request: Request, db: AsyncSession = Depends(get_db)):
    """Generate a meal plan with custom schedule and per-meal servings."""
    logger.info("Generating weekly plan with schedule")

    try:
        data = await request.json()
    except Exception:
        raise HTTPException(400, detail="Invalid JSON") from None

    schedule = data.get("schedule", {})
    if not schedule:
        raise HTTPException(400, detail="Schedule is required")

    portions = data.get("portions", config.TOTAL_PORTIONS)
    calorie_limit = data.get("calorie_limit", config.DAILY_CALORIE_LIMIT)
    max_derived = int(data.get("max_derived", config.COOK_ONCE_MAX_DERIVED))

    recipes = await crud.get_recipes(db, config.DEFAULT_HOUSEHOLD_ID)

    meal_slots = []
    no_cook_slots: set[tuple[str, str]] = set()
    for day, day_meals in schedule.items():
        for meal_type, slot_data in day_meals.items():
            if isinstance(slot_data, dict):
                servings = slot_data.get("servings", portions)
                can_cook = slot_data.get("can_cook", True)
            else:
                servings = slot_data
                can_cook = True
            meal_slots.append((day, meal_type, servings, can_cook))
            if not can_cook:
                no_cook_slots.add((day, meal_type))

    if len(recipes) < len(meal_slots):
        raise HTTPException(
            400,
            detail=f"Need at least {len(meal_slots)} recipes. Only {len(recipes)} available.",
        )

    overrides: dict = {}
    used_recipes: set[str] = set()

    for day, meal_type, servings, can_cook in meal_slots:
        suitable = [r for r in recipes if meal_type in r.tags and r.id not in used_recipes]
        if not suitable:
            suitable = [r for r in recipes if r.id not in used_recipes]
        if not suitable:
            raise HTTPException(400, detail=f"Not enough recipes for {day} {meal_type}")

        if not can_cook:
            reheatable = [r for r in suitable if r.reheats_well]
            if not reheatable:
                reheatable = [r for r in recipes if r.reheats_well and r.id not in used_recipes]
            if reheatable:
                suitable = reheatable
            else:
                logger.warning("No reheatable recipes left for no-cook slot %s %s", day, meal_type)

        recipe = random.choice(suitable)
        used_recipes.add(recipe.id)
        overrides.setdefault(day, {})[meal_type] = {
            "recipe_id": recipe.id,
            "servings": servings,
        }

    plan, plan_id = await _rebuild_plan_from_overrides(db, overrides, recipes, calorie_limit)

    if config.COOK_ONCE_PLANNING and plan:
        plan = add_cook_once_slots(
            plan,
            adult_portions=config.PACKED_LUNCH_PORTIONS,
            no_cook_slots=frozenset(no_cook_slots),
            max_derived=max_derived,
        )
        overrides = _convert_plan_to_manual_overrides(plan)
        plan_id = await crud.save_plan(db, config.DEFAULT_HOUSEHOLD_ID, plan, overrides)
        raw_list = generate_shopping_list(plan)
        excluded = await crud.get_excluded_ingredients(db, config.DEFAULT_HOUSEHOLD_ID)
        sl = apply_exclusions(raw_list, excluded)
        await crud.save_shopping_list(db, plan_id, sl)

    norm_task_id = _start_normalization(
        await crud.get_shopping_list(db, plan_id), plan_id
    )

    return {
        "success": True,
        "message": f"Generated plan with {len(meal_slots)} meals",
        "portions": portions,
        "calorie_limit": calorie_limit,
        "normalization_task_id": norm_task_id,
    }


@router.get("/current-plan")
async def get_current_plan(db: AsyncSession = Depends(get_db)):
    """Get the current weekly plan."""
    logger.debug("Fetching current plan")
    plan, plan_id = await crud.get_current_plan(db, config.DEFAULT_HOUSEHOLD_ID)

    if plan is None:
        return {"plan": None, "message": "No plan generated yet"}

    sl = await crud.get_shopping_list(db, plan_id)

    return {
        "plan": _serialize_plan(plan),
        "shopping_list": {
            "items": [
                {
                    "item": item.item,
                    "quantity": round(item.quantity, 2) if item.quantity is not None else None,
                    "unit": item.unit,
                    "category": item.category,
                    "sources": item.sources,
                }
                for item in sl.items
            ],
            "items_by_category": {
                category: [
                    {
                        "item": item.item,
                        "quantity": round(item.quantity, 2) if item.quantity is not None else None,
                        "unit": item.unit,
                        "sources": item.sources,
                    }
                    for item in items
                ]
                for category, items in sl.items_by_category.items()
            },
        },
    }


@router.put("/current-plan/meals")
async def update_current_plan_meal(request: Request, db: AsyncSession = Depends(get_db)):
    """Update a specific meal slot in the current plan."""
    logger.info("Updating meal slot in current plan")

    try:
        data = await request.json()
    except Exception:
        raise HTTPException(400, detail="Invalid JSON") from None

    required = ["day", "meal_type", "recipe_id"]
    for field in required:
        if field not in data:
            raise HTTPException(400, detail=f"Missing required field: {field}")

    day = data["day"]
    meal_type = data["meal_type"]
    recipe_id = data["recipe_id"]
    servings = data.get("servings", config.TOTAL_PORTIONS)

    recipe = await crud.get_recipe_by_id(db, recipe_id)
    if not recipe:
        raise HTTPException(404, detail=f"Recipe not found: {recipe_id}")

    plan, plan_id = await crud.get_current_plan(db, config.DEFAULT_HOUSEHOLD_ID)
    overrides = _convert_plan_to_manual_overrides(plan) if plan else {}
    overrides.setdefault(day, {})[meal_type] = {"recipe_id": recipe_id, "servings": servings}

    recipes = await crud.get_recipes(db, config.DEFAULT_HOUSEHOLD_ID)
    await _rebuild_plan_from_overrides(db, overrides, recipes)

    return {"success": True, "message": f"Added {recipe.name} to {day} {meal_type}"}


@router.post("/manual-plan/add-meal")
async def add_meal_to_plan(request: Request, db: AsyncSession = Depends(get_db)):
    """Add a meal to the plan."""
    logger.info("Adding meal to plan")

    try:
        data = await request.json()
    except Exception:
        raise HTTPException(400, detail="Invalid JSON") from None

    required = ["day", "meal_type", "recipe_id", "servings"]
    for field in required:
        if field not in data:
            raise HTTPException(400, detail=f"Missing required field: {field}")

    day, meal_type, recipe_id = data["day"], data["meal_type"], data["recipe_id"]
    servings = data["servings"]
    if not isinstance(servings, (int, float)) or servings <= 0:
        raise HTTPException(400, detail="servings must be a positive number")

    recipe = await crud.get_recipe_by_id(db, recipe_id)
    if not recipe:
        raise HTTPException(404, detail=f"Recipe not found: {recipe_id}")

    plan, _ = await crud.get_current_plan(db, config.DEFAULT_HOUSEHOLD_ID)
    overrides = _convert_plan_to_manual_overrides(plan) if plan else {}
    overrides.setdefault(day, {})[meal_type] = {"recipe_id": recipe_id, "servings": servings}

    recipes = await crud.get_recipes(db, config.DEFAULT_HOUSEHOLD_ID)
    await _rebuild_plan_from_overrides(db, overrides, recipes)

    return {"success": True, "message": f"Added {recipe.name} to {day} {meal_type}"}


@router.post("/manual-plan/remove-meal")
async def remove_meal_from_plan(request: Request, db: AsyncSession = Depends(get_db)):
    """Remove a meal from the plan."""
    logger.info("Removing meal from plan")

    try:
        data = await request.json()
    except Exception:
        raise HTTPException(400, detail="Invalid JSON") from None

    day = data.get("day")
    meal_type = data.get("meal_type")
    if not day or not meal_type:
        raise HTTPException(400, detail="Missing day or meal_type")

    plan, _ = await crud.get_current_plan(db, config.DEFAULT_HOUSEHOLD_ID)
    overrides = _convert_plan_to_manual_overrides(plan) if plan else {}

    if day in overrides and meal_type in overrides[day]:
        del overrides[day][meal_type]
        if not overrides[day]:
            del overrides[day]

    recipes = await crud.get_recipes(db, config.DEFAULT_HOUSEHOLD_ID)
    await _rebuild_plan_from_overrides(db, overrides, recipes)

    return {"success": True, "message": f"Removed meal from {day} {meal_type}"}


@router.post("/manual-plan/update-servings")
async def update_meal_servings(request: Request, db: AsyncSession = Depends(get_db)):
    """Update servings for a meal in the plan."""
    logger.info("Updating meal servings")

    try:
        data = await request.json()
    except Exception:
        raise HTTPException(400, detail="Invalid JSON") from None

    day = data.get("day")
    meal_type = data.get("meal_type")
    servings = data.get("servings")

    if not day or not meal_type or servings is None:
        raise HTTPException(400, detail="Missing required fields")
    if not isinstance(servings, (int, float)) or servings <= 0:
        raise HTTPException(400, detail="servings must be a positive number")

    plan, _ = await crud.get_current_plan(db, config.DEFAULT_HOUSEHOLD_ID)
    overrides = _convert_plan_to_manual_overrides(plan) if plan else {}

    if day not in overrides or meal_type not in overrides.get(day, {}):
        raise HTTPException(404, detail="Meal not found in plan")

    overrides[day][meal_type]["servings"] = servings
    recipes = await crud.get_recipes(db, config.DEFAULT_HOUSEHOLD_ID)
    await _rebuild_plan_from_overrides(db, overrides, recipes)

    return {"success": True, "message": f"Updated servings for {day} {meal_type}"}


@router.post("/manual-plan/regenerate-meal")
async def regenerate_meal(request: Request, db: AsyncSession = Depends(get_db)):
    """Regenerate a specific meal with a new random recipe."""
    logger.info("Regenerating a specific meal")

    try:
        data = await request.json()
    except Exception:
        raise HTTPException(400, detail="Invalid JSON") from None

    day = data.get("day")
    meal_type = data.get("meal_type")
    if not day or not meal_type:
        raise HTTPException(400, detail="Missing day or meal_type")

    plan, _ = await crud.get_current_plan(db, config.DEFAULT_HOUSEHOLD_ID)
    overrides = _convert_plan_to_manual_overrides(plan) if plan else {}

    if day not in overrides or meal_type not in overrides.get(day, {}):
        raise HTTPException(404, detail="Meal not found in plan")

    current_servings = overrides[day][meal_type]["servings"]
    current_recipe_id = overrides[day][meal_type]["recipe_id"]

    recipes = await crud.get_recipes(db, config.DEFAULT_HOUSEHOLD_ID)
    available = [r for r in recipes if r.id != current_recipe_id]
    if not available:
        raise HTTPException(400, detail="No other recipes available")

    matching = [r for r in available if meal_type.lower() in [t.lower() for t in r.tags]]
    new_recipe = random.choice(matching) if matching else random.choice(available)

    overrides[day][meal_type] = {"recipe_id": new_recipe.id, "servings": current_servings}
    await _rebuild_plan_from_overrides(db, overrides, recipes)

    return {
        "success": True,
        "message": f"Regenerated {day} {meal_type}",
        "recipe_name": new_recipe.name,
    }


@router.post("/manual-plan/clear")
async def clear_manual_plan(db: AsyncSession = Depends(get_db)):
    """Clear the entire plan."""
    logger.info("Clearing plan")
    # Save an empty plan to signal "no plan"
    # We achieve this by simply not saving a new plan row; the old one remains
    # but will have no meals effectively shown once overrides are empty.
    # For a clean clear, just save a plan row with no meals and empty overrides.
    from sqlalchemy import select

    from app.db.models import WeeklyPlanModel
    stmt = select(WeeklyPlanModel).where(
        WeeklyPlanModel.household_id == config.DEFAULT_HOUSEHOLD_ID
    ).order_by(WeeklyPlanModel.created_at.desc()).limit(1)
    result = await db.execute(stmt)
    latest = result.scalar_one_or_none()
    if latest:
        await db.delete(latest)
        await db.commit()

    return {"success": True, "message": "Plan cleared"}


@router.get("/shopping-list/normalize/{task_id}")
async def get_normalization_status(task_id: str):
    """Poll the status of a background normalization task."""
    logger.debug("Polling normalization status", extra={"task_id": task_id})
    with _norm_lock:
        task = dict(_norm_tasks.get(task_id, {"status": "not_found", "items": None}))
    return task
