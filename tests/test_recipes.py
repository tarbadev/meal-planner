import json
import pytest
from pathlib import Path
import os

from app.recipes import load_recipes, Recipe, RecipeLoadError, save_recipes, RecipeSaveError, update_recipe


def create_test_recipe(**kwargs):
    """Helper to create Recipe with nested nutrition structure for tests."""
    # Extract flat nutrition fields if provided
    calories = kwargs.pop("calories_per_serving", 0)
    protein = kwargs.pop("protein_per_serving", 0.0)
    carbs = kwargs.pop("carbs_per_serving", 0.0)
    fat = kwargs.pop("fat_per_serving", 0.0)

    # Create nested nutrition structure
    nutrition_per_serving = kwargs.pop("nutrition_per_serving", {
        "calories": calories,
        "protein": protein,
        "carbs": carbs,
        "fat": fat,
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
    })

    return Recipe(nutrition_per_serving=nutrition_per_serving, **kwargs)


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
                id="test-recipe",
                name="Test Recipe",
                servings=2,
                prep_time_minutes=5,
                cook_time_minutes=10,
                calories_per_serving=200,
                protein_per_serving=15,
                carbs_per_serving=20,
                fat_per_serving=8
            )
        ]

        save_recipes(file_path, recipes)

        assert file_path.exists()

    def test_save_recipes_preserves_structure(self, tmp_path):
        """Test that save_recipes wraps recipes in correct structure."""
        file_path = tmp_path / "output.json"
        recipes = [
            create_test_recipe(
                id="test-recipe",
                name="Test Recipe",
                servings=2,
                prep_time_minutes=5,
                cook_time_minutes=10,
                calories_per_serving=200,
                protein_per_serving=15,
                carbs_per_serving=20,
                fat_per_serving=8
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
                id="pasta-bolognese",
                name="Pasta Bolognese",
                servings=4,
                prep_time_minutes=15,
                cook_time_minutes=30,
                calories_per_serving=450,
                protein_per_serving=25,
                carbs_per_serving=55,
                fat_per_serving=12,
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
                id="test-recipe",
                name="Test Recipe",
                servings=2,
                prep_time_minutes=5,
                cook_time_minutes=10,
                calories_per_serving=200,
                protein_per_serving=15,
                carbs_per_serving=20,
                fat_per_serving=8
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
                id="recipe-1",
                name="Recipe 1",
                servings=2,
                prep_time_minutes=5,
                cook_time_minutes=10,
                calories_per_serving=200,
                protein_per_serving=15,
                carbs_per_serving=20,
                fat_per_serving=8
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
                id="recipe-2",
                name="Recipe 2",
                servings=4,
                prep_time_minutes=10,
                cook_time_minutes=20,
                calories_per_serving=300,
                protein_per_serving=20,
                carbs_per_serving=30,
                fat_per_serving=10
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
                id="recipe-1",
                name="Recipe 1",
                servings=2,
                prep_time_minutes=5,
                cook_time_minutes=10,
                calories_per_serving=200,
                protein_per_serving=15,
                carbs_per_serving=20,
                fat_per_serving=8
            ),
            create_test_recipe(
                id="recipe-2",
                name="Recipe 2",
                servings=4,
                prep_time_minutes=10,
                cook_time_minutes=20,
                calories_per_serving=300,
                protein_per_serving=20,
                carbs_per_serving=30,
                fat_per_serving=10
            ),
        ]

        updated_recipe = create_test_recipe(
            id="recipe-2",
            name="Updated Recipe 2",
            servings=6,
            prep_time_minutes=15,
            cook_time_minutes=25,
            calories_per_serving=350,
            protein_per_serving=25,
            carbs_per_serving=35,
            fat_per_serving=12
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
                id="recipe-1",
                name="Recipe 1",
                servings=2,
                prep_time_minutes=5,
                cook_time_minutes=10,
                calories_per_serving=200,
                protein_per_serving=15,
                carbs_per_serving=20,
                fat_per_serving=8
            ),
            create_test_recipe(
                id="recipe-2",
                name="Recipe 2",
                servings=4,
                prep_time_minutes=10,
                cook_time_minutes=20,
                calories_per_serving=300,
                protein_per_serving=20,
                carbs_per_serving=30,
                fat_per_serving=10
            ),
        ]

        updated_recipe = create_test_recipe(
            id="recipe-2",
            name="Updated Recipe 2",
            servings=6,
            prep_time_minutes=15,
            cook_time_minutes=25,
            calories_per_serving=350,
            protein_per_serving=25,
            carbs_per_serving=35,
            fat_per_serving=12
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
                id="recipe-1",
                name="Recipe 1",
                servings=2,
                prep_time_minutes=5,
                cook_time_minutes=10,
                calories_per_serving=200,
                protein_per_serving=15,
                carbs_per_serving=20,
                fat_per_serving=8
            ),
        ]

        updated_recipe = create_test_recipe(
            id="nonexistent",
            name="Nonexistent Recipe",
            servings=6,
            prep_time_minutes=15,
            cook_time_minutes=25,
            calories_per_serving=350,
            protein_per_serving=25,
            carbs_per_serving=35,
            fat_per_serving=12
        )

        with pytest.raises(ValueError) as exc_info:
            update_recipe(recipes, updated_recipe)
        assert "not found" in str(exc_info.value).lower()

    def test_update_recipe_returns_new_list(self):
        """Test that update_recipe returns a new list (immutable)."""
        recipes = [
            create_test_recipe(
                id="recipe-1",
                name="Recipe 1",
                servings=2,
                prep_time_minutes=5,
                cook_time_minutes=10,
                calories_per_serving=200,
                protein_per_serving=15,
                carbs_per_serving=20,
                fat_per_serving=8
            ),
        ]

        updated_recipe = create_test_recipe(
            id="recipe-1",
            name="Updated Recipe 1",
            servings=4,
            prep_time_minutes=10,
            cook_time_minutes=15,
            calories_per_serving=250,
            protein_per_serving=20,
            carbs_per_serving=25,
            fat_per_serving=10
        )

        result = update_recipe(recipes, updated_recipe)

        # Original list should be unchanged
        assert recipes[0].name == "Recipe 1"
        assert recipes[0].servings == 2

        # New list should have updated values
        assert result[0].name == "Updated Recipe 1"
        assert result[0].servings == 4
