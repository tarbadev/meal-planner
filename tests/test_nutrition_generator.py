"""Tests for nutrition generator module."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from app.nutrition_generator import (
    UnitConverter,
    USDAFoodDataClient,
    NutritionGenerator,
    NutritionData,
    IngredientNutrition
)


class TestUnitConverter:
    """Tests for UnitConverter class."""

    def test_weight_conversions(self):
        """Test direct weight conversions."""
        converter = UnitConverter()

        assert converter.convert_to_grams(500, 'g', '') == 500
        assert converter.convert_to_grams(1, 'kg', '') == 1000
        assert converter.convert_to_grams(1, 'oz', '') == 28.35
        assert converter.convert_to_grams(1, 'lb', '') == 453.592
        assert converter.convert_to_grams(2, 'pound', '') == 907.184

    def test_volume_to_weight_generic(self):
        """Test volume conversions without ingredient-specific density."""
        converter = UnitConverter()

        # 1 cup = 236.588 ml, assume water density (1g/ml) -> 236.588g
        result = converter.convert_to_grams(1, 'cup', 'unknown-ingredient')
        assert result == pytest.approx(236.588, rel=0.01)

        # 1 tbsp = 14.787 ml
        result = converter.convert_to_grams(1, 'tbsp', '')
        assert result == pytest.approx(14.787, rel=0.01)

        # 1 tsp = 4.929 ml
        result = converter.convert_to_grams(1, 'tsp', '')
        assert result == pytest.approx(4.929, rel=0.01)

    def test_volume_to_weight_with_ingredient_density(self):
        """Test volume conversions with ingredient-specific densities."""
        converter = UnitConverter()

        # 1 cup flour = 120g
        result = converter.convert_to_grams(1, 'cup', 'all-purpose flour')
        assert result == pytest.approx(120, rel=0.01)

        # 1 cup butter = 227g
        result = converter.convert_to_grams(1, 'cup', 'butter')
        assert result == pytest.approx(227, rel=0.01)

        # 1 cup sugar = 200g
        result = converter.convert_to_grams(1, 'cup', 'white sugar')
        assert result == pytest.approx(200, rel=0.01)

    def test_count_conversions(self):
        """Test count-based conversions."""
        converter = UnitConverter()

        assert converter.convert_to_grams(1, 'egg', '') == 50
        assert converter.convert_to_grams(2, 'eggs', '') == 100
        assert converter.convert_to_grams(3, 'cloves', 'garlic') == 9
        assert converter.convert_to_grams(1, 'whole', 'onion') == 150

    def test_unknown_unit_default(self):
        """Test default handling for unknown units."""
        converter = UnitConverter()

        # Serving unit should default to 100g
        result = converter.convert_to_grams(1, 'serving', '')
        assert result == 100

        # Empty unit should default to 100g
        result = converter.convert_to_grams(1, '', '')
        assert result == 100

    def test_unknown_unit_returns_none(self):
        """Test that truly unknown units return None."""
        converter = UnitConverter()

        result = converter.convert_to_grams(1, 'pinch', '')
        assert result is None

        result = converter.convert_to_grams(1, 'dash', '')
        assert result is None


class TestUSDAFoodDataClient:
    """Tests for USDA API client."""

    def test_search_foods_success(self):
        """Test successful food search."""
        client = USDAFoodDataClient()

        # Mock the requests.Session.get method
        with patch.object(client.session, 'get') as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = {
                'foods': [
                    {
                        'fdcId': 174032,
                        'description': 'Beef, ground, 85% lean',
                        'score': 0.876
                    }
                ]
            }
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

            results = client.search_foods('ground beef')

            assert len(results) == 1
            assert results[0]['fdcId'] == 174032
            assert 'Beef' in results[0]['description']

    def test_search_foods_error(self):
        """Test food search with network error."""
        import requests
        client = USDAFoodDataClient()

        with patch.object(client.session, 'get') as mock_get:
            mock_get.side_effect = requests.RequestException("Network error")

            results = client.search_foods('ground beef')

            assert results == []

    def test_get_food_details_success(self):
        """Test successful food details retrieval."""
        client = USDAFoodDataClient()

        with patch.object(client.session, 'get') as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = {
                'fdcId': 174032,
                'description': 'Beef, ground, 85% lean',
                'foodNutrients': []
            }
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

            details = client.get_food_details(174032)

            assert details is not None
            assert details['fdcId'] == 174032

    def test_get_food_details_error(self):
        """Test food details retrieval with error."""
        import requests
        client = USDAFoodDataClient()

        with patch.object(client.session, 'get') as mock_get:
            mock_get.side_effect = requests.RequestException("Network error")

            details = client.get_food_details(174032)

            assert details is None

    def test_extract_nutrition(self):
        """Test nutrition extraction from USDA food data."""
        client = USDAFoodDataClient()

        food_data = {
            'foodNutrients': [
                {
                    'nutrient': {'id': 1008, 'name': 'Energy'},
                    'amount': 215
                },
                {
                    'nutrient': {'id': 1003, 'name': 'Protein'},
                    'amount': 18.59
                },
                {
                    'nutrient': {'id': 1005, 'name': 'Carbohydrate'},
                    'amount': 0
                },
                {
                    'nutrient': {'id': 1004, 'name': 'Total lipid (fat)'},
                    'amount': 15
                }
            ]
        }

        nutrition = client.extract_nutrition(food_data)

        assert nutrition is not None
        assert nutrition.calories == 215
        assert nutrition.protein == 18.59
        assert nutrition.carbs == 0
        assert nutrition.fat == 15
        assert nutrition.confidence == 1.0

    def test_extract_nutrition_no_data(self):
        """Test nutrition extraction with missing nutrients."""
        client = USDAFoodDataClient()

        food_data = {
            'foodNutrients': []
        }

        nutrition = client.extract_nutrition(food_data)

        assert nutrition is None


class TestNutritionGenerator:
    """Tests for NutritionGenerator class."""

    def test_should_generate_nutrition_missing(self):
        """Test detection of missing nutrition."""
        gen = NutritionGenerator()

        # Mock parsed recipe with no nutrition
        class MockRecipe:
            calories_per_serving = 0
            protein_per_serving = 0.0

        assert gen.should_generate_nutrition(MockRecipe()) is True

    def test_should_generate_nutrition_present(self):
        """Test detection when nutrition is present."""
        gen = NutritionGenerator()

        # Mock recipe with nutrition
        class MockRecipeWithNutrition:
            calories_per_serving = 350
            protein_per_serving = 25.0

        assert gen.should_generate_nutrition(MockRecipeWithNutrition()) is False

    def test_clean_ingredient_name(self):
        """Test ingredient name cleaning."""
        gen = NutritionGenerator()

        assert gen._clean_ingredient_name('fresh chopped onion') == 'onion'
        assert gen._clean_ingredient_name('2 cups (250g) flour') == '2 cups flour'  # Parenthetical removed
        assert gen._clean_ingredient_name('boneless skinless chicken breast') == 'chicken breast'
        assert gen._clean_ingredient_name('large diced tomatoes') == 'tomatoes'
        assert gen._clean_ingredient_name('extra virgin olive oil') == 'virgin olive oil'

    def test_generate_from_ingredients_no_ingredients(self):
        """Test generation with empty ingredient list."""
        gen = NutritionGenerator()

        result = gen.generate_from_ingredients([], servings=4)

        assert result is None

    def test_generate_from_ingredients_zero_servings(self):
        """Test generation with zero servings."""
        gen = NutritionGenerator()

        ingredients = [
            {"item": "flour", "quantity": 2, "unit": "cups", "category": "pantry"}
        ]

        result = gen.generate_from_ingredients(ingredients, servings=0)

        assert result is None

    @patch.object(USDAFoodDataClient, 'search_foods')
    @patch.object(USDAFoodDataClient, 'get_food_details')
    @patch.object(USDAFoodDataClient, 'extract_nutrition')
    def test_calculate_ingredient_nutrition_success(self, mock_extract, mock_details, mock_search):
        """Test successful ingredient nutrition calculation."""
        gen = NutritionGenerator()

        # Mock USDA API responses
        mock_search.return_value = [
            {
                'fdcId': 123,
                'description': 'Ground beef, 85% lean',
                'score': 0.9
            }
        ]
        mock_details.return_value = {'fdcId': 123}
        mock_extract.return_value = NutritionData(
            calories=215,
            protein=18.59,
            carbs=0,
            fat=15,
            confidence=1.0
        )

        ingredient = {
            "item": "ground beef",
            "quantity": 500,
            "unit": "g",
            "category": "meat"
        }

        result = gen._calculate_ingredient_nutrition(ingredient)

        assert result is not None
        assert result.item == "ground beef"
        assert result.nutrition is not None
        # 500g = 5x per 100g, so 215 * 5 = 1075 calories
        assert result.nutrition.calories == pytest.approx(1075, rel=0.01)
        assert result.matched_food == 'Ground beef, 85% lean'
        assert result.confidence == 0.9

    def test_calculate_ingredient_nutrition_negligible_quantity(self):
        """Test that ingredients < 5g are skipped."""
        gen = NutritionGenerator()

        ingredient = {
            "item": "salt",
            "quantity": 1,
            "unit": "g",
            "category": "seasoning"
        }

        result = gen._calculate_ingredient_nutrition(ingredient)

        assert result is None

    @patch.object(USDAFoodDataClient, 'search_foods')
    def test_calculate_ingredient_nutrition_no_match(self, mock_search):
        """Test ingredient with no USDA match."""
        gen = NutritionGenerator()

        mock_search.return_value = []  # No results

        ingredient = {
            "item": "exotic-spice-xyz",
            "quantity": 50,
            "unit": "g",
            "category": "seasoning"
        }

        result = gen._calculate_ingredient_nutrition(ingredient)

        assert result is not None
        assert result.nutrition is None
        assert result.confidence == 0

    @patch.object(NutritionGenerator, '_calculate_ingredient_nutrition')
    def test_generate_from_ingredients_success(self, mock_calc_ing):
        """Test full nutrition generation from ingredient list."""
        gen = NutritionGenerator()

        # Mock ingredient nutrition results
        mock_calc_ing.side_effect = [
            IngredientNutrition(
                item="ground beef",
                nutrition=NutritionData(calories=1075, protein=92.95, carbs=0, fat=75, confidence=0.9),
                matched_food="Beef, ground",
                confidence=0.9
            ),
            IngredientNutrition(
                item="pasta",
                nutrition=NutritionData(calories=1400, protein=48, carbs=280, fat=8, confidence=0.85),
                matched_food="Pasta, dry",
                confidence=0.85
            )
        ]

        ingredients = [
            {"item": "ground beef", "quantity": 500, "unit": "g", "category": "meat"},
            {"item": "pasta", "quantity": 400, "unit": "g", "category": "pantry"}
        ]

        result = gen.generate_from_ingredients(ingredients, servings=4)

        assert result is not None
        # Total calories: 1075 + 1400 = 2475, divided by 4 servings = 619 (rounded)
        assert result.calories == 619
        # Total protein: 92.95 + 48 = 140.95, divided by 4 = 35.2 (rounded to 1 decimal)
        assert result.protein == 35.2
        # Confidence: (0.9 + 0.85) / 2 = 0.875
        assert result.confidence == pytest.approx(0.875, rel=0.01)

    @patch.object(NutritionGenerator, '_calculate_ingredient_nutrition')
    def test_generate_from_ingredients_all_failed(self, mock_calc_ing):
        """Test generation when all ingredients fail to match."""
        gen = NutritionGenerator()

        # All ingredients return None
        mock_calc_ing.return_value = None

        ingredients = [
            {"item": "unknown1", "quantity": 50, "unit": "g", "category": "other"},
            {"item": "unknown2", "quantity": 50, "unit": "g", "category": "other"}
        ]

        result = gen.generate_from_ingredients(ingredients, servings=4)

        assert result is None

    @patch.object(NutritionGenerator, '_calculate_ingredient_nutrition')
    def test_generate_from_ingredients_partial_matches(self, mock_calc_ing):
        """Test generation with some matched and some unmatched ingredients."""
        gen = NutritionGenerator()

        # First ingredient succeeds, second fails (returns None)
        mock_calc_ing.side_effect = [
            IngredientNutrition(
                item="flour",
                nutrition=NutritionData(calories=400, protein=12, carbs=80, fat=2, confidence=0.9),
                matched_food="Flour, all-purpose",
                confidence=0.9
            ),
            None  # Second ingredient fails
        ]

        ingredients = [
            {"item": "flour", "quantity": 200, "unit": "g", "category": "pantry"},
            {"item": "unknown-spice", "quantity": 5, "unit": "g", "category": "seasoning"}
        ]

        result = gen.generate_from_ingredients(ingredients, servings=2)

        # Should still succeed with partial matches
        assert result is not None
        # Calories: 400 / 2 servings = 200
        assert result.calories == 200
        assert result.protein == 6.0


@pytest.mark.skip(reason="Integration tests require network access and USDA API may require authentication or have rate limits")
class TestIntegrationUSDAAPI:
    """Integration tests with actual USDA API (requires network).

    Note: These tests are skipped by default as they require:
    - Network connectivity
    - Working USDA API access (may require API key or have rate limits)
    - Tests may be unreliable due to API availability

    Remove the @pytest.mark.skip decorator to run these tests manually.
    """

    def test_real_usda_search(self):
        """Test real USDA API search."""
        client = USDAFoodDataClient()

        results = client.search_foods('ground beef')

        # Should get results
        assert len(results) > 0
        assert 'fdcId' in results[0]
        assert 'description' in results[0]
        assert 'beef' in results[0]['description'].lower()

    def test_real_usda_food_details(self):
        """Test real USDA API food details retrieval."""
        client = USDAFoodDataClient()

        # First search for a food
        results = client.search_foods('chicken breast')
        assert len(results) > 0

        fdc_id = results[0]['fdcId']

        # Get details
        details = client.get_food_details(fdc_id)

        assert details is not None
        assert 'foodNutrients' in details

        # Extract nutrition
        nutrition = client.extract_nutrition(details)

        assert nutrition is not None
        assert nutrition.calories > 0
        assert nutrition.protein > 0

    def test_real_full_generation_workflow(self):
        """Test full nutrition generation with real API."""
        gen = NutritionGenerator()

        ingredients = [
            {"item": "chicken breast", "quantity": 200, "unit": "g", "category": "meat"},
            {"item": "rice", "quantity": 100, "unit": "g", "category": "pantry"}
        ]

        nutrition = gen.generate_from_ingredients(ingredients, servings=2)

        assert nutrition is not None
        assert nutrition.calories > 0
        assert nutrition.protein > 0
        assert 0 < nutrition.confidence <= 1.0
