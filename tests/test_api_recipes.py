"""
Tests for /api/recipes endpoint - server-side pagination, search, and filtering.

Following TDD approach: tests define the API contract first.
"""

import pytest

from app.main import app
from app.recipes import Recipe


@pytest.fixture
def client():
    """Create a test client for the Flask app."""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def sample_recipes(tmp_path, monkeypatch):
    """Create sample recipes for testing."""
    recipes = [
        Recipe(
            id="chicken-parmesan",
            name="Chicken Parmesan",
            servings=4,
            prep_time_minutes=15,
            cook_time_minutes=30,
            ingredients=[{"item": "chicken", "quantity": 1, "unit": "lb"}],
            instructions=["Cook chicken", "Add sauce"],
            tags=["italian", "dinner", "chicken"],
            nutrition_per_serving={"calories": 450, "protein": 35.0, "carbs": 25.0, "fat": 20.0}
        ),
        Recipe(
            id="greek-salad",
            name="Greek Salad",
            servings=2,
            prep_time_minutes=10,
            cook_time_minutes=0,
            ingredients=[{"item": "lettuce", "quantity": 2, "unit": "cups"}],
            instructions=["Mix ingredients"],
            tags=["greek", "salad", "vegetarian", "quick"],
            nutrition_per_serving={"calories": 200, "protein": 5.0, "carbs": 15.0, "fat": 12.0}
        ),
        Recipe(
            id="chocolate-cake",
            name="Chocolate Cake",
            servings=8,
            prep_time_minutes=20,
            cook_time_minutes=35,
            ingredients=[{"item": "flour", "quantity": 2, "unit": "cups"}],
            instructions=["Mix", "Bake"],
            tags=["dessert", "chocolate", "baking"],
            nutrition_per_serving={"calories": 350, "protein": 4.0, "carbs": 45.0, "fat": 18.0}
        ),
        Recipe(
            id="veggie-stir-fry",
            name="Veggie Stir Fry",
            servings=3,
            prep_time_minutes=10,
            cook_time_minutes=15,
            ingredients=[{"item": "vegetables", "quantity": 2, "unit": "cups"}],
            instructions=["Stir fry"],
            tags=["asian", "vegetarian", "vegan", "quick", "dinner"],
            nutrition_per_serving={"calories": 250, "protein": 8.0, "carbs": 35.0, "fat": 10.0}
        ),
        Recipe(
            id="breakfast-burrito",
            name="Breakfast Burrito",
            servings=1,
            prep_time_minutes=5,
            cook_time_minutes=10,
            ingredients=[ {"item": "eggs", "quantity": 2, "unit": ""}],
            instructions=["Scramble eggs", "Wrap"],
            tags=["mexican", "breakfast", "quick"],
            nutrition_per_serving={"calories": 400, "protein": 20.0, "carbs": 30.0, "fat": 22.0}
        ),
    ]

    # Mock the recipes file path and load function
    import app.main

    def mock_load_recipes(path):
        return recipes

    monkeypatch.setattr(app.main, 'load_recipes', mock_load_recipes)

    return recipes


class TestBasicPagination:
    """Test basic pagination functionality."""

    def test_default_pagination(self, client, sample_recipes):
        """Test default pagination returns first page with 24 items per page."""
        response = client.get('/api/recipes')
        assert response.status_code == 200

        data = response.get_json()
        assert 'recipes' in data
        assert 'pagination' in data

        # With 5 recipes, all should be on page 1
        assert len(data['recipes']) == 5
        assert data['pagination']['page'] == 1
        assert data['pagination']['per_page'] == 24
        assert data['pagination']['total_recipes'] == 5
        assert data['pagination']['total_pages'] == 1

    def test_custom_per_page(self, client, sample_recipes):
        """Test custom per_page parameter."""
        response = client.get('/api/recipes?per_page=2')
        assert response.status_code == 200

        data = response.get_json()
        assert len(data['recipes']) == 2
        assert data['pagination']['per_page'] == 2
        assert data['pagination']['total_pages'] == 3  # 5 recipes / 2 per page

    def test_second_page(self, client, sample_recipes):
        """Test fetching second page."""
        response = client.get('/api/recipes?page=2&per_page=2')
        assert response.status_code == 200

        data = response.get_json()
        assert len(data['recipes']) == 2
        assert data['pagination']['page'] == 2
        assert data['pagination']['has_prev'] is True
        assert data['pagination']['has_next'] is True

    def test_last_page(self, client, sample_recipes):
        """Test last page with fewer items."""
        response = client.get('/api/recipes?page=3&per_page=2')
        assert response.status_code == 200

        data = response.get_json()
        assert len(data['recipes']) == 1  # Only 1 recipe on last page
        assert data['pagination']['has_next'] is False

    def test_page_beyond_total(self, client, sample_recipes):
        """Test requesting page beyond total pages returns empty."""
        response = client.get('/api/recipes?page=10&per_page=2')
        assert response.status_code == 200

        data = response.get_json()
        assert len(data['recipes']) == 0
        assert data['pagination']['page'] == 10


