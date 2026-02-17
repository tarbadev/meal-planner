import random
from dataclasses import dataclass
from typing import Any

from app.recipes import Recipe

DAYS_OF_WEEK = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def get_meal_slots_from_schedule(schedule: dict[str, list[str]]) -> list[tuple[str, str]]:
    """Convert meal schedule to flat list of (day, meal_type) tuples.

    Example:
        {"Monday": ["dinner"], "Tuesday": ["lunch", "dinner"]}
        -> [("Monday", "dinner"), ("Tuesday", "lunch"), ("Tuesday", "dinner")]

    Args:
        schedule: Dictionary mapping day names to list of meal types

    Returns:
        List of (day, meal_type) tuples representing all meal slots
    """
    slots = []
    for day, meal_types in schedule.items():
        for meal_type in meal_types:
            slots.append((day, meal_type))
    return slots


@dataclass
class PlannedMeal:
    day: str
    meal_type: str  # "lunch", "dinner", "breakfast", "snack"
    recipe: Recipe
    household_portions: float

    @property
    def portions(self) -> float:
        return self.household_portions

    @property
    def scaled_ingredients(self) -> list[dict[str, Any]]:
        """Scale ingredient quantities based on household portions."""
        scale_factor = self.household_portions / self.recipe.servings
        scaled = []

        for ingredient in self.recipe.ingredients:
            scaled_ingredient = ingredient.copy()
            scaled_ingredient["quantity"] = ingredient["quantity"] * scale_factor
            scaled.append(scaled_ingredient)

        return scaled

    @property
    def calories(self) -> float:
        return self.recipe.calories_per_serving * self.household_portions

    @property
    def protein(self) -> float:
        return self.recipe.protein_per_serving * self.household_portions

    @property
    def carbs(self) -> float:
        return self.recipe.carbs_per_serving * self.household_portions

    @property
    def fat(self) -> float:
        return self.recipe.fat_per_serving * self.household_portions

    # Extended nutrition properties
    def get_nutrition_value(self, field: str) -> float:
        """Get a nutrition value scaled by portions, handling None values."""
        value = self.recipe.nutrition_per_serving.get(field)
        if value is None:
            return 0.0
        return value * self.household_portions

    @property
    def saturated_fat(self) -> float:
        return self.get_nutrition_value('saturated_fat')

    @property
    def polyunsaturated_fat(self) -> float:
        return self.get_nutrition_value('polyunsaturated_fat')

    @property
    def monounsaturated_fat(self) -> float:
        return self.get_nutrition_value('monounsaturated_fat')

    @property
    def sodium(self) -> float:
        return self.get_nutrition_value('sodium')

    @property
    def potassium(self) -> float:
        return self.get_nutrition_value('potassium')

    @property
    def fiber(self) -> float:
        return self.get_nutrition_value('fiber')

    @property
    def sugar(self) -> float:
        return self.get_nutrition_value('sugar')

    @property
    def vitamin_a(self) -> float:
        return self.get_nutrition_value('vitamin_a')

    @property
    def vitamin_c(self) -> float:
        return self.get_nutrition_value('vitamin_c')

    @property
    def calcium(self) -> float:
        return self.get_nutrition_value('calcium')

    @property
    def iron(self) -> float:
        return self.get_nutrition_value('iron')


