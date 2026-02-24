#!/usr/bin/env python3
"""
Daily automated Spoonacular recipe import with variety control.

Imports up to 50 recipes per day from Spoonacular, ensuring variety across
cuisines, dish types, and dietary preferences.

Each search combination (cuisine × meal_type × diet) tracks its own offset so
subsequent runs continue where the previous one left off instead of re-scanning
already-imported recipes from position 0.
"""

import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

import requests

from app import config
from app.db.crud_sync import get_recipes, get_session, upsert_recipe
from app.recipe_parser import ParsedRecipe, generate_recipe_id
from app.recipes import Recipe
from app.tag_inference import TagInferencer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Variety configuration — rotated across runs
# ---------------------------------------------------------------------------

CUISINES = [
    "american", "asian", "british", "cajun", "caribbean", "chinese",
    "european", "french", "german", "greek", "indian",
    "italian", "japanese", "korean", "latin american",
    "mediterranean", "mexican", "middle eastern",
    "southern", "spanish", "thai", "vietnamese",
]

MEAL_TYPES = [
    "main course", "side dish", "dessert", "appetizer", "salad", "bread",
    "breakfast", "soup", "beverage", "sauce", "marinade", "fingerfood",
    "snack", "drink",
]

DIETS = [
    None,           # No restriction (general recipes)
    "vegetarian",
    "vegan",
    "gluten free",
    "ketogenic",
    "paleo",
    "primal",
    "low fodmap",
    "whole30",
]

# File to track all persistent state
TRACKING_FILE = Path(__file__).parent / "spoonacular_imported.json"

# Raw API responses that haven't been saved to the DB yet.
# Each file is {spoonacular_id}.json and is written before the DB insert,
# then deleted on success.  On the next run, any leftover files are retried
# before fetching new recipes.
PENDING_DIR = Path(__file__).parent / "pending_spoonacular"

# Spoonacular allows up to 100 results per request
BATCH_SIZE = 100

# ---------------------------------------------------------------------------
# State helpers — single file, single read/write per run
# ---------------------------------------------------------------------------

def load_state() -> dict:
    """Load full tracking state from disk."""
    if TRACKING_FILE.exists():
        with open(TRACKING_FILE) as f:
            return json.load(f)
    return {}


def save_state(state: dict) -> None:
    """Persist full tracking state to disk."""
    TRACKING_FILE.parent.mkdir(exist_ok=True)
    state["last_updated"] = datetime.now().isoformat()
    with open(TRACKING_FILE, "w") as f:
        json.dump(state, f, indent=2)


def search_key(cuisine, meal_type, diet) -> str:
    return f"{cuisine or ''}|{meal_type or ''}|{diet or ''}"


# ---------------------------------------------------------------------------
# Pending queue — durably persist raw API responses before DB insert
# ---------------------------------------------------------------------------

def save_pending(spoonacular_id: int, recipe_data: dict) -> None:
    """Write raw Spoonacular JSON to disk before attempting a DB insert."""
    PENDING_DIR.mkdir(exist_ok=True)
    path = PENDING_DIR / f"{spoonacular_id}.json"
    with open(path, "w") as f:
        json.dump(recipe_data, f)


def remove_pending(spoonacular_id: int) -> None:
    """Delete the pending file after a successful DB insert."""
    path = PENDING_DIR / f"{spoonacular_id}.json"
    if path.exists():
        path.unlink()


