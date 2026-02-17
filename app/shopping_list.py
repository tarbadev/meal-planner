from collections import defaultdict
from dataclasses import dataclass

from app.planner import WeeklyPlan

# ---------------------------------------------------------------------------
# Unit conversion tables
# All volume units are expressed in ml; all weight units in grams.
# Keys are lowercased canonical spellings (plus common abbreviations).
# ---------------------------------------------------------------------------

_VOLUME_TO_ML: dict[str, float] = {
    "ml": 1, "milliliter": 1, "milliliters": 1, "millilitre": 1, "millilitres": 1,
    "tsp": 4.92892, "teaspoon": 4.92892, "teaspoons": 4.92892,
    "tbsp": 14.7868, "tablespoon": 14.7868, "tablespoons": 14.7868,
    "fl oz": 29.5735, "fluid ounce": 29.5735, "fluid ounces": 29.5735,
    "cup": 236.588, "cups": 236.588,
    "pt": 473.176, "pint": 473.176, "pints": 473.176,
    "qt": 946.353, "quart": 946.353, "quarts": 946.353,
    "l": 1000, "liter": 1000, "liters": 1000, "litre": 1000, "litres": 1000,
    "gal": 3785.41, "gallon": 3785.41, "gallons": 3785.41,
}

_WEIGHT_TO_G: dict[str, float] = {
    "g": 1, "gram": 1, "grams": 1,
    "kg": 1000, "kilogram": 1000, "kilograms": 1000,
    "oz": 28.3495, "ounce": 28.3495, "ounces": 28.3495,
    "lb": 453.592, "pound": 453.592, "pounds": 453.592, "lbs": 453.592,
}


def _unit_info(unit: str) -> tuple[str, float] | None:
    """Return (family, base_equivalent) or None if the unit is unrecognised.

    family is 'volume' (base=ml) or 'weight' (base=g).
    """
    u = unit.lower().strip()
    if u in _VOLUME_TO_ML:
        return ("volume", _VOLUME_TO_ML[u])
    if u in _WEIGHT_TO_G:
        return ("weight", _WEIGHT_TO_G[u])
    return None


def _normalize_unit(unit: str | None) -> str:
    """Normalise 'serving', 'servings', None and empty string to ''.

    Fixes BUG-3: the word 'serving' never appears in the shopping list.
    """
    if not unit or unit.lower() in ("serving", "servings"):
        return ""
    return unit


def _combine_entries(entries: list[tuple[float, str]]) -> list[tuple[float, str]]:
    """Merge (quantity, unit) pairs for the same ingredient into as few lines as possible.

    Rules:
    - All entries with the same unit → sum them up.
    - Entries in the same measurement family (volume or weight) → convert all to
      the base unit, sum, then express in the largest unit present in the group.
    - Unitless entries (unit='') → always summed separately.
    - Entries with unrecognised, incompatible units (e.g. 'clove' vs 'head') → kept
      as separate lines; entries with the *same* unrecognised unit are summed.

    Returns a list of (quantity, unit) pairs (usually just one).
    """
    # Sum by exact unit first
    by_unit: dict[str, float] = defaultdict(float)
    for qty, unit in entries:
        by_unit[unit] += qty

    if len(by_unit) == 1:
        unit, qty = next(iter(by_unit.items()))
        return [(qty, unit)]

    # Multiple distinct units — categorise each
    unitless = by_unit.pop("", 0.0)
    family_buckets: dict[str, list[tuple[str, float, float]]] = defaultdict(list)
    unknown: dict[str, float] = {}

    for unit, qty in by_unit.items():
        info = _unit_info(unit)
        if info:
            family, mult = info
            family_buckets[family].append((unit, qty, mult))
        else:
            unknown[unit] = unknown.get(unit, 0.0) + qty

    result: list[tuple[float, str]] = []

    if unitless > 0:
        result.append((unitless, ""))

    for unit, qty in unknown.items():
        result.append((qty, unit))

    for _family, group in family_buckets.items():
        total_base = sum(qty * mult for _, qty, mult in group)
        # Use the largest unit from the group (highest multiplier) for display
        _, _, best_mult = max(group, key=lambda x: x[2])
        best_unit, _, _ = max(group, key=lambda x: x[2])
        result.append((total_base / best_mult, best_unit))

    return result


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


def generate_shopping_list(weekly_plan: WeeklyPlan) -> ShoppingList:
    """Generate a shopping list from a weekly meal plan.

    Aggregates all ingredients across meals. Ingredients with the same name
    are combined into a single line. When the same ingredient appears with
    different but compatible units (e.g. tsp and tbsp, oz and lb) the
    quantities are converted and expressed in the largest unit present.
    Incompatible units (e.g. volume vs weight, or unknown units like 'clove'
    vs 'head') remain as separate lines.
    """
    # Collect raw entries: item_name → {category, entries: [(qty, unit)]}
    item_data: dict[str, dict] = {}

    for meal in weekly_plan.meals:
        for ingredient in meal.scaled_ingredients:
            name = ingredient["item"]
            raw_unit = ingredient.get("unit", "")
            norm_unit = _normalize_unit(raw_unit)
            qty = ingredient.get("quantity", 0.0)
            category = ingredient.get("category", "other")

            if name not in item_data:
                item_data[name] = {"category": category, "entries": []}
            item_data[name]["entries"].append((qty, norm_unit))

    items: list[ShoppingListItem] = []
    for name, data in item_data.items():
        for qty, unit in _combine_entries(data["entries"]):
            items.append(ShoppingListItem(
                item=name,
                quantity=qty,
                unit=unit,
                category=data["category"],
            ))

    items.sort(key=lambda x: (x.category, x.item))
    return ShoppingList(items=items)
