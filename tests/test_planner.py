from dataclasses import dataclass
from pathlib import Path

import pytest

from app.planner import (
    DAYS_OF_WEEK,
    MealPlanner,
    PlannedMeal,
    WeeklyPlan,
    get_meal_slots_from_schedule,
)
from app.recipes import Recipe
from tests.conftest import create_test_recipe


@pytest.fixture
def sample_recipes():
    return [
        create_test_recipe(
            recipe_id="recipe-1",
            name="Recipe 1",
            servings=4,
            prep_time_minutes=10,
            cook_time_minutes=20,
            calories=400,
            protein=20,
            carbs=50,
            fat=10,
            tags=["italian", "dinner"],
            ingredients=[
                {"item": "pasta", "quantity": 400, "unit": "g", "category": "pantry"}
            ]
        ),
        create_test_recipe(
            recipe_id="recipe-2",
            name="Recipe 2",
            servings=4,
            prep_time_minutes=15,
            cook_time_minutes=25,
            calories=350,
            protein=25,
            carbs=40,
            fat=12,
            tags=["asian", "dinner"],
            ingredients=[
                {"item": "rice", "quantity": 300, "unit": "g", "category": "pantry"}
            ]
        ),
        create_test_recipe(
            recipe_id="recipe-3",
            name="Recipe 3",
            servings=4,
            prep_time_minutes=5,
            cook_time_minutes=15,
            calories=300,
            protein=15,
            carbs=35,
            fat=8,
            tags=["quick", "lunch", "dinner"],
            ingredients=[
                {"item": "bread", "quantity": 200, "unit": "g", "category": "bakery"}
            ]
        ),
        create_test_recipe(
            recipe_id="recipe-4",
            name="Recipe 4",
            servings=4,
            prep_time_minutes=20,
            cook_time_minutes=30,
            calories=450,
            protein=30,
            carbs=45,
            fat=15,
            tags=["healthy", "dinner"],
            ingredients=[
                {"item": "chicken", "quantity": 500, "unit": "g", "category": "meat"}
            ]
        ),
        create_test_recipe(
            recipe_id="recipe-5",
            name="Recipe 5",
            servings=4,
            prep_time_minutes=12,
            cook_time_minutes=18,
            calories=380,
            protein=22,
            carbs=42,
            fat=11,
            tags=["vegetarian", "dinner"],
            ingredients=[
                {"item": "beans", "quantity": 300, "unit": "g", "category": "pantry"}
            ]
        ),
        create_test_recipe(
            recipe_id="recipe-6",
            name="Recipe 6",
            servings=4,
            prep_time_minutes=8,
            cook_time_minutes=12,
            calories=320,
            protein=18,
            carbs=38,
            fat=9,
            tags=["quick", "lunch", "dinner"],
            ingredients=[
                {"item": "eggs", "quantity": 8, "unit": "pieces", "category": "dairy"}
            ]
        ),
        create_test_recipe(
            recipe_id="recipe-7",
            name="Recipe 7",
            servings=4,
            prep_time_minutes=18,
            cook_time_minutes=22,
            calories=410,
            protein=24,
            carbs=48,
            fat=14,
            tags=["comfort", "dinner"],
            ingredients=[
                {"item": "potatoes", "quantity": 600, "unit": "g", "category": "produce"}
            ]
        ),
    ]


@pytest.fixture
def planner():
    return MealPlanner(household_portions=2.75)


class TestGetMealSlotsFromSchedule:
    def test_get_meal_slots_single_meal_per_day(self):
        schedule = {
            "Monday": ["dinner"],
            "Tuesday": ["dinner"],
            "Wednesday": ["dinner"]
        }
        slots = get_meal_slots_from_schedule(schedule)
        assert len(slots) == 3
        assert slots == [("Monday", "dinner"), ("Tuesday", "dinner"), ("Wednesday", "dinner")]

    def test_get_meal_slots_multiple_meals_per_day(self):
        schedule = {
            "Saturday": ["lunch", "dinner"],
            "Sunday": ["lunch", "dinner"]
        }
        slots = get_meal_slots_from_schedule(schedule)
        assert len(slots) == 4
        assert ("Saturday", "lunch") in slots
        assert ("Saturday", "dinner") in slots
        assert ("Sunday", "lunch") in slots
        assert ("Sunday", "dinner") in slots

    def test_get_meal_slots_mixed_schedule(self):
        schedule = {
            "Monday": ["dinner"],
            "Tuesday": ["dinner"],
            "Saturday": ["lunch", "dinner"]
        }
        slots = get_meal_slots_from_schedule(schedule)
        assert len(slots) == 4
        assert slots[0] == ("Monday", "dinner")
        assert slots[1] == ("Tuesday", "dinner")
        assert ("Saturday", "lunch") in slots
        assert ("Saturday", "dinner") in slots

    def test_get_meal_slots_empty_schedule(self):
        schedule = {}
        slots = get_meal_slots_from_schedule(schedule)
        assert len(slots) == 0
        assert slots == []


