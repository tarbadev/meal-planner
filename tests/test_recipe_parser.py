from unittest.mock import Mock, patch

import pytest

from app.recipe_parser import ParsedRecipe, RecipeParseError, RecipeParser, generate_recipe_id
from tests.conftest import create_test_recipe


class TestGenerateRecipeId:
    """Test recipe ID generation."""

    def test_basic_slugification(self):
        """Test basic conversion to slug."""
        result = generate_recipe_id("Chicken Stir Fry", set())
        assert result == "chicken-stir-fry"

    def test_special_characters_removed(self):
        """Test special characters are removed."""
        result = generate_recipe_id("Mom's Best Pizza!", set())
        assert result == "moms-best-pizza"

    def test_multiple_spaces_collapsed(self):
        """Test multiple spaces become single hyphen."""
        result = generate_recipe_id("Triple   Space   Recipe", set())
        assert result == "triple-space-recipe"

    def test_uniqueness_with_conflict(self):
        """Test unique ID generation when conflict exists."""
        existing = {"chicken-stir-fry"}
        result = generate_recipe_id("Chicken Stir Fry", existing)
        assert result == "chicken-stir-fry-2"

    def test_uniqueness_multiple_conflicts(self):
        """Test unique ID generation with multiple conflicts."""
        existing = {"tacos", "tacos-2", "tacos-3"}
        result = generate_recipe_id("Tacos", existing)
        assert result == "tacos-4"


class TestParsedRecipeToDict:
    """Test ParsedRecipe.to_recipe_dict() method."""

    def test_successful_conversion_with_all_fields(self):
        """Test conversion with all fields present."""
        parsed = ParsedRecipe(
            name="Test Recipe",
            servings=4,
            prep_time_minutes=15,
            cook_time_minutes=30,
            calories_per_serving=350,
            protein_per_serving=25,
            carbs_per_serving=40,
            fat_per_serving=12,
            tags=["italian", "quick"],
            ingredients=[{"item": "pasta", "quantity": 400, "unit": "g", "category": "pantry"}],
            instructions=["Boil water", "Cook pasta"],
            source_url="https://example.com/recipe"
        )

        result = parsed.to_recipe_dict("test-recipe")

        assert result["id"] == "test-recipe"
        assert result["name"] == "Test Recipe"
        assert result["servings"] == 4
        assert result["prep_time_minutes"] == 15
        assert result["cook_time_minutes"] == 30
        assert result["nutrition_per_serving"]["calories"] == 350
        assert result["nutrition_per_serving"]["protein"] == 25
        assert result["nutrition_per_serving"]["carbs"] == 40
        assert result["nutrition_per_serving"]["fat"] == 12
        assert result["tags"] == ["italian", "quick"]
        assert len(result["ingredients"]) == 1
        assert len(result["instructions"]) == 2

    def test_defaults_for_missing_optional_fields(self):
        """Test default values are applied for missing optional fields."""
        parsed = ParsedRecipe(
            name="Minimal Recipe",
            ingredients=[{"item": "test", "quantity": 1, "unit": "piece", "category": "other"}],
            instructions=["Do something"]
        )

        result = parsed.to_recipe_dict("minimal")

        assert result["servings"] == 4  # Default
        assert result["prep_time_minutes"] == 0
        assert result["cook_time_minutes"] == 0
        assert result["nutrition_per_serving"]["calories"] == 0
        assert result["nutrition_per_serving"]["protein"] == 0.0
        assert result["nutrition_per_serving"]["carbs"] == 0.0
        assert result["nutrition_per_serving"]["fat"] == 0.0
        assert result["tags"] == ["imported"]  # Default tag

    def test_missing_ingredients_raises_error(self):
        """Test that missing ingredients raises RecipeParseError."""
        parsed = ParsedRecipe(
            name="No Ingredients",
            instructions=["Step 1", "Step 2"]
        )

        with pytest.raises(RecipeParseError) as exc_info:
            parsed.to_recipe_dict("test-id")

        assert "Could not extract ingredients" in str(exc_info.value)
        assert "unusual format" in str(exc_info.value)

    def test_empty_ingredients_list_raises_error(self):
        """Test that empty ingredients list raises RecipeParseError."""
        parsed = ParsedRecipe(
            name="Empty Ingredients",
            ingredients=[],
            instructions=["Step 1"]
        )

        with pytest.raises(RecipeParseError) as exc_info:
            parsed.to_recipe_dict("test-id")

        assert "Could not extract ingredients" in str(exc_info.value)

    def test_missing_instructions_adds_default(self):
        """Test that missing instructions adds a default instruction."""
        parsed = ParsedRecipe(
            name="No Instructions",
            ingredients=[{"item": "test", "quantity": 1, "unit": "piece", "category": "other"}]
        )

        result = parsed.to_recipe_dict("test-id")

        assert "instructions" in result
        assert len(result["instructions"]) == 1
        assert "Combine all ingredients" in result["instructions"][0]

    def test_empty_instructions_list_adds_default(self):
        """Test that empty instructions list adds a default instruction."""
        parsed = ParsedRecipe(
            name="Empty Instructions",
            ingredients=[{"item": "test", "quantity": 1, "unit": "piece", "category": "other"}],
            instructions=[]
        )

        result = parsed.to_recipe_dict("test-id")

        assert "instructions" in result
        assert len(result["instructions"]) == 1
        assert "Combine all ingredients" in result["instructions"][0]


