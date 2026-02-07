import random
from dataclasses import dataclass
from typing import Any

from app.recipes import Recipe


DAYS_OF_WEEK = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


@dataclass
class PlannedMeal:
    day: str
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


@dataclass
class WeeklyPlan:
    meals: list[PlannedMeal]

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

    @property
    def avg_daily_calories(self) -> float:
        return self.total_calories / len(self.meals)

    @property
    def avg_daily_protein(self) -> float:
        return self.total_protein / len(self.meals)

    @property
    def avg_daily_carbs(self) -> float:
        return self.total_carbs / len(self.meals)

    @property
    def avg_daily_fat(self) -> float:
        return self.total_fat / len(self.meals)


class MealPlanner:
    def __init__(self, household_portions: float):
        self.household_portions = household_portions

    def generate_weekly_plan(self, available_recipes: list[Recipe]) -> WeeklyPlan:
        if len(available_recipes) < 7:
            raise ValueError("Need at least 7 recipes to generate a weekly meal plan")

        # Randomly select 7 recipes without repeats
        selected_recipes = random.sample(available_recipes, 7)

        # Create planned meals for each day
        meals = [
            PlannedMeal(
                day=DAYS_OF_WEEK[i],
                recipe=recipe,
                household_portions=self.household_portions
            )
            for i, recipe in enumerate(selected_recipes)
        ]

        return WeeklyPlan(meals=meals)