class TestMealPlanner:
    def test_planner_initialization(self):
        planner = MealPlanner(household_portions=2.75)
        assert planner.household_portions == 2.75

    def test_generate_weekly_plan_returns_weekly_plan(self, planner, sample_recipes):
        plan = planner.generate_weekly_plan(sample_recipes)
        assert isinstance(plan, WeeklyPlan)

    def test_generate_weekly_plan_has_seven_meals(self, planner, sample_recipes):
        plan = planner.generate_weekly_plan(sample_recipes)
        assert len(plan.meals) == 7

    def test_generate_weekly_plan_no_repeats(self, planner, sample_recipes):
        plan = planner.generate_weekly_plan(sample_recipes)
        recipe_ids = [meal.recipe.id for meal in plan.meals]
        assert len(recipe_ids) == len(set(recipe_ids))

    def test_generate_weekly_plan_all_from_available_recipes(self, planner, sample_recipes):
        plan = planner.generate_weekly_plan(sample_recipes)
        available_ids = {r.id for r in sample_recipes}
        for meal in plan.meals:
            assert meal.recipe.id in available_ids

    def test_generate_weekly_plan_requires_sufficient_recipes(self, planner):
        too_few_recipes = [
            create_test_recipe(
                recipe_id=f"recipe-{i}",
                name=f"Recipe {i}",
                servings=4,
                prep_time_minutes=10,
                cook_time_minutes=20,
                calories=400,
                protein=20,
                carbs=50,
                fat=10,
                tags=["dinner"],
                ingredients=[]
            )
            for i in range(5)
        ]

        with pytest.raises(ValueError) as exc_info:
            planner.generate_weekly_plan(too_few_recipes)
        assert "need at least" in str(exc_info.value).lower()

    def test_generate_weekly_plan_respects_meal_schedule(self):
        # Create planner with custom schedule
        meal_schedule = {
            "Monday": ["dinner"],
            "Tuesday": ["dinner"],
            "Saturday": ["lunch", "dinner"]
        }
        planner = MealPlanner(household_portions=2.75, meal_schedule=meal_schedule)

        recipes = [
            create_test_recipe(
                recipe_id=f"recipe-{i}",
                name=f"Recipe {i}",
                servings=4,
                prep_time_minutes=10,
                cook_time_minutes=20,
                calories=400,
                protein=20,
                carbs=50,
                fat=10,
                tags=["lunch", "dinner"],
                ingredients=[]
            )
            for i in range(10)
        ]

        plan = planner.generate_weekly_plan(recipes)

        # Should have 4 meals (2 dinners + 1 lunch + 1 dinner)
        assert len(plan.meals) == 4

        # Check Monday and Tuesday have dinner
        monday_meals = [m for m in plan.meals if m.day == "Monday"]
        assert len(monday_meals) == 1
        assert monday_meals[0].meal_type == "dinner"

        tuesday_meals = [m for m in plan.meals if m.day == "Tuesday"]
        assert len(tuesday_meals) == 1
        assert tuesday_meals[0].meal_type == "dinner"

        # Check Saturday has lunch and dinner
        saturday_meals = [m for m in plan.meals if m.day == "Saturday"]
        assert len(saturday_meals) == 2
        meal_types = {m.meal_type for m in saturday_meals}
        assert meal_types == {"lunch", "dinner"}

    def test_generate_weekly_plan_filters_by_meal_type_tags(self):
        # Create recipes with specific tags
        lunch_recipes = [
            create_test_recipe(
                recipe_id=f"lunch-{i}",
                name=f"Lunch Recipe {i}",
                servings=4,
                prep_time_minutes=10,
                cook_time_minutes=15,
                calories=300,
                protein=15,
                carbs=35,
                fat=8,
                tags=["lunch"],
                ingredients=[]
            )
            for i in range(3)
        ]

        dinner_recipes = [
            create_test_recipe(
                recipe_id=f"dinner-{i}",
                name=f"Dinner Recipe {i}",
                servings=4,
                prep_time_minutes=20,
                cook_time_minutes=30,
                calories=450,
                protein=30,
                carbs=45,
                fat=15,
                tags=["dinner"],
                ingredients=[]
            )
            for i in range(3)
        ]

        all_recipes = lunch_recipes + dinner_recipes

        meal_schedule = {
            "Monday": ["lunch"],
            "Tuesday": ["dinner"]
        }
        planner = MealPlanner(household_portions=2.75, meal_schedule=meal_schedule)
        plan = planner.generate_weekly_plan(all_recipes)

        # Check Monday meal is from lunch recipes
        monday_meal = [m for m in plan.meals if m.day == "Monday"][0]
        assert monday_meal.recipe.id.startswith("lunch-")

        # Check Tuesday meal is from dinner recipes
        tuesday_meal = [m for m in plan.meals if m.day == "Tuesday"][0]
        assert tuesday_meal.recipe.id.startswith("dinner-")

    def test_generate_weekly_plan_falls_back_when_no_tagged_recipes(self):
        # Create recipes without meal type tags
        recipes = [
            create_test_recipe(
                recipe_id=f"recipe-{i}",
                name=f"Recipe {i}",
                servings=4,
                prep_time_minutes=10,
                cook_time_minutes=20,
                calories=400,
                protein=20,
                carbs=50,
                fat=10,
                tags=["other-tag"],  # No lunch or dinner tag
                ingredients=[]
            )
            for i in range(7)
        ]

        # Default schedule expects dinner tags, but recipes don't have them
        # Should fall back to using any available recipe
        planner = MealPlanner(household_portions=2.75)
        plan = planner.generate_weekly_plan(recipes)

        assert len(plan.meals) == 7
        # All recipes should be used despite not having dinner tags
        used_ids = {m.recipe.id for m in plan.meals}
        assert len(used_ids) == 7

    def test_generate_weekly_plan_with_multiple_meals_per_day(self):
        # Create enough recipes for a schedule with multiple meals per day
        recipes = [
            create_test_recipe(
                recipe_id=f"recipe-{i}",
                name=f"Recipe {i}",
                servings=4,
                prep_time_minutes=10,
                cook_time_minutes=20,
                calories=400,
                protein=20,
                carbs=50,
                fat=10,
                tags=["lunch", "dinner"],
                ingredients=[]
            )
            for i in range(10)
        ]

        meal_schedule = {
            "Saturday": ["lunch", "dinner"],
            "Sunday": ["lunch", "dinner"]
        }
        planner = MealPlanner(household_portions=2.75, meal_schedule=meal_schedule)
        plan = planner.generate_weekly_plan(recipes)

        assert len(plan.meals) == 4

        # Check no recipe repeats
        recipe_ids = [m.recipe.id for m in plan.meals]
        assert len(recipe_ids) == len(set(recipe_ids))

    def test_generate_plan_respects_daily_calorie_limit(self):
        # 7 low-cal (100 cal) and 7 high-cal (800 cal) dinner recipes.
        # With daily_calorie_limit=500 and portions=1.0, only low-cal recipes fit.
        low_cal = [
            create_test_recipe(
                recipe_id=f"low-{i}", name=f"Low {i}", servings=1,
                prep_time_minutes=10, cook_time_minutes=20,
                calories=100, protein=5, carbs=10, fat=3,
                tags=["dinner"], ingredients=[]
            ) for i in range(7)
        ]
        high_cal = [
            create_test_recipe(
                recipe_id=f"high-{i}", name=f"High {i}", servings=1,
                prep_time_minutes=10, cook_time_minutes=20,
                calories=800, protein=40, carbs=80, fat=30,
                tags=["dinner"], ingredients=[]
            ) for i in range(7)
        ]

        planner = MealPlanner(household_portions=1.0, daily_calorie_limit=500)
        plan = planner.generate_weekly_plan(low_cal + high_cal)

        assert len(plan.meals) == 7
        for meal in plan.meals:
            assert meal.recipe.id.startswith("low-"), (
                f"Expected low-cal recipe but got {meal.recipe.id} ({meal.calories} cal)"
            )

    def test_calorie_limit_is_per_serving_not_scaled_by_portions(self):
        # Regression: the limit applies to calories_per_serving, not
        # calories_per_serving * household_portions.
        # With portions=2.75 and limit=1600, a 700-cal recipe fits (700 <= 1600)
        # but the old buggy code rejected it because 700 * 2.75 = 1925 > 1600.
        fitting = [
            create_test_recipe(
                recipe_id=f"fit-{i}", name=f"Fitting {i}", servings=1,
                prep_time_minutes=10, cook_time_minutes=20,
                calories=700, protein=30, carbs=70, fat=20,
                tags=["dinner"], ingredients=[]
            ) for i in range(7)
        ]
        over_limit = [
            create_test_recipe(
                recipe_id=f"over-{i}", name=f"Over {i}", servings=1,
                prep_time_minutes=10, cook_time_minutes=20,
                calories=1800, protein=80, carbs=180, fat=60,
                tags=["dinner"], ingredients=[]
            ) for i in range(7)
        ]

        planner = MealPlanner(household_portions=2.75, daily_calorie_limit=1600)
        plan = planner.generate_weekly_plan(fitting + over_limit)

        assert len(plan.meals) == 7
        for meal in plan.meals:
            assert meal.recipe.id.startswith("fit-"), (
                f"Expected 700-cal recipe to fit the 1600 limit but got "
                f"{meal.recipe.id} ({meal.recipe.calories_per_serving} cal/serving)"
            )

    def test_proportional_calorie_splits_by_meal_type(self):
        # Saturday: lunch + dinner with splits {lunch: 0.35, dinner: 0.40}
        # and limit=1500.
        #   lunch  budget = 0.35 / (0.35+0.40) * 1500 = 700 cal
        #   dinner budget = 0.40 / (0.35+0.40) * 1500 = 800 cal
        # "lunch-ok" (650 cal) fits lunch budget; "lunch-over" (750 cal) does not.
        # "dinner-ok" (780 cal) fits dinner budget; "dinner-over" (900 cal) does not.
        lunch_ok = [
            create_test_recipe(
                recipe_id=f"lunch-ok-{i}", name=f"Lunch OK {i}", servings=1,
                prep_time_minutes=10, cook_time_minutes=20,
                calories=650, protein=30, carbs=60, fat=15,
                tags=["lunch"], ingredients=[]
            ) for i in range(2)
        ]
        lunch_over = [
            create_test_recipe(
                recipe_id=f"lunch-over-{i}", name=f"Lunch Over {i}", servings=1,
                prep_time_minutes=10, cook_time_minutes=20,
                calories=750, protein=30, carbs=60, fat=15,
                tags=["lunch"], ingredients=[]
            ) for i in range(2)
        ]
        dinner_ok = [
            create_test_recipe(
                recipe_id=f"dinner-ok-{i}", name=f"Dinner OK {i}", servings=1,
                prep_time_minutes=10, cook_time_minutes=20,
                calories=780, protein=40, carbs=80, fat=20,
                tags=["dinner"], ingredients=[]
            ) for i in range(2)
        ]
        dinner_over = [
            create_test_recipe(
                recipe_id=f"dinner-over-{i}", name=f"Dinner Over {i}", servings=1,
                prep_time_minutes=10, cook_time_minutes=20,
                calories=900, protein=40, carbs=80, fat=20,
                tags=["dinner"], ingredients=[]
            ) for i in range(2)
        ]

        planner = MealPlanner(
            household_portions=1.0,
            meal_schedule={"Saturday": ["lunch", "dinner"]},
            daily_calorie_limit=1500,
            meal_calorie_splits={"lunch": 0.35, "dinner": 0.40},
        )
        plan = planner.generate_weekly_plan(lunch_ok + lunch_over + dinner_ok + dinner_over)

        lunch_meal = next(m for m in plan.meals if m.meal_type == "lunch")
        dinner_meal = next(m for m in plan.meals if m.meal_type == "dinner")
        assert lunch_meal.recipe.calories_per_serving <= 700, (
            f"Lunch should respect its 700-cal budget, got {lunch_meal.recipe.calories_per_serving}"
        )
        assert dinner_meal.recipe.calories_per_serving <= 800, (
            f"Dinner should respect its 800-cal budget, got {dinner_meal.recipe.calories_per_serving}"
        )
        # The daily total must never exceed the limit regardless of individual budgets.
        total = lunch_meal.calories + dinner_meal.calories
        assert total <= 1500, f"Daily total {total} exceeds limit 1500"

    def test_daily_total_stays_within_limit_when_first_meal_overshoots(self):
        # Regression: proportional budgets are independent, so if the first meal
        # overshoots via fallback the second meal's budget must shrink to compensate.
        #
        # Only recipe available for lunch is 900 cal (over the proportional 700 share).
        # Fallback selects it.  Remaining budget for dinner = 1500 - 900 = 600.
        # The 780-cal dinner recipe must be rejected in favour of the 550-cal one.
        lunch_only = [
            create_test_recipe(
                recipe_id="big-lunch", name="Big Lunch", servings=1,
                prep_time_minutes=10, cook_time_minutes=20,
                calories=900, protein=40, carbs=90, fat=25,
                tags=["lunch"], ingredients=[]
            )
        ]
        dinner_options = [
            create_test_recipe(
                recipe_id="dinner-fits", name="Dinner Fits", servings=1,
                prep_time_minutes=10, cook_time_minutes=20,
                calories=550, protein=30, carbs=55, fat=15,
                tags=["dinner"], ingredients=[]
            ),
            create_test_recipe(
                recipe_id="dinner-too-big", name="Dinner Too Big", servings=1,
                prep_time_minutes=10, cook_time_minutes=20,
                calories=780, protein=40, carbs=78, fat=20,
                tags=["dinner"], ingredients=[]
            ),
        ]

        planner = MealPlanner(
            household_portions=1.0,
            meal_schedule={"Saturday": ["lunch", "dinner"]},
            daily_calorie_limit=1500,
            meal_calorie_splits={"lunch": 0.35, "dinner": 0.40},
        )
        plan = planner.generate_weekly_plan(lunch_only + dinner_options)

        lunch_meal = next(m for m in plan.meals if m.meal_type == "lunch")
        dinner_meal = next(m for m in plan.meals if m.meal_type == "dinner")
        assert lunch_meal.recipe.id == "big-lunch"          # only option
        assert dinner_meal.recipe.id == "dinner-fits"       # 780 exceeds remaining 600
        assert lunch_meal.calories + dinner_meal.calories <= 1500

    def test_generate_plan_picks_lowest_calorie_when_none_fit(self):
        # daily_calorie_limit=50; all 7 recipes exceed it; plan must still be generated.
        recipes = [
            create_test_recipe(
                recipe_id=f"recipe-{cal}", name=f"Recipe {cal}", servings=1,
                prep_time_minutes=10, cook_time_minutes=20,
                calories=cal, protein=5, carbs=10, fat=3,
                tags=["dinner"], ingredients=[]
            ) for cal in [200, 300, 400, 500, 600, 700, 800]
        ]

        planner = MealPlanner(household_portions=1.0, daily_calorie_limit=50)
        plan = planner.generate_weekly_plan(recipes)

        assert len(plan.meals) == 7
        selected_calories = sorted(meal.calories for meal in plan.meals)
        assert selected_calories == [200.0, 300.0, 400.0, 500.0, 600.0, 700.0, 800.0]

    def test_generate_plan_treats_zero_calorie_recipes_neutrally(self):
        # Recipes with 0 calories must never be blocked by any calorie budget.
        zero_cal = [
            create_test_recipe(
                recipe_id=f"zero-{i}", name=f"Zero {i}", servings=1,
                prep_time_minutes=10, cook_time_minutes=20,
                calories=0, protein=0, carbs=0, fat=0,
                tags=["dinner"], ingredients=[]
            ) for i in range(7)
        ]

        planner = MealPlanner(household_portions=1.0, daily_calorie_limit=1)
        plan = planner.generate_weekly_plan(zero_cal)

        assert len(plan.meals) == 7
        for meal in plan.meals:
            assert meal.calories == 0.0

    def test_budget_fallback_uses_untagged_recipes_to_stay_within_limit(self):
        # Regression: when all "dinner"-tagged recipes exceed the remaining daily
        # budget, the planner must widen its search to untagged unused recipes
        # instead of picking the lowest-calorie tagged recipe (which still overshoots).
        #
        # Scenario:
        #   - Saturday: lunch + dinner, daily limit = 1000
        #   - Lunch: 400-cal lunch recipe fits its proportional share (460).
        #   - Remaining for dinner = 1000 - 400 = 600.
        #   - All "dinner"-tagged recipes are 700 cal (> 600 remaining).
        #   - One untagged recipe exists at 500 cal (≤ 600 remaining) and must be
        #     selected for the dinner slot.
        normal_lunch = create_test_recipe(
            recipe_id="normal-lunch", name="Normal Lunch", servings=1,
            prep_time_minutes=10, cook_time_minutes=20,
            calories=400, protein=20, carbs=40, fat=10,
            tags=["lunch"], ingredients=[]
        )
        heavy_dinner = create_test_recipe(
            recipe_id="heavy-dinner", name="Heavy Dinner", servings=1,
            prep_time_minutes=10, cook_time_minutes=20,
            calories=700, protein=35, carbs=70, fat=18,
            tags=["dinner"], ingredients=[]
        )
        untagged_light = create_test_recipe(
            recipe_id="light-untagged", name="Light Untagged", servings=1,
            prep_time_minutes=5, cook_time_minutes=10,
            calories=500, protein=15, carbs=50, fat=12,
            tags=[],  # no meal-type tag — generic fallback
            ingredients=[]
        )

        planner = MealPlanner(
            household_portions=1.0,
            meal_schedule={"Saturday": ["lunch", "dinner"]},
            daily_calorie_limit=1000,
            meal_calorie_splits={"lunch": 0.46, "dinner": 0.54},
        )
        plan = planner.generate_weekly_plan([normal_lunch, heavy_dinner, untagged_light])

        lunch_meal = next(m for m in plan.meals if m.meal_type == "lunch")
        dinner_meal = next(m for m in plan.meals if m.meal_type == "dinner")
        assert lunch_meal.recipe.id == "normal-lunch"
        assert dinner_meal.recipe.id == "light-untagged"   # untagged fallback selected
        assert lunch_meal.calories + dinner_meal.calories <= 1000


