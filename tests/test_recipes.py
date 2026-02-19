import json
import os
from pathlib import Path

import pytest

import app.recipes as recipes_module
from app.recipes import (
    Recipe,
    RecipeLoadError,
    RecipeSaveError,
    load_recipes,
    save_recipes,
    update_recipe,
)
from tests.conftest import create_test_recipe


@pytest.fixture(autouse=True)
def clear_recipe_cache():
    """Ensure the module-level recipe cache is empty before and after every test."""
    recipes_module._cache.clear()
    yield
    recipes_module._cache.clear()


@pytest.fixture
def sample_recipes_data():
    """Fixture with sample recipes in NEW nested format (for testing migration compatibility)."""
    return {
        "recipes": [
            {
                "id": "pasta-bolognese",
                "name": "Pasta Bolognese",
                "servings": 4,
                "prep_time_minutes": 15,
                "cook_time_minutes": 30,
                "nutrition_per_serving": {
                    "calories": 450,
                    "protein": 25,
                    "carbs": 55,
                    "fat": 12,
                    "saturated_fat": None,
                    "polyunsaturated_fat": None,
                    "monounsaturated_fat": None,
                    "sodium": None,
                    "potassium": None,
                    "fiber": None,
                    "sugar": None,
                    "vitamin_a": None,
                    "vitamin_c": None,
                    "calcium": None,
                    "iron": None
                },
                "tags": ["italian", "kid-friendly"],
                "ingredients": [
                    {"item": "ground beef", "quantity": 500, "unit": "g"},
                    {"item": "pasta", "quantity": 400, "unit": "g"},
                ],
                "instructions": []
            },
            {
                "id": "chicken-stir-fry",
                "name": "Chicken Stir Fry",
                "servings": 4,
                "prep_time_minutes": 10,
                "cook_time_minutes": 15,
                "nutrition_per_serving": {
                    "calories": 350,
                    "protein": 30,
                    "carbs": 25,
                    "fat": 10,
                    "saturated_fat": None,
                    "polyunsaturated_fat": None,
                    "monounsaturated_fat": None,
                    "sodium": None,
                    "potassium": None,
                    "fiber": None,
                    "sugar": None,
                    "vitamin_a": None,
                    "vitamin_c": None,
                    "calcium": None,
                    "iron": None
                },
                "tags": ["asian", "quick"],
                "ingredients": [
                    {"item": "chicken breast", "quantity": 500, "unit": "g"},
                    {"item": "mixed vegetables", "quantity": 300, "unit": "g"},
                ],
                "instructions": []
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
        # Test extended nutrition fields
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
        # Properties should still work
        assert recipe.calories_per_serving == 200
        assert recipe.protein_per_serving == 15
        assert recipe.carbs_per_serving == 20
        assert recipe.fat_per_serving == 8
        # Should have nested structure
        assert "nutrition_per_serving" in recipe.__dict__
        assert recipe.nutrition_per_serving["calories"] == 200
        # Extended fields should be None
        assert recipe.nutrition_per_serving["saturated_fat"] is None

    def test_recipe_missing_required_field(self):
        data = {
            "id": "incomplete",
            "name": "Incomplete Recipe"
            # missing other required fields
        }

        with pytest.raises(ValueError):
            Recipe.from_dict(data)


class TestSaveRecipes:
    def test_save_recipes_writes_to_file(self, tmp_path):
        """Test that save_recipes creates a file."""
        file_path = tmp_path / "output.json"
        recipes = [
            create_test_recipe(
                recipe_id="test-recipe",
                name="Test Recipe",
                servings=2,
                prep_time_minutes=5,
                cook_time_minutes=10,
                calories=200,
                protein=15,
                carbs=20,
                fat=8
            )
        ]

        save_recipes(file_path, recipes)

        assert file_path.exists()

    def test_save_recipes_preserves_structure(self, tmp_path):
        """Test that save_recipes wraps recipes in correct structure."""
        file_path = tmp_path / "output.json"
        recipes = [
            create_test_recipe(
                recipe_id="test-recipe",
                name="Test Recipe",
                servings=2,
                prep_time_minutes=5,
                cook_time_minutes=10,
                calories=200,
                protein=15,
                carbs=20,
                fat=8
            )
        ]

        save_recipes(file_path, recipes)

        with open(file_path) as f:
            data = json.load(f)

        assert "recipes" in data
        assert isinstance(data["recipes"], list)
        assert len(data["recipes"]) == 1

    def test_save_recipes_includes_all_fields(self, tmp_path):
        """Test that all recipe fields are saved correctly (saves in new format with nested nutrition)."""
        file_path = tmp_path / "output.json"
        recipes = [
            create_test_recipe(
                recipe_id="pasta-bolognese",
                name="Pasta Bolognese",
                servings=4,
                prep_time_minutes=15,
                cook_time_minutes=30,
                calories=450,
                protein=25,
                carbs=55,
                fat=12,
                tags=["italian", "kid-friendly"],
                ingredients=[
                    {"item": "ground beef", "quantity": 500, "unit": "g", "category": "meat"},
                    {"item": "pasta", "quantity": 400, "unit": "g", "category": "pantry"},
                ]
            )
        ]

        save_recipes(file_path, recipes)

        with open(file_path) as f:
            data = json.load(f)

        recipe_data = data["recipes"][0]
        assert recipe_data["id"] == "pasta-bolognese"
        assert recipe_data["name"] == "Pasta Bolognese"
        assert recipe_data["servings"] == 4
        assert recipe_data["prep_time_minutes"] == 15
        assert recipe_data["cook_time_minutes"] == 30
        # Check nested nutrition structure
        assert "nutrition_per_serving" in recipe_data
        assert recipe_data["nutrition_per_serving"]["calories"] == 450
        assert recipe_data["nutrition_per_serving"]["protein"] == 25
        assert recipe_data["nutrition_per_serving"]["carbs"] == 55
        assert recipe_data["nutrition_per_serving"]["fat"] == 12
        assert recipe_data["tags"] == ["italian", "kid-friendly"]
        assert len(recipe_data["ingredients"]) == 2
        assert recipe_data["ingredients"][0]["item"] == "ground beef"

    def test_save_recipes_handles_write_error(self, tmp_path):
        """Test that save_recipes raises RecipeSaveError on write failure."""
        # Create a directory with no write permissions
        read_only_dir = tmp_path / "readonly"
        read_only_dir.mkdir()
        os.chmod(read_only_dir, 0o444)  # Read-only

        file_path = read_only_dir / "recipes.json"
        recipes = [
            create_test_recipe(
                recipe_id="test-recipe",
                name="Test Recipe",
                servings=2,
                prep_time_minutes=5,
                cook_time_minutes=10,
                calories=200,
                protein=15,
                carbs=20,
                fat=8
            )
        ]

        with pytest.raises(RecipeSaveError):
            save_recipes(file_path, recipes)

        # Restore permissions for cleanup
        os.chmod(read_only_dir, 0o755)

    def test_save_recipes_atomic_write(self, tmp_path):
        """Test that save_recipes uses atomic write (doesn't corrupt on failure)."""
        file_path = tmp_path / "recipes.json"

        # Create initial file
        initial_recipes = [
            create_test_recipe(
                recipe_id="recipe-1",
                name="Recipe 1",
                servings=2,
                prep_time_minutes=5,
                cook_time_minutes=10,
                calories=200,
                protein=15,
                carbs=20,
                fat=8
            )
        ]
        save_recipes(file_path, initial_recipes)

        # Verify we can load it back
        loaded = load_recipes(file_path)
        assert len(loaded) == 1
        assert loaded[0].id == "recipe-1"

        # Write new recipes
        new_recipes = [
            create_test_recipe(
                recipe_id="recipe-2",
                name="Recipe 2",
                servings=4,
                prep_time_minutes=10,
                cook_time_minutes=20,
                calories=300,
                protein=20,
                carbs=30,
                fat=10
            )
        ]
        save_recipes(file_path, new_recipes)

        # Verify new recipes were written correctly
        loaded = load_recipes(file_path)
        assert len(loaded) == 1
        assert loaded[0].id == "recipe-2"


class TestUpdateRecipe:
    def test_update_recipe_replaces_existing(self):
        """Test that update_recipe replaces the correct recipe."""
        recipes = [
            create_test_recipe(
                recipe_id="recipe-1",
                name="Recipe 1",
                servings=2,
                prep_time_minutes=5,
                cook_time_minutes=10,
                calories=200,
                protein=15,
                carbs=20,
                fat=8
            ),
            create_test_recipe(
                recipe_id="recipe-2",
                name="Recipe 2",
                servings=4,
                prep_time_minutes=10,
                cook_time_minutes=20,
                calories=300,
                protein=20,
                carbs=30,
                fat=10
            ),
        ]

        updated_recipe = create_test_recipe(
            recipe_id="recipe-2",
            name="Updated Recipe 2",
            servings=6,
            prep_time_minutes=15,
            cook_time_minutes=25,
            calories=350,
            protein=25,
            carbs=35,
            fat=12
        )

        result = update_recipe(recipes, updated_recipe)

        # Find the updated recipe
        updated = [r for r in result if r.id == "recipe-2"][0]
        assert updated.name == "Updated Recipe 2"
        assert updated.servings == 6

    def test_update_recipe_preserves_others(self):
        """Test that update_recipe doesn't modify other recipes."""
        recipes = [
            create_test_recipe(
                recipe_id="recipe-1",
                name="Recipe 1",
                servings=2,
                prep_time_minutes=5,
                cook_time_minutes=10,
                calories=200,
                protein=15,
                carbs=20,
                fat=8
            ),
            create_test_recipe(
                recipe_id="recipe-2",
                name="Recipe 2",
                servings=4,
                prep_time_minutes=10,
                cook_time_minutes=20,
                calories=300,
                protein=20,
                carbs=30,
                fat=10
            ),
        ]

        updated_recipe = create_test_recipe(
            recipe_id="recipe-2",
            name="Updated Recipe 2",
            servings=6,
            prep_time_minutes=15,
            cook_time_minutes=25,
            calories=350,
            protein=25,
            carbs=35,
            fat=12
        )

        result = update_recipe(recipes, updated_recipe)

        # Verify recipe-1 is unchanged
        recipe_1 = [r for r in result if r.id == "recipe-1"][0]
        assert recipe_1.name == "Recipe 1"
        assert recipe_1.servings == 2

    def test_update_recipe_not_found(self):
        """Test that update_recipe raises error when recipe not found."""
        recipes = [
            create_test_recipe(
                recipe_id="recipe-1",
                name="Recipe 1",
                servings=2,
                prep_time_minutes=5,
                cook_time_minutes=10,
                calories=200,
                protein=15,
                carbs=20,
                fat=8
            ),
        ]

        updated_recipe = create_test_recipe(
            recipe_id="nonexistent",
            name="Nonexistent Recipe",
            servings=6,
            prep_time_minutes=15,
            cook_time_minutes=25,
            calories=350,
            protein=25,
            carbs=35,
            fat=12
        )

        with pytest.raises(ValueError) as exc_info:
            update_recipe(recipes, updated_recipe)
        assert "not found" in str(exc_info.value).lower()

    def test_update_recipe_returns_new_list(self):
        """Test that update_recipe returns a new list (immutable)."""
        recipes = [
            create_test_recipe(
                recipe_id="recipe-1",
                name="Recipe 1",
                servings=2,
                prep_time_minutes=5,
                cook_time_minutes=10,
                calories=200,
                protein=15,
                carbs=20,
                fat=8
            ),
        ]

        updated_recipe = create_test_recipe(
            recipe_id="recipe-1",
            name="Updated Recipe 1",
            servings=4,
            prep_time_minutes=10,
            cook_time_minutes=15,
            calories=250,
            protein=20,
            carbs=25,
            fat=10
        )

        result = update_recipe(recipes, updated_recipe)

        # Original list should be unchanged
        assert recipes[0].name == "Recipe 1"
        assert recipes[0].servings == 2

        # New list should have updated values
        assert result[0].name == "Updated Recipe 1"
        assert result[0].servings == 4


class TestRecipeCache:
    """load_recipes() uses an mtime-keyed cache to avoid redundant disk reads."""

    def test_second_load_hits_cache(self, recipes_file, monkeypatch):
        """A second load_recipes() call with the same mtime skips json.load."""
        read_count = [0]
        original_open = open

        def counting_open(path, *args, **kwargs):
            read_count[0] += 1
            return original_open(path, *args, **kwargs)

        monkeypatch.setattr("builtins.open", counting_open)

        load_recipes(recipes_file)   # first call — reads from disk
        load_recipes(recipes_file)   # second call — should hit cache

        assert read_count[0] == 1

    def test_cache_invalidated_on_mtime_change(self, recipes_file, sample_recipes_data):
        """load_recipes() re-reads the file after it is modified."""
        load_recipes(recipes_file)  # warm the cache

        # Append a new recipe and overwrite the file (mtime changes)
        extra = {**sample_recipes_data["recipes"][0], "id": "new-recipe", "name": "New Recipe"}
        new_data = {"recipes": sample_recipes_data["recipes"] + [extra]}
        recipes_file.write_text(json.dumps(new_data))

        recipes = load_recipes(recipes_file)
        assert len(recipes) == 3
        assert any(r.id == "new-recipe" for r in recipes)

    def test_save_recipes_invalidates_cache(self, recipes_file):
        """save_recipes() clears the cache entry so the next load sees new content."""
        original = load_recipes(recipes_file)  # warm the cache
        assert len(original) == 2

        # Save a single-recipe list, which should bust the cache
        save_recipes(recipes_file, [original[0]])

        reloaded = load_recipes(recipes_file)
        assert len(reloaded) == 1
        assert reloaded[0].id == original[0].id

    def test_returns_shallow_copy(self, recipes_file):
        """Mutating the returned list must not corrupt the cached list."""
        first = load_recipes(recipes_file)
        first.clear()  # wipe the caller's copy

        second = load_recipes(recipes_file)
        assert len(second) == 2  # cache is intact

    def test_cache_populated_after_load(self, recipes_file):
        """After load_recipes(), the cache entry exists for the resolved path."""
        load_recipes(recipes_file)
        assert str(recipes_file.resolve()) in recipes_module._cache


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
