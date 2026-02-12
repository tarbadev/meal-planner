#!/usr/bin/env python3
"""
Daily automated Spoonacular recipe import with variety control.

Imports 50 recipes per day from Spoonacular's free tier, ensuring variety
across cuisines, dish types, and dietary preferences.

Tracks imported recipe IDs to avoid duplicates across runs.
"""

import sys
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

import requests
import time
import json
import random
from datetime import datetime
from app import config
from app.recipe_parser import ParsedRecipe, generate_recipe_id
from app.recipes import Recipe, load_recipes, save_recipes
from app.nutrition_generator import NutritionGenerator
from app.tag_inference import TagInferencer


# Variety configuration - rotate through these for diverse imports
# Only include cuisines with good recipe coverage in Spoonacular
CUISINES = [
    "american", "asian", "british", "cajun", "caribbean", "chinese",
    "european", "french", "german", "greek", "indian",
    "italian", "japanese", "korean", "latin american",
    "mediterranean", "mexican", "middle eastern",
    "southern", "spanish", "thai", "vietnamese"
]

MEAL_TYPES = [
    "main course", "side dish", "dessert", "appetizer", "salad", "bread",
    "breakfast", "soup", "beverage", "sauce", "marinade", "fingerfood",
    "snack", "drink"
]

DIETS = [
    None,  # No restriction (general recipes)
    "vegetarian",
    "vegan",
    "gluten free",
    "ketogenic",
    "paleo",
    "primal",
    "low fodmap",
    "whole30"
]

# File to track imported Spoonacular IDs
TRACKING_FILE = Path(__file__).parent / "spoonacular_imported.json"


def load_imported_ids():
    """Load set of already-imported Spoonacular recipe IDs."""
    if TRACKING_FILE.exists():
        with open(TRACKING_FILE, "r") as f:
            data = json.load(f)
            return set(data.get("imported_ids", []))
    return set()


def save_imported_ids(imported_ids):
    """Save the set of imported Spoonacular recipe IDs."""
    TRACKING_FILE.parent.mkdir(exist_ok=True)
    with open(TRACKING_FILE, "w") as f:
        json.dump({
            "imported_ids": list(imported_ids),
            "last_updated": datetime.now().isoformat()
        }, f, indent=2)


def load_variety_state():
    """Load current variety rotation state."""
    if TRACKING_FILE.exists():
        with open(TRACKING_FILE, "r") as f:
            data = json.load(f)
            return data.get("variety_state", {
                "cuisine_index": 0,
                "meal_type_index": 0,
                "diet_index": 0
            })
    return {"cuisine_index": 0, "meal_type_index": 0, "diet_index": 0}


def save_variety_state(state):
    """Save variety rotation state."""
    TRACKING_FILE.parent.mkdir(exist_ok=True)
    data = {}
    if TRACKING_FILE.exists():
        with open(TRACKING_FILE, "r") as f:
            data = json.load(f)

    data["variety_state"] = state
    data["last_updated"] = datetime.now().isoformat()

    with open(TRACKING_FILE, "w") as f:
        json.dump(data, f, indent=2)


def search_spoonacular_recipes(api_key, cuisine=None, meal_type=None, diet=None, number=10, offset=0):
    """Search for recipes on Spoonacular with filters."""
    url = "https://api.spoonacular.com/recipes/complexSearch"

    params = {
        "apiKey": api_key,
        "number": number,
        "offset": offset,
        "addRecipeInformation": True,
        "fillIngredients": True,
        "addRecipeNutrition": True,
        "instructionsRequired": True,
        "sort": "random"
    }

    if cuisine:
        params["cuisine"] = cuisine
    if meal_type:
        params["type"] = meal_type
    if diet:
        params["diet"] = diet

    response = requests.get(url, params=params)
    response.raise_for_status()
    return response.json()


