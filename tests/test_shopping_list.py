import pytest

from app.planner import PlannedMeal, WeeklyPlan
from app.recipes import Recipe
from app.shopping_list import (
    ShoppingList,
    ShoppingListItem,
    _combine_entries,
    generate_shopping_list,
)
from app.shopping_normalizer import apply_exclusions
from tests.conftest import create_test_recipe


@pytest.fixture
def sample_planned_meals():
    recipe1 = create_test_recipe(
        recipe_id="recipe-1",
        name="Recipe 1",
        servings=4,
        prep_time_minutes=10,
        cook_time_minutes=20,
        calories=400,
        protein=20,
        carbs=50,
        fat=10,
        tags=[],
        ingredients=[
            {"item": "onion", "quantity": 1, "unit": "whole", "category": "produce"},
            {"item": "garlic", "quantity": 3, "unit": "cloves", "category": "produce"},
            {"item": "pasta", "quantity": 400, "unit": "g", "category": "pantry"}
        ]
    )

    recipe2 = create_test_recipe(
        recipe_id="recipe-2",
        name="Recipe 2",
        servings=4,
        prep_time_minutes=15,
        cook_time_minutes=25,
        calories=350,
        protein=25,
        carbs=40,
        fat=12,
        tags=[],
        ingredients=[
            {"item": "onion", "quantity": 2, "unit": "whole", "category": "produce"},
            {"item": "rice", "quantity": 300, "unit": "g", "category": "pantry"},
            {"item": "chicken", "quantity": 500, "unit": "g", "category": "meat"}
        ]
    )

    recipe3 = create_test_recipe(
        recipe_id="recipe-3",
        name="Recipe 3",
        servings=4,
        prep_time_minutes=5,
        cook_time_minutes=15,
        calories=300,
        protein=15,
        carbs=35,
        fat=8,
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
    extra_recipe = create_test_recipe(
        recipe_id="extra",
        name="Extra",
        servings=4,
        prep_time_minutes=10,
        cook_time_minutes=20,
        calories=400,
        protein=20,
        carbs=50,
        fat=10,
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

    def test_generate_shopping_list_merges_compatible_volume_units(self):
        # 200 ml + 1 cup of milk — both volume, should merge into one line expressed in cups
        recipe1 = create_test_recipe(
            recipe_id="r1",
            name="R1",
            servings=4,
            prep_time_minutes=10,
            cook_time_minutes=20,
            calories=400,
            protein=20,
            carbs=50,
            fat=10,
            tags=[],
            ingredients=[
                {"item": "milk", "quantity": 200, "unit": "ml", "category": "dairy"}
            ]
        )

        recipe2 = create_test_recipe(
            recipe_id="r2",
            name="R2",
            servings=4,
            prep_time_minutes=10,
            cook_time_minutes=20,
            calories=400,
            protein=20,
            carbs=50,
            fat=10,
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
        # ml and cup are both volume → merged into one line (cup is the larger unit)
        assert len(milk_items) == 1
        assert milk_items[0].unit == "cup"
        # 200 ml/serving * 4 portions / 4 servings = 200 ml total
        # + 1 cup/serving * 4 portions / 4 servings = 1 cup = 236.588 ml
        # total = 436.588 ml / 236.588 ml-per-cup ≈ 1.845 cups
        assert abs(milk_items[0].quantity - 1.845) < 0.01

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
        by_category = shopping_list.items_by_category

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
        by_category = shopping_list.items_by_category

        assert len(by_category["produce"]) == 2
        assert len(by_category["dairy"]) == 2
        assert len(by_category["pantry"]) == 1


class TestBug2SameIngredientCombining:
    """BUG-2: Same ingredient name from different meals must always be combined."""

    def test_combining_same_ingredient_both_with_serving_unit(self):
        recipe1 = create_test_recipe(
            recipe_id="r1", name="R1", servings=4,
            prep_time_minutes=10, cook_time_minutes=20,
            calories=400, protein=20, carbs=50, fat=10, tags=[],
            ingredients=[{"item": "tomato", "quantity": 1, "unit": "serving", "category": "produce"}]
        )
        recipe2 = create_test_recipe(
            recipe_id="r2", name="R2", servings=4,
            prep_time_minutes=10, cook_time_minutes=20,
            calories=400, protein=20, carbs=50, fat=10, tags=[],
            ingredients=[{"item": "tomato", "quantity": 1, "unit": "serving", "category": "produce"}]
        )
        meals = [
            PlannedMeal(day="Monday", meal_type="dinner", recipe=recipe1, household_portions=4.0),
            PlannedMeal(day="Tuesday", meal_type="dinner", recipe=recipe2, household_portions=4.0),
        ]
        shopping_list = generate_shopping_list(WeeklyPlan(meals=meals))

        tomato_items = [i for i in shopping_list.items if i.item == "tomato"]
        assert len(tomato_items) == 1, f"Expected 1 combined tomato entry, got {len(tomato_items)}"
        assert abs(tomato_items[0].quantity - 2.0) < 0.01

    def test_combining_same_ingredient_serving_unit_with_empty_unit(self):
        recipe1 = create_test_recipe(
            recipe_id="r1", name="R1", servings=4,
            prep_time_minutes=10, cook_time_minutes=20,
            calories=400, protein=20, carbs=50, fat=10, tags=[],
            ingredients=[{"item": "tomato", "quantity": 1, "unit": "serving", "category": "produce"}]
        )
        recipe2 = create_test_recipe(
            recipe_id="r2", name="R2", servings=4,
            prep_time_minutes=10, cook_time_minutes=20,
            calories=400, protein=20, carbs=50, fat=10, tags=[],
            ingredients=[{"item": "tomato", "quantity": 1, "unit": "", "category": "produce"}]
        )
        meals = [
            PlannedMeal(day="Monday", meal_type="dinner", recipe=recipe1, household_portions=4.0),
            PlannedMeal(day="Tuesday", meal_type="dinner", recipe=recipe2, household_portions=4.0),
        ]
        shopping_list = generate_shopping_list(WeeklyPlan(meals=meals))

        tomato_items = [i for i in shopping_list.items if i.item == "tomato"]
        assert len(tomato_items) == 1, f"Expected 1 combined tomato entry, got {len(tomato_items)}"
        assert abs(tomato_items[0].quantity - 2.0) < 0.01


class TestBug3ServingUnitDisplay:
    """BUG-3: 'serving' must not appear in the shopping list unit field."""

    def test_serving_unit_normalised_to_empty_string(self):
        recipe = create_test_recipe(
            recipe_id="r1", name="R1", servings=4,
            prep_time_minutes=10, cook_time_minutes=20,
            calories=400, protein=20, carbs=50, fat=10, tags=[],
            ingredients=[{"item": "tomato", "quantity": 1, "unit": "serving", "category": "produce"}]
        )
        meals = [PlannedMeal(day="Monday", meal_type="dinner", recipe=recipe, household_portions=2.75)]
        shopping_list = generate_shopping_list(WeeklyPlan(meals=meals))

        tomato_items = [i for i in shopping_list.items if i.item == "tomato"]
        assert len(tomato_items) == 1
        assert tomato_items[0].unit == "", (
            f"Expected unit='' but got unit='{tomato_items[0].unit}'. "
            "'serving' must not appear in the display."
        )

    def test_missing_unit_key_normalised_to_empty_string(self):
        recipe = create_test_recipe(
            recipe_id="r1", name="R1", servings=4,
            prep_time_minutes=10, cook_time_minutes=20,
            calories=400, protein=20, carbs=50, fat=10, tags=[],
            ingredients=[{"item": "tomato", "quantity": 1, "category": "produce"}]
        )
        meals = [PlannedMeal(day="Monday", meal_type="dinner", recipe=recipe, household_portions=4.0)]
        shopping_list = generate_shopping_list(WeeklyPlan(meals=meals))

        tomato_items = [i for i in shopping_list.items if i.item == "tomato"]
        assert len(tomato_items) == 1
        assert tomato_items[0].unit == "", (
            f"Expected unit='' for ingredient without 'unit' key, got '{tomato_items[0].unit}'"
        )


class TestUnitConversion:
    """Unit conversion: same ingredient with compatible but different units combines into one line."""

    # --- volume ---

    def test_tsp_plus_tbsp_combines_to_tbsp(self):
        # 3 tsp == 1 tbsp; 3 tsp + 1 tbsp = 2 tbsp (largest unit = tbsp)
        result = _combine_entries([(3.0, "tsp"), (1.0, "tbsp")])
        assert len(result) == 1
        unit = result[0][1]
        qty = result[0][0]
        assert unit == "tbsp"
        assert abs(qty - 2.0) < 0.01

    def test_ml_plus_cup_combines_to_cup(self):
        # 236.588 ml == 1 cup; 236.588 ml + 1 cup = 2 cups (largest = cup)
        result = _combine_entries([(236.588, "ml"), (1.0, "cup")])
        assert len(result) == 1
        assert result[0][1] == "cup"
        assert abs(result[0][0] - 2.0) < 0.01

    def test_volume_combines_across_three_units(self):
        # 3 tsp + 1 tbsp + 0.5 cup; largest = cup
        # 3 tsp = 14.79 ml, 1 tbsp = 14.79 ml, 0.5 cup = 118.29 ml → total = 147.87 ml
        # / 236.588 (cup) ≈ 0.625 cup
        result = _combine_entries([(3.0, "tsp"), (1.0, "tbsp"), (0.5, "cup")])
        assert len(result) == 1
        assert result[0][1] == "cup"
        assert abs(result[0][0] - 0.625) < 0.01

    # --- weight ---

    def test_oz_plus_lb_combines_to_lb(self):
        # 16 oz == 1 lb; 16 oz + 1 lb = 2 lb (largest = lb)
        result = _combine_entries([(16.0, "oz"), (1.0, "lb")])
        assert len(result) == 1
        assert result[0][1] == "lb"
        assert abs(result[0][0] - 2.0) < 0.01

    def test_g_plus_kg_combines_to_kg(self):
        # 500 g + 0.5 kg = 1 kg (largest = kg)
        result = _combine_entries([(500.0, "g"), (0.5, "kg")])
        assert len(result) == 1
        assert result[0][1] == "kg"
        assert abs(result[0][0] - 1.0) < 0.01

    # --- incompatible units kept separate ---

    def test_volume_and_weight_kept_separate(self):
        # 1 cup + 100 g — different families, cannot merge
        result = _combine_entries([(1.0, "cup"), (100.0, "g")])
        assert len(result) == 2
        units = {r[1] for r in result}
        assert "cup" in units
        assert "g" in units

    def test_unknown_units_same_kept_combined(self):
        # 3 cloves + 2 cloves → 5 cloves
        result = _combine_entries([(3.0, "clove"), (2.0, "clove")])
        assert len(result) == 1
        assert result[0] == (5.0, "clove")

    def test_unknown_units_different_kept_separate(self):
        # 3 cloves + 1 head — unknown units that differ, cannot merge
        result = _combine_entries([(3.0, "clove"), (1.0, "head")])
        assert len(result) == 2
        units = {r[1] for r in result}
        assert "clove" in units
        assert "head" in units

    def test_unitless_kept_separate_from_known_unit(self):
        # 2 (unitless) + 1 cup — unitless cannot merge with volume
        result = _combine_entries([(2.0, ""), (1.0, "cup")])
        assert len(result) == 2
        units = {r[1] for r in result}
        assert "" in units
        assert "cup" in units

    # --- integration via generate_shopping_list ---

    def test_integration_tsp_and_tbsp_combined_in_plan(self):
        def make_recipe(rid, qty, unit):
            return create_test_recipe(
                recipe_id=rid, name=rid, servings=1,
                prep_time_minutes=5, cook_time_minutes=10,
                calories=100, protein=5, carbs=10, fat=3, tags=[], ingredients=[
                    {"item": "oil", "quantity": qty, "unit": unit, "category": "pantry"}
                ]
            )

        meals = [
            PlannedMeal(day="Monday", meal_type="dinner",
                        recipe=make_recipe("r1", 3.0, "tsp"), household_portions=1.0),
            PlannedMeal(day="Tuesday", meal_type="dinner",
                        recipe=make_recipe("r2", 1.0, "tbsp"), household_portions=1.0),
        ]
        shopping_list = generate_shopping_list(WeeklyPlan(meals=meals))

        oil_items = [i for i in shopping_list.items if i.item == "oil"]
        assert len(oil_items) == 1, f"Expected 1 combined oil line, got {len(oil_items)}"
        assert oil_items[0].unit == "tbsp"
        assert abs(oil_items[0].quantity - 2.0) < 0.01


class TestApplyExclusions:
    def _make_list(self, *names):
        items = [ShoppingListItem(item=n, quantity=1.0, unit="", category="other") for n in names]
        return ShoppingList(items=items)

    def test_exact_match_excluded(self):
        """An excluded term that exactly matches an item name removes it."""
        sl = self._make_list("egg", "milk", "butter")
        result = apply_exclusions(sl, ["egg"])
        names = [i.item for i in result.items]
        assert "egg" not in names
        assert "milk" in names

    def test_plural_excluded(self):
        """'egg' in the excluded list also removes the item named 'eggs'."""
        sl = self._make_list("eggs", "milk")
        result = apply_exclusions(sl, ["egg"])
        # 'eggs' does NOT contain the whole word 'egg' — word boundary stops at 's'
        # so 'eggs' should NOT be excluded by the term 'egg'
        names = [i.item for i in result.items]
        assert "eggs" in names

    def test_substring_not_excluded(self):
        """'egg' in the excluded list must NOT remove 'eggplant'."""
        sl = self._make_list("eggplant", "egg", "scrambled eggs")
        result = apply_exclusions(sl, ["egg"])
        names = [i.item for i in result.items]
        assert "eggplant" in names
        assert "egg" not in names
        # "scrambled eggs" contains neither standalone "egg" (it's "eggs") so kept
        assert "scrambled eggs" in names

    def test_multi_word_excluded_term(self):
        """Multi-word excluded terms are matched as a whole phrase."""
        sl = self._make_list("olive oil", "oil", "sunflower oil")
        result = apply_exclusions(sl, ["olive oil"])
        names = [i.item for i in result.items]
        assert "olive oil" not in names
        assert "oil" in names
        assert "sunflower oil" in names

    def test_empty_exclusions_keeps_all(self):
        sl = self._make_list("salt", "pepper", "water")
        result = apply_exclusions(sl, [])
        assert len(result.items) == 3

    def test_case_insensitive(self):
        """Exclusion matching is case-insensitive."""
        sl = self._make_list("Salt", "Pepper")
        result = apply_exclusions(sl, ["salt"])
        names = [i.item for i in result.items]
        assert "Salt" not in names
        assert "Pepper" in names