def process_pending(db, existing_ids: set, existing_names: set, tag_inferencer, imported_ids: set) -> int:
    """Retry any recipes that were fetched but not saved in a previous run.

    Returns the number of recipes successfully recovered.
    """
    if not PENDING_DIR.exists():
        return 0

    pending_files = sorted(PENDING_DIR.glob("*.json"))
    if not pending_files:
        return 0

    print(f"Found {len(pending_files)} pending recipe(s) from a previous run — retrying…")
    recovered = 0

    for pending_file in pending_files:
        spoonacular_id = int(pending_file.stem)
        with open(pending_file) as f:
            recipe_data = json.load(f)

        name = recipe_data.get("title", pending_file.stem)
        try:
            parsed, _ = parse_spoonacular_recipe(recipe_data)
            parsed.tags = tag_inferencer.enhance_tags(
                name=parsed.name,
                ingredients=parsed.ingredients or [],
                instructions=parsed.instructions or [],
                prep_time_minutes=parsed.prep_time_minutes or 0,
                cook_time_minutes=parsed.cook_time_minutes or 0,
                existing_tags=parsed.tags or [],
            )
            recipe_id = generate_recipe_id(parsed.name, existing_ids)
            existing_ids.add(recipe_id)
            existing_names.add(name.lower())
            new_recipe = Recipe.from_dict(parsed.to_recipe_dict(recipe_id))
            upsert_recipe(db, new_recipe, config.DEFAULT_HOUSEHOLD_ID)
            imported_ids.add(spoonacular_id)
            remove_pending(spoonacular_id)
            recovered += 1
            print(f"   ✅ Recovered: {name}")
        except Exception as e:
            logger.exception("Failed to recover pending recipe", extra={"recipe_name": name})
            print(f"   ❌ Still failing: {name} — {e}")

    return recovered


# ---------------------------------------------------------------------------
# Spoonacular API
# ---------------------------------------------------------------------------

