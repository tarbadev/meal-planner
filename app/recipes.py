from __future__ import annotations

from dataclasses import dataclass, field
from functools import cached_property
from typing import Any

from app.db.models import RecipeModel


class RecipeLoadError(Exception):
    """Raised when recipes cannot be loaded."""
    pass


class RecipeSaveError(Exception):
    """Raised when recipes cannot be saved."""
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
    source_url: str | None = None
    image_url: str | None = None
    reheats_well: bool = False
    stores_days: int = 0
    packs_well_as_lunch: bool = False

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

    @cached_property
    def search_blob(self) -> str:
        """Single lowercase string of name + tags + ingredient items for fast search."""
        parts = [self.name] + self.tags + [ing.get("item", "") for ing in self.ingredients]
        return " ".join(parts).lower()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Recipe:
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
            nutrition_per_serving = data["nutrition_per_serving"]
        else:
            # Old format: migrate flat fields to nested structure
            old_required = ["calories_per_serving", "protein_per_serving", "carbs_per_serving", "fat_per_serving"]
            missing_old = [f for f in old_required if f not in data]
            if missing_old:
                raise ValueError(f"Missing required nutrition fields: {', '.join(missing_old)}")

            nutrition_per_serving = {
                "calories": data["calories_per_serving"],
                "protein": data["protein_per_serving"],
                "carbs": data["carbs_per_serving"],
                "fat": data["fat_per_serving"],
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
            source_url=data.get("source_url"),
            image_url=data.get("image_url"),
            reheats_well=data.get("reheats_well", False),
            stores_days=data.get("stores_days", 0),
            packs_well_as_lunch=data.get("packs_well_as_lunch", False),
        )

    def to_db_dict(self) -> dict[str, Any]:
        """Serialise to a dict suitable for inserting/updating a RecipeModel row."""
        return {
            "id": self.id,
            "name": self.name,
            "servings": self.servings,
            "prep_time_minutes": self.prep_time_minutes,
            "cook_time_minutes": self.cook_time_minutes,
            "nutrition": self.nutrition_per_serving,
            "tags": self.tags,
            "ingredients": self.ingredients,
            "instructions": self.instructions,
            "source_url": self.source_url,
            "image_url": self.image_url,
            "reheats_well": self.reheats_well,
            "stores_days": self.stores_days,
            "packs_well_as_lunch": self.packs_well_as_lunch,
        }

    @classmethod
    def from_orm_model(cls, orm: RecipeModel) -> Recipe:
        """Construct a Recipe dataclass from a RecipeModel ORM object."""
        return cls(
            id=orm.id,
            name=orm.name,
            servings=orm.servings,
            prep_time_minutes=orm.prep_time_minutes,
            cook_time_minutes=orm.cook_time_minutes,
            nutrition_per_serving=orm.nutrition or {},
            tags=list(orm.tags or []),
            ingredients=list(orm.ingredients or []),
            instructions=list(orm.instructions or []),
            source_url=orm.source_url,
            image_url=orm.image_url,
            reheats_well=orm.reheats_well,
            stores_days=orm.stores_days,
            packs_well_as_lunch=orm.packs_well_as_lunch,
        )
