"""Unit tests for the Recipe dataclass and search_blob.

These tests cover pure-Python logic and do not require a database or HTTP server.
File I/O tests (load_recipes / save_recipes) were removed when the app migrated
from JSON-file storage to PostgreSQL.
"""

import pytest

from app.recipes import Recipe
from tests.conftest import create_test_recipe


class TestRecipe:
    def test_recipe_from_dict_new_format(self):
        """Test loading recipe with new nested nutrition format."""
        data = {
            "id": "test-recipe",
            "name": "Test Recipe",
            "servings": 2,
            "prep_time_minutes": 5,
            "cook_time_minutes": 10,
            "nutrition_per_serving": {
                "calories": 200,
                "protein": 15,
                "carbs": 20,
                "fat": 8,
                "saturated_fat": 3.0,
                "fiber": 5.0,
                "sodium": 400.0,
                "polyunsaturated_fat": None,
                "monounsaturated_fat": None,
                "potassium": None,
                "sugar": None,
                "vitamin_a": None,
                "vitamin_c": None,
                "calcium": None,
                "iron": None
            },
            "tags": ["test"],
            "ingredients": [{"item": "test item", "quantity": 1, "unit": "piece"}]
        }

        recipe = Recipe.from_dict(data)

        assert recipe.id == "test-recipe"
        assert recipe.name == "Test Recipe"
        assert recipe.servings == 2
        assert recipe.calories_per_serving == 200
        assert recipe.protein_per_serving == 15
        assert recipe.carbs_per_serving == 20
        assert recipe.fat_per_serving == 8
        assert recipe.nutrition_per_serving["saturated_fat"] == 3.0
        assert recipe.nutrition_per_serving["fiber"] == 5.0
        assert recipe.nutrition_per_serving["sodium"] == 400.0

    def test_recipe_from_dict_old_format_backward_compatibility(self):
        """Test that old flat nutrition format is still supported (backward compatibility)."""
        data = {
            "id": "test-recipe",
            "name": "Test Recipe",
            "servings": 2,
            "prep_time_minutes": 5,
            "cook_time_minutes": 10,
            "calories_per_serving": 200,
            "protein_per_serving": 15,
            "carbs_per_serving": 20,
            "fat_per_serving": 8,
            "tags": ["test"],
            "ingredients": [{"item": "test item", "quantity": 1, "unit": "piece"}]
        }

        recipe = Recipe.from_dict(data)

        assert recipe.id == "test-recipe"
        assert recipe.name == "Test Recipe"
        assert recipe.servings == 2
        assert recipe.calories_per_serving == 200
        assert recipe.protein_per_serving == 15
        assert recipe.carbs_per_serving == 20
        assert recipe.fat_per_serving == 8
        assert "nutrition_per_serving" in recipe.__dict__
        assert recipe.nutrition_per_serving["calories"] == 200
        assert recipe.nutrition_per_serving["saturated_fat"] is None

    def test_recipe_missing_required_field(self):
        data = {
            "id": "incomplete",
            "name": "Incomplete Recipe"
            # missing other required fields
        }

        with pytest.raises(ValueError):
            Recipe.from_dict(data)


class TestRecipeSearchBlob:
    """Recipe.search_blob pre-computes a lowercase searchable string."""

    def _make_recipe(self, name, tags, ingredients):
        return create_test_recipe(
            recipe_id="r1", name=name, servings=2,
            prep_time_minutes=5, cook_time_minutes=10,
            calories=200, protein=10, carbs=20, fat=5,
            tags=tags, ingredients=ingredients,
        )

    def test_blob_includes_name(self):
        r = self._make_recipe("Chicken Tikka", [], [])
        assert "chicken tikka" in r.search_blob

    def test_blob_includes_tags(self):
        r = self._make_recipe("Soup", ["vegan", "quick"], [])
        assert "vegan" in r.search_blob
        assert "quick" in r.search_blob

    def test_blob_includes_ingredient_items(self):
        r = self._make_recipe(
            "Salad", [],
            [{"item": "Romaine Lettuce", "quantity": 1, "unit": "head", "category": "veg"}],
        )
        assert "romaine lettuce" in r.search_blob

    def test_blob_is_lowercase(self):
        r = self._make_recipe("UPPERCASE Name", ["TAG"], [])
        assert r.search_blob == r.search_blob.lower()

    def test_blob_is_cached(self):
        r = self._make_recipe("Test", ["t"], [])
        first = r.search_blob
        second = r.search_blob
        assert first is second  # same object — cached_property returns same str instance
