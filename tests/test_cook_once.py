"""Tests for the cook-once planning feature."""

import pytest

from app.planner import (
    DAYS_OF_WEEK,
    PlannedMeal,
    WeeklyPlan,
    add_cook_once_slots,
)
from app.recipes import Recipe

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_recipe(
    rid="r1",
    name="Test Recipe",
    reheats_well=False,
    stores_days=0,
    packs_well_as_lunch=False,
) -> Recipe:
    return Recipe(
        id=rid,
        name=name,
        servings=4,
        prep_time_minutes=10,
        cook_time_minutes=20,
        nutrition_per_serving={"calories": 500, "protein": 30, "carbs": 40, "fat": 15},
        tags=["dinner"],
        reheats_well=reheats_well,
        stores_days=stores_days,
        packs_well_as_lunch=packs_well_as_lunch,
    )


def make_meal(day, meal_type="dinner", recipe=None, portions=2.75, meal_source="fresh"):
    if recipe is None:
        recipe = make_recipe()
    return PlannedMeal(
        day=day,
        meal_type=meal_type,
        recipe=recipe,
        household_portions=portions,
        meal_source=meal_source,
    )


def make_plan(meals):
    return WeeklyPlan(meals=meals, daily_calorie_limit=None)


# ---------------------------------------------------------------------------
# Basic add_cook_once_slots tests
# ---------------------------------------------------------------------------

class TestAddCookOnceSlots:
    def test_no_flags_no_derived_slots(self):
        """A recipe with no flags produces no derived slots."""
        recipe = make_recipe(reheats_well=False, stores_days=0, packs_well_as_lunch=False)
        plan = make_plan([make_meal("Monday", recipe=recipe)])
        result = add_cook_once_slots(plan)
        assert len(result.meals) == 1

    def test_leftover_fills_next_day(self):
        """Monday dinner with reheats_well + stores_days=1 seeds Tuesday dinner."""
        recipe = make_recipe(reheats_well=True, stores_days=1)
        plan = make_plan([make_meal("Monday", recipe=recipe)])
        result = add_cook_once_slots(plan)

        assert len(result.meals) == 2
        leftover = next(m for m in result.meals if m.meal_source == "leftover")
        assert leftover.day == "Tuesday"
        assert leftover.meal_type == "dinner"
        assert leftover.linked_meal == "Monday:dinner"
        assert leftover.recipe.id == recipe.id

    def test_leftover_replaces_fresh_slot(self):
        """If Tuesday dinner is a fresh meal it is replaced by Monday's leftover.
        The default schedule fills every dinner slot, so replacement (not skip)
        is required for the feature to produce any output."""
        recipe = make_recipe(reheats_well=True, stores_days=2)
        tuesday_recipe = make_recipe(rid="r2", name="Other Recipe")
        plan = make_plan([
            make_meal("Monday", recipe=recipe),
            make_meal("Tuesday", recipe=tuesday_recipe),
        ])
        result = add_cook_once_slots(plan)

        leftovers = [m for m in result.meals if m.meal_source == "leftover"]
        assert len(leftovers) == 1
        assert leftovers[0].day == "Tuesday"  # replaced, not skipped
        # Total meal count stays the same: Monday(fresh) + Tuesday(leftover)
        assert len(result.meals) == 2

    def test_leftover_skips_derived_slot_fills_next(self):
        """If day+1 is already a derived slot, leftover with stores_days=2 moves to day+2."""
        recipe = make_recipe(reheats_well=True, stores_days=2)
        tue_derived = PlannedMeal(
            day="Tuesday", meal_type="dinner",
            recipe=make_recipe(rid="r2", name="Sunday Leftover"),
            household_portions=2.75, meal_source="leftover", linked_meal="Sunday:dinner",
        )
        plan = make_plan([make_meal("Monday", recipe=recipe), tue_derived])
        result = add_cook_once_slots(plan)

        mon_leftovers = [m for m in result.meals if m.linked_meal == "Monday:dinner"]
        assert len(mon_leftovers) == 1
        assert mon_leftovers[0].day == "Wednesday"  # Tuesday was derived → moved to Wednesday

    def test_leftover_only_fills_first_gap(self):
        """Even with stores_days=2, only the nearest free slot is filled."""
        recipe = make_recipe(reheats_well=True, stores_days=2)
        plan = make_plan([make_meal("Monday", recipe=recipe)])
        result = add_cook_once_slots(plan)

        leftovers = [m for m in result.meals if m.meal_source == "leftover"]
        assert len(leftovers) == 1
        assert leftovers[0].day == "Tuesday"

    def test_packed_lunch_next_weekday(self):
        """Monday dinner with packs_well seeds Tuesday lunch for adults."""
        recipe = make_recipe(packs_well_as_lunch=True)
        plan = make_plan([make_meal("Monday", recipe=recipe)])
        result = add_cook_once_slots(plan, adult_portions=2.0)

        packed = next(m for m in result.meals if m.meal_source == "packed_lunch")
        assert packed.day == "Tuesday"
        assert packed.meal_type == "lunch"
        assert packed.household_portions == 2.0
        assert packed.linked_meal == "Monday:dinner"

    def test_packed_lunch_skips_occupied_slot(self):
        """If Tuesday lunch is occupied, no packed lunch is created (next-only rule)."""
        recipe = make_recipe(packs_well_as_lunch=True)
        tuesday_lunch = make_meal("Tuesday", meal_type="lunch", recipe=make_recipe(rid="r2"))
        plan = make_plan([
            make_meal("Monday", recipe=recipe),
            tuesday_lunch,
        ])
        result = add_cook_once_slots(plan)

        packed = [m for m in result.meals if m.meal_source == "packed_lunch"]
        assert len(packed) == 0

    def test_derived_slots_do_not_seed_further(self):
        """Derived slots (leftover) never seed additional derived slots."""
        recipe = make_recipe(reheats_well=True, stores_days=2, packs_well_as_lunch=True)
        plan = make_plan([make_meal("Monday", recipe=recipe)])
        result = add_cook_once_slots(plan)

        # Only the original Monday meal should seed derived slots.
        # The Tuesday leftover should NOT itself seed a Wednesday leftover.
        derived = [m for m in result.meals if m.meal_source != "fresh"]
        for d in derived:
            assert d.meal_source in ("leftover", "packed_lunch")
            # Make sure no derived slot was created FROM a derived slot
            # (linked_meal must point to original Monday:dinner)
            assert d.linked_meal == "Monday:dinner"