def parse_spoonacular_recipe(recipe_data):
    """Convert Spoonacular recipe format to ParsedRecipe."""

    # Parse ingredients
    ingredients = []
    for ing in recipe_data.get("extendedIngredients", []):
        ingredients.append({
            "quantity": ing.get("amount", 0),
            "unit": ing.get("unit", ""),
            "item": ing.get("name", ""),
            "notes": ing.get("original", ""),
            "category": ing.get("aisle", "").lower() if ing.get("aisle") else "other"
        })

    # Parse instructions
    instructions = []
    analyzed_instructions = recipe_data.get("analyzedInstructions", [])

    if analyzed_instructions:
        for instruction_set in analyzed_instructions:
            for step in instruction_set.get("steps", []):
                instructions.append(step.get("step", ""))
    else:
        # Fallback to summary if structured instructions not available
        summary = recipe_data.get("instructions", "")
        if summary:
            instructions = [s.strip() for s in summary.split(".") if s.strip()]

    # Extract nutrition
    nutrition_data = recipe_data.get("nutrition", {})
    nutrients = {n["name"]: n["amount"] for n in nutrition_data.get("nutrients", [])}

    # Build tags
    tags = []
    if recipe_data.get("cuisines"):
        tags.extend([c.lower() for c in recipe_data["cuisines"]])
    if recipe_data.get("dishTypes"):
        tags.extend([d.lower() for d in recipe_data["dishTypes"]])
    if recipe_data.get("diets"):
        tags.extend([d.lower() for d in recipe_data["diets"]])
    tags.append("spoonacular")

    # Create ParsedRecipe
    parsed_recipe = ParsedRecipe(
        name=recipe_data["title"],
        servings=recipe_data.get("servings", 4),
        prep_time_minutes=recipe_data.get("preparationMinutes"),
        cook_time_minutes=recipe_data.get("cookingMinutes"),
        ingredients=ingredients,
        instructions=instructions,
        tags=tags,
        source_url=recipe_data.get("sourceUrl"),
        image_url=recipe_data.get("image"),
        # Nutrition from Spoonacular
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
        iron_per_serving=nutrients.get("Iron", 0)
    )

    return parsed_recipe, recipe_data["id"]