class TestSearch:
    """Test search functionality."""

    def test_search_by_name(self, client, sample_recipes):
        """Test search by recipe name."""
        response = client.get('/api/recipes?search=chicken')
        assert response.status_code == 200

        data = response.get_json()
        assert len(data['recipes']) == 1
        assert data['recipes'][0]['name'] == 'Chicken Parmesan'
        assert data['pagination']['total_recipes'] == 1

    def test_search_case_insensitive(self, client, sample_recipes):
        """Test search is case insensitive."""
        response = client.get('/api/recipes?search=GREEK')
        assert response.status_code == 200

        data = response.get_json()
        assert len(data['recipes']) == 1
        assert data['recipes'][0]['name'] == 'Greek Salad'

    def test_search_partial_match(self, client, sample_recipes):
        """Test partial name matching."""
        response = client.get('/api/recipes?search=cake')
        assert response.status_code == 200

        data = response.get_json()
        assert len(data['recipes']) == 1
        assert 'Cake' in data['recipes'][0]['name']

    def test_search_no_results(self, client, sample_recipes):
        """Test search with no matches."""
        response = client.get('/api/recipes?search=pizza')
        assert response.status_code == 200

        data = response.get_json()
        assert len(data['recipes']) == 0
        assert data['pagination']['total_recipes'] == 0

    def test_search_by_ingredient_name(self, client, sample_recipes):
        """Test search by ingredient name finds matching recipe."""
        response = client.get('/api/recipes?search=lettuce')
        assert response.status_code == 200

        data = response.get_json()
        assert len(data['recipes']) == 1
        assert data['recipes'][0]['name'] == 'Greek Salad'
        assert data['pagination']['total_recipes'] == 1

    def test_search_by_ingredient_case_insensitive(self, client, sample_recipes):
        """Test ingredient search is case-insensitive."""
        response = client.get('/api/recipes?search=FLOUR')
        assert response.status_code == 200

        data = response.get_json()
        assert len(data['recipes']) == 1
        assert data['recipes'][0]['name'] == 'Chocolate Cake'

    def test_search_by_name_still_works_regression(self, client, sample_recipes):
        """Test that searching by recipe name still works after ingredient search added."""
        response = client.get('/api/recipes?search=burrito')
        assert response.status_code == 200

        data = response.get_json()
        assert len(data['recipes']) == 1
        assert data['recipes'][0]['name'] == 'Breakfast Burrito'

    def test_search_partial_ingredient_name(self, client, sample_recipes):
        """Test that partial ingredient name match returns recipe."""
        # "lettu" is a partial match for the ingredient "lettuce" in Greek Salad
        # and does not appear in any recipe name or tag
        response = client.get('/api/recipes?search=lettu')
        assert response.status_code == 200

        data = response.get_json()
        assert len(data['recipes']) == 1
        assert data['recipes'][0]['name'] == 'Greek Salad'


class TestTagFiltering:
    """Test filtering by tags."""

    def test_filter_single_tag(self, client, sample_recipes):
        """Test filtering by a single tag."""
        response = client.get('/api/recipes?tags=vegetarian')
        assert response.status_code == 200

        data = response.get_json()
        assert len(data['recipes']) == 2  # Greek Salad and Veggie Stir Fry
        assert data['pagination']['total_recipes'] == 2

    def test_filter_multiple_tags(self, client, sample_recipes):
        """Test filtering by multiple tags (AND logic)."""
        response = client.get('/api/recipes?tags=vegetarian,quick')
        assert response.status_code == 200

        data = response.get_json()
        # Both Greek Salad and Veggie Stir Fry have both tags
        assert len(data['recipes']) == 2

    def test_filter_tag_no_matches(self, client, sample_recipes):
        """Test tag filter with no matches."""
        response = client.get('/api/recipes?tags=nonexistent')
        assert response.status_code == 200

        data = response.get_json()
        assert len(data['recipes']) == 0


