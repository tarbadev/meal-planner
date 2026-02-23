"""Integration tests — shopping list and excluded ingredients."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import crud
from tests.conftest import TEST_HOUSEHOLD_ID, create_test_recipe


def _recipe(idx: int = 0):
    return create_test_recipe(
        recipe_id=f"recipe-{idx}",
        name=f"Recipe {idx}",
        tags=["dinner"],
        ingredients=[{"item": f"ingredient-{idx}", "quantity": 1, "unit": "cup"}],
        instructions=["Cook."],
    )


async def _seed_and_generate(client, db_session, count: int = 12):
    for i in range(count):
        await crud.upsert_recipe(db_session, _recipe(i), TEST_HOUSEHOLD_ID)
    await client.post("/generate")


@pytest.mark.asyncio
async def test_shopping_list_included_in_current_plan(client, db_session: AsyncSession):
    await _seed_and_generate(client, db_session)

    resp = await client.get("/current-plan")
    assert resp.status_code == 200
    body = resp.json()
    assert "shopping_list" in body
    assert isinstance(body["shopping_list"]["items"], list)


@pytest.mark.asyncio
async def test_add_shopping_item(client, db_session: AsyncSession):
    await _seed_and_generate(client, db_session)

    resp = await client.post(
        "/shopping-list/add-item",
        json={"name": "Extra Milk", "quantity": 2, "unit": "liters", "category": "dairy"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["item"]["item"] == "Extra Milk"


@pytest.mark.asyncio
async def test_delete_shopping_item(client, db_session: AsyncSession):
    await _seed_and_generate(client, db_session)

    # Get current list to find an index
    plan_resp = await client.get("/current-plan")
    items = plan_resp.json()["shopping_list"]["items"]
    assert len(items) > 0

    resp = await client.post("/shopping-list/delete-item", json={"index": 0})
    assert resp.status_code == 200
    assert resp.json()["success"] is True

    # Verify one fewer item
    plan_resp2 = await client.get("/current-plan")
    items2 = plan_resp2.json()["shopping_list"]["items"]
    assert len(items2) == len(items) - 1


@pytest.mark.asyncio
async def test_update_shopping_item(client, db_session: AsyncSession):
    await _seed_and_generate(client, db_session)

    resp = await client.post(
        "/shopping-list/update-item",
        json={"index": 0, "quantity": 999, "name": "renamed-ingredient"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["item"]["quantity"] == 999
    assert body["item"]["item"] == "renamed-ingredient"


@pytest.mark.asyncio
async def test_shopping_item_no_list(client):
    """Shopping item operations without a plan should return 404."""
    resp = await client.post("/shopping-list/add-item", json={"name": "Milk", "quantity": 1})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_excluded_ingredients_default(client):
    """GET /excluded-ingredients returns a non-empty list (defaults)."""
    resp = await client.get("/excluded-ingredients")
    assert resp.status_code == 200
    items = resp.json()
    assert isinstance(items, list)
    assert len(items) > 0


@pytest.mark.asyncio
async def test_excluded_ingredients_update(client, db_session: AsyncSession):
    resp = await client.post(
        "/excluded-ingredients",
        json={"items": ["garlic", "onion"]},
    )
    assert resp.status_code == 200
    assert resp.json()["success"] is True

    get_resp = await client.get("/excluded-ingredients")
    items = get_resp.json()
    assert "garlic" in items
    assert "onion" in items


@pytest.mark.asyncio
async def test_excluded_ingredients_not_list(client):
    resp = await client.post("/excluded-ingredients", json={"items": "not-a-list"})
    assert resp.status_code == 400
