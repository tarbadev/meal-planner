import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class RecipeLoadError(Exception):
    """Raised when recipes cannot be loaded from file."""
    pass


@dataclass
class Recipe:
    id: str
    name: str
    servings: int
    prep_time_minutes: int
    cook_time_minutes: int
    calories_per_serving: int
    protein_per_serving: int
    carbs_per_serving: int
    fat_per_serving: int
    tags: list[str] = field(default_factory=list)
    ingredients: list[dict[str, Any]] = field(default_factory=list)

    @property
    def total_time_minutes(self) -> int:
        return self.prep_time_minutes + self.cook_time_minutes

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Recipe":
        required_fields = [
            "id", "name", "servings", "prep_time_minutes", "cook_time_minutes",
            "calories_per_serving", "protein_per_serving", "carbs_per_serving",
            "fat_per_serving"
        ]

        missing = [f for f in required_fields if f not in data]
        if missing:
            raise ValueError(f"Missing required fields: {', '.join(missing)}")

        return cls(
            id=data["id"],
            name=data["name"],
            servings=data["servings"],
            prep_time_minutes=data["prep_time_minutes"],
            cook_time_minutes=data["cook_time_minutes"],
            calories_per_serving=data["calories_per_serving"],
            protein_per_serving=data["protein_per_serving"],
            carbs_per_serving=data["carbs_per_serving"],
            fat_per_serving=data["fat_per_serving"],
            tags=data.get("tags", []),
            ingredients=data.get("ingredients", []),
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