class TestSorting:
    """Test sorting functionality."""

    def test_sort_by_name_asc(self, client, sample_recipes):
        """Test sorting by name ascending."""
        response = client.get('/api/recipes?sort=name_asc')
        assert response.status_code == 200

        data = response.get_json()
        names = [r['name'] for r in data['recipes']]
        assert names == sorted(names)
        assert names[0] == 'Breakfast Burrito'

    def test_sort_by_name_desc(self, client, sample_recipes):
        """Test sorting by name descending."""
        response = client.get('/api/recipes?sort=name_desc')
        assert response.status_code == 200

        data = response.get_json()
        names = [r['name'] for r in data['recipes']]
        assert names == sorted(names, reverse=True)
        assert names[0] == 'Veggie Stir Fry'

    def test_sort_by_calories_asc(self, client, sample_recipes):
        """Test sorting by calories ascending."""
        response = client.get('/api/recipes?sort=calories_asc')
        assert response.status_code == 200

        data = response.get_json()
        calories = [r['nutrition_per_serving']['calories'] for r in data['recipes']]
        assert calories == sorted(calories)
        assert calories[0] == 200  # Greek Salad

    def test_sort_by_time_asc(self, client, sample_recipes):
        """Test sorting by total time ascending."""
        response = client.get('/api/recipes?sort=time_asc')
        assert response.status_code == 200

        data = response.get_json()
        # Greek Salad has 10 min prep + 0 cook = 10 min total
        assert data['recipes'][0]['name'] == 'Greek Salad'


class TestCalorieFiltering:
    """Test filtering by calorie ranges."""

    def test_max_calories(self, client, sample_recipes):
        """Test maximum calories filter."""
        response = client.get('/api/recipes?max_calories=300')
        assert response.status_code == 200

        data = response.get_json()
        # Greek Salad (200) and Veggie Stir Fry (250)
        assert len(data['recipes']) == 2
        for recipe in data['recipes']:
            assert recipe['nutrition_per_serving']['calories'] <= 300

    def test_min_calories(self, client, sample_recipes):
        """Test minimum calories filter."""
        response = client.get('/api/recipes?min_calories=400')
        assert response.status_code == 200

        data = response.get_json()
        # Chicken Parmesan (450) and Breakfast Burrito (400)
        assert len(data['recipes']) == 2
        for recipe in data['recipes']:
            assert recipe['nutrition_per_serving']['calories'] >= 400

    def test_calorie_range(self, client, sample_recipes):
        """Test calorie range filter."""
        response = client.get('/api/recipes?min_calories=200&max_calories=400')
        assert response.status_code == 200

        data = response.get_json()
        # Greek Salad (200), Veggie Stir Fry (250), Chocolate Cake (350), Breakfast Burrito (400)
        assert len(data['recipes']) == 4


class TestTimeFiltering:
    """Test filtering by time."""

    def test_max_time(self, client, sample_recipes):
        """Test maximum time filter."""
        response = client.get('/api/recipes?max_time=20')
        assert response.status_code == 200

        data = response.get_json()
        # Greek Salad (10), Breakfast Burrito (15)
        assert len(data['recipes']) == 2


class TestCombinedFilters:
    """Test combining multiple filters."""

    def test_search_and_tags(self, client, sample_recipes):
        """Test search combined with tag filtering."""
        response = client.get('/api/recipes?search=salad&tags=vegetarian')
        assert response.status_code == 200

        data = response.get_json()
        assert len(data['recipes']) == 1
        assert data['recipes'][0]['name'] == 'Greek Salad'

    def test_tags_and_sort(self, client, sample_recipes):
        """Test tag filtering with sorting."""
        response = client.get('/api/recipes?tags=quick&sort=calories_asc')
        assert response.status_code == 200

        data = response.get_json()
        # Greek Salad, Veggie Stir Fry, Breakfast Burrito (all quick)
        assert len(data['recipes']) == 3
        # Sorted by calories: 200, 250, 400
        assert data['recipes'][0]['name'] == 'Greek Salad'

    def test_all_filters_combined(self, client, sample_recipes):
        """Test combining search, tags, calories, and pagination."""
        response = client.get('/api/recipes?tags=vegetarian&max_calories=300&sort=name_asc&per_page=1')
        assert response.status_code == 200

        data = response.get_json()
        # Greek Salad (200) and Veggie Stir Fry (250) match
        # Sorted by name, so Greek Salad first
        # Only 1 per page
        assert len(data['recipes']) == 1
        assert data['recipes'][0]['name'] == 'Greek Salad'
        assert data['pagination']['total_recipes'] == 2


class TestRecipeFormat:
    """Test recipe response format."""

    def test_recipe_includes_all_fields(self, client, sample_recipes):
        """Test that recipe response includes all expected fields."""
        response = client.get('/api/recipes')
        assert response.status_code == 200

        data = response.get_json()
        recipe = data['recipes'][0]

        # Check required fields
        assert 'id' in recipe
        assert 'name' in recipe
        assert 'servings' in recipe
        assert 'prep_time_minutes' in recipe
        assert 'cook_time_minutes' in recipe
        assert 'total_time_minutes' in recipe
        assert 'tags' in recipe
        assert 'nutrition_per_serving' in recipe

        # Check nutrition subfields
        nutrition = recipe['nutrition_per_serving']
        assert 'calories' in nutrition
        assert 'protein' in nutrition
        assert 'carbs' in nutrition
        assert 'fat' in nutrition
