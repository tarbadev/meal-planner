import logging
import random
from dataclasses import dataclass
from typing import Any

from app.recipes import Recipe

logger = logging.getLogger(__name__)

DAYS_OF_WEEK = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

# Tags that identify a recipe as belonging to a specific meal type.
# Used to avoid assigning, e.g., a "dinner" recipe to a "lunch" slot as a budget fallback.
_MEAL_TYPE_TAGS: frozenset[str] = frozenset({"breakfast", "lunch", "dinner", "snack"})


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
    meal_source: str = "fresh"       # "fresh" | "leftover" | "packed_lunch"
    linked_meal: str | None = None   # "{day}:{meal_type}" of the source cook slot

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
            scaled_ingredient["quantity"] = ingredient.get("quantity", 0) * scale_factor
            scaled.append(scaled_ingredient)

        return scaled

    @property
    def calories(self) -> float:
        """Calories per serving (one person). Use scaled_ingredients for household quantities."""
        return self.recipe.calories_per_serving

    @property
    def protein(self) -> float:
        return self.recipe.protein_per_serving

    @property
    def carbs(self) -> float:
        return self.recipe.carbs_per_serving

    @property
    def fat(self) -> float:
        return self.recipe.fat_per_serving

    # Extended nutrition properties
    def get_nutrition_value(self, field: str) -> float:
        """Get a per-serving nutrition value, handling None values."""
        value = self.recipe.nutrition_per_serving.get(field)
        if value is None:
            return 0.0
        return value

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
        meal_calorie_splits: dict[str, float] | None = None,
    ):
        self.household_portions = household_portions
        self.daily_calorie_limit = daily_calorie_limit
        # Relative weights used to split the daily budget across meal types.
        # A missing key falls back to weight 1.0 (equal share).
        self.meal_calorie_splits: dict[str, float] = meal_calorie_splits or {}
        if meal_schedule is None:
            meal_schedule = {day: ["dinner"] for day in DAYS_OF_WEEK}
        self.meal_schedule = meal_schedule

    def _select_recipe(
        self,
        suitable_recipes: list[Recipe],
        meal_type_budget: float | None,
        budget_fallback_pool: list[Recipe] | None = None,
    ) -> Recipe:
        """Select a recipe that fits within *meal_type_budget* calories/serving.

        When meal_type_budget is None (no calorie limit configured), picks
        randomly.  Recipes with 0 calories are treated neutrally and always
        fit.

        When no meal-type-tagged recipe fits the budget, the search widens to
        *budget_fallback_pool* (all remaining unused recipes) before falling
        back to the lowest-calorie tagged option.  This prevents a high-calorie
        first meal from forcing subsequent slots over the daily limit simply
        because the tagged pool has no low-calorie candidates.
        """
        if meal_type_budget is None:
            return random.choice(suitable_recipes)

        fitting = [
            r for r in suitable_recipes
            if r.calories_per_serving == 0
            or r.calories_per_serving <= meal_type_budget
        ]

        if fitting:
            return random.choice(fitting)

        # No tagged recipe fits — try any unused recipe within budget
        if budget_fallback_pool:
            fitting_any = [
                r for r in budget_fallback_pool
                if r.calories_per_serving == 0
                or r.calories_per_serving <= meal_type_budget
            ]
            if fitting_any:
                return random.choice(fitting_any)

        # Last resort: lowest-calorie tagged recipe to minimise overage
        return min(suitable_recipes, key=lambda r: r.calories_per_serving)

    def _compute_meal_budgets(
        self, meal_slots: list[tuple[str, str]]
    ) -> dict[tuple[str, str], float | None]:
        """Pre-compute the per-slot calorie budget for every (day, meal_type) pair.

        Budget is proportional to each meal type's weight in MEAL_CALORIE_SPLITS
        relative to the total weight of all meal types scheduled that day.
        A day with only dinner gets the full daily limit; a day with lunch +
        dinner splits it ~46 / 54 % by default.
        """
        if self.daily_calorie_limit is None:
            return dict.fromkeys(meal_slots)

        # Group meal types per day preserving schedule order
        day_meal_types: dict[str, list[str]] = {}
        for day, meal_type in meal_slots:
            day_meal_types.setdefault(day, []).append(meal_type)

        budgets: dict[tuple[str, str], float] = {}
        for day, meal_types in day_meal_types.items():
            total_weight = sum(
                self.meal_calorie_splits.get(mt, 1.0) for mt in meal_types
            )
            for meal_type in meal_types:
                weight = self.meal_calorie_splits.get(meal_type, 1.0)
                budgets[(day, meal_type)] = weight / total_weight * self.daily_calorie_limit

        return budgets

    def generate_weekly_plan(self, available_recipes: list[Recipe]) -> WeeklyPlan:
        meal_slots = get_meal_slots_from_schedule(self.meal_schedule)
        num_meals = len(meal_slots)

        logger.info("Generating weekly plan", extra={"recipe_pool_size": len(available_recipes), "meal_slots": num_meals})

        if len(available_recipes) < num_meals:
            raise ValueError(
                f"Need at least {num_meals} recipes to generate meal plan. "
                f"Only {len(available_recipes)} recipes available."
            )

        # Proportional targets: the ideal per-meal share of the daily limit.
        proportional_budgets = self._compute_meal_budgets(meal_slots)

        meals = []
        used_recipes: set[str] = set()
        daily_calories_used: dict[str, float] = {}

        for day, meal_type in meal_slots:
            logger.debug("Filling meal slot", extra={"day": day, "meal_type": meal_type})
            suitable_recipes = [
                r for r in available_recipes
                if meal_type in r.tags and r.id not in used_recipes
            ]

            if not suitable_recipes:
                logger.warning("No suitable recipes for meal type, using fallback", extra={"day": day, "meal_type": meal_type})
                suitable_recipes = [
                    r for r in available_recipes
                    if r.id not in used_recipes
                ]

            if not suitable_recipes:
                raise ValueError(f"Not enough recipes for {day} {meal_type}")

            # Effective budget = min(proportional share, remaining daily budget).
            # This means: prefer the meal-type-appropriate portion size, but if
            # an earlier meal on this day overshot (via fallback), tighten the
            # cap so the running total stays within the daily limit.
            proportional = proportional_budgets[(day, meal_type)]
            if proportional is not None:
                remaining = self.daily_calorie_limit - daily_calories_used.get(day, 0.0)
                effective_budget: float | None = min(proportional, remaining)
            else:
                effective_budget = None

            # Recipes with no meal-type tag are generic and can fill any slot as
            # a last resort if no properly-tagged recipe fits within the budget.
            untagged_unused = [
                r for r in available_recipes
                if r.id not in used_recipes
                and not _MEAL_TYPE_TAGS.intersection(r.tags)
            ]
            recipe = self._select_recipe(suitable_recipes, effective_budget, budget_fallback_pool=untagged_unused)
            used_recipes.add(recipe.id)
            daily_calories_used[day] = daily_calories_used.get(day, 0.0) + recipe.calories_per_serving

            meals.append(PlannedMeal(
                day=day,
                meal_type=meal_type,
                recipe=recipe,
                household_portions=self.household_portions
            ))

        logger.info("Weekly plan generated", extra={"total_meals": len(meals)})
        return WeeklyPlan(meals=meals, daily_calorie_limit=self.daily_calorie_limit)


