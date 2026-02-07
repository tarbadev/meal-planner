import json
import pytest
from pathlib import Path

from app.main import app
from app.recipes import Recipe, save_recipes


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Create a test client with a temporary recipes file."""
    # Create test recipes file
    recipes_file = tmp_path / "recipes.json"
    test_recipes = [
        Recipe(
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
        ),
        Recipe(
            id="chicken-stir-fry",
            name="Chicken Stir Fry",
            servings=4,
            prep_time_minutes=10,
            cook_time_minutes=15,
            calories_per_serving=350,
            protein_per_serving=30,
            carbs_per_serving=25,
            fat_per_serving=10,
            tags=["asian", "quick"],
            ingredients=[
                {"item": "chicken breast", "quantity": 500, "unit": "g", "category": "meat"},
                {"item": "mixed vegetables", "quantity": 300, "unit": "g", "category": "produce"},
            ]
        ),
    ]
    save_recipes(recipes_file, test_recipes)

    # Patch the config to use our test file
    import config
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
        import config

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
        import config
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
