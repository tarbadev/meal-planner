import json
import pytest
from pathlib import Path

from app.recipes import load_recipes, Recipe, RecipeLoadError


@pytest.fixture
def sample_recipes_data():
    return {
        "recipes": [
            {
                "id": "pasta-bolognese",
                "name": "Pasta Bolognese",
                "servings": 4,
                "prep_time_minutes": 15,
                "cook_time_minutes": 30,
                "calories_per_serving": 450,
                "protein_per_serving": 25,
                "carbs_per_serving": 55,
                "fat_per_serving": 12,
                "tags": ["italian", "kid-friendly"],
                "ingredients": [
                    {"item": "ground beef", "quantity": 500, "unit": "g"},
                    {"item": "pasta", "quantity": 400, "unit": "g"},
                ]
            },
            {
                "id": "chicken-stir-fry",
                "name": "Chicken Stir Fry",
                "servings": 4,
                "prep_time_minutes": 10,
                "cook_time_minutes": 15,
                "calories_per_serving": 350,
                "protein_per_serving": 30,
                "carbs_per_serving": 25,
                "fat_per_serving": 10,
                "tags": ["asian", "quick"],
                "ingredients": [
                    {"item": "chicken breast", "quantity": 500, "unit": "g"},
                    {"item": "mixed vegetables", "quantity": 300, "unit": "g"},
                ]
            }
        ]
    }


@pytest.fixture
def recipes_file(tmp_path, sample_recipes_data):
    file_path = tmp_path / "recipes.json"
    file_path.write_text(json.dumps(sample_recipes_data))
    return file_path


class TestLoadRecipes:
    def test_load_recipes_returns_list(self, recipes_file):
        recipes = load_recipes(recipes_file)
        assert isinstance(recipes, list)

    def test_load_recipes_returns_correct_count(self, recipes_file):
        recipes = load_recipes(recipes_file)
        assert len(recipes) == 2

    def test_load_recipes_returns_recipe_objects(self, recipes_file):
        recipes = load_recipes(recipes_file)
        assert all(isinstance(r, Recipe) for r in recipes)

    def test_recipe_has_required_attributes(self, recipes_file):
        recipes = load_recipes(recipes_file)
        recipe = recipes[0]

        assert recipe.id == "pasta-bolognese"
        assert recipe.name == "Pasta Bolognese"
        assert recipe.servings == 4
        assert recipe.prep_time_minutes == 15
        assert recipe.cook_time_minutes == 30
        assert recipe.calories_per_serving == 450
        assert recipe.protein_per_serving == 25
        assert recipe.carbs_per_serving == 55
        assert recipe.fat_per_serving == 12

    def test_recipe_has_tags(self, recipes_file):
        recipes = load_recipes(recipes_file)
        recipe = recipes[0]
        assert recipe.tags == ["italian", "kid-friendly"]

    def test_recipe_has_ingredients(self, recipes_file):
        recipes = load_recipes(recipes_file)
        recipe = recipes[0]

        assert len(recipe.ingredients) == 2
        assert recipe.ingredients[0]["item"] == "ground beef"
        assert recipe.ingredients[0]["quantity"] == 500
        assert recipe.ingredients[0]["unit"] == "g"

    def test_recipe_total_time(self, recipes_file):
        recipes = load_recipes(recipes_file)
        recipe = recipes[0]
        assert recipe.total_time_minutes == 45

    def test_load_recipes_file_not_found(self, tmp_path):
        with pytest.raises(RecipeLoadError) as exc_info:
            load_recipes(tmp_path / "nonexistent.json")
        assert "not found" in str(exc_info.value).lower()

    def test_load_recipes_invalid_json(self, tmp_path):
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("not valid json {{{")

        with pytest.raises(RecipeLoadError) as exc_info:
            load_recipes(bad_file)
        assert "invalid" in str(exc_info.value).lower() or "parse" in str(exc_info.value).lower()

    def test_load_recipes_missing_recipes_key(self, tmp_path):
        file_path = tmp_path / "empty.json"
        file_path.write_text(json.dumps({"data": []}))

        with pytest.raises(RecipeLoadError) as exc_info:
            load_recipes(file_path)
        assert "recipes" in str(exc_info.value).lower()


class TestRecipe:
    def test_recipe_from_dict(self):
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

    def test_recipe_missing_required_field(self):
        data = {
            "id": "incomplete",
            "name": "Incomplete Recipe"
            # missing other required fields
        }

        with pytest.raises(ValueError):
            Recipe.from_dict(data)