class TestRecipeParserHelpers:
    """Test helper methods in RecipeParser."""

    def test_extract_servings_from_int(self):
        """Test servings extraction from integer."""
        parser = RecipeParser()
        result = parser._extract_servings(4)
        assert result == 4

    def test_extract_servings_from_string(self):
        """Test servings extraction from string."""
        parser = RecipeParser()
        assert parser._extract_servings("4 servings") == 4
        assert parser._extract_servings("Serves 6") == 6
        assert parser._extract_servings("Makes 12") == 12

    def test_extract_servings_returns_none_for_no_number(self):
        """Test servings extraction returns None when no number found."""
        parser = RecipeParser()
        result = parser._extract_servings("unknown")
        assert result is None

    def test_extract_calories(self):
        """Test calories extraction from nutrition object."""
        parser = RecipeParser()
        result = parser._extract_calories({"calories": "350 calories"})
        assert result == 350

    def test_extract_nutrient(self):
        """Test nutrient extraction from nutrition object."""
        parser = RecipeParser()
        assert parser._extract_nutrient({"proteinContent": "25 g"}, "proteinContent") == 25.0
        assert parser._extract_nutrient({"proteinContent": "25.5 g"}, "proteinContent") == 25.5
        assert parser._extract_nutrient({"carbohydrateContent": "40g"}, "carbohydrateContent") == 40.0
        assert parser._extract_nutrient({"carbohydrateContent": "40.8g"}, "carbohydrateContent") == 40.8
        assert parser._extract_nutrient({"fatContent": "12"}, "fatContent") == 12.0
        assert parser._extract_nutrient({"fatContent": "12.3"}, "fatContent") == 12.3

    def test_parse_fraction_simple(self):
        """Test parsing simple fractions."""
        parser = RecipeParser()
        assert parser._parse_fraction("1/2") == 0.5
        assert parser._parse_fraction("1/4") == 0.25
        assert parser._parse_fraction("3/4") == 0.75

    def test_parse_fraction_mixed_numbers(self):
        """Test parsing mixed numbers."""
        parser = RecipeParser()
        assert parser._parse_fraction("1 1/2") == 1.5
        assert parser._parse_fraction("2 3/4") == 2.75

    def test_parse_fraction_regular_numbers(self):
        """Test parsing regular numbers."""
        parser = RecipeParser()
        assert parser._parse_fraction("2") == 2.0
        assert parser._parse_fraction("0.5") == 0.5

    def test_parse_fraction_invalid(self):
        """Test parsing invalid fractions returns default."""
        parser = RecipeParser()
        assert parser._parse_fraction("") == 1.0
        assert parser._parse_fraction("abc") == 1.0

    def test_extract_grams(self):
        """Test extracting grams from various formats."""
        parser = RecipeParser()
        assert parser._extract_grams(25) == 25.0
        assert parser._extract_grams(25.5) == 25.5
        assert parser._extract_grams("30g") == 30.0
        assert parser._extract_grams("30.5g") == 30.5
        assert parser._extract_grams("40 grams") == 40.0
        assert parser._extract_grams("invalid") == 0.0

    def test_parse_ingredient_with_quantity_and_unit(self):
        """Test parsing ingredient with quantity and unit."""
        parser = RecipeParser()
        result = parser._parse_ingredient("2 cups flour")

        assert result["item"] == "flour"
        assert result["quantity"] == 2.0
        assert result["unit"] == "cups"
        assert result["category"] == "grains"  # Automatically categorized

    def test_parse_ingredient_with_fraction(self):
        """Test parsing ingredient with fraction."""
        parser = RecipeParser()
        result = parser._parse_ingredient("1/2 cup sugar")

        assert result["item"] == "sugar"  # Unit is extracted separately
        assert result["quantity"] == 0.5
        assert result["unit"] == "cup"

    def test_parse_ingredient_fallback_no_quantity(self):
        """Test parsing ingredient without quantity extracts preparation notes."""
        parser = RecipeParser()
        result = parser._parse_ingredient("Salt and pepper to taste")

        assert result["item"] == "Salt and pepper"
        assert result["notes"] == "to taste"
        assert result["quantity"] == 1
        assert result["unit"] == "serving"


