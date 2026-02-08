import pytest
from app.shopping_list import ShoppingList, ShoppingListItem, generate_shopping_list
from app.planner import PlannedMeal, WeeklyPlan
from app.recipes import Recipe


@pytest.fixture
def sample_planned_meals():
    recipe1 = Recipe(
        id="recipe-1",
        name="Recipe 1",
        servings=4,
        prep_time_minutes=10,
        cook_time_minutes=20,
        calories_per_serving=400,
        protein_per_serving=20,
        carbs_per_serving=50,
        fat_per_serving=10,
        tags=[],
        ingredients=[
            {"item": "onion", "quantity": 1, "unit": "whole", "category": "produce"},
            {"item": "garlic", "quantity": 3, "unit": "cloves", "category": "produce"},
            {"item": "pasta", "quantity": 400, "unit": "g", "category": "pantry"}
        ]
    )

    recipe2 = Recipe(
        id="recipe-2",
        name="Recipe 2",
        servings=4,
        prep_time_minutes=15,
        cook_time_minutes=25,
        calories_per_serving=350,
        protein_per_serving=25,
        carbs_per_serving=40,
        fat_per_serving=12,
        tags=[],
        ingredients=[
            {"item": "onion", "quantity": 2, "unit": "whole", "category": "produce"},
            {"item": "rice", "quantity": 300, "unit": "g", "category": "pantry"},
            {"item": "chicken", "quantity": 500, "unit": "g", "category": "meat"}
        ]
    )

    recipe3 = Recipe(
        id="recipe-3",
        name="Recipe 3",
        servings=4,
        prep_time_minutes=5,
        cook_time_minutes=15,
        calories_per_serving=300,
        protein_per_serving=15,
        carbs_per_serving=35,
        fat_per_serving=8,
        tags=[],
        ingredients=[
            {"item": "garlic", "quantity": 2, "unit": "cloves", "category": "produce"},
            {"item": "tomatoes", "quantity": 4, "unit": "whole", "category": "produce"}
        ]
    )

    return [
        PlannedMeal(day="Monday", meal_type="dinner", recipe=recipe1, household_portions=2.75),
        PlannedMeal(day="Tuesday", meal_type="dinner", recipe=recipe2, household_portions=2.75),
        PlannedMeal(day="Wednesday", meal_type="dinner", recipe=recipe3, household_portions=2.75),
    ]


@pytest.fixture
def weekly_plan(sample_planned_meals):
    # Add 4 more meals to make it 7
    extra_recipe = Recipe(
        id="extra",
        name="Extra",
        servings=4,
        prep_time_minutes=10,
        cook_time_minutes=20,
        calories_per_serving=400,
        protein_per_serving=20,
        carbs_per_serving=50,
        fat_per_serving=10,
        tags=[],
        ingredients=[{"item": "bread", "quantity": 200, "unit": "g", "category": "bakery"}]
    )

    all_meals = sample_planned_meals + [
        PlannedMeal(day="Thursday", meal_type="dinner", recipe=extra_recipe, household_portions=2.75),
        PlannedMeal(day="Friday", meal_type="dinner", recipe=extra_recipe, household_portions=2.75),
        PlannedMeal(day="Saturday", meal_type="dinner", recipe=extra_recipe, household_portions=2.75),
        PlannedMeal(day="Sunday", meal_type="dinner", recipe=extra_recipe, household_portions=2.75),
    ]

    return WeeklyPlan(meals=all_meals)


class TestShoppingListItem:
    def test_shopping_list_item_creation(self):
        item = ShoppingListItem(
            item="onion",
            quantity=3.0,
            unit="whole",
            category="produce"
        )

        assert item.item == "onion"
        assert item.quantity == 3.0
        assert item.unit == "whole"
        assert item.category == "produce"


