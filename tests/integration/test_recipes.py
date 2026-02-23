"""Integration tests — recipe CRUD endpoints."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import crud
from app.recipes import Recipe
from tests.conftest import TEST_HOUSEHOLD_ID, create_test_recipe


def _sample_recipe(**kwargs) -> Recipe:
    defaults = {
        "recipe_id": "test-chicken",
        "name": "Test Chicken",
        "servings": 4,
        "tags": ["dinner"],
        "ingredients": [{"item": "chicken", "quantity": 500, "unit": "g"}],
        "instructions": ["Cook the chicken."],
    }
    defaults.update(kwargs)
    return create_test_recipe(**defaults)


# ---------------------------------------------------------------------------
# GET /api/recipes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_api_recipes_empty(client):
    r = await client.get("/api/recipes")
    assert r.status_code == 200
    body = r.json()
    assert body["recipes"] == []
    assert body["pagination"]["total_recipes"] == 0


@pytest.mark.asyncio
async def test_api_recipes_returns_inserted(client, db_session: AsyncSession):
    recipe = _sample_recipe()
    await crud.upsert_recipe(db_session, recipe, TEST_HOUSEHOLD_ID)

    r = await client.get("/api/recipes")
    assert r.status_code == 200
    names = [rec["name"] for rec in r.json()["recipes"]]
    assert "Test Chicken" in names


@pytest.mark.asyncio
async def test_api_recipes_search_filter(client, db_session: AsyncSession):
    await crud.upsert_recipe(db_session, _sample_recipe(recipe_id="r1", name="Chicken Curry"), TEST_HOUSEHOLD_ID)
    await crud.upsert_recipe(
        db_session,
        _sample_recipe(recipe_id="r2", name="Beef Stew", ingredients=[{"item": "beef", "quantity": 500, "unit": "g"}]),
        TEST_HOUSEHOLD_ID,
    )

    r = await client.get("/api/recipes?search=chicken")
    assert r.status_code == 200
    names = [rec["name"] for rec in r.json()["recipes"]]
    assert "Chicken Curry" in names
    assert "Beef Stew" not in names


@pytest.mark.asyncio
async def test_api_recipes_pagination(client, db_session: AsyncSession):
    for i in range(5):
        await crud.upsert_recipe(
            db_session,
            _sample_recipe(recipe_id=f"r{i}", name=f"Recipe {i}"),
            TEST_HOUSEHOLD_ID,
        )

    r = await client.get("/api/recipes?page=1&per_page=3")
    assert r.status_code == 200
    body = r.json()
    assert len(body["recipes"]) == 3
    assert body["pagination"]["total_recipes"] == 5
    assert body["pagination"]["has_next"] is True


# ---------------------------------------------------------------------------
# GET /recipes/<id>
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_recipe_found(client, db_session: AsyncSession):
    recipe = _sample_recipe()
    await crud.upsert_recipe(db_session, recipe, TEST_HOUSEHOLD_ID)

    r = await client.get(f"/recipes/{recipe.id}")
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == recipe.id
    assert body["name"] == recipe.name


@pytest.mark.asyncio
async def test_get_recipe_not_found(client):
    r = await client.get("/recipes/does-not-exist")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# POST /recipes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_recipe_minimal(client):
    payload = {
        "name": "Simple Soup",
        "servings": 4,
        "ingredients": ["1 onion", "2 cups broth"],
        "instructions": ["Boil everything."],
    }
    r = await client.post("/recipes", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert body["recipe"]["name"] == "Simple Soup"


@pytest.mark.asyncio
async def test_create_recipe_missing_name(client):
    payload = {
        "servings": 4,
        "ingredients": ["egg"],
        "instructions": ["Cook."],
    }
    r = await client.post("/recipes", json=payload)
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_create_recipe_missing_ingredients(client):
    payload = {
        "name": "Empty",
        "servings": 4,
        "ingredients": [],
        "instructions": ["Do something."],
    }
    r = await client.post("/recipes", json=payload)
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# PUT /recipes/<id>
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_recipe(client, db_session: AsyncSession):
    recipe = _sample_recipe()
    await crud.upsert_recipe(db_session, recipe, TEST_HOUSEHOLD_ID)

    updated_data = {
        "id": recipe.id,
        "name": "Updated Chicken",
        "servings": 6,
        "prep_time_minutes": 15,
        "cook_time_minutes": 30,
        "nutrition_per_serving": {"calories": 450, "protein": 30.0, "carbs": 20.0, "fat": 15.0},
        "tags": ["dinner", "updated"],
        "ingredients": [{"item": "chicken", "quantity": 600, "unit": "g"}],
        "instructions": ["Cook thoroughly."],
    }
    r = await client.put(f"/recipes/{recipe.id}", json=updated_data)
    assert r.status_code == 200
    assert r.json()["success"] is True

    # Verify DB state
    from_db = await crud.get_recipe_by_id(db_session, recipe.id)
    assert from_db is not None
    assert from_db.name == "Updated Chicken"
    assert from_db.servings == 6


@pytest.mark.asyncio
async def test_update_recipe_id_mismatch(client, db_session: AsyncSession):
    recipe = _sample_recipe()
    await crud.upsert_recipe(db_session, recipe, TEST_HOUSEHOLD_ID)

    r = await client.put(f"/recipes/{recipe.id}", json={"id": "wrong-id", "name": "X",
        "servings": 4, "prep_time_minutes": 0, "cook_time_minutes": 0,
        "nutrition_per_serving": {"calories": 100, "protein": 5.0, "carbs": 10.0, "fat": 2.0},
        "ingredients": [{"item": "x"}], "instructions": ["x"]})
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_update_recipe_not_found(client):
    r = await client.put("/recipes/nonexistent", json={
        "id": "nonexistent", "name": "X", "servings": 4,
        "prep_time_minutes": 0, "cook_time_minutes": 0,
        "nutrition_per_serving": {"calories": 0, "protein": 0.0, "carbs": 0.0, "fat": 0.0},
        "ingredients": [{"item": "x"}], "instructions": ["x"],
    })
    assert r.status_code == 404
