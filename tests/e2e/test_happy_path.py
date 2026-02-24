"""E2E happy-path tests.

Run locally:
    pytest tests/e2e/ -v

Run against a deployed environment:
    E2E_BASE_URL=https://your-app.up.railway.app pytest tests/e2e/ -v
"""

import pytest

# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


class TestHealth:
    def test_health_returns_ok(self, http):
        resp = http.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["db"] == "ok"


# ---------------------------------------------------------------------------
# Recipes
# ---------------------------------------------------------------------------


class TestRecipes:
    def test_list_recipes_returns_results(self, http, ensure_recipes):
        resp = http.get("/recipes")
        assert resp.status_code == 200
        data = resp.json()
        assert "recipes" in data
        assert len(data["recipes"]) > 0

    def test_recipe_has_required_fields(self, http, ensure_recipes):
        resp = http.get("/recipes")
        recipe = resp.json()["recipes"][0]
        for field in ("id", "name", "servings", "tags"):
            assert field in recipe, f"Missing field: {field}"

    def test_get_recipe_by_id(self, http, ensure_recipes):
        recipes = http.get("/recipes").json()["recipes"]
        recipe_id = recipes[0]["id"]
        resp = http.get(f"/recipes/{recipe_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == recipe_id

    def test_get_unknown_recipe_returns_404(self, http):
        resp = http.get("/recipes/this-recipe-does-not-exist")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Plan generation
# ---------------------------------------------------------------------------


class TestPlanGeneration:
    def test_plan_is_not_none(self, generated_plan):
        assert generated_plan["plan"] is not None

    def test_plan_has_meals(self, generated_plan):
        assert len(generated_plan["plan"]["meals"]) > 0

    def test_plan_has_plan_id(self, generated_plan):
        assert generated_plan.get("plan_id") is not None

    def test_plan_has_week_start_date(self, generated_plan):
        wsd = generated_plan.get("week_start_date")
        assert wsd is not None
        # Should be a YYYY-MM-DD string
        assert len(wsd) == 10
        assert wsd[4] == "-" and wsd[7] == "-"

    def test_plan_is_marked_current(self, generated_plan):
        assert generated_plan.get("is_current") is True

    def test_plan_meals_have_required_fields(self, generated_plan):
        for meal in generated_plan["plan"]["meals"]:
            for field in ("day", "meal_type", "recipe_id", "recipe_name", "portions"):
                assert field in meal, f"Meal missing field: {field}"

    def test_plan_has_totals(self, generated_plan):
        totals = generated_plan["plan"].get("totals")
        assert totals is not None
        assert "calories" in totals

    def test_plan_has_shopping_list(self, generated_plan):
        sl = generated_plan.get("shopping_list")
        assert sl is not None
        assert "items" in sl
        assert len(sl["items"]) > 0

    def test_shopping_list_items_have_required_fields(self, generated_plan):
        for item in generated_plan["shopping_list"]["items"]:
            for field in ("item", "category"):
                assert field in item, f"Shopping item missing field: {field}"


# ---------------------------------------------------------------------------
# Plan history  (GET /plans and GET /plans/{id})
# ---------------------------------------------------------------------------


class TestPlanHistory:
    def test_list_plans_returns_current(self, http, generated_plan):
        resp = http.get("/plans")
        assert resp.status_code == 200
        plans = resp.json()
        assert isinstance(plans, list)
        assert len(plans) >= 1
        ids = [p["id"] for p in plans]
        assert generated_plan["plan_id"] in ids

    def test_list_plans_entry_has_required_fields(self, http, generated_plan):
        plans = http.get("/plans").json()
        entry = next(p for p in plans if p["id"] == generated_plan["plan_id"])
        for field in ("id", "week_start_date", "meal_count"):
            assert field in entry, f"Plan list entry missing field: {field}"
        assert entry["meal_count"] > 0

    def test_get_plan_by_id_returns_plan(self, http, generated_plan):
        plan_id = generated_plan["plan_id"]
        resp = http.get(f"/plans/{plan_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["plan_id"] == plan_id
        assert data["is_current"] is True
        assert len(data["meals"]) > 0

    def test_get_plan_by_id_week_start_matches(self, http, generated_plan):
        plan_id = generated_plan["plan_id"]
        resp = http.get(f"/plans/{plan_id}")
        assert resp.json()["week_start_date"] == generated_plan["week_start_date"]

    def test_get_unknown_plan_returns_404(self, http, generated_plan):
        resp = http.get("/plans/00000000-0000-0000-0000-000000000000")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Manual plan edits
#
# Tests are ordered deliberately: add → update → regenerate → remove.
# All operate on Wednesday breakfast, which is not in the default schedule,
# so it does not interfere with the meals from generated_plan.
# ---------------------------------------------------------------------------

_EDIT_DAY = "Wednesday"
_EDIT_MEAL_TYPE = "breakfast"


class TestManualEdits:
    def test_add_meal(self, http, generated_plan):
        recipes = http.get("/recipes").json()["recipes"]
        recipe_id = recipes[0]["id"]

        resp = http.post(
            "/manual-plan/add-meal",
            json={
                "day": _EDIT_DAY,
                "meal_type": _EDIT_MEAL_TYPE,
                "recipe_id": recipe_id,
                "servings": 2.0,
            },
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is True

        # Verify it appears in the plan
        plan = http.get("/current-plan").json()
        added = next(
            (
                m for m in plan["plan"]["meals"]
                if m["day"] == _EDIT_DAY and m["meal_type"] == _EDIT_MEAL_TYPE
            ),
            None,
        )
        assert added is not None
        assert added["recipe_id"] == recipe_id

    def test_update_servings(self, http, generated_plan):
        resp = http.post(
            "/manual-plan/update-servings",
            json={"day": _EDIT_DAY, "meal_type": _EDIT_MEAL_TYPE, "servings": 3.5},
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is True

        plan = http.get("/current-plan").json()
        meal = next(
            m for m in plan["plan"]["meals"]
            if m["day"] == _EDIT_DAY and m["meal_type"] == _EDIT_MEAL_TYPE
        )
        assert meal["portions"] == pytest.approx(3.5)

    def test_regenerate_meal(self, http, generated_plan):
        resp = http.post(
            "/manual-plan/regenerate-meal",
            json={"day": _EDIT_DAY, "meal_type": _EDIT_MEAL_TYPE},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "recipe_name" in data

    def test_remove_meal(self, http, generated_plan):
        resp = http.post(
            "/manual-plan/remove-meal",
            json={"day": _EDIT_DAY, "meal_type": _EDIT_MEAL_TYPE},
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is True

        plan = http.get("/current-plan").json()
        still_there = any(
            m["day"] == _EDIT_DAY and m["meal_type"] == _EDIT_MEAL_TYPE
            for m in plan["plan"]["meals"]
        )
        assert not still_there


# ---------------------------------------------------------------------------
# Shopping list
# ---------------------------------------------------------------------------


class TestShoppingList:
    def test_add_custom_item(self, http, generated_plan):
        resp = http.post(
            "/shopping-list/add-item",
            json={"name": "e2e test item", "quantity": 2, "unit": "kg", "category": "other"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["item"]["item"] == "e2e test item"

    def test_update_item(self, http, generated_plan):
        # Find the index of our test item
        plan = http.get("/current-plan").json()
        items = plan["shopping_list"]["items"]
        idx = next(
            (i for i, it in enumerate(items) if it["item"] == "e2e test item"), None
        )
        assert idx is not None, "Could not find e2e test item in shopping list"

        resp = http.post(
            "/shopping-list/update-item",
            json={"index": idx, "quantity": 5},
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_delete_item(self, http, generated_plan):
        plan = http.get("/current-plan").json()
        items = plan["shopping_list"]["items"]
        idx = next(
            (i for i, it in enumerate(items) if it["item"] == "e2e test item"), None
        )
        assert idx is not None, "Could not find e2e test item to delete"

        resp = http.post("/shopping-list/delete-item", json={"index": idx})
        assert resp.status_code == 200
        assert resp.json()["success"] is True


# ---------------------------------------------------------------------------
# Excluded ingredients
# ---------------------------------------------------------------------------


class TestExcludedIngredients:
    def test_get_excluded_ingredients(self, http):
        resp = http.get("/excluded-ingredients")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_update_excluded_ingredients(self, http):
        resp = http.post(
            "/excluded-ingredients",
            json={"items": ["e2e-test-exclude", "water", "salt"]},
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is True

        # Verify the list reflects what we sent
        result = http.get("/excluded-ingredients").json()
        assert "e2e-test-exclude" in result

    def test_clear_excluded_ingredients(self, http):
        # Reset to empty so we don't pollute the environment
        resp = http.post("/excluded-ingredients", json={"items": []})
        assert resp.status_code == 200
