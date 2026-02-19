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


def llm_normalize(shopping_list: ShoppingList) -> ShoppingList:
    """LLM post-processing pass: merge duplicates, normalize names, fix quantities.

    Called from the dedicated /shopping-list/normalize endpoint — never inline
    with plan generation — so a slow or failed API call doesn't block the worker.

    Falls back to the input list unchanged if the LLM call fails.
    """
    if not shopping_list.items:
        return shopping_list

    payload = [
        {
            "item": item.item,
            "quantity": round(item.quantity, 3) if item.quantity is not None else None,
            "unit": item.unit,
            "category": item.category,
        }
        for item in shopping_list.items
    ]

    logger.info("Starting LLM normalization", extra={"item_count": len(shopping_list.items)})
    t0 = time.monotonic()
    try:
        # Background thread — not bound by gunicorn worker timeout, use 60 s
        client = OpenAI(api_key=config.OPENAI_API_KEY, timeout=60.0)
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
        raw_items = result.get("items", [])

        items = [
            ShoppingListItem(
                item=entry["item"],
                quantity=entry.get("quantity"),
                unit=entry.get("unit", ""),
                category=entry.get("category", "other"),
            )
            for entry in raw_items
            if entry.get("item")
        ]
        items.sort(key=lambda x: (x.category, x.item))
        logger.info(
            "LLM normalization complete",
            extra={
                "input_count": len(shopping_list.items),
                "output_count": len(items),
                "elapsed_s": round(time.monotonic() - t0, 2),
            },
        )
        return ShoppingList(items=items)

    except Exception:
        logger.exception("LLM normalization failed, keeping list as-is", extra={"item_count": len(shopping_list.items)})
        return shopping_list