class TestSchemaOrgParsing:
    """Test parsing schema.org JSON-LD markup."""

    def test_parse_schema_org_basic(self):
        """Test basic schema.org parsing."""
        html = """
        <html>
        <script type="application/ld+json">
        {
            "@type": "Recipe",
            "name": "Chocolate Cake",
            "recipeYield": "8 servings",
            "prepTime": "PT20M",
            "cookTime": "PT30M",
            "recipeIngredient": [
                "2 cups flour",
                "1 cup sugar",
                "3 eggs"
            ],
            "recipeInstructions": [
                {"@type": "HowToStep", "text": "Mix dry ingredients"},
                {"@type": "HowToStep", "text": "Add wet ingredients"},
                {"@type": "HowToStep", "text": "Bake at 350F"}
            ],
            "nutrition": {
                "calories": "320 calories",
                "proteinContent": "6 g",
                "carbohydrateContent": "45 g",
                "fatContent": "12 g"
            }
        }
        </script>
        </html>
        """

        parser = RecipeParser()
        result = parser._parse_schema_org(html)

        assert result is not None
        assert result.name == "Chocolate Cake"
        assert result.servings == 8
        assert result.prep_time_minutes == 20
        assert result.cook_time_minutes == 30
        assert result.calories_per_serving == 320
        assert result.protein_per_serving == 6
        assert result.carbs_per_serving == 45
        assert result.fat_per_serving == 12
        assert len(result.ingredients) == 3
        assert len(result.instructions) == 3
        assert result.instructions[0] == "Mix dry ingredients"

    def test_parse_schema_org_with_graph(self):
        """Test parsing schema.org with @graph structure."""
        html = """
        <html>
        <script type="application/ld+json">
        {
            "@graph": [
                {"@type": "WebSite", "name": "Example"},
                {
                    "@type": "Recipe",
                    "name": "Simple Pasta",
                    "recipeIngredient": ["pasta", "sauce"],
                    "recipeInstructions": "Cook pasta and add sauce"
                }
            ]
        }
        </script>
        </html>
        """

        parser = RecipeParser()
        result = parser._parse_schema_org(html)

        assert result is not None
        assert result.name == "Simple Pasta"
        assert len(result.ingredients) == 2
        assert len(result.instructions) == 1

    def test_parse_schema_org_instructions_as_string(self):
        """Test parsing when instructions are a single string."""
        html = """
        <html>
        <script type="application/ld+json">
        {
            "@type": "Recipe",
            "name": "Quick Recipe",
            "recipeIngredient": ["ingredient 1"],
            "recipeInstructions": "Step 1: Do this\\nStep 2: Do that\\nStep 3: Finish"
        }
        </script>
        </html>
        """

        parser = RecipeParser()
        result = parser._parse_schema_org(html)

        assert result is not None
        assert len(result.instructions) == 3

    def test_parse_schema_org_no_recipe(self):
        """Test parsing returns None when no recipe found."""
        html = """
        <html>
        <script type="application/ld+json">
        {"@type": "WebSite", "name": "Example"}
        </script>
        </html>
        """

        parser = RecipeParser()
        result = parser._parse_schema_org(html)

        assert result is None


