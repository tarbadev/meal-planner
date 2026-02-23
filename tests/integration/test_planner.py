"""Integration tests — plan generation and persistence."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import crud
from tests.conftest import TEST_HOUSEHOLD_ID, create_test_recipe


def _seed_recipes(count: int = 12):
    """Return a list of simple test recipes with dinner tags."""
    return [
        create_test_recipe(
            recipe_id=f"recipe-{i}",
            name=f"Recipe {i}",
            tags=["dinner"],
            ingredients=[{"item": f"ingredient-{i}", "quantity": 1, "unit": "cup"}],
            instructions=["Cook."],
        )
        for i in range(count)
    ]


@pytest.mark.asyncio
async def test_generate_creates_plan(client, db_session: AsyncSession):
    """POST /generate should create a plan and persist it to DB."""
    for r in _seed_recipes(12):
        await crud.upsert_recipe(db_session, r, TEST_HOUSEHOLD_ID)

    resp = await client.post("/generate")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True

    plan, plan_id = await crud.get_current_plan(db_session, TEST_HOUSEHOLD_ID)
    assert plan is not None
    assert len(plan.meals) > 0
    assert plan_id is not None


@pytest.mark.asyncio
async def test_current_plan_no_plan(client):
    """GET /current-plan with no plan should return {plan: null}."""
    resp = await client.get("/current-plan")
    assert resp.status_code == 200
    assert resp.json()["plan"] is None


@pytest.mark.asyncio
async def test_current_plan_persists(client, db_session: AsyncSession):
    """Plan returned by GET /current-plan matches what was generated."""
    for r in _seed_recipes(12):
        await crud.upsert_recipe(db_session, r, TEST_HOUSEHOLD_ID)

    await client.post("/generate")

    resp = await client.get("/current-plan")
    assert resp.status_code == 200
    body = resp.json()
    assert body["plan"] is not None
    assert len(body["plan"]["meals"]) > 0
    assert "shopping_list" in body


@pytest.mark.asyncio
async def test_generate_with_schedule(client, db_session: AsyncSession):
    """POST /generate-with-schedule should respect provided schedule."""
    for r in _seed_recipes(12):
        await crud.upsert_recipe(db_session, r, TEST_HOUSEHOLD_ID)

    schedule = {
        "Monday": {"dinner": {"servings": 2.75, "can_cook": True}},
        "Tuesday": {"dinner": {"servings": 2.75, "can_cook": True}},
        "Wednesday": {"dinner": {"servings": 2.75, "can_cook": True}},
    }
    resp = await client.post("/generate-with-schedule", json={"schedule": schedule})
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True

    plan, _ = await crud.get_current_plan(db_session, TEST_HOUSEHOLD_ID)
    assert plan is not None
    days = {m.day for m in plan.meals}
    assert days <= {"Monday", "Tuesday", "Wednesday"}


@pytest.mark.asyncio
async def test_generate_with_schedule_missing_schedule(client):
    resp = await client.post("/generate-with-schedule", json={})
    assert resp.status_code == 400