class TestGenerateShoppingList:
    def test_generate_shopping_list_returns_shopping_list(self, weekly_plan):
        shopping_list = generate_shopping_list(weekly_plan)
        assert isinstance(shopping_list, ShoppingList)

    def test_generate_shopping_list_combines_duplicate_items(self, sample_planned_meals):
        # recipe1 has 1 onion, recipe2 has 2 onions
        # With 2.75 portions (servings=4): recipe1 = 0.6875 onions, recipe2 = 1.375 onions
        # Total should be ~2.0625 onions

        plan = WeeklyPlan(meals=sample_planned_meals[:2])
        shopping_list = generate_shopping_list(plan)

        onion_items = [item for item in shopping_list.items if item.item == "onion"]
        assert len(onion_items) == 1
        assert abs(onion_items[0].quantity - 2.0625) < 0.01

    def test_generate_shopping_list_combines_garlic_with_same_unit(self, sample_planned_meals):
        # recipe1 has 3 cloves garlic, recipe3 has 2 cloves garlic
        # With 2.75 portions (servings=4): recipe1 = 2.0625, recipe3 = 1.375
        # Total should be ~3.4375 cloves

        plan = WeeklyPlan(meals=[sample_planned_meals[0], sample_planned_meals[2]])
        shopping_list = generate_shopping_list(plan)

        garlic_items = [item for item in shopping_list.items if item.item == "garlic"]
        assert len(garlic_items) == 1
        assert abs(garlic_items[0].quantity - 3.4375) < 0.01

    def test_generate_shopping_list_keeps_items_with_different_units_separate(self):
        # Create recipes with same item but different units
        recipe1 = Recipe(
            id="r1",
            name="R1",
            servings=4,
            prep_time_minutes=10,
            cook_time_minutes=20,
            calories_per_serving=400,
            protein_per_serving=20,
            carbs_per_serving=50,
            fat_per_serving=10,
            tags=[],
            ingredients=[
                {"item": "milk", "quantity": 200, "unit": "ml", "category": "dairy"}
            ]
        )

        recipe2 = Recipe(
            id="r2",
            name="R2",
            servings=4,
            prep_time_minutes=10,
            cook_time_minutes=20,
            calories_per_serving=400,
            protein_per_serving=20,
            carbs_per_serving=50,
            fat_per_serving=10,
            tags=[],
            ingredients=[
                {"item": "milk", "quantity": 1, "unit": "cup", "category": "dairy"}
            ]
        )

        meals = [
            PlannedMeal(day="Monday", meal_type="dinner", recipe=recipe1, household_portions=4.0),
            PlannedMeal(day="Tuesday", meal_type="dinner", recipe=recipe2, household_portions=4.0),
        ]

        plan = WeeklyPlan(meals=meals)
        shopping_list = generate_shopping_list(plan)

        milk_items = [item for item in shopping_list.items if item.item == "milk"]
        assert len(milk_items) == 2  # Should be separate because different units

    def test_generate_shopping_list_groups_by_category(self, weekly_plan):
        shopping_list = generate_shopping_list(weekly_plan)

        categories = [item.category for item in shopping_list.items]
        assert len(categories) > 0

        # Check that items are sorted by category
        for i in range(len(categories) - 1):
            assert categories[i] <= categories[i + 1]


class TestShoppingList:
    def test_shopping_list_has_items(self, weekly_plan):
        shopping_list = generate_shopping_list(weekly_plan)
        assert len(shopping_list.items) > 0

    def test_shopping_list_items_by_category(self, weekly_plan):
        shopping_list = generate_shopping_list(weekly_plan)
        by_category = shopping_list.items_by_category()

        assert isinstance(by_category, dict)

        # Check that all items are in some category
        all_items_count = sum(len(items) for items in by_category.values())
        assert all_items_count == len(shopping_list.items)

    def test_shopping_list_items_by_category_groups_correctly(self):
        items = [
            ShoppingListItem(item="apple", quantity=5, unit="whole", category="produce"),
            ShoppingListItem(item="banana", quantity=3, unit="whole", category="produce"),
            ShoppingListItem(item="milk", quantity=1, unit="l", category="dairy"),
            ShoppingListItem(item="cheese", quantity=200, unit="g", category="dairy"),
            ShoppingListItem(item="pasta", quantity=400, unit="g", category="pantry"),
        ]

        shopping_list = ShoppingList(items=items)
        by_category = shopping_list.items_by_category()

        assert len(by_category["produce"]) == 2
        assert len(by_category["dairy"]) == 2
        assert len(by_category["pantry"]) == 1
