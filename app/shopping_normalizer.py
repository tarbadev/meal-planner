"""LLM-based shopping list normalization.

Merges semantically similar ingredients, normalizes names, strips noise
modifiers, and removes excluded ingredients.

Design note: the LLM call is intentionally kept out of the plan-generation
request path.  `apply_exclusions()` is fast (pure filtering) and is called
inline during plan generation.  `llm_normalize()` is slow and is called from a
dedicated `/shopping-list/normalize` endpoint so it never blocks a gunicorn
worker long enough to trigger SIGABRT.
"""

import json
import logging
import os
import re
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

from openai import OpenAI

import app.config as config
from app.shopping_list import ShoppingList, ShoppingListItem

logger = logging.getLogger(__name__)

EXCLUDED_INGREDIENTS_FILE = "data/excluded_ingredients.json"

DEFAULT_EXCLUDED_INGREDIENTS = ["water", "salt", "ice"]

_NORMALIZE_SYSTEM_PROMPT = """\
You are normalizing a grocery shopping list for a family meal planner.

Given a JSON array of shopping list items, return a cleaned version.

RULES:

1. MERGE DUPLICATES — items that refer to the same ingredient must be merged:
   - Plurals: "eggs" = "egg", "chicken breasts" = "chicken breast"
   - Modifiers to strip: "large egg" → "egg", "fresh parsley" → "parsley",
     "extra virgin olive oil" → "olive oil", "chopped onion" → "onion"
   - Variants: "hamburger buns" = "burger buns", "feta cheese" = "feta",
     "ground beef" = "minced beef"
   - When merging, sum quantities that share the same unit
   - When merging compatible units (oz + lb, tsp + tbsp + cup), convert to the
     most readable unit and sum
   - When units are incompatible (volume vs weight for same ingredient), keep
     the entry with the larger absolute quantity and discard the other

2. QUANTITYLESS ITEMS — for condiments and sauces typically bought as a whole
   bottle/jar (worcestershire sauce, fish sauce, hot sauce, soy sauce, any
   vinegar, ketchup, mustard, sriracha, vanilla extract, oyster sauce, etc.),
   set quantity to null and unit to "". The shopper just needs to know to buy it.

3. NAMES — use the shorter, more common, generic name. Return all names in
   lowercase.

4. CATEGORY — keep the category from the original item; if merging items with
   different categories pick the most specific one.

Return ONLY valid JSON in this exact format (no markdown, no extra keys):
{"items": [{"item": string, "quantity": number|null, "unit": string, "category": string}]}
"""


def load_excluded_ingredients() -> list[str]:
    """Return the user-customized excluded ingredients, or defaults."""
    try:
        with open(EXCLUDED_INGREDIENTS_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return DEFAULT_EXCLUDED_INGREDIENTS.copy()


def save_excluded_ingredients(items: list[str]) -> None:
    """Persist the excluded ingredients list."""
    os.makedirs(os.path.dirname(EXCLUDED_INGREDIENTS_FILE), exist_ok=True)
    with open(EXCLUDED_INGREDIENTS_FILE, "w") as f:
        json.dump(items, f, indent=2)


def apply_exclusions(shopping_list: ShoppingList, excluded: list[str]) -> ShoppingList:
    """Fast, synchronous step: drop excluded ingredients and return a new list.

    Called inline during plan generation — no network I/O.
    """
    excluded_lower = [e.lower().strip() for e in excluded if e.strip()]
    kept = [
        item
        for item in shopping_list.items
        if not any(
            re.search(r"\b" + re.escape(ex) + r"\b", item.item.lower())
            for ex in excluded_lower
        )
    ]
    return ShoppingList(items=kept)


def _normalize_category(items: list[ShoppingListItem]) -> list[ShoppingListItem]:
    """Call the LLM for a single category subset and return normalised items.

    Uses max_retries=0 so a stalled request fails fast — the caller falls back
    to the original items for that category on any exception.
    """
    client = OpenAI(api_key=config.OPENAI_API_KEY, timeout=30.0, max_retries=0)
    payload = [
        {
            "item": item.item,
            "quantity": round(item.quantity, 3) if item.quantity is not None else None,
            "unit": item.unit,
            "category": item.category,
        }
        for item in items
    ]
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": _NORMALIZE_SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(payload)},
        ],
        response_format={"type": "json_object"},
        temperature=0,
    )
    result = json.loads(response.choices[0].message.content)
    return [
        ShoppingListItem(
            item=entry["item"],
            quantity=entry.get("quantity"),
            unit=entry.get("unit", ""),
            category=entry.get("category", items[0].category),
        )
        for entry in result.get("items", [])
        if entry.get("item")
    ]


def llm_normalize(shopping_list: ShoppingList) -> ShoppingList:
    """LLM post-processing pass: merge duplicates, normalize names, fix quantities.

    Splits the list by category and fires one LLM call per category in
    parallel, so total latency ≈ the slowest single category (~3–5 s) instead
    of one large sequential call.

    Falls back to the original items for any category whose call fails, so a
    single API error never wipes the whole list.
    """
    if not shopping_list.items:
        return shopping_list

    # Group by category
    by_category: dict[str, list[ShoppingListItem]] = defaultdict(list)
    for item in shopping_list.items:
        by_category[item.category].append(item)

    logger.info(
        "Starting parallel LLM normalization",
        extra={"item_count": len(shopping_list.items), "category_count": len(by_category)},
    )
    logger.debug(
        "llm_normalize input",
        extra={
            "items": [
                {"item": i.item, "quantity": i.quantity, "unit": i.unit, "category": i.category}
                for i in shopping_list.items
            ]
        },
    )
    t0 = time.monotonic()

    normalised: list[ShoppingListItem] = []
    with ThreadPoolExecutor(max_workers=len(by_category)) as pool:
        future_to_cat = {
            pool.submit(_normalize_category, items): (cat, items)
            for cat, items in by_category.items()
        }
        for future in as_completed(future_to_cat):
            cat, original_items = future_to_cat[future]
            try:
                normalised.extend(future.result())
            except Exception:
                logger.exception(
                    "LLM normalization failed for category, keeping originals",
                    extra={"category": cat, "item_count": len(original_items)},
                )
                normalised.extend(original_items)

    normalised.sort(key=lambda x: (x.category, x.item))
    elapsed = round(time.monotonic() - t0, 2)
    logger.info(
        "Parallel LLM normalization complete",
        extra={
            "input_count": len(shopping_list.items),
            "output_count": len(normalised),
            "elapsed_s": elapsed,
        },
    )
    logger.debug(
        "llm_normalize output",
        extra={
            "elapsed_s": elapsed,
            "items": [
                {"item": i.item, "quantity": i.quantity, "unit": i.unit, "category": i.category}
                for i in normalised
            ],
        },
    )
    return ShoppingList(items=normalised)