def main():
    """Main daily import function."""
    print("=" * 70)
    print("Spoonacular Daily Recipe Import")
    print(f"Run Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    print()

    # Check for API key
    if not config.SPOONACULAR_API_KEY:
        print("❌ Error: SPOONACULAR_API_KEY not configured")
        print()
        print("You need a Spoonacular API key to use this script.")
        print("Get your FREE API key at: https://spoonacular.com/food-api/console#Dashboard")
        print()
        print("Then add it to your .env file:")
        print('  SPOONACULAR_API_KEY="your-key-here"')
        print()
        print("Or set it as an environment variable:")
        print('  export SPOONACULAR_API_KEY="your-key-here"')
        return

    spoonacular_api_key = config.SPOONACULAR_API_KEY
    recipes_file = Path(config.RECIPES_FILE)

    # Load existing recipes
    print(f"Loading existing recipes from: {recipes_file}")
    existing_recipes = load_recipes(recipes_file)
    existing_ids = {r.id for r in existing_recipes}
    existing_names = {r.name.lower() for r in existing_recipes}
    print(f"Found {len(existing_recipes)} existing recipes")

    # Load tracking data
    imported_spoonacular_ids = load_imported_ids()
    variety_state = load_variety_state()
    print(f"Previously imported {len(imported_spoonacular_ids)} Spoonacular recipes")
    print()

    # Determine today's variety mix
    # Rotate through cuisines, meal types, and diets to ensure variety
    cuisine = CUISINES[variety_state["cuisine_index"] % len(CUISINES)]
    meal_type = MEAL_TYPES[variety_state["meal_type_index"] % len(MEAL_TYPES)]
    diet = DIETS[variety_state["diet_index"] % len(DIETS)]

    print("🎲 Today's variety filters:")
    print(f"   Cuisine: {cuisine}")
    print(f"   Meal Type: {meal_type}")
    print(f"   Diet: {diet if diet else 'None (general recipes)'}")
    print()

    # Update variety state for next run
    variety_state["cuisine_index"] += 1
    variety_state["meal_type_index"] += 1
    variety_state["diet_index"] += 1
    save_variety_state(variety_state)

    print("=" * 70)
    print("Fetching recipes from Spoonacular...")
    print("=" * 70)
    print()

    target_count = 50
    imported_count = 0
    skipped_count = 0
    failed_count = 0
    offset = 0

    tag_inferencer = TagInferencer()

    # Try with filters first, fall back to less restrictive if no results
    search_attempts = [
        {"cuisine": cuisine, "meal_type": meal_type, "diet": diet},
        {"cuisine": cuisine, "meal_type": meal_type, "diet": None},  # Remove diet filter
        {"cuisine": cuisine, "meal_type": None, "diet": None},  # Only cuisine
        {"cuisine": None, "meal_type": meal_type, "diet": None},  # Only meal type
        {"cuisine": None, "meal_type": None, "diet": None},  # No filters
    ]

    current_search_idx = 0
    current_search = search_attempts[current_search_idx]

    while imported_count < target_count:
        try:
            # Search for recipes
            print(f"Searching with offset {offset}...", flush=True)
            results = search_spoonacular_recipes(
                api_key=spoonacular_api_key,
                cuisine=current_search["cuisine"],
                meal_type=current_search["meal_type"],
                diet=current_search["diet"],
                number=10,
                offset=offset
            )

            recipes = results.get("results", [])

            if not recipes:
                # Try next search strategy if we haven't tried them all
                if offset == 0 and current_search_idx < len(search_attempts) - 1:
                    current_search_idx += 1
                    current_search = search_attempts[current_search_idx]
                    filters = []
                    if current_search["cuisine"]:
                        filters.append(f"cuisine={current_search['cuisine']}")
                    if current_search["meal_type"]:
                        filters.append(f"type={current_search['meal_type']}")
                    if current_search["diet"]:
                        filters.append(f"diet={current_search['diet']}")
                    print(f"  No results, trying with: {', '.join(filters) if filters else 'no filters'}...")
                    continue
                else:
                    print("  No more recipes found")
                    break

            for recipe_data in recipes:
                if imported_count >= target_count:
                    break

                recipe_name = recipe_data["title"]
                spoonacular_id = recipe_data["id"]

                # Check if already imported from Spoonacular
                if spoonacular_id in imported_spoonacular_ids:
                    print(f"⏭️  Skipping (already imported): {recipe_name}")
                    skipped_count += 1
                    continue

                # Check if recipe name already exists
                if recipe_name.lower() in existing_names:
                    print(f"⏭️  Skipping (name exists): {recipe_name}")
                    skipped_count += 1
                    imported_spoonacular_ids.add(spoonacular_id)  # Track to avoid re-checking
                    continue

                try:
                    print(f"📥 Importing: {recipe_name}")

                    # Parse recipe
                    parsed_recipe, spoon_id = parse_spoonacular_recipe(recipe_data)

                    # Enhance tags
                    parsed_recipe.tags = tag_inferencer.enhance_tags(
                        name=parsed_recipe.name,
                        ingredients=parsed_recipe.ingredients or [],
                        instructions=parsed_recipe.instructions or [],
                        prep_time_minutes=parsed_recipe.prep_time_minutes or 0,
                        cook_time_minutes=parsed_recipe.cook_time_minutes or 0,
                        existing_tags=parsed_recipe.tags or []
                    )
                    print(f"  🏷️  Tags: {', '.join(parsed_recipe.tags[:5])}")

                    # Generate unique ID
                    recipe_id = generate_recipe_id(parsed_recipe.name, existing_ids)
                    existing_ids.add(recipe_id)
                    existing_names.add(recipe_name.lower())

                    # Convert to Recipe
                    recipe_dict = parsed_recipe.to_recipe_dict(recipe_id)
                    new_recipe = Recipe.from_dict(recipe_dict)

                    # Add to list
                    existing_recipes.append(new_recipe)
                    imported_spoonacular_ids.add(spoonacular_id)
                    imported_count += 1

                    print(f"  ✅ Imported successfully! ({imported_count}/{target_count})")
                    print()

                except Exception as e:
                    print(f"  ❌ Error importing {recipe_name}: {e}")
                    failed_count += 1
                    print()
                    continue

            offset += 10
            time.sleep(1)  # Rate limiting

        except Exception as e:
            print(f"❌ Error during search: {e}")
            break

    # Save everything
    print("=" * 70)
    print("Saving data...")
    save_recipes(recipes_file, existing_recipes)
    save_imported_ids(imported_spoonacular_ids)
    print(f"✅ Saved {len(existing_recipes)} total recipes")
    print(f"✅ Tracked {len(imported_spoonacular_ids)} Spoonacular IDs")
    print()

    # Summary
    print("=" * 70)
    print("DAILY IMPORT SUMMARY")
    print("=" * 70)
    print(f"✅ Imported:    {imported_count} recipes")
    print(f"⏭️  Skipped:     {skipped_count} recipes (duplicates)")
    print(f"❌ Failed:      {failed_count} recipes")
    print(f"📚 Total in DB: {len(existing_recipes)} recipes")
    print("=" * 70)

    if imported_count < target_count:
        print()
        print("⚠️  WARNING: Did not reach target of 50 recipes")
        print("   This may happen if:")
        print("   - Current filters have too few recipes")
        print("   - Many recipes were already imported")
        print("   - API rate limit was reached")
        print()
        print("   Next run will use different variety filters")


if __name__ == "__main__":
    main()
