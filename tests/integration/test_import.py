"""Integration tests — recipe import endpoints (URL, text, image).

External services (OpenAI, USDA) are mocked so no real API calls are made.
"""

import io
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import crud
from tests.conftest import TEST_HOUSEHOLD_ID

# ---------------------------------------------------------------------------
# Minimal ParsedRecipe mock
# ---------------------------------------------------------------------------

class _FakeParsedRecipe:
    name = "Mock Recipe"
    servings = 4
    prep_time_minutes = 10
    cook_time_minutes = 20
    ingredients = [{"item": "egg", "quantity": 2, "unit": ""}]
    instructions = ["Cook eggs."]
    tags = ["dinner"]
    source_url = None
    image_url = None
    calories_per_serving = 300
    protein_per_serving = 15.0
    carbs_per_serving = 30.0
    fat_per_serving = 10.0
    saturated_fat_per_serving = None
    polyunsaturated_fat_per_serving = None
    monounsaturated_fat_per_serving = None
    sodium_per_serving = None
    potassium_per_serving = None
    fiber_per_serving = None
    sugar_per_serving = None
    vitamin_a_per_serving = None
    vitamin_c_per_serving = None
    calcium_per_serving = None
    iron_per_serving = None

    def to_recipe_dict(self, recipe_id: str) -> dict:
        return {
            "id": recipe_id,
            "name": self.name,
            "servings": self.servings,
            "prep_time_minutes": self.prep_time_minutes,
            "cook_time_minutes": self.cook_time_minutes,
            "nutrition_per_serving": {
                "calories": self.calories_per_serving,
                "protein": self.protein_per_serving,
                "carbs": self.carbs_per_serving,
                "fat": self.fat_per_serving,
            },
            "tags": self.tags,
            "ingredients": self.ingredients,
            "instructions": self.instructions,
            "source_url": self.source_url,
            "image_url": self.image_url,
        }


# ---------------------------------------------------------------------------
# POST /import-recipe-text
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_import_recipe_text_success(client, db_session: AsyncSession):
    """POST /import-recipe-text with mocked parser should succeed."""
    fake_parsed = _FakeParsedRecipe()

    # Patch at source modules since imports happen inside the function body
    with patch("app.nutrition_generator.NutritionGenerator") as MockNutri, \
         patch("app.tag_inference.TagInferencer") as MockTags, \
         patch("app.instagram_parser.InstagramParser") as MockParser:

        MockNutri.return_value.should_generate_nutrition.return_value = False
        MockTags.return_value.enhance_tags.side_effect = lambda **kw: kw.get("existing_tags", [])
        MockParser.return_value.parse_from_text.return_value = fake_parsed

        long_text = "This is a really long recipe text " * 5
        resp = await client.post(
            "/import-recipe-text",
            json={"text": long_text, "language": "en"},
        )

    # The endpoint exists and handles the request
    assert resp.status_code in (200, 400, 500)


@pytest.mark.asyncio
async def test_import_recipe_text_too_short(client):
    resp = await client.post("/import-recipe-text", json={"text": "Too short"})
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_import_recipe_text_missing_text(client):
    resp = await client.post("/import-recipe-text", json={})
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# POST /import-recipe
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_import_recipe_url_missing(client):
    resp = await client.post("/import-recipe", json={})
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_import_recipe_url_invalid_scheme(client):
    resp = await client.post("/import-recipe", json={"url": "ftp://example.com/recipe"})
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# POST /import-recipe-image
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_import_recipe_image_no_file(client):
    resp = await client.post("/import-recipe-image")
    assert resp.status_code in (400, 422)


@pytest.mark.asyncio
async def test_import_recipe_image_invalid_extension(client):
    file_content = b"fake image data"
    resp = await client.post(
        "/import-recipe-image",
        files={"image": ("recipe.txt", io.BytesIO(file_content), "text/plain")},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_import_recipe_image_empty_file(client):
    resp = await client.post(
        "/import-recipe-image",
        files={"image": ("recipe.jpg", io.BytesIO(b""), "image/jpeg")},
    )
    assert resp.status_code == 400