@dataclass
class WeeklyPlan:
    meals: list[PlannedMeal]
    daily_calorie_limit: float | None = None

    # Core nutrition totals
    @property
    def total_calories(self) -> float:
        return sum(meal.calories for meal in self.meals)

    @property
    def total_protein(self) -> float:
        return sum(meal.protein for meal in self.meals)

    @property
    def total_carbs(self) -> float:
        return sum(meal.carbs for meal in self.meals)

    @property
    def total_fat(self) -> float:
        return sum(meal.fat for meal in self.meals)

    # Extended nutrition totals
    @property
    def total_saturated_fat(self) -> float:
        return sum(meal.saturated_fat for meal in self.meals)

    @property
    def total_polyunsaturated_fat(self) -> float:
        return sum(meal.polyunsaturated_fat for meal in self.meals)

    @property
    def total_monounsaturated_fat(self) -> float:
        return sum(meal.monounsaturated_fat for meal in self.meals)

    @property
    def total_sodium(self) -> float:
        return sum(meal.sodium for meal in self.meals)

    @property
    def total_potassium(self) -> float:
        return sum(meal.potassium for meal in self.meals)

    @property
    def total_fiber(self) -> float:
        return sum(meal.fiber for meal in self.meals)

    @property
    def total_sugar(self) -> float:
        return sum(meal.sugar for meal in self.meals)

    @property
    def total_vitamin_a(self) -> float:
        return sum(meal.vitamin_a for meal in self.meals)

    @property
    def total_vitamin_c(self) -> float:
        return sum(meal.vitamin_c for meal in self.meals)

    @property
    def total_calcium(self) -> float:
        return sum(meal.calcium for meal in self.meals)

    @property
    def total_iron(self) -> float:
        return sum(meal.iron for meal in self.meals)

    # Core nutrition averages
    @property
    def avg_daily_calories(self) -> float:
        return self.total_calories / len(self.meals) if self.meals else 0

    @property
    def avg_daily_protein(self) -> float:
        return self.total_protein / len(self.meals) if self.meals else 0

    @property
    def avg_daily_carbs(self) -> float:
        return self.total_carbs / len(self.meals) if self.meals else 0

    @property
    def avg_daily_fat(self) -> float:
        return self.total_fat / len(self.meals) if self.meals else 0

    # Extended nutrition averages
    @property
    def avg_daily_saturated_fat(self) -> float:
        return self.total_saturated_fat / len(self.meals) if self.meals else 0

    @property
    def avg_daily_polyunsaturated_fat(self) -> float:
        return self.total_polyunsaturated_fat / len(self.meals) if self.meals else 0

    @property
    def avg_daily_monounsaturated_fat(self) -> float:
        return self.total_monounsaturated_fat / len(self.meals) if self.meals else 0

    @property
    def avg_daily_sodium(self) -> float:
        return self.total_sodium / len(self.meals) if self.meals else 0

    @property
    def avg_daily_potassium(self) -> float:
        return self.total_potassium / len(self.meals) if self.meals else 0

    @property
    def avg_daily_fiber(self) -> float:
        return self.total_fiber / len(self.meals) if self.meals else 0

    @property
    def avg_daily_sugar(self) -> float:
        return self.total_sugar / len(self.meals) if self.meals else 0

    @property
    def avg_daily_vitamin_a(self) -> float:
        return self.total_vitamin_a / len(self.meals) if self.meals else 0

    @property
    def avg_daily_vitamin_c(self) -> float:
        return self.total_vitamin_c / len(self.meals) if self.meals else 0

    @property
    def avg_daily_calcium(self) -> float:
        return self.total_calcium / len(self.meals) if self.meals else 0

    @property
    def avg_daily_iron(self) -> float:
        return self.total_iron / len(self.meals) if self.meals else 0

    def get_daily_nutrition(self) -> dict[str, dict[str, float]]:
        """Calculate nutrition totals for each day.

        Returns:
            Dictionary mapping day names to nutrition data:
            {
                "Monday": {"calories": 2000, "protein": 150, ...},
                "Tuesday": {"calories": 1800, "protein": 140, ...},
                ...
            }
        """
        daily_totals: dict[str, dict[str, float]] = {}

        for meal in self.meals:
            if meal.day not in daily_totals:
                daily_totals[meal.day] = {
                    "calories": 0,
                    "protein": 0,
                    "carbs": 0,
                    "fat": 0,
                }

            daily_totals[meal.day]["calories"] += meal.calories
            daily_totals[meal.day]["protein"] += meal.protein
            daily_totals[meal.day]["carbs"] += meal.carbs
            daily_totals[meal.day]["fat"] += meal.fat

        return daily_totals