WEEKDAYS = {"Monday", "Tuesday", "Wednesday", "Thursday", "Friday"}


def add_cook_once_slots(
    plan: WeeklyPlan,
    adult_portions: float = 2.0,
    no_cook_slots: frozenset[tuple[str, str]] = frozenset(),
    max_derived: int = 2,
) -> WeeklyPlan:
    """Post-process a WeeklyPlan by replacing/filling slots with leftover/packed-lunch meals.

    Leftover dinners: REPLACE the next day's fresh dinner.  The default schedule
    fills every dinner slot, so a "skip occupied" approach would never fire.
    Derived slots are never overwritten — if day+1 is already a derived meal,
    the search continues to day+2 (up to stores_days, max 2).

    Packed lunches: only FILL empty slots (weekday lunch slots are empty by
    default, so no replacement needed there).

    Derived slots don't seed further derived slots: before processing a source
    meal we confirm it is still "fresh" in new_meals (prevents cascading when an
    earlier iteration already replaced it with a leftover).

    max_derived caps how many derived meals (packed_lunch + leftover combined)
    can be created from one cooked dinner.  Use 1 to prevent the same recipe
    appearing more than twice (cook + one re-use).
    """
    new_meals = list(plan.meals)

    def _find(day, meal_type):
        return next((m for m in new_meals if m.day == day and m.meal_type == meal_type), None)

    for meal in plan.meals:
        if meal.meal_source != "fresh" or meal.meal_type != "dinner":
            continue

        # Skip if this meal was itself replaced by a leftover in an earlier iteration
        current = _find(meal.day, "dinner")
        if current is None or current.meal_source != "fresh":
            continue

        recipe = meal.recipe
        source_key = f"{meal.day}:dinner"
        try:
            day_idx = DAYS_OF_WEEK.index(meal.day)
        except ValueError:
            continue

        derived_count = 0  # track derived meals created for this source

        # Packed lunch: next weekday only, adults only — fill empty slots or replace no-cook fresh lunch
        if derived_count < max_derived and recipe.packs_well_as_lunch and meal.day in WEEKDAYS:
            if day_idx + 1 < len(DAYS_OF_WEEK):
                next_day = DAYS_OF_WEEK[day_idx + 1]
                if next_day in WEEKDAYS:
                    existing_lunch = _find(next_day, "lunch")
                    slot_is_no_cook = (next_day, "lunch") in no_cook_slots
                    # Fill empty slot OR replace a no-cook fresh lunch
                    if existing_lunch is None or (slot_is_no_cook and existing_lunch.meal_source == "fresh"):
                        if existing_lunch is not None:
                            new_meals.remove(existing_lunch)
                        new_meals.append(PlannedMeal(
                            day=next_day, meal_type="lunch", recipe=recipe,
                            household_portions=adult_portions,
                            meal_source="packed_lunch", linked_meal=source_key,
                        ))
                        derived_count += 1

        # Leftover dinner: replace next fresh dinner; skip over already-derived slots
        if derived_count < max_derived and recipe.reheats_well and recipe.stores_days >= 1:
            for offset in range(1, min(recipe.stores_days, 2) + 1):
                target_idx = day_idx + offset
                if target_idx >= len(DAYS_OF_WEEK):
                    break
                target_day = DAYS_OF_WEEK[target_idx]
                target = _find(target_day, "dinner")

                if target is not None and target.meal_source == "fresh":
                    # Replace the independently-planned fresh dinner with a leftover
                    new_meals.remove(target)
                    new_meals.append(PlannedMeal(
                        day=target_day, meal_type="dinner", recipe=recipe,
                        household_portions=meal.household_portions,
                        meal_source="leftover", linked_meal=source_key,
                    ))
                    break
                elif target is None:
                    # Empty slot — fill it
                    new_meals.append(PlannedMeal(
                        day=target_day, meal_type="dinner", recipe=recipe,
                        household_portions=meal.household_portions,
                        meal_source="leftover", linked_meal=source_key,
                    ))
                    break
                # target is a derived slot — don't overwrite, try next offset

    return WeeklyPlan(meals=new_meals, daily_calorie_limit=plan.daily_calorie_limit)
