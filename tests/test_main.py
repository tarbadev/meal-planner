import io
import json
from pathlib import Path

import pytest

from app.main import _is_valid_image_bytes, app
from app.recipes import Recipe, save_recipes
from tests.conftest import create_test_recipe


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Create a test client with a temporary recipes file."""
    # Create test recipes file
    recipes_file = tmp_path / "recipes.json"
    test_recipes = [
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
            tags=["italian", "kid-friendly", "dinner"],
            ingredients=[
                {"item": "ground beef", "quantity": 500, "unit": "g", "category": "meat"},
                {"item": "pasta", "quantity": 400, "unit": "g", "category": "pantry"},
            ],
        ),
        create_test_recipe(
            recipe_id="chicken-stir-fry",
            name="Chicken Stir Fry",
            servings=4,
            prep_time_minutes=10,
            cook_time_minutes=15,
            calories=350,
            protein=30,
            carbs=25,
            fat=10,
            tags=["asian", "quick", "lunch", "dinner"],
            ingredients=[
                {"item": "chicken breast", "quantity": 500, "unit": "g", "category": "meat"},
                {"item": "mixed vegetables", "quantity": 300, "unit": "g", "category": "produce"},
            ],
        ),
    ]
    save_recipes(recipes_file, test_recipes)

    # Patch the config to use our test file
    from app import config
    monkeypatch.setattr(config, 'RECIPES_FILE', str(recipes_file))

    # Create test client
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


class TestGetRecipe:
    def test_get_recipe_success(self, client):
        """Test successful retrieval of a recipe."""
        response = client.get('/recipes/pasta-bolognese')
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data['id'] == 'pasta-bolognese'
        assert data['name'] == 'Pasta Bolognese'
        assert data['servings'] == 4
        assert len(data['ingredients']) == 2

    def test_get_recipe_not_found(self, client):
        """Test getting a non-existent recipe."""
        response = client.get('/recipes/nonexistent')
        assert response.status_code == 404

        data = json.loads(response.data)
        assert 'error' in data or 'message' in data


class TestUpdateRecipe:
    def test_update_recipe_success(self, client, tmp_path, monkeypatch):
        """Test successful recipe update."""
        from app import config

        updated_data = {
            "id": "pasta-bolognese",
            "name": "Spaghetti Bolognese",
            "servings": 6,
            "prep_time_minutes": 15,
            "cook_time_minutes": 30,
            "calories_per_serving": 450,
            "protein_per_serving": 25,
            "carbs_per_serving": 55,
            "fat_per_serving": 12,
            "tags": ["italian", "kid-friendly", "comfort-food"],
            "ingredients": [
                {"item": "ground beef", "quantity": 750, "unit": "g", "category": "meat"},
                {"item": "spaghetti", "quantity": 600, "unit": "g", "category": "pantry"},
                {"item": "tomato sauce", "quantity": 400, "unit": "ml", "category": "pantry"},
            ]
        }

        response = client.put(
            '/recipes/pasta-bolognese',
            data=json.dumps(updated_data),
            content_type='application/json'
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True

        # Verify the recipe was updated by fetching it
        get_response = client.get('/recipes/pasta-bolognese')
        assert get_response.status_code == 200
        recipe_data = json.loads(get_response.data)
        assert recipe_data['name'] == 'Spaghetti Bolognese'
        assert recipe_data['servings'] == 6
        assert len(recipe_data['ingredients']) == 3

    def test_update_recipe_persists_to_file(self, client, tmp_path, monkeypatch):
        """Test that recipe updates are persisted to the file."""
        from app import config
        from app.recipes import load_recipes

        updated_data = {
            "id": "pasta-bolognese",
            "name": "Spaghetti Bolognese",
            "servings": 6,
            "prep_time_minutes": 15,
            "cook_time_minutes": 30,
            "calories_per_serving": 450,
            "protein_per_serving": 25,
            "carbs_per_serving": 55,
            "fat_per_serving": 12,
            "tags": ["italian"],
            "ingredients": [
                {"item": "ground beef", "quantity": 750, "unit": "g", "category": "meat"},
            ]
        }

        response = client.put(
            '/recipes/pasta-bolognese',
            data=json.dumps(updated_data),
            content_type='application/json'
        )

        assert response.status_code == 200

        # Load from file and verify
        recipes = load_recipes(config.RECIPES_FILE)
        updated_recipe = [r for r in recipes if r.id == 'pasta-bolognese'][0]
        assert updated_recipe.name == 'Spaghetti Bolognese'
        assert updated_recipe.servings == 6

    def test_update_recipe_invalid_json(self, client):
        """Test updating with invalid JSON."""
        response = client.put(
            '/recipes/pasta-bolognese',
            data='not valid json {{{',
            content_type='application/json'
        )

        assert response.status_code == 400

    def test_update_recipe_missing_fields(self, client):
        """Test updating with missing required fields."""
        incomplete_data = {
            "id": "pasta-bolognese",
            "name": "Spaghetti Bolognese"
            # missing other required fields
        }

        response = client.put(
            '/recipes/pasta-bolognese',
            data=json.dumps(incomplete_data),
            content_type='application/json'
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data or 'message' in data

    def test_update_recipe_negative_numbers(self, client):
        """Test that negative numbers are rejected."""
        invalid_data = {
            "id": "pasta-bolognese",
            "name": "Pasta Bolognese",
            "servings": -1,  # Negative servings
            "prep_time_minutes": 15,
            "cook_time_minutes": 30,
            "calories_per_serving": 450,
            "protein_per_serving": 25,
            "carbs_per_serving": 55,
            "fat_per_serving": 12,
            "tags": [],
            "ingredients": []
        }

        response = client.put(
            '/recipes/pasta-bolognese',
            data=json.dumps(invalid_data),
            content_type='application/json'
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data or 'message' in data

    def test_update_recipe_not_found(self, client):
        """Test updating a non-existent recipe."""
        new_data = {
            "id": "nonexistent",
            "name": "Nonexistent Recipe",
            "servings": 4,
            "prep_time_minutes": 10,
            "cook_time_minutes": 20,
            "calories_per_serving": 300,
            "protein_per_serving": 20,
            "carbs_per_serving": 30,
            "fat_per_serving": 10,
            "tags": [],
            "ingredients": []
        }

        response = client.put(
            '/recipes/nonexistent',
            data=json.dumps(new_data),
            content_type='application/json'
        )

        assert response.status_code == 404

    def test_update_recipe_id_mismatch(self, client):
        """Test that ID in URL must match ID in body."""
        mismatched_data = {
            "id": "different-id",
            "name": "Recipe",
            "servings": 4,
            "prep_time_minutes": 10,
            "cook_time_minutes": 20,
            "calories_per_serving": 300,
            "protein_per_serving": 20,
            "carbs_per_serving": 30,
            "fat_per_serving": 10,
            "tags": [],
            "ingredients": []
        }

        response = client.put(
            '/recipes/pasta-bolognese',
            data=json.dumps(mismatched_data),
            content_type='application/json'
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data or 'message' in data


class TestImportRecipe:
    """Test the /import-recipe endpoint."""

    def test_import_recipe_success(self, client, monkeypatch):
        """Test successful recipe import from URL."""
        from unittest.mock import Mock, patch

        from app.recipe_parser import ParsedRecipe

        # Mock the parser
        mock_parsed_recipe = ParsedRecipe(
            name="Imported Recipe",
            servings=4,
            prep_time_minutes=20,
            cook_time_minutes=30,
            calories_per_serving=400,
            protein_per_serving=22,
            carbs_per_serving=50,
            fat_per_serving=15,
            tags=["imported"],
            ingredients=[
                {"item": "flour", "quantity": 2, "unit": "cups", "category": "pantry"},
                {"item": "eggs", "quantity": 3, "unit": "whole", "category": "dairy"}
            ],
            instructions=["Mix ingredients", "Bake at 350F", "Let cool"]
        )

        with patch('app.recipe_parser.RecipeParser.parse_from_url') as mock_parse:
            mock_parse.return_value = mock_parsed_recipe

            response = client.post(
                '/import-recipe',
                data=json.dumps({"url": "https://example.com/recipe"}),
                content_type='application/json'
            )

            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['success'] is True
            assert 'imported successfully' in data['message'].lower()
            assert data['recipe']['name'] == "Imported Recipe"
            assert data['recipe']['ingredient_count'] == 2
            assert data['recipe']['instruction_count'] == 3

    def test_import_recipe_missing_url(self, client):
        """Test import without URL."""
        response = client.post(
            '/import-recipe',
            data=json.dumps({}),
            content_type='application/json'
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data
        assert 'URL is required' in data['message']

    def test_import_recipe_invalid_url_format(self, client):
        """Test import with invalid URL format."""
        response = client.post(
            '/import-recipe',
            data=json.dumps({"url": "not-a-valid-url"}),
            content_type='application/json'
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data
        assert 'http://' in data['message'] or 'https://' in data['message']

    def test_import_recipe_invalid_json(self, client):
        """Test import with invalid JSON."""
        response = client.post(
            '/import-recipe',
            data="not json",
            content_type='application/json'
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data

    def test_import_recipe_parse_error(self, client):
        """Test import when parsing fails."""
        from unittest.mock import patch

        from app.recipe_parser import RecipeParseError

        with patch('app.recipe_parser.RecipeParser.parse_from_url') as mock_parse:
            mock_parse.side_effect = RecipeParseError("Could not extract ingredients")

            response = client.post(
                '/import-recipe',
                data=json.dumps({"url": "https://example.com/recipe"}),
                content_type='application/json'
            )

            assert response.status_code == 400
            data = json.loads(response.data)
            assert 'error' in data
            assert 'Parse error' in data['error']
            assert 'Could not extract ingredients' in data['message']

    def test_import_recipe_generates_unique_id(self, client, monkeypatch):
        """Test that imported recipe gets a unique ID."""
        from unittest.mock import patch

        from app.recipe_parser import ParsedRecipe

        mock_parsed_recipe = ParsedRecipe(
            name="Pasta Bolognese",  # Same name as existing recipe
            servings=4,
            ingredients=[{"item": "test", "quantity": 1, "unit": "piece", "category": "other"}],
            instructions=["Do something"]
        )

        with patch('app.recipe_parser.RecipeParser.parse_from_url') as mock_parse:
            mock_parse.return_value = mock_parsed_recipe

            response = client.post(
                '/import-recipe',
                data=json.dumps({"url": "https://example.com/recipe"}),
                content_type='application/json'
            )

            assert response.status_code == 200
            data = json.loads(response.data)
            # Should have a different ID than the existing pasta-bolognese
            assert data['recipe']['id'] == 'pasta-bolognese-2'

    def test_import_recipe_clears_current_plan(self, client, monkeypatch):
        """Test that importing a recipe clears the current plan."""
        from unittest.mock import patch

        from app import main
        from app.recipe_parser import ParsedRecipe

        # Set a current plan
        main.current_plan = "some plan"
        main.current_shopping_list = "some list"

        mock_parsed_recipe = ParsedRecipe(
            name="New Recipe",
            ingredients=[{"item": "test", "quantity": 1, "unit": "piece", "category": "other"}],
            instructions=["Do something"]
        )

        with patch('app.recipe_parser.RecipeParser.parse_from_url') as mock_parse:
            mock_parse.return_value = mock_parsed_recipe

            response = client.post(
                '/import-recipe',
                data=json.dumps({"url": "https://example.com/recipe"}),
                content_type='application/json'
            )

            assert response.status_code == 200
            # Verify plan was cleared
            assert main.current_plan is None
            assert main.current_shopping_list is None

    def test_import_recipe_missing_ingredients_fails(self, client):
        """Test that importing a recipe without ingredients fails."""
        from unittest.mock import patch

        from app.recipe_parser import ParsedRecipe, RecipeParseError

        mock_parsed_recipe = ParsedRecipe(
            name="Invalid Recipe",
            ingredients=[],  # Empty ingredients
            instructions=["Do something"]
        )

        with patch('app.recipe_parser.RecipeParser.parse_from_url') as mock_parse:
            mock_parse.return_value = mock_parsed_recipe

            response = client.post(
                '/import-recipe',
                data=json.dumps({"url": "https://example.com/recipe"}),
                content_type='application/json'
            )

            assert response.status_code == 400
            data = json.loads(response.data)
            assert 'Parse error' in data['error']
            assert 'Could not extract ingredients' in data['message']

    def test_import_recipe_missing_instructions_adds_default(self, client):
        """Test that importing a recipe without instructions adds a default instruction."""
        from unittest.mock import patch

        from app.recipe_parser import ParsedRecipe

        mock_parsed_recipe = ParsedRecipe(
            name="Marinade Recipe",
            ingredients=[{"item": "test", "quantity": 1, "unit": "piece", "category": "other"}],
            instructions=[]  # Empty instructions
        )

        with patch('app.recipe_parser.RecipeParser.parse_from_url') as mock_parse:
            mock_parse.return_value = mock_parsed_recipe

            response = client.post(
                '/import-recipe',
                data=json.dumps({"url": "https://example.com/recipe"}),
                content_type='application/json'
            )

            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['success'] is True
            # Check that instruction_count is 1 (default instruction was added)
            assert data['recipe']['instruction_count'] == 1

    def test_import_recipe_generates_nutrition_when_missing(self, client):
        """Test that nutrition is automatically generated when missing."""
        from unittest.mock import Mock, patch

        from app.nutrition_generator import NutritionData
        from app.recipe_parser import ParsedRecipe

        # Mock recipe with no nutrition
        mock_parsed_recipe = ParsedRecipe(
            name="Test Recipe",
            servings=4,
            calories_per_serving=0,  # No nutrition
            protein_per_serving=0.0,
            carbs_per_serving=0.0,
            fat_per_serving=0.0,
            ingredients=[
                {"item": "flour", "quantity": 2, "unit": "cups", "category": "pantry"},
                {"item": "eggs", "quantity": 2, "unit": "whole", "category": "dairy"}
            ],
            instructions=["Mix ingredients", "Bake"]
        )

        # Mock generated nutrition
        mock_nutrition = NutritionData(
            calories=350.0,
            protein=15.0,
            carbs=45.0,
            fat=12.0,
            confidence=0.85
        )

        with patch('app.recipe_parser.RecipeParser.parse_from_url') as mock_parse, \
             patch('app.nutrition_generator.NutritionGenerator.generate_from_ingredients') as mock_gen:
            mock_parse.return_value = mock_parsed_recipe
            mock_gen.return_value = mock_nutrition

            response = client.post(
                '/import-recipe',
                data=json.dumps({"url": "https://example.com/recipe"}),
                content_type='application/json'
            )

            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['success'] is True
            assert data['recipe']['has_nutrition'] is True
            assert data['recipe']['nutrition_generated'] is True

            # Verify nutrition generation was called
            mock_gen.assert_called_once()

    def test_import_recipe_skips_generation_when_nutrition_present(self, client):
        """Test that nutrition generation is skipped when nutrition already exists."""
        from unittest.mock import Mock, patch

        from app.recipe_parser import ParsedRecipe

        # Mock recipe WITH existing nutrition
        mock_parsed_recipe = ParsedRecipe(
            name="Test Recipe",
            servings=4,
            calories_per_serving=350,  # Has nutrition
            protein_per_serving=25.0,
            carbs_per_serving=40.0,
            fat_per_serving=12.0,
            ingredients=[
                {"item": "flour", "quantity": 2, "unit": "cups", "category": "pantry"}
            ],
            instructions=["Mix", "Bake"]
        )

        with patch('app.recipe_parser.RecipeParser.parse_from_url') as mock_parse, \
             patch('app.nutrition_generator.NutritionGenerator.generate_from_ingredients') as mock_gen:
            mock_parse.return_value = mock_parsed_recipe

            response = client.post(
                '/import-recipe',
                data=json.dumps({"url": "https://example.com/recipe"}),
                content_type='application/json'
            )

            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['recipe']['has_nutrition'] is True
            assert data['recipe']['nutrition_generated'] is False

            # Verify nutrition generation was NOT called
            mock_gen.assert_not_called()

    def test_import_recipe_continues_when_generation_fails(self, client):
        """Test that import succeeds even if nutrition generation fails."""
        from unittest.mock import patch

        from app.recipe_parser import ParsedRecipe

        # Mock recipe with no nutrition
        mock_parsed_recipe = ParsedRecipe(
            name="Test Recipe",
            servings=4,
            calories_per_serving=0,
            protein_per_serving=0.0,
            ingredients=[
                {"item": "unknown-ingredient", "quantity": 1, "unit": "piece", "category": "other"}
            ],
            instructions=["Do something"]
        )

        with patch('app.recipe_parser.RecipeParser.parse_from_url') as mock_parse, \
             patch('app.nutrition_generator.NutritionGenerator.generate_from_ingredients') as mock_gen:
            mock_parse.return_value = mock_parsed_recipe
            mock_gen.return_value = None  # Generation failed

            response = client.post(
                '/import-recipe',
                data=json.dumps({"url": "https://example.com/recipe"}),
                content_type='application/json'
            )

            # Import should still succeed
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['success'] is True
            # No nutrition was generated
            assert data['recipe']['has_nutrition'] is False
            assert data['recipe']['nutrition_generated'] is False

    def test_import_recipe_with_generated_nutrition_adds_tag(self, client, monkeypatch):
        """Test that nutrition-generated tag is added when nutrition is generated."""
        from unittest.mock import patch

        from app import config
        from app.nutrition_generator import NutritionData
        from app.recipe_parser import ParsedRecipe
        from app.recipes import load_recipes

        mock_parsed_recipe = ParsedRecipe(
            name="Test Recipe",
            servings=4,
            calories_per_serving=0,
            protein_per_serving=0.0,
            ingredients=[
                {"item": "flour", "quantity": 2, "unit": "cups", "category": "pantry"}
            ],
            instructions=["Mix", "Bake"]
        )

        mock_nutrition = NutritionData(
            calories=350.0,
            protein=15.0,
            carbs=45.0,
            fat=12.0,
            confidence=0.85
        )

        with patch('app.recipe_parser.RecipeParser.parse_from_url') as mock_parse, \
             patch('app.nutrition_generator.NutritionGenerator.generate_from_ingredients') as mock_gen:
            mock_parse.return_value = mock_parsed_recipe
            mock_gen.return_value = mock_nutrition

            response = client.post(
                '/import-recipe',
                data=json.dumps({"url": "https://example.com/recipe"}),
                content_type='application/json'
            )

            assert response.status_code == 200

            # Load the recipe from file and verify it has the tag
            recipes = load_recipes(config.RECIPES_FILE)
            imported_recipe = [r for r in recipes if r.name == "Test Recipe"][0]
            assert "nutrition-generated" in imported_recipe.tags

    def test_import_recipe_no_tag_when_nutrition_all_zeros(self, client, monkeypatch):
        """Test that nutrition-generated tag is NOT added when nutrition is all zeros."""
        from unittest.mock import patch

        from app import config
        from app.nutrition_generator import NutritionData
        from app.recipe_parser import ParsedRecipe
        from app.recipes import load_recipes

        mock_parsed_recipe = ParsedRecipe(
            name="Test Recipe No Nutrition",
            servings=4,
            calories_per_serving=0,
            protein_per_serving=0.0,
            ingredients=[
                {"item": "flour", "quantity": 2, "unit": "cups", "category": "pantry"}
            ],
            instructions=["Mix", "Bake"]
        )

        # Mock nutrition with all zeros (failed generation)
        mock_nutrition = NutritionData(
            calories=0.0,
            protein=0.0,
            carbs=0.0,
            fat=0.0,
            confidence=0.0
        )

        with patch('app.recipe_parser.RecipeParser.parse_from_url') as mock_parse, \
             patch('app.nutrition_generator.NutritionGenerator.generate_from_ingredients') as mock_gen:
            mock_parse.return_value = mock_parsed_recipe
            mock_gen.return_value = mock_nutrition

            response = client.post(
                '/import-recipe',
                data=json.dumps({"url": "https://example.com/recipe"}),
                content_type='application/json'
            )

            assert response.status_code == 200

            # Load the recipe from file and verify it does NOT have the tag
            recipes = load_recipes(config.RECIPES_FILE)
            imported_recipe = [r for r in recipes if r.name == "Test Recipe No Nutrition"][0]
            assert "nutrition-generated" not in imported_recipe.tags

    def test_import_recipe_adds_inferred_tags(self, client, monkeypatch):
        """Test that tag inference adds appropriate tags during import."""
        from unittest.mock import patch

        from app import config
        from app.recipe_parser import ParsedRecipe
        from app.recipes import load_recipes

        # Mock a dessert recipe
        mock_parsed_recipe = ParsedRecipe(
            name="Chocolate Cake",
            servings=8,
            prep_time_minutes=20,
            cook_time_minutes=30,
            calories_per_serving=350,
            protein_per_serving=5.0,
            carbs_per_serving=45.0,
            fat_per_serving=15.0,
            ingredients=[
                {"item": "all-purpose flour", "quantity": 200, "unit": "g", "category": "grains"},
                {"item": "sugar", "quantity": 150, "unit": "g", "category": "pantry"},
                {"item": "cocoa powder", "quantity": 50, "unit": "g", "category": "pantry"},
                {"item": "eggs", "quantity": 2, "unit": "whole", "category": "dairy"},
                {"item": "baking powder", "quantity": 1, "unit": "tsp", "category": "pantry"}
            ],
            instructions=["Preheat oven to 350°F", "Mix ingredients", "Bake for 30 minutes"],
            tags=[]
        )

        with patch('app.recipe_parser.RecipeParser.parse_from_url') as mock_parse, \
             patch('app.nutrition_generator.NutritionGenerator.generate_from_ingredients') as mock_gen:
            mock_parse.return_value = mock_parsed_recipe
            mock_gen.return_value = None  # No nutrition generation

            response = client.post(
                '/import-recipe',
                data=json.dumps({"url": "https://example.com/recipe"}),
                content_type='application/json'
            )

            assert response.status_code == 200

            # Load the recipe and verify inferred tags
            recipes = load_recipes(config.RECIPES_FILE)
            imported_recipe = [r for r in recipes if r.name == "Chocolate Cake"][0]

            # Should have inferred dessert tag
            assert "dessert" in imported_recipe.tags
            # Should have inferred baking tag
            assert "baking" in imported_recipe.tags
            # Should have inferred vegetarian tag (no meat)
            assert "vegetarian" in imported_recipe.tags


class TestCreateRecipe:
    def test_create_recipe_success(self, client, monkeypatch):
        """Test successful manual recipe creation."""
        from app import config
        from app.recipes import load_recipes

        recipe_data = {
            "name": "My Custom Recipe",
            "servings": 4,
            "prep_time_minutes": 15,
            "cook_time_minutes": 30,
            "ingredients": [
                "2 cups flour",
                "1 tsp salt",
                "3 eggs"
            ],
            "instructions": [
                "Mix dry ingredients",
                "Add eggs",
                "Bake at 350F for 30 minutes"
            ],
            "tags": ["dinner", "easy"],
            "source_url": "https://example.com/recipe",
            "image_url": "https://example.com/image.jpg"
        }

        response = client.post(
            '/recipes',
            data=json.dumps(recipe_data),
            content_type='application/json'
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert 'My Custom Recipe' in data['message']
        assert data['recipe']['id'] == 'my-custom-recipe'
        assert data['recipe']['name'] == 'My Custom Recipe'
        assert data['recipe']['servings'] == 4
        assert data['recipe']['ingredient_count'] == 3
        assert data['recipe']['instruction_count'] == 3

        # Verify recipe was saved to file
        recipes = load_recipes(config.RECIPES_FILE)
        created_recipe = [r for r in recipes if r.name == "My Custom Recipe"][0]
        assert created_recipe.id == 'my-custom-recipe'
        assert created_recipe.servings == 4
        assert created_recipe.prep_time_minutes == 15
        assert created_recipe.cook_time_minutes == 30
        assert len(created_recipe.ingredients) == 3
        assert len(created_recipe.instructions) == 3
        assert "dinner" in created_recipe.tags
        assert "easy" in created_recipe.tags
        assert created_recipe.source_url == "https://example.com/recipe"
        assert created_recipe.image_url == "https://example.com/image.jpg"

    def test_create_recipe_minimal_fields(self, client, monkeypatch):
        """Test creating recipe with only required fields."""
        from app import config
        from app.recipes import load_recipes

        recipe_data = {
            "name": "Minimal Recipe",
            "servings": 2,
            "ingredients": ["ingredient 1"],
            "instructions": ["step 1"]
        }

        response = client.post(
            '/recipes',
            data=json.dumps(recipe_data),
            content_type='application/json'
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True

        # Verify defaults were applied
        recipes = load_recipes(config.RECIPES_FILE)
        created_recipe = [r for r in recipes if r.name == "Minimal Recipe"][0]
        assert created_recipe.prep_time_minutes == 0
        assert created_recipe.cook_time_minutes == 0
        assert "manual-entry" in created_recipe.tags

    def test_create_recipe_missing_name(self, client):
        """Test that missing name returns error."""
        recipe_data = {
            "servings": 4,
            "ingredients": ["ingredient 1"],
            "instructions": ["step 1"]
        }

        response = client.post(
            '/recipes',
            data=json.dumps(recipe_data),
            content_type='application/json'
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'Validation error' in data['error']
        assert 'name' in data['message'].lower()

    def test_create_recipe_missing_servings(self, client):
        """Test that missing servings returns error."""
        recipe_data = {
            "name": "Test Recipe",
            "ingredients": ["ingredient 1"],
            "instructions": ["step 1"]
        }

        response = client.post(
            '/recipes',
            data=json.dumps(recipe_data),
            content_type='application/json'
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'Validation error' in data['error']

    def test_create_recipe_missing_ingredients(self, client):
        """Test that missing ingredients returns error."""
        recipe_data = {
            "name": "Test Recipe",
            "servings": 4,
            "instructions": ["step 1"]
        }

        response = client.post(
            '/recipes',
            data=json.dumps(recipe_data),
            content_type='application/json'
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'Validation error' in data['error']
        assert 'ingredients' in data['message'].lower()

    def test_create_recipe_empty_ingredients_list(self, client):
        """Test that empty ingredients list returns error."""
        recipe_data = {
            "name": "Test Recipe",
            "servings": 4,
            "ingredients": [],
            "instructions": ["step 1"]
        }

        response = client.post(
            '/recipes',
            data=json.dumps(recipe_data),
            content_type='application/json'
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'Validation error' in data['error']
        assert 'ingredient' in data['message'].lower()

    def test_create_recipe_missing_instructions(self, client):
        """Test that missing instructions returns error."""
        recipe_data = {
            "name": "Test Recipe",
            "servings": 4,
            "ingredients": ["ingredient 1"]
        }

        response = client.post(
            '/recipes',
            data=json.dumps(recipe_data),
            content_type='application/json'
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'Validation error' in data['error']
        assert 'instructions' in data['message'].lower()

    def test_create_recipe_empty_instructions_list(self, client):
        """Test that empty instructions list returns error."""
        recipe_data = {
            "name": "Test Recipe",
            "servings": 4,
            "ingredients": ["ingredient 1"],
            "instructions": []
        }

        response = client.post(
            '/recipes',
            data=json.dumps(recipe_data),
            content_type='application/json'
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'Validation error' in data['error']
        assert 'instruction' in data['message'].lower()

    def test_create_recipe_invalid_servings(self, client):
        """Test that invalid servings returns error."""
        recipe_data = {
            "name": "Test Recipe",
            "servings": 0,
            "ingredients": ["ingredient 1"],
            "instructions": ["step 1"]
        }

        response = client.post(
            '/recipes',
            data=json.dumps(recipe_data),
            content_type='application/json'
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'Validation error' in data['error']
        assert 'positive' in data['message'].lower()

    def test_create_recipe_negative_time(self, client):
        """Test that negative time values return error."""
        recipe_data = {
            "name": "Test Recipe",
            "servings": 4,
            "prep_time_minutes": -10,
            "ingredients": ["ingredient 1"],
            "instructions": ["step 1"]
        }

        response = client.post(
            '/recipes',
            data=json.dumps(recipe_data),
            content_type='application/json'
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'Validation error' in data['error']
        assert 'negative' in data['message'].lower()

    def test_create_recipe_structured_ingredients(self, client, monkeypatch):
        """Test creating recipe with pre-structured ingredient dicts."""
        from app import config
        from app.recipes import load_recipes

        recipe_data = {
            "name": "Structured Ingredients Recipe",
            "servings": 4,
            "ingredients": [
                {"item": "chicken breast", "quantity": 500, "unit": "g", "category": "meat"},
                {"item": "olive oil", "quantity": 2, "unit": "tbsp", "category": "pantry"}
            ],
            "instructions": ["Cook the chicken"]
        }

        response = client.post(
            '/recipes',
            data=json.dumps(recipe_data),
            content_type='application/json'
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True

        # Verify structured ingredients were preserved
        recipes = load_recipes(config.RECIPES_FILE)
        created_recipe = [r for r in recipes if r.name == "Structured Ingredients Recipe"][0]
        assert created_recipe.ingredients[0]['item'] == 'chicken breast'
        assert created_recipe.ingredients[0]['quantity'] == 500
        assert created_recipe.ingredients[0]['unit'] == 'g'
        assert created_recipe.ingredients[0]['category'] == 'meat'

    def test_create_recipe_invalid_json(self, client):
        """Test that invalid JSON returns error."""
        response = client.post(
            '/recipes',
            data="not valid json",
            content_type='application/json'
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'Invalid JSON' in data['error']

    def test_create_recipe_generates_unique_id(self, client, monkeypatch):
        """Test that recipe IDs are unique even with conflicting names."""
        from app import config
        from app.recipes import load_recipes

        # Create first recipe
        recipe_data = {
            "name": "Duplicate Name",
            "servings": 4,
            "ingredients": ["ingredient 1"],
            "instructions": ["step 1"]
        }

        response1 = client.post(
            '/recipes',
            data=json.dumps(recipe_data),
            content_type='application/json'
        )
        assert response1.status_code == 200

        # Create second recipe with same name
        response2 = client.post(
            '/recipes',
            data=json.dumps(recipe_data),
            content_type='application/json'
        )
        assert response2.status_code == 200

        # Verify unique IDs were generated
        recipes = load_recipes(config.RECIPES_FILE)
        duplicate_recipes = [r for r in recipes if r.name == "Duplicate Name"]
        assert len(duplicate_recipes) == 2
        assert duplicate_recipes[0].id == 'duplicate-name'
        assert duplicate_recipes[1].id == 'duplicate-name-2'

    def test_create_recipe_clears_current_plan(self, client):
        """Test that creating a recipe clears the current plan."""
        from app import main

        # Set a current plan
        main.current_plan = "some plan"
        main.current_shopping_list = "some list"

        recipe_data = {
            "name": "New Recipe",
            "servings": 4,
            "ingredients": ["ingredient 1"],
            "instructions": ["step 1"]
        }

        response = client.post(
            '/recipes',
            data=json.dumps(recipe_data),
            content_type='application/json'
        )

        assert response.status_code == 200
        # Verify plan was cleared
        assert main.current_plan is None
        assert main.current_shopping_list is None


class TestShareRecipe:
    """Test the PWA share target endpoint /share-recipe."""

    def test_share_recipe_with_url(self, client):
        """Test sharing a recipe URL redirects to home with import_url param."""
        response = client.post(
            '/share-recipe',
            data={
                'url': 'https://example.com/recipe',
                'title': 'Test Recipe',
                'text': 'Some description'
            },
            content_type='application/x-www-form-urlencoded',
            follow_redirects=False
        )

        assert response.status_code == 302
        assert '/?import_url=https://example.com/recipe' in response.location

    def test_share_recipe_with_text_no_url(self, client):
        """Test sharing text without URL redirects to home with import_text param."""
        response = client.post(
            '/share-recipe',
            data={
                'text': 'Recipe ingredients and instructions here',
                'title': 'My Recipe'
            },
            content_type='application/x-www-form-urlencoded',
            follow_redirects=False
        )

        assert response.status_code == 302
        assert 'import_text=' in response.location
        assert 'Recipe' in response.location

    def test_share_recipe_with_title_only(self, client):
        """Test sharing only a title redirects to home with import_text param."""
        response = client.post(
            '/share-recipe',
            data={
                'title': 'Recipe Title'
            },
            content_type='application/x-www-form-urlencoded',
            follow_redirects=False
        )

        assert response.status_code == 302
        assert 'import_text=' in response.location
        assert 'Recipe' in response.location

    def test_share_recipe_no_data(self, client):
        """Test sharing with no data redirects to home page."""
        response = client.post(
            '/share-recipe',
            data={},
            content_type='application/x-www-form-urlencoded',
            follow_redirects=False
        )

        assert response.status_code == 302
        assert response.location.endswith('/')
        assert 'import_url' not in response.location
        assert 'import_text' not in response.location

    def test_share_recipe_url_priority_over_text(self, client):
        """Test that URL takes priority over text when both are provided."""
        response = client.post(
            '/share-recipe',
            data={
                'url': 'https://example.com/recipe',
                'text': 'Some text',
                'title': 'Title'
            },
            content_type='application/x-www-form-urlencoded',
            follow_redirects=False
        )

        assert response.status_code == 302
        assert 'import_url=' in response.location
        assert 'import_text=' not in response.location

    def test_share_recipe_empty_strings(self, client):
        """Test sharing with empty strings redirects to home page."""
        response = client.post(
            '/share-recipe',
            data={
                'url': '   ',
                'text': '  ',
                'title': ''
            },
            content_type='application/x-www-form-urlencoded',
            follow_redirects=False
        )

        assert response.status_code == 302
        assert response.location.endswith('/')
        assert 'import_url' not in response.location
        assert 'import_text' not in response.location


class TestRegenerateMeal:
    """Test the /manual-plan/regenerate-meal endpoint."""

    def test_regenerate_meal_success(self, client, monkeypatch):
        """Test successful meal regeneration."""
        from unittest.mock import patch

        from app import main

        main.manual_plan = {
            "Monday": {
                "Dinner": {
                    "recipe_id": "pasta-bolognese",
                    "servings": 2
                }
            }
        }

        with patch('random.choice') as mock_choice:
            mock_choice.return_value = create_test_recipe(
                recipe_id="chicken-stir-fry",
                name="Chicken Stir Fry",
                tags=["dinner"]
            )

            response = client.post(
                '/manual-plan/regenerate-meal',
                data=json.dumps({
                    "day": "Monday",
                    "meal_type": "Dinner"
                }),
                content_type='application/json'
            )

            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['success'] is True
            assert 'Regenerated Monday Dinner' in data['message']
            assert data['recipe_name'] == 'Chicken Stir Fry'
            assert main.manual_plan["Monday"]["Dinner"]["recipe_id"] == "chicken-stir-fry"
            assert main.manual_plan["Monday"]["Dinner"]["servings"] == 2

    def test_regenerate_meal_maintains_servings(self, client, monkeypatch):
        """Test that regeneration maintains the original serving size."""
        from app import main

        main.manual_plan = {
            "Tuesday": {
                "Lunch": {
                    "recipe_id": "pasta-bolognese",
                    "servings": 3
                }
            }
        }

        response = client.post(
            '/manual-plan/regenerate-meal',
            data=json.dumps({
                "day": "Tuesday",
                "meal_type": "Lunch"
            }),
            content_type='application/json'
        )

        assert response.status_code == 200
        assert main.manual_plan["Tuesday"]["Lunch"]["servings"] == 3

    def test_regenerate_meal_excludes_current_recipe(self, client, tmp_path, monkeypatch):
        """Test that regeneration excludes the current recipe."""
        from app import config, main
        from app.recipes import load_recipes

        main.manual_plan = {
            "Wednesday": {
                "Dinner": {
                    "recipe_id": "pasta-bolognese",
                    "servings": 2
                }
            }
        }

        response = client.post(
            '/manual-plan/regenerate-meal',
            data=json.dumps({
                "day": "Wednesday",
                "meal_type": "Dinner"
            }),
            content_type='application/json'
        )

        assert response.status_code == 200
        new_recipe_id = main.manual_plan["Wednesday"]["Dinner"]["recipe_id"]
        assert new_recipe_id != "pasta-bolognese"

    def test_regenerate_meal_prefers_matching_tags(self, client, tmp_path, monkeypatch):
        """Test that regeneration prefers recipes with matching meal type tags."""
        from unittest.mock import patch

        from app import main

        main.manual_plan = {
            "Thursday": {
                "Dinner": {
                    "recipe_id": "pasta-bolognese",
                    "servings": 2
                }
            }
        }

        dinner_recipe = create_test_recipe(
            recipe_id="chicken-stir-fry",
            name="Chicken Stir Fry",
            tags=["dinner", "quick"]
        )
        breakfast_recipe = create_test_recipe(
            recipe_id="pancakes",
            name="Pancakes",
            tags=["breakfast"]
        )

        with patch('app.main.load_recipes') as mock_load:
            mock_load.return_value = [
                create_test_recipe(
                    recipe_id="pasta-bolognese",
                    name="Pasta Bolognese",
                    tags=["dinner"]
                ),
                dinner_recipe,
                breakfast_recipe
            ]

            with patch('random.choice') as mock_choice:
                mock_choice.return_value = dinner_recipe

                response = client.post(
                    '/manual-plan/regenerate-meal',
                    data=json.dumps({
                        "day": "Thursday",
                        "meal_type": "Dinner"
                    }),
                    content_type='application/json'
                )

                assert response.status_code == 200
                matching_recipes_arg = mock_choice.call_args[0][0]
                assert any(r.id == "chicken-stir-fry" for r in matching_recipes_arg)
                assert not any(r.id == "pancakes" for r in matching_recipes_arg)

    def test_regenerate_meal_missing_day(self, client):
        """Test that missing day returns error."""
        response = client.post(
            '/manual-plan/regenerate-meal',
            data=json.dumps({
                "meal_type": "Dinner"
            }),
            content_type='application/json'
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data
        assert 'Missing day or meal_type' in data['error']

    def test_regenerate_meal_missing_meal_type(self, client):
        """Test that missing meal_type returns error."""
        response = client.post(
            '/manual-plan/regenerate-meal',
            data=json.dumps({
                "day": "Monday"
            }),
            content_type='application/json'
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data
        assert 'Missing day or meal_type' in data['error']

    def test_regenerate_meal_not_in_plan(self, client):
        """Test that regenerating a meal not in plan returns error."""
        from app import main

        main.manual_plan = {}

        response = client.post(
            '/manual-plan/regenerate-meal',
            data=json.dumps({
                "day": "Monday",
                "meal_type": "Dinner"
            }),
            content_type='application/json'
        )

        assert response.status_code == 404
        data = json.loads(response.data)
        assert 'error' in data
        assert 'Meal not found in plan' in data['error']

    def test_regenerate_meal_no_other_recipes(self, client, tmp_path, monkeypatch):
        """Test that regenerating when only one recipe exists returns error."""
        from app import config, main
        from app.recipes import save_recipes

        recipes_file = tmp_path / "single_recipe.json"
        single_recipe = [
            create_test_recipe(
                recipe_id="only-recipe",
                name="Only Recipe",
                tags=["dinner"]
            )
        ]
        save_recipes(recipes_file, single_recipe)
        monkeypatch.setattr(config, 'RECIPES_FILE', str(recipes_file))

        main.manual_plan = {
            "Friday": {
                "Dinner": {
                    "recipe_id": "only-recipe",
                    "servings": 2
                }
            }
        }

        response = client.post(
            '/manual-plan/regenerate-meal',
            data=json.dumps({
                "day": "Friday",
                "meal_type": "Dinner"
            }),
            content_type='application/json'
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data
        assert 'No other recipes available' in data['error']

    def test_regenerate_meal_invalid_json(self, client):
        """Test that invalid JSON returns error."""
        response = client.post(
            '/manual-plan/regenerate-meal',
            data='not valid json',
            content_type='application/json'
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data
        assert 'Invalid JSON' in data['error']

    def test_regenerate_meal_fallback_to_any_recipe(self, client, tmp_path, monkeypatch):
        """Test that regeneration falls back to any recipe when no matching tags."""
        from unittest.mock import patch

        from app import main

        main.manual_plan = {
            "Saturday": {
                "Snack": {
                    "recipe_id": "pasta-bolognese",
                    "servings": 1
                }
            }
        }

        with patch('random.choice') as mock_choice:
            mock_choice.return_value = create_test_recipe(
                recipe_id="chicken-stir-fry",
                name="Chicken Stir Fry",
                tags=["dinner", "lunch"]
            )

            response = client.post(
                '/manual-plan/regenerate-meal',
                data=json.dumps({
                    "day": "Saturday",
                    "meal_type": "Snack"
                }),
                content_type='application/json'
            )

            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['success'] is True
            assert main.manual_plan["Saturday"]["Snack"]["recipe_id"] == "chicken-stir-fry"


class TestShoppingListEditing:
    """Test shopping list CRUD operations."""

    def test_update_shopping_item_quantity(self, client, monkeypatch):
        """Test updating item quantity."""
        from app import main
        from app.shopping_list import ShoppingList, ShoppingListItem

        main.current_shopping_list = ShoppingList(items=[
            ShoppingListItem(item="apples", quantity=3.0, unit="lbs", category="produce"),
            ShoppingListItem(item="milk", quantity=1.0, unit="gallon", category="dairy")
        ])

        response = client.post(
            '/shopping-list/update-item',
            data=json.dumps({
                "index": 0,
                "quantity": 5.0
            }),
            content_type='application/json'
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['item']['quantity'] == 5.0
        assert main.current_shopping_list.items[0].quantity == 5.0

    def test_update_shopping_item_name(self, client, monkeypatch):
        """Test updating item name."""
        from app import main
        from app.shopping_list import ShoppingList, ShoppingListItem

        main.current_shopping_list = ShoppingList(items=[
            ShoppingListItem(item="apples", quantity=3.0, unit="lbs", category="produce")
        ])

        response = client.post(
            '/shopping-list/update-item',
            data=json.dumps({
                "index": 0,
                "name": "green apples"
            }),
            content_type='application/json'
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['item']['item'] == 'green apples'
        assert main.current_shopping_list.items[0].item == 'green apples'

    def test_update_shopping_item_invalid_index(self, client):
        """Test updating with invalid index."""
        from app import main
        from app.shopping_list import ShoppingList, ShoppingListItem

        main.current_shopping_list = ShoppingList(items=[
            ShoppingListItem(item="apples", quantity=3.0, unit="lbs", category="produce")
        ])

        response = client.post(
            '/shopping-list/update-item',
            data=json.dumps({
                "index": 10,
                "quantity": 5.0
            }),
            content_type='application/json'
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data
        assert 'Invalid item index' in data['error']

    def test_update_shopping_item_no_list(self, client):
        """Test updating when no shopping list exists."""
        from app import main

        main.current_shopping_list = None

        response = client.post(
            '/shopping-list/update-item',
            data=json.dumps({
                "index": 0,
                "quantity": 5.0
            }),
            content_type='application/json'
        )

        assert response.status_code == 404
        data = json.loads(response.data)
        assert 'error' in data

    def test_delete_shopping_item(self, client):
        """Test deleting an item from shopping list."""
        from app import main
        from app.shopping_list import ShoppingList, ShoppingListItem

        main.current_shopping_list = ShoppingList(items=[
            ShoppingListItem(item="apples", quantity=3.0, unit="lbs", category="produce"),
            ShoppingListItem(item="milk", quantity=1.0, unit="gallon", category="dairy")
        ])

        response = client.post(
            '/shopping-list/delete-item',
            data=json.dumps({"index": 0}),
            content_type='application/json'
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['deleted_item'] == 'apples'
        assert len(main.current_shopping_list.items) == 1
        assert main.current_shopping_list.items[0].item == 'milk'

    def test_delete_shopping_item_invalid_index(self, client):
        """Test deleting with invalid index."""
        from app import main
        from app.shopping_list import ShoppingList, ShoppingListItem

        main.current_shopping_list = ShoppingList(items=[
            ShoppingListItem(item="apples", quantity=3.0, unit="lbs", category="produce")
        ])

        response = client.post(
            '/shopping-list/delete-item',
            data=json.dumps({"index": 5}),
            content_type='application/json'
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data

    def test_add_shopping_item(self, client):
        """Test adding a custom item to shopping list."""
        from app import main
        from app.shopping_list import ShoppingList, ShoppingListItem

        main.current_shopping_list = ShoppingList(items=[
            ShoppingListItem(item="apples", quantity=3.0, unit="lbs", category="produce")
        ])

        response = client.post(
            '/shopping-list/add-item',
            data=json.dumps({
                "name": "bananas",
                "quantity": 2.0,
                "unit": "lbs",
                "category": "produce"
            }),
            content_type='application/json'
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['item']['item'] == 'bananas'
        assert data['item']['quantity'] == 2.0
        assert len(main.current_shopping_list.items) == 2

    def test_add_shopping_item_minimal(self, client):
        """Test adding item with minimal data."""
        from app import main
        from app.shopping_list import ShoppingList

        main.current_shopping_list = ShoppingList(items=[])

        response = client.post(
            '/shopping-list/add-item',
            data=json.dumps({
                "name": "salt"
            }),
            content_type='application/json'
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['item']['item'] == 'salt'
        assert data['item']['quantity'] == 1
        assert data['item']['category'] == 'other'

    def test_add_shopping_item_invalid_quantity(self, client):
        """Test adding item with invalid quantity."""
        from app import main
        from app.shopping_list import ShoppingList

        main.current_shopping_list = ShoppingList(items=[])

        response = client.post(
            '/shopping-list/add-item',
            data=json.dumps({
                "name": "salt",
                "quantity": -5
            }),
            content_type='application/json'
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data
        assert 'positive' in data['error'].lower()

    def test_add_shopping_item_empty_name(self, client):
        """Test adding item with empty name."""
        from app import main
        from app.shopping_list import ShoppingList

        main.current_shopping_list = ShoppingList(items=[])

        response = client.post(
            '/shopping-list/add-item',
            data=json.dumps({
                "name": "   "
            }),
            content_type='application/json'
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data
        assert 'name is required' in data['error'].lower()


class TestUpdateCurrentPlanMeal:
    """Test the PUT /current-plan/meals endpoint."""

    def test_update_meal_success(self, client):
        """Test successfully adding a recipe to a meal slot."""
        from app import main

        # Ensure clean state
        main.manual_plan = {}

        response = client.put(
            '/current-plan/meals',
            data=json.dumps({
                "day": "Monday",
                "meal_type": "dinner",
                "recipe_id": "pasta-bolognese",
                "servings": 4
            }),
            content_type='application/json'
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert 'Pasta Bolognese' in data['message']
        assert 'Monday' in data['message']
        assert 'dinner' in data['message']

        # Verify the manual plan was updated
        assert 'Monday' in main.manual_plan
        assert 'dinner' in main.manual_plan['Monday']
        assert main.manual_plan['Monday']['dinner']['recipe_id'] == 'pasta-bolognese'

    def test_update_meal_creates_current_plan(self, client):
        """Test that adding a meal creates/updates the current plan."""
        from app import main

        main.manual_plan = {}
        main.current_plan = None

        response = client.put(
            '/current-plan/meals',
            data=json.dumps({
                "day": "Tuesday",
                "meal_type": "dinner",
                "recipe_id": "chicken-stir-fry",
                "servings": 2
            }),
            content_type='application/json'
        )

        assert response.status_code == 200
        # The current plan should now be populated
        assert main.current_plan is not None

    def test_update_meal_recipe_not_found(self, client):
        """Test updating a slot with a non-existent recipe."""
        response = client.put(
            '/current-plan/meals',
            data=json.dumps({
                "day": "Monday",
                "meal_type": "dinner",
                "recipe_id": "nonexistent-recipe",
                "servings": 4
            }),
            content_type='application/json'
        )

        assert response.status_code == 404
        data = json.loads(response.data)
        assert 'error' in data

    def test_update_meal_missing_day(self, client):
        """Test that missing 'day' field returns 400."""
        response = client.put(
            '/current-plan/meals',
            data=json.dumps({
                "meal_type": "dinner",
                "recipe_id": "pasta-bolognese",
                "servings": 4
            }),
            content_type='application/json'
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data

    def test_update_meal_missing_meal_type(self, client):
        """Test that missing 'meal_type' field returns 400."""
        response = client.put(
            '/current-plan/meals',
            data=json.dumps({
                "day": "Monday",
                "recipe_id": "pasta-bolognese",
                "servings": 4
            }),
            content_type='application/json'
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data

    def test_update_meal_missing_recipe_id(self, client):
        """Test that missing 'recipe_id' field returns 400."""
        response = client.put(
            '/current-plan/meals',
            data=json.dumps({
                "day": "Monday",
                "meal_type": "dinner",
                "servings": 4
            }),
            content_type='application/json'
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data

    def test_update_meal_invalid_json(self, client):
        """Test that invalid JSON returns 400."""
        response = client.put(
            '/current-plan/meals',
            data='not json',
            content_type='application/json'
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data

    def test_update_meal_uses_default_servings(self, client):
        """Test that servings defaults to config.TOTAL_PORTIONS when not provided."""
        from app import config, main

        main.manual_plan = {}

        response = client.put(
            '/current-plan/meals',
            data=json.dumps({
                "day": "Wednesday",
                "meal_type": "lunch",
                "recipe_id": "pasta-bolognese"
            }),
            content_type='application/json'
        )

        assert response.status_code == 200
        assert main.manual_plan['Wednesday']['lunch']['servings'] == config.TOTAL_PORTIONS

    def test_update_meal_overwrites_existing_slot(self, client):
        """Test that updating an existing slot replaces the recipe."""
        from app import main

        main.manual_plan = {
            'Monday': {
                'dinner': {'recipe_id': 'pasta-bolognese', 'servings': 4}
            }
        }

        response = client.put(
            '/current-plan/meals',
            data=json.dumps({
                "day": "Monday",
                "meal_type": "dinner",
                "recipe_id": "chicken-stir-fry",
                "servings": 3
            }),
            content_type='application/json'
        )

        assert response.status_code == 200
        assert main.manual_plan['Monday']['dinner']['recipe_id'] == 'chicken-stir-fry'
        assert main.manual_plan['Monday']['dinner']['servings'] == 3


class TestServingsValidation:
    """servings must be a positive number on add-meal and update-servings."""

    def test_add_meal_rejects_zero_servings(self, client):
        response = client.post(
            '/manual-plan/add-meal',
            data=json.dumps({
                "day": "Monday", "meal_type": "dinner",
                "recipe_id": "pasta-bolognese", "servings": 0,
            }),
            content_type='application/json',
        )
        assert response.status_code == 400
        assert "servings" in json.loads(response.data).get("error", "").lower()

    def test_add_meal_rejects_negative_servings(self, client):
        response = client.post(
            '/manual-plan/add-meal',
            data=json.dumps({
                "day": "Monday", "meal_type": "dinner",
                "recipe_id": "pasta-bolognese", "servings": -2,
            }),
            content_type='application/json',
        )
        assert response.status_code == 400

    def test_add_meal_rejects_string_servings(self, client):
        response = client.post(
            '/manual-plan/add-meal',
            data=json.dumps({
                "day": "Monday", "meal_type": "dinner",
                "recipe_id": "pasta-bolognese", "servings": "lots",
            }),
            content_type='application/json',
        )
        assert response.status_code == 400

    def test_add_meal_accepts_positive_servings(self, client):
        response = client.post(
            '/manual-plan/add-meal',
            data=json.dumps({
                "day": "Monday", "meal_type": "dinner",
                "recipe_id": "pasta-bolognese", "servings": 4,
            }),
            content_type='application/json',
        )
        assert response.status_code == 200

    def test_update_servings_rejects_zero(self, client):
        # First add a meal so we can update it
        client.post(
            '/manual-plan/add-meal',
            data=json.dumps({
                "day": "Monday", "meal_type": "dinner",
                "recipe_id": "pasta-bolognese", "servings": 4,
            }),
            content_type='application/json',
        )
        response = client.post(
            '/manual-plan/update-servings',
            data=json.dumps({"day": "Monday", "meal_type": "dinner", "servings": 0}),
            content_type='application/json',
        )
        assert response.status_code == 400

    def test_update_servings_rejects_negative(self, client):
        client.post(
            '/manual-plan/add-meal',
            data=json.dumps({
                "day": "Monday", "meal_type": "dinner",
                "recipe_id": "pasta-bolognese", "servings": 4,
            }),
            content_type='application/json',
        )
        response = client.post(
            '/manual-plan/update-servings',
            data=json.dumps({"day": "Monday", "meal_type": "dinner", "servings": -1}),
            content_type='application/json',
        )
        assert response.status_code == 400

    def test_update_servings_accepts_positive(self, client):
        client.post(
            '/manual-plan/add-meal',
            data=json.dumps({
                "day": "Monday", "meal_type": "dinner",
                "recipe_id": "pasta-bolognese", "servings": 4,
            }),
            content_type='application/json',
        )
        response = client.post(
            '/manual-plan/update-servings',
            data=json.dumps({"day": "Monday", "meal_type": "dinner", "servings": 6}),
            content_type='application/json',
        )
        assert response.status_code == 200


class TestNullQuantitySerialization:
    """round(item.quantity, 2) raises TypeError when quantity is None (BUG-3)."""

    def test_current_plan_with_null_quantity_item(self, client, monkeypatch):
        """Shopping list items with quantity=None must serialise to null, not crash."""
        from app import main
        from app.planner import PlannedMeal, WeeklyPlan
        from app.recipes import Recipe
        from app.shopping_list import ShoppingList, ShoppingListItem

        # Build a minimal plan so get_current_plan has a current_plan to render.
        recipe = create_test_recipe(
            recipe_id="pasta-bolognese",
            name="Pasta Bolognese",
            servings=4,
            ingredients=[{"item": "salt", "unit": "to taste", "category": "pantry"}],
        )
        plan = WeeklyPlan(meals=[
            PlannedMeal(day="Monday", meal_type="dinner", recipe=recipe, household_portions=4.0)
        ])

        # Inject a shopping list that contains a None-quantity item.
        sl = ShoppingList(items=[
            ShoppingListItem(item="salt", quantity=None, unit="", category="pantry"),
            ShoppingListItem(item="flour", quantity=2.5, unit="cup", category="pantry"),
        ])

        monkeypatch.setattr(main, "current_plan", plan)
        monkeypatch.setattr(main, "current_shopping_list", sl)

        response = client.get("/current-plan")
        assert response.status_code == 200

        data = json.loads(response.data)
        items = data["shopping_list"]["items"]
        salt = next(i for i in items if i["item"] == "salt")
        flour = next(i for i in items if i["item"] == "flour")

        assert salt["quantity"] is None
        assert flour["quantity"] == pytest.approx(2.5)


class TestShoppingListIndexSafety:
    """index TOCTOU: bounds check and item access must use the same list snapshot."""

    @pytest.fixture
    def client_with_shopping_list(self, client, monkeypatch):
        from app import main
        from app.shopping_list import ShoppingList, ShoppingListItem

        sl = ShoppingList(items=[
            ShoppingListItem(item="flour", quantity=2.0, unit="cup", category="pantry"),
            ShoppingListItem(item="sugar", quantity=1.0, unit="cup", category="pantry"),
        ])
        monkeypatch.setattr(main, "current_shopping_list", sl)
        return client

    def test_update_item_valid_index(self, client_with_shopping_list):
        response = client_with_shopping_list.post(
            '/shopping-list/update-item',
            data=json.dumps({"index": 0, "quantity": 3.0}),
            content_type='application/json',
        )
        assert response.status_code == 200

    def test_update_item_out_of_bounds(self, client_with_shopping_list):
        response = client_with_shopping_list.post(
            '/shopping-list/update-item',
            data=json.dumps({"index": 99}),
            content_type='application/json',
        )
        assert response.status_code == 400

    def test_delete_item_valid_index(self, client_with_shopping_list):
        response = client_with_shopping_list.post(
            '/shopping-list/delete-item',
            data=json.dumps({"index": 0}),
            content_type='application/json',
        )
        assert response.status_code == 200
        assert json.loads(response.data)["deleted_item"] == "flour"

    def test_delete_item_out_of_bounds(self, client_with_shopping_list):
        response = client_with_shopping_list.post(
            '/shopping-list/delete-item',
            data=json.dumps({"index": 5}),
            content_type='application/json',
        )
        assert response.status_code == 400

    def test_delete_item_negative_index(self, client_with_shopping_list):
        response = client_with_shopping_list.post(
            '/shopping-list/delete-item',
            data=json.dumps({"index": -1}),
            content_type='application/json',
        )
        assert response.status_code == 400


class TestImageMagicBytes:
    """_is_valid_image_bytes rejects non-image content regardless of extension."""

    PNG_MAGIC = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
    JPEG_MAGIC = b"\xff\xd8\xff\xe0" + b"\x00" * 100
    GIF_MAGIC = b"GIF89a" + b"\x00" * 100
    WEBP_MAGIC = b"RIFF\x00\x00\x00\x00WEBP" + b"\x00" * 100
    FAKE_MAGIC = b"<?php echo 'hello'; ?>" + b"\x00" * 100

    # --- unit tests for the helper ---
    def test_png_recognised(self):
        assert _is_valid_image_bytes(self.PNG_MAGIC)

    def test_jpeg_recognised(self):
        assert _is_valid_image_bytes(self.JPEG_MAGIC)

    def test_gif_recognised(self):
        assert _is_valid_image_bytes(self.GIF_MAGIC)

    def test_webp_recognised(self):
        assert _is_valid_image_bytes(self.WEBP_MAGIC)

    def test_php_rejected(self):
        assert not _is_valid_image_bytes(self.FAKE_MAGIC)

    def test_empty_bytes_rejected(self):
        assert not _is_valid_image_bytes(b"")

    # --- endpoint integration: spoofed file rejected ---
    def test_upload_with_php_content_and_png_extension_is_rejected(self, client):
        """A file named .png whose bytes are PHP source must be rejected with 400."""
        data = {"image": (io.BytesIO(self.FAKE_MAGIC), "malicious.png")}
        response = client.post(
            "/import-recipe-image",
            data=data,
            content_type="multipart/form-data",
        )
        assert response.status_code == 400
        body = json.loads(response.data)
        assert "content" in body.get("error", "").lower() or "image" in body.get("message", "").lower()

    def test_upload_with_valid_png_bytes_passes_magic_check(self, client, monkeypatch):
        """A real PNG file passes the magic check (further processing may fail without API key)."""
        from app.image_recipe_extractor import ImageRecipeData, ImageRecipeExtractor

        mock_result = ImageRecipeData(
            name="Test Recipe", servings=2, ingredients=[], instructions=[],
            tags=[], prep_time_minutes=None, cook_time_minutes=None,
            notes=None, confidence=0.9,
        )
        monkeypatch.setattr(ImageRecipeExtractor, "extract_recipe", lambda self, d, e: mock_result)

        from app.nutrition_generator import NutritionGenerator
        monkeypatch.setattr(NutritionGenerator, "generate_from_ingredients", lambda self, n, i: {})

        from app import main
        monkeypatch.setattr(main, "current_plan", None)
        monkeypatch.setattr(main, "current_shopping_list", None)

        data = {"image": (io.BytesIO(self.PNG_MAGIC), "photo.png")}
        response = client.post(
            "/import-recipe-image",
            data=data,
            content_type="multipart/form-data",
        )
        # Must NOT be rejected for invalid content (may succeed or fail for other reasons)
        body = json.loads(response.data)
        assert body.get("error") != "Invalid file content"