class TestPlannedMeal:
    def test_planned_meal_has_day_and_recipe(self, sample_recipes):
        meal = PlannedMeal(day="Monday", meal_type="dinner", recipe=sample_recipes[0], household_portions=2.75)
        assert meal.day == "Monday"
        assert meal.recipe == sample_recipes[0]

    def test_planned_meal_has_meal_type(self, sample_recipes):
        meal = PlannedMeal(day="Monday", meal_type="lunch", recipe=sample_recipes[0], household_portions=2.75)
        assert meal.meal_type == "lunch"

    def test_planned_meal_calculates_portions(self, sample_recipes):
        meal = PlannedMeal(day="Monday", meal_type="dinner", recipe=sample_recipes[0], household_portions=2.75)
        assert meal.portions == 2.75

    def test_planned_meal_calculates_scaled_ingredients(self, sample_recipes):
        recipe = create_test_recipe(
            recipe_id="test",
            name="Test",
            servings=4,
            prep_time_minutes=10,
            cook_time_minutes=20,
            calories=400,
            protein=20,
            carbs=50,
            fat=10,
            tags=[],
            ingredients=[
                {"item": "pasta", "quantity": 400, "unit": "g", "category": "pantry"}
            ]
        )

        meal = PlannedMeal(day="Monday", meal_type="dinner", recipe=recipe, household_portions=2.75)
        scaled = meal.scaled_ingredients

        assert len(scaled) == 1
        # 400g for 4 servings = 100g per serving
        # 2.75 portions * 100g = 275g
        assert scaled[0]["quantity"] == 275.0