def search_spoonacular_recipes(api_key, cuisine, meal_type, diet, number, offset):
    """Search Spoonacular with the given filters. Returns raw JSON."""
    params = {
        "apiKey": api_key,
        "number": number,
        "offset": offset,
        "addRecipeInformation": True,
        "fillIngredients": True,
        "addRecipeNutrition": True,
        "instructionsRequired": True,
        # No sort=random — stable ordering lets offset tracking work correctly
    }
    if cuisine:
        params["cuisine"] = cuisine
    if meal_type:
        params["type"] = meal_type
    if diet:
        params["diet"] = diet

    response = requests.get(
        "https://api.spoonacular.com/recipes/complexSearch",
        params=params,
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


# ---------------------------------------------------------------------------
# Recipe parsing
# ---------------------------------------------------------------------------

def parse_spoonacular_recipe(recipe_data):
    """Convert Spoonacular recipe format to (ParsedRecipe, spoonacular_id)."""
    ingredients = []
    for ing in recipe_data.get("extendedIngredients", []):
        ingredients.append({
            "quantity": ing.get("amount", 0),
            "unit": ing.get("unit", ""),
            "item": ing.get("name", ""),
            "notes": ing.get("original", ""),
            "category": ing.get("aisle", "").lower() if ing.get("aisle") else "other",
        })

    instructions = []
    for instruction_set in recipe_data.get("analyzedInstructions", []):
        for step in instruction_set.get("steps", []):
            instructions.append(step.get("step", ""))
    if not instructions:
        raw = recipe_data.get("instructions", "")
        if raw:
            instructions = [s.strip() for s in raw.split(".") if s.strip()]

    nutrients = {
        n["name"]: n["amount"]
        for n in recipe_data.get("nutrition", {}).get("nutrients", [])
    }

    tags = []
    tags.extend(c.lower() for c in recipe_data.get("cuisines", []))
    tags.extend(d.lower() for d in recipe_data.get("dishTypes", []))
    tags.extend(d.lower() for d in recipe_data.get("diets", []))
    tags.append("spoonacular")

    parsed = ParsedRecipe(
        name=recipe_data["title"],
        servings=recipe_data.get("servings", 4),
        prep_time_minutes=recipe_data.get("preparationMinutes"),
        cook_time_minutes=recipe_data.get("cookingMinutes"),
        ingredients=ingredients,
        instructions=instructions,
        tags=tags,
        source_url=recipe_data.get("sourceUrl"),
        image_url=recipe_data.get("image"),
        calories_per_serving=int(nutrients.get("Calories", 0)),
        protein_per_serving=nutrients.get("Protein", 0),
        carbs_per_serving=nutrients.get("Carbohydrates", 0),
        fat_per_serving=nutrients.get("Fat", 0),
        saturated_fat_per_serving=nutrients.get("Saturated Fat", 0),
        sodium_per_serving=nutrients.get("Sodium", 0),
        fiber_per_serving=nutrients.get("Fiber", 0),
        sugar_per_serving=nutrients.get("Sugar", 0),
        vitamin_c_per_serving=nutrients.get("Vitamin C", 0),
        calcium_per_serving=nutrients.get("Calcium", 0),
        iron_per_serving=nutrients.get("Iron", 0),
    )
    return parsed, recipe_data["id"]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 70)
    print("Spoonacular Daily Recipe Import")
    print(f"Run Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    print()

    if not config.SPOONACULAR_API_KEY:
        print("❌ Error: SPOONACULAR_API_KEY not configured")
        print("Get your free key at: https://spoonacular.com/food-api/console#Dashboard")
        print("Then set: export SPOONACULAR_API_KEY='your-key-here'")
        return

    api_key = config.SPOONACULAR_API_KEY

    # ---- Load persistent state ----
    state = load_state()
    imported_ids = set(state.get("imported_ids", []))
    variety = state.get("variety_state", {
        "cuisine_index": 0,
        "meal_type_index": 0,
        "diet_index": 0,
    })
    # Per-search-key offset tracking: {"american|main course|": 200, ...}
    search_offsets: dict[str, int] = state.get("search_offsets", {})

    # ---- Load recipes from DB ----
    db = get_session()
    existing_recipes = get_recipes(db, config.DEFAULT_HOUSEHOLD_ID)
    existing_ids = {r.id for r in existing_recipes}
    existing_names = {r.name.lower() for r in existing_recipes}
    logger.info("Loaded existing recipe DB", extra={"recipe_count": len(existing_recipes), "tracked_ids": len(imported_ids)})
    print(f"Existing recipes in DB: {len(existing_recipes)}")
    print(f"Previously tracked Spoonacular IDs: {len(imported_ids)}")
    print()

    # ---- Retry any recipes that failed to save in a previous run ----
    tag_inferencer = TagInferencer()
    recovered = process_pending(db, existing_ids, existing_names, tag_inferencer, imported_ids)
    if recovered:
        print(f"Recovered {recovered} recipe(s) from pending queue")
        print()

    # ---- Build ordered list of search strategies for this run ----
    # Primary: today's variety combination
    cuisine   = CUISINES[variety["cuisine_index"] % len(CUISINES)]
    meal_type = MEAL_TYPES[variety["meal_type_index"] % len(MEAL_TYPES)]
    diet      = DIETS[variety["diet_index"] % len(DIETS)]

    print("🎲 Today's variety filters:")
    print(f"   Cuisine:   {cuisine}")
    print(f"   Meal Type: {meal_type}")
    print(f"   Diet:      {diet or 'None (general recipes)'}")
    print()

    # Advance variety indices for the next run
    variety["cuisine_index"]   += 1
    variety["meal_type_index"] += 1
    variety["diet_index"]      += 1

    # Progressive fallback strategies (narrower → broader)
    search_attempts = [
        (cuisine,  meal_type, diet),
        (cuisine,  meal_type, None),
        (cuisine,  None,      None),
        (None,     meal_type, None),
        (None,     None,      None),  # No filters — broadest pool
    ]

    # ---- Import loop ----
    TARGET = 50
    imported_count = 0
    skipped_count  = 0
    failed_count   = 0

    print("=" * 70)
    print("Fetching recipes from Spoonacular...")
    print("=" * 70)
    print()

    for search_idx, (c, mt, d) in enumerate(search_attempts):
        if imported_count >= TARGET:
            break

        key = search_key(c, mt, d)
        offset = search_offsets.get(key, 0)

        filters = []
        if c:
            filters.append(f"cuisine={c}")
        if mt:
            filters.append(f"type={mt}")
        if d:
            filters.append(f"diet={d}")
        label = ", ".join(filters) if filters else "no filters"
        print(f"── Strategy {search_idx + 1}/{len(search_attempts)}: [{label}]  (starting at offset {offset})")

        while imported_count < TARGET:
            try:
                logger.info("Searching Spoonacular", extra={"offset": offset, "cuisine": c, "meal_type": mt, "diet": d})
                print(f"   Searching offset {offset}…", flush=True)
                results = search_spoonacular_recipes(
                    api_key=api_key,
                    cuisine=c,
                    meal_type=mt,
                    diet=d,
                    number=BATCH_SIZE,
                    offset=offset,
                )
            except Exception as e:
                logger.exception("Spoonacular API error", extra={"offset": offset, "cuisine": c, "meal_type": mt, "diet": d})
                print(f"   ❌ API error: {e}")
                break

            recipes     = results.get("results", [])
            total_avail = results.get("totalResults", 0)

            if not recipes:
                logger.warning("No Spoonacular results returned", extra={"offset": offset, "total_avail": total_avail})
                print(f"   No results returned (total available: {total_avail})")
                break

            logger.info("Spoonacular search returned results", extra={"count": len(recipes), "total_avail": total_avail})
            print(f"   Got {len(recipes)} results (total pool: {total_avail})")

            for recipe_data in recipes:
                if imported_count >= TARGET:
                    break

                name          = recipe_data["title"]
                spoonacular_id = recipe_data["id"]

                if spoonacular_id in imported_ids:
                    skipped_count += 1
                    continue

                if name.lower() in existing_names:
                    skipped_count += 1
                    imported_ids.add(spoonacular_id)  # don't re-check next time
                    continue

                save_pending(spoonacular_id, recipe_data)
                try:
                    logger.info("Importing recipe from Spoonacular", extra={"recipe_name": name, "spoonacular_id": spoonacular_id})
                    print(f"   📥 Importing: {name}")
                    parsed, spoon_id = parse_spoonacular_recipe(recipe_data)

                    parsed.tags = tag_inferencer.enhance_tags(
                        name=parsed.name,
                        ingredients=parsed.ingredients or [],
                        instructions=parsed.instructions or [],
                        prep_time_minutes=parsed.prep_time_minutes or 0,
                        cook_time_minutes=parsed.cook_time_minutes or 0,
                        existing_tags=parsed.tags or [],
                    )

                    recipe_id = generate_recipe_id(parsed.name, existing_ids)
                    existing_ids.add(recipe_id)
                    existing_names.add(name.lower())

                    new_recipe = Recipe.from_dict(parsed.to_recipe_dict(recipe_id))
                    upsert_recipe(db, new_recipe, config.DEFAULT_HOUSEHOLD_ID)
                    remove_pending(spoonacular_id)
                    existing_recipes.append(new_recipe)
                    imported_ids.add(spoonacular_id)
                    imported_count += 1

                    logger.info("Recipe imported successfully", extra={"recipe_id": recipe_id, "recipe_name": name, "imported_count": imported_count})
                    print(f"      ✅ Done  ({imported_count}/{TARGET})  tags: {', '.join(parsed.tags[:5])}")

                except Exception as e:
                    logger.exception("Failed to import recipe from Spoonacular", extra={"recipe_name": name, "spoonacular_id": spoonacular_id})
                    print(f"      ❌ Error: {e}")
                    failed_count += 1

            offset += len(recipes)
            # Persist the new offset so the next run can skip this range
            search_offsets[key] = offset

            # All results for this combination exhausted → next strategy
            if offset >= total_avail:
                logger.info("Exhausted all results for this search strategy", extra={"total_avail": total_avail, "cuisine": c, "meal_type": mt, "diet": d})
                print(f"   Exhausted all {total_avail} results for this strategy")
                break

            time.sleep(1)  # Rate limiting

        print()

    # ---- Save state (recipes already persisted per-recipe above) ----
    print("=" * 70)
    print("Saving state…")
    db.close()

    state["imported_ids"]  = list(imported_ids)
    state["variety_state"] = variety
    state["search_offsets"] = search_offsets
    save_state(state)

    logger.info("Spoonacular import run complete", extra={"imported": imported_count, "skipped": skipped_count, "failed": failed_count, "total_in_db": len(existing_recipes)})
    print(f"✅ Saved {len(existing_recipes)} total recipes")
    print(f"✅ Tracked {len(imported_ids)} Spoonacular IDs")
    print()

    # ---- Summary ----
    print("=" * 70)
    print("DAILY IMPORT SUMMARY")
    print("=" * 70)
    print(f"✅ Imported:    {imported_count} recipes")
    print(f"⏭️  Skipped:     {skipped_count} recipes (duplicates)")
    print(f"❌ Failed:      {failed_count} recipes")
    print(f"📚 Total in DB: {len(existing_recipes)} recipes")
    print("=" * 70)

    if imported_count < TARGET:
        print()
        print(f"⚠️  Reached only {imported_count}/{TARGET} target.")
        print("   Possible reasons: all available recipes already imported,")
        print("   or Spoonacular API rate limit hit.")
        print("   Next run will use different variety filters and saved offsets.")


if __name__ == "__main__":
    main()
