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

    def items_by_category(self) -> dict[str, list[ShoppingListItem]]:
        """Group items by category."""
        grouped = defaultdict(list)
        for item in self.items:
            grouped[item.category].append(item)
        return dict(grouped)


def generate_shopping_list(weekly_plan: WeeklyPlan) -> ShoppingList:
    """Generate a shopping list from a weekly meal plan.

    Aggregates all ingredients across meals, combines items with the same
    name and unit, and sorts by category.
    """
    # Collect all ingredients with scaled quantities
    aggregated = defaultdict(lambda: {"quantity": 0.0, "unit": "", "category": ""})

    for meal in weekly_plan.meals:
        for ingredient in meal.scaled_ingredients:
            # Create a unique key for item + unit combination
            key = (ingredient["item"], ingredient["unit"])

            if aggregated[key]["unit"] == "":
                # First time seeing this item+unit combination
                aggregated[key]["unit"] = ingredient["unit"]
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
