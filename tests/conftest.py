"""Pytest configuration and fixtures."""

# Tests now automatically get test API keys from config.py when pytest is detected

from app.recipes import Recipe


def create_test_recipe(
    recipe_id: str,
    name: str,
    servings: int = 4,
    prep_time_minutes: int = 10,
    cook_time_minutes: int = 20,
    calories: int = 400,
    protein: float = 20.0,
    carbs: float = 40.0,
    fat: float = 15.0,
    tags: list | None = None,
    ingredients: list | None = None,
    instructions: list | None = None,
) -> Recipe:
    """Helper to create test Recipe with new nested nutrition structure."""
    return Recipe(
        id=recipe_id,
        name=name,
        servings=servings,
        prep_time_minutes=prep_time_minutes,
        cook_time_minutes=cook_time_minutes,
        nutrition_per_serving={
            "calories": calories,
            "protein": protein,
            "carbs": carbs,
            "fat": fat,
        },
        tags=tags or [],
        ingredients=ingredients or [],
        instructions=instructions or [],
    )
