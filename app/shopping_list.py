import logging
import unicodedata
from collections import defaultdict
from dataclasses import dataclass

from rapidfuzz import fuzz

from app.ingredient_normalizer import canonicalise_category
from app.planner import WeeklyPlan

# Similarity threshold (0–100) for fuzzy name merging.  Items scoring at or
# above this are treated as the same ingredient.  85 catches diacritic/plural
# variants that slip through _normalize_name while being conservative enough
# to keep e.g. "chicken" and "chicken breast" separate.
_FUZZY_THRESHOLD = 85

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Unit conversion tables
# All volume units are expressed in ml; all weight units in grams.
# Keys are lowercased canonical spellings (plus common abbreviations).
# ---------------------------------------------------------------------------

_VOLUME_TO_ML: dict[str, float] = {
    "ml": 1, "milliliter": 1, "milliliters": 1, "millilitre": 1, "millilitres": 1,
    # teaspoon — "t" is a common shorthand in recipes
    "t": 4.92892, "tsp": 4.92892, "teaspoon": 4.92892, "teaspoons": 4.92892,
    # tablespoon — "T" and "Tbsp" are common shorthands
    "T": 14.7868, "tbsp": 14.7868, "Tbsp": 14.7868, "tablespoon": 14.7868, "tablespoons": 14.7868,
    "fl oz": 29.5735, "fluid ounce": 29.5735, "fluid ounces": 29.5735,
    # cup — "c" is a common shorthand
    "c": 236.588, "cup": 236.588, "cups": 236.588,
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


def _best_volume_unit(total_ml: float) -> tuple[float, str]:
    """Return (quantity, unit) in the most readable volume unit for total_ml."""
    if total_ml >= 1000:
        return total_ml / 1000, "l"
    if total_ml >= 59.1471:   # ≥ ¼ cup (4 tbsp) — prefer cups over a pile of tbsp
        return total_ml / 236.588, "cup"
    if total_ml >= 14.7868:   # ≥ 1 tbsp
        return total_ml / 14.7868, "tbsp"
    return total_ml / 4.92892, "tsp"


def _best_weight_unit(total_g: float) -> tuple[float, str]:
    """Return (quantity, unit) in the most readable weight unit for total_g."""
    if total_g >= 1000:
        return total_g / 1000, "kg"
    if total_g >= 453.592:    # ≥ 1 lb
        return total_g / 453.592, "lb"
    if total_g >= 28.3495:    # ≥ 1 oz
        return total_g / 28.3495, "oz"
    return total_g, "g"


def _unit_info(unit: str) -> tuple[str, float] | None:
    """Return (family, base_equivalent) or None if the unit is unrecognised.

    family is 'volume' (base=ml) or 'weight' (base=g).
    Case-sensitive lookup first (to distinguish 't'=tsp vs 'T'=tbsp),
    then falls back to lowercase for convenience.
    """
    stripped = unit.strip()
    # Case-sensitive first pass (handles t vs T, Tbsp, etc.)
    if stripped in _VOLUME_TO_ML:
        return ("volume", _VOLUME_TO_ML[stripped])
    if stripped in _WEIGHT_TO_G:
        return ("weight", _WEIGHT_TO_G[stripped])
    # Case-insensitive fallback
    u = stripped.lower()
    if u in _VOLUME_TO_ML:
        return ("volume", _VOLUME_TO_ML[u])
    if u in _WEIGHT_TO_G:
        return ("weight", _WEIGHT_TO_G[u])
    return None


# Map shorthand abbreviations to canonical display names
_UNIT_DISPLAY: dict[str, str] = {
    "t": "tsp", "tsp": "tsp", "teaspoon": "tsp", "teaspoons": "tsp",
    "T": "tbsp", "Tbsp": "tbsp", "tbsp": "tbsp", "tablespoon": "tbsp", "tablespoons": "tbsp",
    "c": "cup", "cups": "cup",
    "milliliter": "ml", "milliliters": "ml", "millilitre": "ml", "millilitres": "ml",
    "fluid ounce": "fl oz", "fluid ounces": "fl oz",
    "pint": "pt", "pints": "pt",
    "quart": "qt", "quarts": "qt",
    "liter": "l", "liters": "l", "litre": "l", "litres": "l",
    "gallon": "gal", "gallons": "gal",
    "gram": "g", "grams": "g",
    "kilogram": "kg", "kilograms": "kg",
    "ounce": "oz", "ounces": "oz",
    "pound": "lb", "pounds": "lb", "lbs": "lb",
}


# Units that convey no useful shopping quantity — ingredients with these
# units will have quantity set to None (just "buy it").
_QUANTITY_MEANINGLESS_UNITS = {"to taste", "to serve", "as needed", "as required", "au goût"}


def _normalize_unit(unit: str | None) -> str | None:
    """Normalise serving variants to '' and abbreviations to display-friendly names.

    Returns None for units that convey no meaningful quantity (to taste, to serve).
    Fixes BUG-3: the word 'serving' never appears in the shopping list.
    Also canonicalises shorthands like 'T' → 'tbsp' and 'c' → 'cup'.
    """
    if not unit:
        return ""
    stripped = unit.strip()
    if stripped.lower() in ("serving", "servings"):
        return ""
    if stripped.lower() in _QUANTITY_MEANINGLESS_UNITS:
        return None  # signals: include item but drop quantity
    return _UNIT_DISPLAY.get(stripped, stripped)


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

    for family, group in family_buckets.items():
        total_base = sum(qty * mult for _, qty, mult in group)
        unique_units = {u for u, _, _ in group}
        if len(unique_units) == 1:
            # All entries share the same unit — sum and preserve it
            orig_unit, _, orig_mult = group[0]
            result.append((total_base / orig_mult, orig_unit))
        elif family == "volume":
            # Multiple different volume units — pick the most readable
            result.append(_best_volume_unit(total_base))
        else:
            # Multiple different weight units — pick the most readable
            result.append(_best_weight_unit(total_base))

    return result


@dataclass
class ShoppingListItem:
    item: str
    quantity: float | None  # None = buy it but no meaningful quantity
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


def _normalize_name(name: str) -> str:
    """Return a canonical grouping key for an ingredient name.

    1. Strip diacritics (jalapeño → jalapeno).
    2. Lowercase and trim whitespace.
    3. Strip a trailing 's' to handle simple plurals (jalapenos → jalapeno,
       peppers → pepper).  Words ending in 'ss' are left alone (e.g. 'moss').
    """
    nfkd = unicodedata.normalize("NFKD", name.strip())
    s = "".join(c for c in nfkd if not unicodedata.combining(c)).lower()
    if len(s) > 4 and s.endswith("s") and not s.endswith("ss"):
        s = s[:-1]
    return s


def _fuzzy_merge_items(item_data: dict[str, dict]) -> dict[str, dict]:
    """Merge item_data entries whose normalized names score >= _FUZZY_THRESHOLD.

    Uses a greedy pass: the first key in insertion order becomes the canonical
    representative for its similarity cluster.  Quantities and category are
    merged into the canonical entry.
    """
    if len(item_data) <= 1:
        return item_data

    keys = list(item_data.keys())
    canonical_for: dict[str, str] = {}

    for i, key in enumerate(keys):
        if key in canonical_for:
            continue
        canonical_for[key] = key
        for other in keys[i + 1:]:
            if other in canonical_for:
                continue
            if fuzz.WRatio(key, other) >= _FUZZY_THRESHOLD:
                canonical_for[other] = key

    result: dict[str, dict] = {}
    for key, canonical in canonical_for.items():
        src = item_data[key]
        if canonical not in result:
            result[canonical] = {
                "display_name": item_data[canonical]["display_name"],
                "category": src["category"],
                "entries": list(src["entries"]),
                "quantity_meaningless": src["quantity_meaningless"],
            }
        else:
            result[canonical]["entries"].extend(src["entries"])
            result[canonical]["quantity_meaningless"] |= src["quantity_meaningless"]

    return result


def generate_shopping_list(weekly_plan: WeeklyPlan) -> ShoppingList:
    """Generate a shopping list from a weekly meal plan.

    Aggregates all ingredients across meals. Ingredients with the same name
    are combined into a single line. When the same ingredient appears with
    different but compatible units (e.g. tsp and tbsp, oz and lb) the
    quantities are converted and expressed in the largest unit present.
    Incompatible units (e.g. volume vs weight, or unknown units like 'clove'
    vs 'head') remain as separate lines.
    """
    logger.debug("Generating shopping list", extra={"meal_count": len(weekly_plan.meals)})
    # Collect raw entries keyed by *normalised* name so diacritic variants and
    # simple plurals are grouped before the fuzzy-merge pass.
    item_data: dict[str, dict] = {}

    for meal in weekly_plan.meals:
        for ingredient in meal.scaled_ingredients:
            name = ingredient["item"]
            key = _normalize_name(name)
            raw_unit = ingredient.get("unit", "")
            norm_unit = _normalize_unit(raw_unit)
            qty = ingredient.get("quantity", 0.0)
            category = canonicalise_category(ingredient.get("category", "other"))

            if key not in item_data:
                item_data[key] = {
                    "display_name": name,   # first-seen original name for display
                    "category": category,
                    "entries": [],
                    "quantity_meaningless": False,
                }

            if norm_unit is None:
                # "to taste" / "to serve" — mark as quantityless, don't accumulate
                item_data[key]["quantity_meaningless"] = True
            else:
                item_data[key]["entries"].append((qty, norm_unit))

    # Fuzzy-merge remaining near-duplicates (e.g. "jalapeno" ↔ "jalapeno pepper")
    item_data = _fuzzy_merge_items(item_data)

    items: list[ShoppingListItem] = []
    for _key, data in item_data.items():
        display = data["display_name"]
        if data["quantity_meaningless"] and not data["entries"]:
            # Only "to taste" appearances — include item but no quantity
            items.append(ShoppingListItem(
                item=display,
                quantity=None,
                unit="",
                category=data["category"],
            ))
        else:
            for qty, unit in _combine_entries(data["entries"]):
                items.append(ShoppingListItem(
                    item=display,
                    quantity=qty,
                    unit=unit,
                    category=data["category"],
                ))

    items.sort(key=lambda x: (x.category, x.item))
    logger.info(
        "Shopping list generated",
        extra={"item_count": len(items), "category_count": len({i.category for i in items})},
    )
    return ShoppingList(items=items)
