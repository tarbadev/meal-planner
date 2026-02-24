"""E2E test configuration.

Tests run against a live HTTP server.  Set E2E_BASE_URL to target a deployed
environment; defaults to http://localhost:8000 for local runs.

Data isolation strategy
-----------------------
The app currently has a single household.  The session fixtures:
  1. Check whether the server has enough recipes; if not, seed test recipes.
  2. Before running tests, clear any existing plan for the current week.
  3. After all tests complete, delete seeded recipes and clear the plan again.

This keeps dev environments clean: a pre-existing plan is replaced during the
session and removed at teardown.  Seeded recipes are always deleted on exit.
"""

import os

import httpx
import pytest

BASE_URL = os.getenv("E2E_BASE_URL", "http://localhost:8000")

# Minimum number of recipes the server must have for plan generation to work.
# The default schedule has 9 meal slots; we need at least that many unique
# recipes, so we seed 16 (10 dinner + 6 lunch) as a comfortable buffer.
_MIN_RECIPES = 16

_SEED_RECIPES = [
    {
        "name": f"E2E Test Dinner {i}",
        "servings": 4,
        "prep_time_minutes": 10,
        "cook_time_minutes": 20,
        "tags": ["dinner"],
        "ingredients": [{"item": "test ingredient", "quantity": 1, "unit": "cup"}],
        "instructions": ["Cook everything together."],
    }
    for i in range(10)
] + [
    {
        "name": f"E2E Test Lunch {i}",
        "servings": 4,
        "prep_time_minutes": 5,
        "cook_time_minutes": 0,
        "tags": ["lunch"],
        "ingredients": [{"item": "test ingredient", "quantity": 1, "unit": "cup"}],
        "instructions": ["Assemble and serve."],
    }
    for i in range(6)
]

# Tracked at session level so teardown can clean up regardless of test outcome.
_seeded_ids: list[str] = []


# ---------------------------------------------------------------------------
# Core fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def http():
    """Synchronous httpx client for the entire test session."""
    with httpx.Client(base_url=BASE_URL, timeout=30) as client:
        yield client


@pytest.fixture(scope="session", autouse=True)
def server_available(http):
    """Skip the whole session if the server cannot be reached."""
    try:
        resp = http.get("/health", timeout=5)
        if resp.status_code != 200:
            pytest.skip(f"Server at {BASE_URL} returned HTTP {resp.status_code}")
    except httpx.ConnectError:
        pytest.skip(f"Cannot connect to server at {BASE_URL}")


@pytest.fixture(scope="session")
def ensure_recipes(http, server_available):
    """Seed test recipes when the server has fewer than _MIN_RECIPES.

    Deletes every seeded recipe at session teardown so the server is not
    left in a dirtier state than it started.
    """
    resp = http.get("/recipes")
    count = len(resp.json().get("recipes", [])) if resp.status_code == 200 else 0

    if count < _MIN_RECIPES:
        for recipe in _SEED_RECIPES:
            r = http.post("/recipes", json=recipe)
            if r.status_code == 200 and r.json().get("success"):
                _seeded_ids.append(r.json()["recipe"]["id"])

    yield

    for recipe_id in _seeded_ids:
        http.delete(f"/recipes/{recipe_id}")
    _seeded_ids.clear()


@pytest.fixture(scope="session")
def generated_plan(http, ensure_recipes):
    """Generate a fresh plan once per session.

    Clears any existing plan beforehand and cleans up at teardown.
    Yields the full /current-plan JSON response.
    """
    http.post("/manual-plan/clear")

    resp = http.post("/generate")
    assert resp.status_code == 200, f"POST /generate failed: {resp.text}"
    assert resp.json()["success"] is True

    plan_resp = http.get("/current-plan")
    assert plan_resp.status_code == 200, f"GET /current-plan failed: {plan_resp.text}"
    assert plan_resp.json().get("plan") is not None, "Plan is empty after generate"

    yield plan_resp.json()

    http.post("/manual-plan/clear")
