import json
import os
import tempfile
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any


class RecipeLoadError(Exception):
    """Raised when recipes cannot be loaded from file."""
    pass


class RecipeSaveError(Exception):
    """Raised when recipes cannot be saved to file."""
    pass


@dataclass
class Recipe:
    id: str
    name: str
    servings: int
    prep_time_minutes: int
    cook_time_minutes: int
    nutrition_per_serving: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    ingredients: list[dict[str, Any]] = field(default_factory=list)
    instructions: list[str] = field(default_factory=list)

    @property
    def total_time_minutes(self) -> int:
        return self.prep_time_minutes + self.cook_time_minutes

    # Backward compatibility properties for accessing flat nutrition fields
    @property
    def calories_per_serving(self) -> int:
        return self.nutrition_per_serving.get("calories", 0)

    @property
    def protein_per_serving(self) -> float:
        return self.nutrition_per_serving.get("protein", 0.0)

    @property
    def carbs_per_serving(self) -> float:
        return self.nutrition_per_serving.get("carbs", 0.0)

    @property
    def fat_per_serving(self) -> float:
        return self.nutrition_per_serving.get("fat", 0.0)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Recipe":
        """Create Recipe from dictionary, supporting both old and new formats.

        Old format: flat nutrition fields (calories_per_serving, protein_per_serving, etc.)
        New format: nested nutrition_per_serving dict
        """
        # Check for basic required fields
        basic_required = ["id", "name", "servings", "prep_time_minutes", "cook_time_minutes"]
        missing = [f for f in basic_required if f not in data]
        if missing:
            raise ValueError(f"Missing required fields: {', '.join(missing)}")

        # Handle nutrition: check if using new nested format or old flat format
        if "nutrition_per_serving" in data:
            # New format: use nested structure directly
            nutrition_per_serving = data["nutrition_per_serving"]
        else:
            # Old format: migrate flat fields to nested structure
            # Required nutrition fields in old format
            old_required = ["calories_per_serving", "protein_per_serving", "carbs_per_serving", "fat_per_serving"]
            missing_old = [f for f in old_required if f not in data]
            if missing_old:
                raise ValueError(f"Missing required nutrition fields: {', '.join(missing_old)}")

            # Migrate to new structure
            nutrition_per_serving = {
                "calories": data["calories_per_serving"],
                "protein": data["protein_per_serving"],
                "carbs": data["carbs_per_serving"],
                "fat": data["fat_per_serving"],
                # New fields default to None
                "saturated_fat": None,
                "polyunsaturated_fat": None,
                "monounsaturated_fat": None,
                "sodium": None,
                "potassium": None,
                "fiber": None,
                "sugar": None,
                "vitamin_a": None,
                "vitamin_c": None,
                "calcium": None,
                "iron": None
            }

        return cls(
            id=data["id"],
            name=data["name"],
            servings=data["servings"],
            prep_time_minutes=data["prep_time_minutes"],
            cook_time_minutes=data["cook_time_minutes"],
            nutrition_per_serving=nutrition_per_serving,
            tags=data.get("tags", []),
            ingredients=data.get("ingredients", []),
            instructions=data.get("instructions", []),
        )


def load_recipes(file_path: Path | str) -> list[Recipe]:
    file_path = Path(file_path)

    if not file_path.exists():
        raise RecipeLoadError(f"Recipe file not found: {file_path}")

    try:
        with open(file_path) as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise RecipeLoadError(f"Invalid JSON in recipe file: {e}")

    if "recipes" not in data:
        raise RecipeLoadError("Recipe file must contain a 'recipes' key")

    return [Recipe.from_dict(r) for r in data["recipes"]]


def save_recipes(file_path: Path | str, recipes: list[Recipe]) -> None:
    """Save recipes to JSON file with atomic write.

    Args:
        file_path: Path to the JSON file
        recipes: List of Recipe objects to save

    Raises:
        RecipeSaveError: If the file cannot be written
    """
    file_path = Path(file_path)

    # Convert Recipe objects to dicts
    recipes_data = [asdict(recipe) for recipe in recipes]

    # Wrap in expected structure
    data = {"recipes": recipes_data}

    try:
        # Atomic write: write to temp file first, then replace
        # Use the same directory to ensure same filesystem for atomic rename
        temp_fd, temp_path = tempfile.mkstemp(
            dir=file_path.parent,
            prefix=".recipes_tmp_",
            suffix=".json"
        )

        try:
            # Write to temp file
            with os.fdopen(temp_fd, 'w') as f:
                json.dump(data, f, indent=2)

            # Atomic replace
            os.replace(temp_path, file_path)

        except Exception:
            # Clean up temp file if something went wrong
            try:
                os.unlink(temp_path)
            except OSError:
                pass
            raise

    except (IOError, OSError, PermissionError) as e:
        raise RecipeSaveError(f"Failed to save recipes to {file_path}: {e}")


def update_recipe(recipes: list[Recipe], updated_recipe: Recipe) -> list[Recipe]:
    """Replace recipe in list by ID, return new list.

    Args:
        recipes: List of Recipe objects
        updated_recipe: Recipe object with updated data

    Returns:
        New list with updated recipe

    Raises:
        ValueError: If recipe with given ID is not found
    """
    # Find the index of the recipe to update
    recipe_index = None
    for i, recipe in enumerate(recipes):
        if recipe.id == updated_recipe.id:
            recipe_index = i
            break

    if recipe_index is None:
        raise ValueError(f"Recipe with ID '{updated_recipe.id}' not found")

    # Create a new list with the updated recipe
    new_recipes = recipes.copy()
    new_recipes[recipe_index] = updated_recipe

    return new_recipes
