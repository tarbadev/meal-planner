import json
from pathlib import Path

import pytest

from app.main import app
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