# ---------------------------------------------------------------------------
# Edge cases: Sunday / Friday
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_sunday_dinner_no_weekday_packed_lunch(self):
        """Sunday dinner never generates a weekday packed lunch (Monday is after Sunday
        but isn't 'next_day in WEEKDAYS after Sunday in the linear list')."""
        recipe = make_recipe(packs_well_as_lunch=True)
        plan = make_plan([make_meal("Sunday", recipe=recipe)])
        result = add_cook_once_slots(plan)

        packed = [m for m in result.meals if m.meal_source == "packed_lunch"]
        assert len(packed) == 0, "Sunday dinner must not seed a packed lunch"

    def test_sunday_dinner_no_leftover(self):
        """Sunday dinner (idx=6) cannot create a leftover because target_idx >= 7."""
        recipe = make_recipe(reheats_well=True, stores_days=2)
        plan = make_plan([make_meal("Sunday", recipe=recipe)])
        result = add_cook_once_slots(plan)

        leftovers = [m for m in result.meals if m.meal_source == "leftover"]
        assert len(leftovers) == 0

    def test_friday_dinner_no_weekday_packed_lunch(self):
        """Friday dinner: next day is Saturday, which is not in WEEKDAYS."""
        recipe = make_recipe(packs_well_as_lunch=True)
        plan = make_plan([make_meal("Friday", recipe=recipe)])
        result = add_cook_once_slots(plan)

        packed = [m for m in result.meals if m.meal_source == "packed_lunch"]
        assert len(packed) == 0

    def test_friday_dinner_leftover_saturday(self):
        """Friday dinner CAN create a Saturday leftover (not limited to weekdays)."""
        recipe = make_recipe(reheats_well=True, stores_days=1)
        plan = make_plan([make_meal("Friday", recipe=recipe)])
        result = add_cook_once_slots(plan)

        leftovers = [m for m in result.meals if m.meal_source == "leftover"]
        assert len(leftovers) == 1
        assert leftovers[0].day == "Saturday"

    def test_saturday_dinner_packs_no_weekday_lunch(self):
        """Saturday is NOT in WEEKDAYS so no packed lunch is generated."""
        recipe = make_recipe(packs_well_as_lunch=True)
        plan = make_plan([make_meal("Saturday", recipe=recipe)])
        result = add_cook_once_slots(plan)

        packed = [m for m in result.meals if m.meal_source == "packed_lunch"]
        assert len(packed) == 0

    def test_thursday_dinner_packs_friday_lunch(self):
        """Thursday → Friday lunch (both weekdays)."""
        recipe = make_recipe(packs_well_as_lunch=True)
        plan = make_plan([make_meal("Thursday", recipe=recipe)])
        result = add_cook_once_slots(plan)

        packed = [m for m in result.meals if m.meal_source == "packed_lunch"]
        assert len(packed) == 1
        assert packed[0].day == "Friday"


