from collections import defaultdict
from dataclasses import dataclass

from app.planner import WeeklyPlan


@dataclass
class ShoppingListItem:
    item: str
    quantity: float
    unit: str
    category: str


@dataclass
class ShoppingList:
    items: list[ShoppingListItem]

    @property
    def items_by_category(self) -> dict[str, list[ShoppingListItem]]:
        """Group items by category."""
        grouped = defaultdict(list)
        for item in self.items:
            grouped[item.category].append(item)
        return dict(grouped)


def _normalize_unit(unit: str | None) -> str:
    """Normalize unit so 'serving', 'servings', None, and empty are all ''.

    Fixes BUG-2: ingredients with unit='serving' in one recipe and unit='' in
    another share the same aggregation key and are combined into one line.

    Fixes BUG-3: 'serving' is never stored on ShoppingListItem.unit, so the
    display string becomes '0.6875 tomato' not '0.6875 serving tomato'.
    """
    if not unit or unit.lower() in ("serving", "servings"):
        return ""
    return unit


def generate_shopping_list(weekly_plan: WeeklyPlan) -> ShoppingList:
    """Generate a shopping list from a weekly meal plan.

    Aggregates all ingredients across meals, combines items with the same
    name and unit, and sorts by category.
    """
    # Collect all ingredients with scaled quantities
    aggregated = defaultdict(lambda: {"quantity": 0.0, "unit": "", "category": ""})

    for meal in weekly_plan.meals:
        for ingredient in meal.scaled_ingredients:
            normalized_unit = _normalize_unit(ingredient.get("unit", ""))
            # Key uses normalized unit so 'serving' and '' map to the same bucket
            key = (ingredient["item"], normalized_unit)

            if aggregated[key]["unit"] == "" and normalized_unit:
                # First time seeing this item+unit combination
                aggregated[key]["unit"] = normalized_unit
            if aggregated[key]["category"] == "":
                aggregated[key]["category"] = ingredient.get("category", "other")

            # Add to the quantity
            aggregated[key]["quantity"] += ingredient["quantity"]

    # Convert to ShoppingListItem objects
    items = [
        ShoppingListItem(
            item=item_name,
            quantity=data["quantity"],
            unit=data["unit"],
            category=data["category"]
        )
        for (item_name, unit), data in aggregated.items()
    ]

    # Sort by category, then by item name
    items.sort(key=lambda x: (x.category, x.item))

    return ShoppingList(items=items)