class MealPlanner:
    def __init__(
        self,
        household_portions: float,
        meal_schedule: dict[str, list[str]] = None,
        daily_calorie_limit: float | None = None,
    ):
        self.household_portions = household_portions
        self.daily_calorie_limit = daily_calorie_limit
        # Default to simple 7-dinner schedule if not provided
        if meal_schedule is None:
            meal_schedule = {day: ["dinner"] for day in DAYS_OF_WEEK}
        self.meal_schedule = meal_schedule

    def _select_recipe(
        self,
        suitable_recipes: list[Recipe],
        day: str,
        slots_per_day: dict[str, int],
        slots_filled_today: dict[str, int],
        daily_calories_used: dict[str, float],
    ) -> Recipe:
        """Select a recipe preferring ones within the daily calorie budget.

        When daily_calorie_limit is None, picks randomly (existing behaviour).
        When set, distributes remaining budget evenly across remaining slots.
        Recipes with 0 calories are treated neutrally and always fit.
        If no recipe fits, picks the lowest-calorie option (never leaves a slot empty).
        """
        if self.daily_calorie_limit is None:
            return random.choice(suitable_recipes)

        calories_used = daily_calories_used.get(day, 0.0)
        remaining_budget = self.daily_calorie_limit - calories_used
        filled = slots_filled_today.get(day, 0)
        remaining_slots = slots_per_day[day] - filled  # >= 1 (includes current slot)
        budget_per_slot = remaining_budget / remaining_slots

        fitting = [
            r for r in suitable_recipes
            if r.calories_per_serving == 0
            or r.calories_per_serving * self.household_portions <= budget_per_slot
        ]

        if fitting:
            return random.choice(fitting)

        # Fallback: pick lowest-calorie to minimise overage, never leave slot empty
        return min(suitable_recipes, key=lambda r: r.calories_per_serving)

    def generate_weekly_plan(self, available_recipes: list[Recipe]) -> WeeklyPlan:
        # Get meal slots from schedule
        meal_slots = get_meal_slots_from_schedule(self.meal_schedule)
        num_meals = len(meal_slots)

        # Validate enough recipes
        if len(available_recipes) < num_meals:
            raise ValueError(
                f"Need at least {num_meals} recipes to generate meal plan. "
                f"Only {len(available_recipes)} recipes available."
            )

        # Pre-compute total slots per day for calorie budget distribution
        slots_per_day: dict[str, int] = {}
        for day, _ in meal_slots:
            slots_per_day[day] = slots_per_day.get(day, 0) + 1

        meals = []
        used_recipes: set[str] = set()
        daily_calories_used: dict[str, float] = {}
        slots_filled_today: dict[str, int] = {}

        for day, meal_type in meal_slots:
            # Filter recipes that have this meal type tag AND haven't been used
            suitable_recipes = [
                r for r in available_recipes
                if meal_type in r.tags and r.id not in used_recipes
            ]

            # Fallback: if no suitable recipes, use any unused recipe
            if not suitable_recipes:
                suitable_recipes = [
                    r for r in available_recipes
                    if r.id not in used_recipes
                ]

            if not suitable_recipes:
                raise ValueError(f"Not enough recipes for {day} {meal_type}")

            recipe = self._select_recipe(
                suitable_recipes, day, slots_per_day, slots_filled_today, daily_calories_used
            )
            used_recipes.add(recipe.id)

            cal = recipe.calories_per_serving * self.household_portions
            daily_calories_used[day] = daily_calories_used.get(day, 0.0) + cal
            slots_filled_today[day] = slots_filled_today.get(day, 0) + 1

            meals.append(PlannedMeal(
                day=day,
                meal_type=meal_type,
                recipe=recipe,
                household_portions=self.household_portions
            ))

        return WeeklyPlan(meals=meals, daily_calorie_limit=self.daily_calorie_limit)
