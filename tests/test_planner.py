from dataclasses import dataclass
from pathlib import Path

import pytest

from app.planner import MealPlanner, PlannedMeal, WeeklyPlan, get_meal_slots_from_schedule
from app.recipes import Recipe


@pytest.fixture
def sample_recipes():
    return [
        Recipe(
            id="recipe-1",
            name="Recipe 1",
            servings=4,
            prep_time_minutes=10,
            cook_time_minutes=20,
            calories_per_serving=400,
            protein_per_serving=20,
            carbs_per_serving=50,
            fat_per_serving=10,
            tags=["italian", "dinner"],
            ingredients=[
                {"item": "pasta", "quantity": 400, "unit": "g", "category": "pantry"}
            ]
        ),
        Recipe(
            id="recipe-2",
            name="Recipe 2",
            servings=4,
            prep_time_minutes=15,
            cook_time_minutes=25,
            calories_per_serving=350,
            protein_per_serving=25,
            carbs_per_serving=40,
            fat_per_serving=12,
            tags=["asian", "dinner"],
            ingredients=[
                {"item": "rice", "quantity": 300, "unit": "g", "category": "pantry"}
            ]
        ),
        Recipe(
            id="recipe-3",
            name="Recipe 3",
            servings=4,
            prep_time_minutes=5,
            cook_time_minutes=15,
            calories_per_serving=300,
            protein_per_serving=15,
            carbs_per_serving=35,
            fat_per_serving=8,
            tags=["quick", "lunch", "dinner"],
            ingredients=[
                {"item": "bread", "quantity": 200, "unit": "g", "category": "bakery"}
            ]
        ),
        Recipe(
            id="recipe-4",
            name="Recipe 4",
            servings=4,
            prep_time_minutes=20,
            cook_time_minutes=30,
            calories_per_serving=450,
            protein_per_serving=30,
            carbs_per_serving=45,
            fat_per_serving=15,
            tags=["healthy", "dinner"],
            ingredients=[
                {"item": "chicken", "quantity": 500, "unit": "g", "category": "meat"}
            ]
        ),
        Recipe(
            id="recipe-5",
            name="Recipe 5",
            servings=4,
            prep_time_minutes=12,
            cook_time_minutes=18,
            calories_per_serving=380,
            protein_per_serving=22,
            carbs_per_serving=42,
            fat_per_serving=11,
            tags=["vegetarian", "dinner"],
            ingredients=[
                {"item": "beans", "quantity": 300, "unit": "g", "category": "pantry"}
            ]
        ),
        Recipe(
            id="recipe-6",
            name="Recipe 6",
            servings=4,
            prep_time_minutes=8,
            cook_time_minutes=12,
            calories_per_serving=320,
            protein_per_serving=18,
            carbs_per_serving=38,
            fat_per_serving=9,
            tags=["quick", "lunch", "dinner"],
            ingredients=[
                {"item": "eggs", "quantity": 8, "unit": "pieces", "category": "dairy"}
            ]
        ),
        Recipe(
            id="recipe-7",
            name="Recipe 7",
            servings=4,
            prep_time_minutes=18,
            cook_time_minutes=22,
            calories_per_serving=410,
            protein_per_serving=24,
            carbs_per_serving=48,
            fat_per_serving=14,
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
            Recipe(
                id=f"recipe-{i}",
                name=f"Recipe {i}",
                servings=4,
                prep_time_minutes=10,
                cook_time_minutes=20,
                calories_per_serving=400,
                protein_per_serving=20,
                carbs_per_serving=50,
                fat_per_serving=10,
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
            Recipe(
                id=f"recipe-{i}",
                name=f"Recipe {i}",
                servings=4,
                prep_time_minutes=10,
                cook_time_minutes=20,
                calories_per_serving=400,
                protein_per_serving=20,
                carbs_per_serving=50,
                fat_per_serving=10,
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
            Recipe(
                id=f"lunch-{i}",
                name=f"Lunch Recipe {i}",
                servings=4,
                prep_time_minutes=10,
                cook_time_minutes=15,
                calories_per_serving=300,
                protein_per_serving=15,
                carbs_per_serving=35,
                fat_per_serving=8,
                tags=["lunch"],
                ingredients=[]
            )
            for i in range(3)
        ]

        dinner_recipes = [
            Recipe(
                id=f"dinner-{i}",
                name=f"Dinner Recipe {i}",
                servings=4,
                prep_time_minutes=20,
                cook_time_minutes=30,
                calories_per_serving=450,
                protein_per_serving=30,
                carbs_per_serving=45,
                fat_per_serving=15,
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
            Recipe(
                id=f"recipe-{i}",
                name=f"Recipe {i}",
                servings=4,
                prep_time_minutes=10,
                cook_time_minutes=20,
                calories_per_serving=400,
                protein_per_serving=20,
                carbs_per_serving=50,
                fat_per_serving=10,
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
            Recipe(
                id=f"recipe-{i}",
                name=f"Recipe {i}",
                servings=4,
                prep_time_minutes=10,
                cook_time_minutes=20,
                calories_per_serving=400,
                protein_per_serving=20,
                carbs_per_serving=50,
                fat_per_serving=10,
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
        recipe = Recipe(
            id="test",
            name="Test",
            servings=4,
            prep_time_minutes=10,
            cook_time_minutes=20,
            calories_per_serving=400,
            protein_per_serving=20,
            carbs_per_serving=50,
            fat_per_serving=10,
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

    def test_weekly_plan_nutrition_accounts_for_household_portions(self):
        # Create 7 simple recipes with same nutrition values but unique IDs
        recipes = [
            Recipe(
                id=f"simple-{i}",
                name=f"Simple Recipe {i}",
                servings=4,
                prep_time_minutes=10,
                cook_time_minutes=20,
                calories_per_serving=400,
                protein_per_serving=20,
                carbs_per_serving=50,
                fat_per_serving=10,
                tags=["dinner"],
                ingredients=[]
            )
            for i in range(7)
        ]

        planner = MealPlanner(household_portions=2.0)
        plan = planner.generate_weekly_plan(recipes)

        # For 2.0 portions: 400 cal/serving * 2.0 = 800 cal per meal
        # 7 meals = 5600 total calories
        expected_total = 400 * 2.0 * 7
        assert abs(plan.total_calories - expected_total) < 0.01