# ---------------------------------------------------------------------------
# Plan preservation
# ---------------------------------------------------------------------------

class TestPlanPreservation:
    def test_daily_calorie_limit_preserved(self):
        recipe = make_recipe(reheats_well=True, stores_days=1)
        plan = WeeklyPlan(meals=[make_meal("Monday", recipe=recipe)], daily_calorie_limit=1600)
        result = add_cook_once_slots(plan)
        assert result.daily_calorie_limit == 1600

    def test_original_meals_retained(self):
        recipe = make_recipe(reheats_well=True, stores_days=1)
        original = make_meal("Monday", recipe=recipe)
        plan = make_plan([original])
        result = add_cook_once_slots(plan)

        fresh = [m for m in result.meals if m.meal_source == "fresh"]
        assert len(fresh) == 1
        assert fresh[0].day == "Monday"


# ---------------------------------------------------------------------------
# main.py helpers (imported here to avoid circular deps with Flask app context)
# ---------------------------------------------------------------------------

class TestConvertPlanToManualPlan:
    def test_round_trip(self):
        """_convert_plan_to_manual_plan serialises meal_source and linked_meal."""
        from app.main import _convert_plan_to_manual_plan

        recipe = make_recipe()
        fresh = PlannedMeal(
            day="Monday", meal_type="dinner", recipe=recipe,
            household_portions=2.75, meal_source="fresh",
        )
        leftover = PlannedMeal(
            day="Tuesday", meal_type="dinner", recipe=recipe,
            household_portions=2.75, meal_source="leftover", linked_meal="Monday:dinner",
        )
        plan = make_plan([fresh, leftover])
        manual = _convert_plan_to_manual_plan(plan)

        assert manual["Monday"]["dinner"]["meal_source"] == "fresh"
        assert manual["Monday"]["dinner"]["linked_meal"] is None
        assert manual["Tuesday"]["dinner"]["meal_source"] == "leftover"
        assert manual["Tuesday"]["dinner"]["linked_meal"] == "Monday:dinner"

    def test_recipe_id_and_servings(self):
        from app.main import _convert_plan_to_manual_plan

        recipe = make_recipe(rid="beef-stew")
        plan = make_plan([make_meal("Wednesday", recipe=recipe, portions=3.0)])
        manual = _convert_plan_to_manual_plan(plan)

        assert manual["Wednesday"]["dinner"]["recipe_id"] == "beef-stew"
        assert manual["Wednesday"]["dinner"]["servings"] == 3.0


class TestSerializePlan:
    def test_meal_source_in_serialized_output(self):
        from app.main import _serialize_plan

        recipe = make_recipe()
        packed = PlannedMeal(
            day="Tuesday", meal_type="lunch", recipe=recipe,
            household_portions=2.0, meal_source="packed_lunch", linked_meal="Monday:dinner",
        )
        plan = make_plan([packed])
        serialized = _serialize_plan(plan)

        meal_dict = serialized["meals"][0]
        assert meal_dict["meal_source"] == "packed_lunch"
        assert meal_dict["linked_meal"] == "Monday:dinner"


class TestRegenerateFromManualPlan:
    def test_preserves_meal_source(self, monkeypatch):
        """_regenerate_from_manual_plan reads meal_source and linked_meal from manual_plan."""
        import app.main as main_module
        from app.main import _regenerate_from_manual_plan

        recipe = make_recipe(rid="chicken-curry", name="Chicken Curry")
        recipes = [recipe]

        # Patch module-level manual_plan
        monkeypatch.setattr(
            main_module,
            "manual_plan",
            {
                "Monday": {
                    "dinner": {
                        "recipe_id": "chicken-curry",
                        "servings": 2.75,
                        "meal_source": "fresh",
                        "linked_meal": None,
                    }
                },
                "Tuesday": {
                    "dinner": {
                        "recipe_id": "chicken-curry",
                        "servings": 2.75,
                        "meal_source": "leftover",
                        "linked_meal": "Monday:dinner",
                    }
                },
            },
        )

        _regenerate_from_manual_plan(recipes)

        plan = main_module.current_plan
        assert plan is not None
        mon = next(m for m in plan.meals if m.day == "Monday")
        tue = next(m for m in plan.meals if m.day == "Tuesday")
        assert mon.meal_source == "fresh"
        assert tue.meal_source == "leftover"
        assert tue.linked_meal == "Monday:dinner"