class TestWeeklyPlan:
    def test_weekly_plan_has_meals(self, planner, sample_recipes):
        plan = planner.generate_weekly_plan(sample_recipes)
        assert len(plan.meals) > 0

    def test_weekly_plan_calculates_total_nutrition(self, planner, sample_recipes):
        plan = planner.generate_weekly_plan(sample_recipes)

        assert plan.total_calories > 0
        assert plan.total_protein > 0
        assert plan.total_carbs > 0
        assert plan.total_fat > 0

    def test_weekly_plan_calculates_daily_averages(self, planner, sample_recipes):
        plan = planner.generate_weekly_plan(sample_recipes)

        expected_avg_calories = plan.total_calories / 7
        expected_avg_protein = plan.total_protein / 7

        assert abs(plan.avg_daily_calories - expected_avg_calories) < 0.01
        assert abs(plan.avg_daily_protein - expected_avg_protein) < 0.01

    def test_weekly_plan_nutrition_is_per_serving(self):
        # Nutrition properties on PlannedMeal are per-serving (per person),
        # regardless of household_portions.  household_portions only affects
        # scaled_ingredients (shopping quantities).
        recipes = [
            create_test_recipe(
                recipe_id=f"simple-{i}",
                name=f"Simple Recipe {i}",
                servings=4,
                prep_time_minutes=10,
                cook_time_minutes=20,
                calories=400,
                protein=20,
                carbs=50,
                fat=10,
                tags=["dinner"],
                ingredients=[]
            )
            for i in range(7)
        ]

        planner = MealPlanner(household_portions=2.0)
        plan = planner.generate_weekly_plan(recipes)

        # total_calories = 400 cal/serving * 7 meals (no portions scaling)
        expected_total = 400 * 7
        assert abs(plan.total_calories - expected_total) < 0.01
        for meal in plan.meals:
            assert meal.calories == 400

    def test_weekly_plan_calculates_daily_nutrition(self, planner, sample_recipes):
        plan = planner.generate_weekly_plan(sample_recipes)
        daily_nutrition = plan.get_daily_nutrition()

        # Should have entries for each unique day in the plan
        assert len(daily_nutrition) > 0

        # Each day should have nutrition data
        for day, nutrition in daily_nutrition.items():
            assert "calories" in nutrition
            assert "protein" in nutrition
            assert "carbs" in nutrition
            assert "fat" in nutrition
            assert nutrition["calories"] > 0

    def test_weekly_plan_with_calorie_limit(self):
        recipes = [
            create_test_recipe(
                recipe_id=f"meal-{i}",
                name=f"Meal {i}",
                servings=4,
                prep_time_minutes=10,
                cook_time_minutes=20,
                calories=500,
                protein=25,
                carbs=60,
                fat=15,
                tags=["dinner"],
                ingredients=[]
            )
            for i in range(7)
        ]

        planner = MealPlanner(household_portions=2.0, daily_calorie_limit=2000)
        plan = planner.generate_weekly_plan(recipes)

        assert plan.daily_calorie_limit == 2000

        # Each meal is 500 cal/serving (per person); daily total = 500 (one dinner per day)
        daily_nutrition = plan.get_daily_nutrition()
        for day, nutrition in daily_nutrition.items():
            assert abs(nutrition["calories"] - 500) < 0.01

    def test_weekly_plan_daily_nutrition_sums_multiple_meals_per_day(self):
        recipes = [
            create_test_recipe(
                recipe_id=f"meal-{i}",
                name=f"Meal {i}",
                servings=4,
                prep_time_minutes=10,
                cook_time_minutes=20,
                calories=400,
                protein=20,
                carbs=50,
                fat=10,
                tags=["lunch", "dinner"],
                ingredients=[]
            )
            for i in range(14)  # Need 14 recipes for 2 meals per day * 7 days
        ]

        # Schedule with lunch and dinner
        meal_schedule = {day: ["lunch", "dinner"] for day in DAYS_OF_WEEK}
        planner = MealPlanner(household_portions=2.0, meal_schedule=meal_schedule)
        plan = planner.generate_weekly_plan(recipes)

        daily_nutrition = plan.get_daily_nutrition()

        # Each meal is 400 cal/serving (per person); two meals per day = 800 cal
        for day, nutrition in daily_nutrition.items():
            assert abs(nutrition["calories"] - 800) < 0.01


class TestScaledIngredients:
    def test_scaled_ingredients_normal(self):
        """Scaling works correctly when quantity is present."""
        recipe = create_test_recipe(
            recipe_id="r1",
            name="R1",
            servings=4,
            ingredients=[{"item": "flour", "quantity": 200, "unit": "g", "category": "pantry"}],
        )
        meal = PlannedMeal(day="Monday", meal_type="dinner", recipe=recipe, household_portions=2.0)
        scaled = meal.scaled_ingredients
        assert scaled[0]["quantity"] == pytest.approx(100.0)  # 200g / 4 servings * 2 portions

    def test_scaled_ingredients_missing_quantity_no_keyerror(self):
        """Ingredient dict without 'quantity' key must not raise KeyError."""
        recipe = create_test_recipe(
            recipe_id="r2",
            name="R2",
            servings=4,
            ingredients=[{"item": "salt", "unit": "to taste", "category": "pantry"}],
        )
        meal = PlannedMeal(day="Monday", meal_type="dinner", recipe=recipe, household_portions=4.0)
        scaled = meal.scaled_ingredients  # must not raise
        assert scaled[0]["quantity"] == 0  # 0 * scale_factor = 0