class TestWPRMParsing:
    """Test parsing WP Recipe Maker plugin data."""

    def test_parse_wprm_basic(self):
        """Test basic WPRM parsing."""
        html = """
        <html>
        <script>
        window.wprm_recipes = {
            "recipe-123": {
                "name": "WPRM Recipe",
                "servings": 4,
                "prep_time": 15,
                "cook_time": 30,
                "ingredients": [{
                    "ingredients": [
                        {"name": "flour", "amount": "2", "unit": "cups"},
                        {"name": "eggs", "amount": "3", "unit": "whole"}
                    ]
                }],
                "instructions": [{
                    "instructions": [
                        {"text": "Mix ingredients"},
                        {"text": "Bake for 30 minutes"}
                    ]
                }],
                "nutrition": {
                    "calories": 350,
                    "protein": "12g",
                    "carbohydrates": "45g",
                    "fat": "10g"
                }
            }
        };
        </script>
        </html>
        """

        parser = RecipeParser()
        result = parser._parse_wprm(html)

        assert result is not None
        assert result.name == "WPRM Recipe"
        assert result.servings == 4
        assert result.prep_time_minutes == 15
        assert result.cook_time_minutes == 30
        assert result.calories_per_serving == 350
        assert result.protein_per_serving == 12
        assert result.carbs_per_serving == 45
        assert result.fat_per_serving == 10
        assert len(result.ingredients) == 2
        assert result.ingredients[0]["item"] == "flour"
        assert result.ingredients[0]["quantity"] == 2.0
        assert len(result.instructions) == 2

    def test_parse_wprm_with_fractions(self):
        """Test WPRM parsing with fraction amounts."""
        html = """
        <html>
        <script>
        window.wprm_recipes = {
            "recipe-456": {
                "name": "Fraction Test",
                "servings": 2,
                "prep_time": 10,
                "cook_time": 20,
                "ingredients": [{
                    "ingredients": [
                        {"name": "sugar", "amount": "1/2", "unit": "cup"},
                        {"name": "butter", "amount": "1 1/4", "unit": "cups"}
                    ]
                }],
                "instructions": [{
                    "instructions": [{"text": "Mix everything"}]
                }],
                "nutrition": {}
            }
        };
        </script>
        </html>
        """

        parser = RecipeParser()
        result = parser._parse_wprm(html)

        assert result is not None
        assert result.ingredients[0]["quantity"] == 0.5
        assert result.ingredients[1]["quantity"] == 1.25

    def test_parse_wprm_no_data(self):
        """Test WPRM parsing returns None when no data found."""
        html = "<html><body>No WPRM data here</body></html>"

        parser = RecipeParser()
        result = parser._parse_wprm(html)

        assert result is None


class TestHTMLPatternParsing:
    """Test HTML pattern fallback parsing."""

    def test_parse_html_patterns_basic(self):
        """Test basic HTML pattern parsing."""
        html = """
        <html>
        <body>
            <h1>My Recipe</h1>
            <p>Prep Time: 15 min</p>
            <p>Cook Time: 30 min</p>
            <p>Serving Size: 4</p>
            <p>Calories: 350</p>
            <p>Protein: 20</p>
            <p>Carbs: 45</p>
            <p>Fat: 12</p>
            <h2>Ingredients</h2>
            <ul>
                <li>2 cups flour</li>
                <li>1 cup sugar</li>
                <li>3 eggs</li>
            </ul>
            <h2>Instructions</h2>
            <ol>
                <li>Mix dry ingredients together</li>
                <li>Add wet ingredients and stir</li>
                <li>Bake at 350F for 30 minutes</li>
            </ol>
        </body>
        </html>
        """

        parser = RecipeParser()
        result = parser._parse_html_patterns(html)

        assert result is not None
        assert result.name == "My Recipe"
        assert result.prep_time_minutes == 15
        assert result.cook_time_minutes == 30
        assert result.servings == 4
        assert result.calories_per_serving == 350
        assert result.protein_per_serving == 20
        assert result.carbs_per_serving == 45
        assert result.fat_per_serving == 12
        assert len(result.ingredients) == 3
        assert len(result.instructions) == 3

    def test_parse_html_patterns_no_name(self):
        """Test HTML parsing returns None when no name found."""
        html = "<html><body><p>Some content</p></body></html>"

        parser = RecipeParser()
        result = parser._parse_html_patterns(html)

        assert result is None


class TestParseFromUrl:
    """Test the main parse_from_url method."""

    @patch('app.recipe_parser.requests.get')
    def test_parse_from_url_success_with_schema_org(self, mock_get):
        """Test successful parsing with schema.org data."""
        mock_response = Mock()
        mock_response.text = """
        <html>
        <script type="application/ld+json">
        {
            "@type": "Recipe",
            "name": "Test Recipe",
            "recipeIngredient": ["ingredient 1", "ingredient 2"],
            "recipeInstructions": "Do something"
        }
        </script>
        </html>
        """
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        parser = RecipeParser()
        result = parser.parse_from_url("https://example.com/recipe")

        assert result is not None
        assert result.name == "Test Recipe"
        assert result.source_url == "https://example.com/recipe"
        mock_get.assert_called_once()

    @patch('app.recipe_parser.requests.get')
    def test_parse_from_url_network_error(self, mock_get):
        """Test network error handling."""
        mock_get.side_effect = Exception("Network error")

        parser = RecipeParser()
        with pytest.raises(RecipeParseError) as exc_info:
            parser.parse_from_url("https://example.com/recipe")

        assert "Failed to fetch URL" in str(exc_info.value)

    @patch('app.recipe_parser.requests.get')
    def test_parse_from_url_no_recipe_data(self, mock_get):
        """Test error when no recipe data can be extracted."""
        mock_response = Mock()
        mock_response.text = "<html><body>No recipe here</body></html>"
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        parser = RecipeParser()
        with pytest.raises(RecipeParseError) as exc_info:
            parser.parse_from_url("https://example.com/recipe")

        assert "Could not extract recipe data" in str(exc_info.value)
