"""Tests for automatic tag inference."""

import pytest

from app.tag_inference import TagInferencer


class TestTagInferencer:
    """Test automatic tag inference from recipe content."""

    def test_dessert_detection_from_name(self):
        """Test dessert tag detection from recipe name."""
        inferencer = TagInferencer()

        # Test various dessert names
        dessert_names = [
            "Chocolate Cake",
            "Vanilla Cupcakes",
            "Apple Pie",
            "Chocolate Chip Cookies",
            "Strawberry Cheesecake"
        ]

        for name in dessert_names:
            tags = inferencer.infer_tags(name=name, ingredients=[])
            assert "dessert" in tags, f"Failed to detect dessert for: {name}"

    def test_dessert_detection_from_ingredients(self):
        """Test dessert tag detection from ingredients."""
        inferencer = TagInferencer()

        ingredients = [
            {"item": "chocolate chips", "quantity": 130, "unit": "g"},
            {"item": "sugar", "quantity": 150, "unit": "g"},
            {"item": "vanilla extract", "quantity": 1, "unit": "tsp"}
        ]

        tags = inferencer.infer_tags(
            name="Recipe",
            ingredients=ingredients
        )

        assert "dessert" in tags

    def test_breakfast_detection(self):
        """Test breakfast tag detection."""
        inferencer = TagInferencer()

        tags = inferencer.infer_tags(
            name="Blueberry Pancakes",
            ingredients=[]
        )

        assert "breakfast" in tags

    def test_soup_detection(self):
        """Test soup tag detection."""
        inferencer = TagInferencer()

        tags = inferencer.infer_tags(
            name="Chicken Noodle Soup",
            ingredients=[{"item": "chicken broth", "quantity": 4, "unit": "cups"}]
        )

        assert "soup" in tags

    def test_pasta_detection_from_name(self):
        """Test pasta tag detection from name."""
        inferencer = TagInferencer()

        tags = inferencer.infer_tags(
            name="Spaghetti Carbonara",
            ingredients=[]
        )

        assert "pasta" in tags

    def test_pasta_detection_from_ingredients(self):
        """Test pasta tag detection from ingredients."""
        inferencer = TagInferencer()

        ingredients = [
            {"item": "spaghetti", "quantity": 400, "unit": "g"},
            {"item": "parmesan cheese", "quantity": 50, "unit": "g"}
        ]

        tags = inferencer.infer_tags(
            name="Italian Dish",
            ingredients=ingredients
        )

        assert "pasta" in tags

    def test_vegetarian_detection_no_meat(self):
        """Test vegetarian tag when no meat ingredients."""
        inferencer = TagInferencer()

        ingredients = [
            {"item": "pasta", "quantity": 400, "unit": "g"},
            {"item": "tomato sauce", "quantity": 200, "unit": "g"},
            {"item": "mozzarella cheese", "quantity": 100, "unit": "g"}
        ]

        tags = inferencer.infer_tags(
            name="Pasta Dish",
            ingredients=ingredients
        )

        assert "vegetarian" in tags

    def test_not_vegetarian_with_meat(self):
        """Test vegetarian tag NOT added when meat present."""
        inferencer = TagInferencer()

        ingredients = [
            {"item": "chicken breast", "quantity": 500, "unit": "g"},
            {"item": "pasta", "quantity": 400, "unit": "g"}
        ]

        tags = inferencer.infer_tags(
            name="Chicken Pasta",
            ingredients=ingredients
        )

        assert "vegetarian" not in tags

    def test_vegan_detection(self):
        """Test vegan tag when no animal products."""
        inferencer = TagInferencer()

        ingredients = [
            {"item": "pasta", "quantity": 400, "unit": "g"},
            {"item": "tomato sauce", "quantity": 200, "unit": "g"},
            {"item": "olive oil", "quantity": 2, "unit": "tbsp"},
            {"item": "garlic", "quantity": 2, "unit": "clove"}
        ]

        tags = inferencer.infer_tags(
            name="Pasta Dish",
            ingredients=ingredients
        )

        assert "vegan" in tags

    def test_not_vegan_with_dairy(self):
        """Test vegan tag NOT added when dairy present."""
        inferencer = TagInferencer()

        ingredients = [
            {"item": "pasta", "quantity": 400, "unit": "g"},
            {"item": "cheese", "quantity": 100, "unit": "g"}
        ]

        tags = inferencer.infer_tags(
            name="Pasta",
            ingredients=ingredients
        )

        assert "vegan" not in tags
        assert "vegetarian" in tags  # But should be vegetarian

    def test_not_vegan_with_eggs(self):
        """Test vegan tag NOT added when eggs present."""
        inferencer = TagInferencer()

        ingredients = [
            {"item": "flour", "quantity": 200, "unit": "g"},
            {"item": "eggs", "quantity": 2, "unit": "whole"}
        ]

        tags = inferencer.infer_tags(
            name="Pasta",
            ingredients=ingredients
        )

        assert "vegan" not in tags

    def test_quick_tag_for_fast_recipes(self):
        """Test quick tag for recipes ≤30 minutes."""
        inferencer = TagInferencer()

        tags = inferencer.infer_tags(
            name="Quick Stir Fry",
            ingredients=[],
            prep_time_minutes=10,
            cook_time_minutes=15
        )

        assert "quick" in tags

    def test_no_quick_tag_for_slow_recipes(self):
        """Test quick tag NOT added for recipes >30 minutes."""
        inferencer = TagInferencer()

        tags = inferencer.infer_tags(
            name="Slow Roast",
            ingredients=[],
            prep_time_minutes=20,
            cook_time_minutes=120
        )

        assert "quick" not in tags

    def test_baking_detection_from_name(self):
        """Test baking tag detection from name."""
        inferencer = TagInferencer()

        tags = inferencer.infer_tags(
            name="Baked Salmon",
            ingredients=[]
        )

        assert "baking" in tags

    def test_baking_detection_from_instructions(self):
        """Test baking tag detection from instructions."""
        inferencer = TagInferencer()

        instructions = [
            "Preheat oven to 350°F",
            "Bake for 25 minutes until golden"
        ]

        tags = inferencer.infer_tags(
            name="Recipe",
            ingredients=[],
            instructions=instructions
        )

        assert "baking" in tags

    def test_baking_detection_from_ingredients(self):
        """Test baking tag detection from baking ingredients."""
        inferencer = TagInferencer()

        ingredients = [
            {"item": "baking powder", "quantity": 1, "unit": "tsp"},
            {"item": "flour", "quantity": 200, "unit": "g"}
        ]

        tags = inferencer.infer_tags(
            name="Recipe",
            ingredients=ingredients
        )

        assert "baking" in tags

    def test_slow_cooker_detection(self):
        """Test slow-cooker tag detection."""
        inferencer = TagInferencer()

        tags = inferencer.infer_tags(
            name="Slow Cooker Beef Stew",
            ingredients=[]
        )

        assert "slow-cooker" in tags

    def test_instant_pot_detection(self):
        """Test instant-pot tag detection."""
        inferencer = TagInferencer()

        instructions = ["Add to Instant Pot", "Pressure cook for 20 minutes"]

        tags = inferencer.infer_tags(
            name="Recipe",
            ingredients=[],
            instructions=instructions
        )

        assert "instant-pot" in tags

    def test_grilling_detection(self):
        """Test grilling tag detection."""
        inferencer = TagInferencer()

        tags = inferencer.infer_tags(
            name="Grilled Chicken",
            ingredients=[]
        )

        assert "grilling" in tags

    def test_no_duplicate_tags(self):
        """Test that existing tags are not duplicated."""
        inferencer = TagInferencer()

        existing_tags = ["dessert", "imported"]

        enhanced = inferencer.enhance_tags(
            name="Chocolate Cake",
            ingredients=[],
            existing_tags=existing_tags
        )

        # Should have dessert only once
        assert enhanced.count("dessert") == 1
        assert "imported" in enhanced

    def test_enhance_tags_combines_existing_and_inferred(self):
        """Test enhance_tags combines existing and new tags."""
        inferencer = TagInferencer()

        existing_tags = ["imported", "nutrition-generated"]

        ingredients = [
            {"item": "pasta", "quantity": 400, "unit": "g"},
            {"item": "tomato sauce", "quantity": 200, "unit": "g"}
        ]

        enhanced = inferencer.enhance_tags(
            name="Pasta Dish",
            ingredients=ingredients,
            existing_tags=existing_tags
        )

        assert "imported" in enhanced
        assert "nutrition-generated" in enhanced
        assert "pasta" in enhanced
        assert "vegetarian" in enhanced
        assert "vegan" in enhanced

    def test_multiple_tags_detected(self):
        """Test multiple tags can be detected from single recipe."""
        inferencer = TagInferencer()

        ingredients = [
            {"item": "flour", "quantity": 200, "unit": "g"},
            {"item": "sugar", "quantity": 150, "unit": "g"},
            {"item": "baking powder", "quantity": 1, "unit": "tsp"},
            {"item": "eggs", "quantity": 2, "unit": "whole"}
        ]

        instructions = ["Preheat oven to 350°F", "Bake for 25 minutes"]

        tags = inferencer.infer_tags(
            name="Vanilla Cake",
            ingredients=ingredients,
            instructions=instructions,
            prep_time_minutes=10,
            cook_time_minutes=15
        )

        assert "dessert" in tags
        assert "baking" in tags
        assert "quick" in tags
        assert "vegetarian" in tags  # Has eggs but no meat

    def test_salad_detection(self):
        """Test salad tag detection."""
        inferencer = TagInferencer()

        tags = inferencer.infer_tags(
            name="Caesar Salad",
            ingredients=[{"item": "lettuce", "quantity": 200, "unit": "g"}]
        )

        assert "salad" in tags

    def test_empty_inputs_no_crash(self):
        """Test that empty inputs don't cause crashes."""
        inferencer = TagInferencer()

        tags = inferencer.infer_tags(
            name="",
            ingredients=[]
        )

        assert isinstance(tags, list)
        # Should at least detect vegan/vegetarian for no ingredients
        assert "vegan" in tags or "vegetarian" in tags

    def test_case_insensitive_detection(self):
        """Test that tag detection is case-insensitive."""
        inferencer = TagInferencer()

        tags = inferencer.infer_tags(
            name="CHOCOLATE CAKE",
            ingredients=[{"item": "SUGAR", "quantity": 100, "unit": "g"}]
        )

        assert "dessert" in tags
