"""Integration tests — manual plan operations."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import crud
from tests.conftest import TEST_HOUSEHOLD_ID, create_test_recipe


def _recipe(idx: int = 0, **kwargs):
    defaults = {
        "recipe_id": f"recipe-{idx}",
        "name": f"Recipe {idx}",
        "tags": ["dinner"],
        "ingredients": [{"item": "egg", "quantity": 2, "unit": ""}],
        "instructions": ["Cook."],
    }
    defaults.update(kwargs)
    return create_test_recipe(**defaults)


async def _seed_and_generate(client, db_session, count: int = 12):
    for i in range(count):
        await crud.upsert_recipe(db_session, _recipe(i), TEST_HOUSEHOLD_ID)
    await client.post("/generate")


@pytest.mark.asyncio
async def test_add_meal_to_plan(client, db_session: AsyncSession):
    await _seed_and_generate(client, db_session)

    resp = await client.post(
        "/manual-plan/add-meal",
        json={"day": "Monday", "meal_type": "lunch", "recipe_id": "recipe-0", "servings": 2.75},
    )
    assert resp.status_code == 200
    assert resp.json()["success"] is True

    plan, _, _wsd = await crud.get_current_plan(db_session, TEST_HOUSEHOLD_ID)
    lunch_meals = [m for m in plan.meals if m.day == "Monday" and m.meal_type == "lunch"]
    assert len(lunch_meals) == 1
    assert lunch_meals[0].recipe.id == "recipe-0"


@pytest.mark.asyncio
async def test_add_meal_missing_fields(client, db_session: AsyncSession):
    await _seed_and_generate(client, db_session)
    resp = await client.post("/manual-plan/add-meal", json={"day": "Monday"})
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_remove_meal_from_plan(client, db_session: AsyncSession):
    await _seed_and_generate(client, db_session)

    # Add a meal first
    await client.post(
        "/manual-plan/add-meal",
        json={"day": "Saturday", "meal_type": "lunch", "recipe_id": "recipe-0", "servings": 2.75},
    )

    resp = await client.post(
        "/manual-plan/remove-meal",
        json={"day": "Saturday", "meal_type": "lunch"},
    )
    assert resp.status_code == 200

    plan, _, _wsd = await crud.get_current_plan(db_session, TEST_HOUSEHOLD_ID)
    lunch_meals = [m for m in plan.meals if m.day == "Saturday" and m.meal_type == "lunch"]
    assert len(lunch_meals) == 0


@pytest.mark.asyncio
async def test_update_servings(client, db_session: AsyncSession):
    await _seed_and_generate(client, db_session)

    # Get any meal from the plan
    plan, _, _wsd = await crud.get_current_plan(db_session, TEST_HOUSEHOLD_ID)
    assert plan.meals, "Expected at least one meal in plan"
    meal = plan.meals[0]

    resp = await client.post(
        "/manual-plan/update-servings",
        json={"day": meal.day, "meal_type": meal.meal_type, "servings": 5.0},
    )
    assert resp.status_code == 200

    updated_plan, _, _wsd = await crud.get_current_plan(db_session, TEST_HOUSEHOLD_ID)
    updated_meal = next(
        m for m in updated_plan.meals
        if m.day == meal.day and m.meal_type == meal.meal_type
    )
    assert updated_meal.household_portions == 5.0


@pytest.mark.asyncio
async def test_regenerate_meal(client, db_session: AsyncSession):
    await _seed_and_generate(client, db_session)

    plan, _, _wsd = await crud.get_current_plan(db_session, TEST_HOUSEHOLD_ID)
    meal = plan.meals[0]

    resp = await client.post(
        "/manual-plan/regenerate-meal",
        json={"day": meal.day, "meal_type": meal.meal_type},
    )
    assert resp.status_code == 200
    assert resp.json()["success"] is True


@pytest.mark.asyncio
async def test_clear_plan(client, db_session: AsyncSession):
    await _seed_and_generate(client, db_session)

    # Confirm plan exists
    plan, _, _wsd = await crud.get_current_plan(db_session, TEST_HOUSEHOLD_ID)
    assert plan is not None

    resp = await client.post("/manual-plan/clear")
    assert resp.status_code == 200

    plan_after, _, _wsd = await crud.get_current_plan(db_session, TEST_HOUSEHOLD_ID)
    assert plan_after is None
