#!/usr/bin/env python3
"""
Import all recipes from TheMealDB API and backfill nutrition data.

TheMealDB provides ~300 free recipes with ingredients and instructions.
This script fetches all recipes and generates nutrition data using the USDA API.

Usage:
    python import_themealdb.py              # Import all recipes
    python import_themealdb.py --limit 5    # Import only 5 recipes (for testing)
"""

import argparse
import sys
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

import time

import requests

from app import config
from app.nutrition_generator import NutritionGenerator
from app.recipe_parser import ParsedRecipe, generate_recipe_id
from app.recipes import Recipe, load_recipes, save_recipes
from app.tag_inference import TagInferencer


def fetch_all_themealdb_recipes(limit=None):
    """Fetch all available recipes from TheMealDB API."""
    base_url = "https://www.themealdb.com/api/json/v1/1"

    limit_msg = f" (limit: {limit})" if limit else ""
    print(f"Fetching recipes from TheMealDB{limit_msg}...")
    print("-" * 60)

    # Get all categories
    print("📥 Fetching category list...", flush=True)
    categories_url = f"{base_url}/list.php?c=list"
    response = requests.get(categories_url)
    response.raise_for_status()
    categories = [cat["strCategory"] for cat in response.json()["meals"]]

    print(f"✅ Found {len(categories)} categories: {', '.join(categories[:5])}...")
    print()

    all_recipes = []

    # Fetch recipes from each category
    for cat_idx, category in enumerate(categories, 1):
        if limit and len(all_recipes) >= limit:
            print(f"\n✅ Reached limit of {limit} recipes")
            break

        print(f"📂 [{cat_idx}/{len(categories)}] Category: {category}", flush=True)
        category_url = f"{base_url}/filter.php?c={category}"

        try:
            response = requests.get(category_url)
            response.raise_for_status()
            meals = response.json().get("meals", [])

            if not meals:
                print("   ⚠️  No recipes found")
                continue

            print(f"   Found {len(meals)} recipes", flush=True)

            # Fetch full details for each recipe
            for meal_idx, meal in enumerate(meals, 1):
                if limit and len(all_recipes) >= limit:
                    break

                meal_id = meal["idMeal"]
                meal_name = meal["strMeal"]
                detail_url = f"{base_url}/lookup.php?i={meal_id}"

                try:
                    print(f"   [{meal_idx}/{len(meals)}] Fetching: {meal_name}...", end=" ", flush=True)
                    detail_response = requests.get(detail_url)
                    detail_response.raise_for_status()
                    meal_detail = detail_response.json()["meals"][0]
                    all_recipes.append(meal_detail)
                    print("✅")
                    time.sleep(0.1)  # Be nice to the API
                except Exception as e:
                    print(f"❌ Error: {e}")
                    continue

        except Exception as e:
            print(f"   ❌ Error fetching category: {e}")
            continue

    print()
    print(f"✅ Total recipes fetched: {len(all_recipes)}")
    return all_recipes


def parse_themealdb_recipe(meal_data):
    """Convert TheMealDB recipe format to ParsedRecipe."""

    # Parse ingredients (TheMealDB has ingredients as strIngredient1-20 and strMeasure1-20)
    ingredients = []
    for i in range(1, 21):
        ingredient = meal_data.get(f"strIngredient{i}", "")
        measure = meal_data.get(f"strMeasure{i}", "")

        if ingredient and ingredient.strip():
            # Combine measure and ingredient
            ingredient_text = f"{measure} {ingredient}".strip()

            # Parse into structured format (basic parsing)
            from app.ingredient_parser import IngredientParser
            parser = IngredientParser()
            parsed = parser.parse(ingredient_text)

            ingredients.append({
                "quantity": parsed.quantity,
                "unit": parsed.unit,
                "item": parsed.item,
                "notes": parsed.notes,
                "category": parsed.category
            })

    # Parse instructions (split by newlines or periods)
    instructions_text = meal_data.get("strInstructions", "")
    instructions = []

    # Split by numbered steps or newlines
    if "\r\n" in instructions_text:
        instructions = [s.strip() for s in instructions_text.split("\r\n") if s.strip()]
    elif "\n" in instructions_text:
        instructions = [s.strip() for s in instructions_text.split("\n") if s.strip()]
    else:
        # Split by periods if no newlines
        instructions = [s.strip() + "." for s in instructions_text.split(".") if s.strip()]

    # Build tags from category and area
    tags = []
    if meal_data.get("strCategory"):
        tags.append(meal_data["strCategory"].lower())
    if meal_data.get("strArea"):
        tags.append(meal_data["strArea"].lower())
    tags.append("themealdb")

    # Create ParsedRecipe
    parsed_recipe = ParsedRecipe(
        name=meal_data["strMeal"],
        servings=4,  # TheMealDB doesn't provide servings, default to 4
        prep_time_minutes=None,  # Not provided
        cook_time_minutes=None,  # Not provided
        ingredients=ingredients,
        instructions=instructions,
        tags=tags,
        source_url=meal_data.get("strSource"),
        image_url=meal_data.get("strMealThumb"),
        calories_per_serving=None,
        protein_per_serving=None,
        carbs_per_serving=None,
        fat_per_serving=None
    )

    return parsed_recipe


def has_nutrition(recipe):
    """Check if a recipe has meaningful nutrition data."""
    nutrition = recipe.nutrition_per_serving
    if not nutrition:
        return False

    # Check if nutrition is all zeros (failed generation)
    return (
        nutrition.get('calories', 0) > 0 or
        nutrition.get('protein', 0) > 0 or
        nutrition.get('carbs', 0) > 0 or
        nutrition.get('fat', 0) > 0
    )


def backfill_nutrition(parsed_recipe, nutrition_gen):
    """Generate nutrition data for a recipe if missing."""
    if nutrition_gen.should_generate_nutrition(parsed_recipe):
        generated_nutrition = nutrition_gen.generate_from_ingredients(
            parsed_recipe.ingredients,
            parsed_recipe.servings or 4
        )

        if generated_nutrition:
            parsed_recipe.calories_per_serving = int(generated_nutrition.calories)
            parsed_recipe.protein_per_serving = generated_nutrition.protein
            parsed_recipe.carbs_per_serving = generated_nutrition.carbs
            parsed_recipe.fat_per_serving = generated_nutrition.fat
            parsed_recipe.saturated_fat_per_serving = generated_nutrition.saturated_fat
            parsed_recipe.polyunsaturated_fat_per_serving = generated_nutrition.polyunsaturated_fat
            parsed_recipe.monounsaturated_fat_per_serving = generated_nutrition.monounsaturated_fat
            parsed_recipe.sodium_per_serving = generated_nutrition.sodium
            parsed_recipe.potassium_per_serving = generated_nutrition.potassium
            parsed_recipe.fiber_per_serving = generated_nutrition.fiber
            parsed_recipe.sugar_per_serving = generated_nutrition.sugar
            parsed_recipe.vitamin_a_per_serving = generated_nutrition.vitamin_a
            parsed_recipe.vitamin_c_per_serving = generated_nutrition.vitamin_c
            parsed_recipe.calcium_per_serving = generated_nutrition.calcium
            parsed_recipe.iron_per_serving = generated_nutrition.iron

            has_meaningful_nutrition = (
                generated_nutrition.calories > 0 or
                generated_nutrition.protein > 0 or
                generated_nutrition.carbs > 0 or
                generated_nutrition.fat > 0
            )
            if has_meaningful_nutrition:
                if not parsed_recipe.tags:
                    parsed_recipe.tags = []
                parsed_recipe.tags.append("nutrition-generated")

            return True

    return False


def enhance_tags(parsed_recipe, tag_inferencer):
    """Enhance tags using the tag inferencer."""
    parsed_recipe.tags = tag_inferencer.enhance_tags(
        name=parsed_recipe.name,
        ingredients=parsed_recipe.ingredients or [],
        instructions=parsed_recipe.instructions or [],
        prep_time_minutes=parsed_recipe.prep_time_minutes or 0,
        cook_time_minutes=parsed_recipe.cook_time_minutes or 0,
        existing_tags=parsed_recipe.tags or []
    )


def backfill_existing_nutrition(existing_recipes, recipes_file, limit=None):
    """Backfill nutrition for existing recipes missing nutrition data."""
    print("=" * 70)
    print("Backfilling nutrition for existing recipes...")
    print("=" * 70)
    print()

    nutrition_gen = NutritionGenerator(api_key=config.USDA_API_KEY)

    # Find recipes missing nutrition
    recipes_to_fix = [r for r in existing_recipes if not has_nutrition(r)]

    if limit:
        recipes_to_fix = recipes_to_fix[:limit]

    if not recipes_to_fix:
        print("✅ All recipes have nutrition data!")
        return

    print(f"Found {len(recipes_to_fix)} recipes needing nutrition")
    print()

    fixed_count = 0
    failed_count = 0

    for idx, recipe in enumerate(recipes_to_fix, 1):
        print(f"[{idx}/{len(recipes_to_fix)}] 🔧 Fixing: {recipe.name}", flush=True)

        try:
            # Convert Recipe to ParsedRecipe format for nutrition generation
            parsed_recipe = ParsedRecipe(
                name=recipe.name,
                servings=recipe.servings,
                prep_time_minutes=recipe.prep_time_minutes,
                cook_time_minutes=recipe.cook_time_minutes,
                ingredients=recipe.ingredients,
                instructions=recipe.instructions,
                tags=recipe.tags,
                source_url=recipe.source_url,
                image_url=recipe.image_url
            )

            # Generate nutrition
            print("   ⚙️  Generating nutrition...", end=" ", flush=True)
            nutrition_added = backfill_nutrition(parsed_recipe, nutrition_gen)

            if nutrition_added:
                # Update the recipe with new nutrition
                nutrition = recipe.nutrition_per_serving
                nutrition['calories'] = parsed_recipe.calories_per_serving or 0
                nutrition['protein'] = parsed_recipe.protein_per_serving or 0.0
                nutrition['carbs'] = parsed_recipe.carbs_per_serving or 0.0
                nutrition['fat'] = parsed_recipe.fat_per_serving or 0.0
                nutrition['saturated_fat'] = parsed_recipe.saturated_fat_per_serving
                nutrition['sodium'] = parsed_recipe.sodium_per_serving
                nutrition['fiber'] = parsed_recipe.fiber_per_serving
                nutrition['sugar'] = parsed_recipe.sugar_per_serving

                fixed_count += 1
                print(f"✅ ({nutrition['calories']} cal)")
            else:
                failed_count += 1
                print("❌ Failed")

        except Exception as e:
            print(f"   ❌ Error: {e}")
            failed_count += 1

    # Save updated recipes
    print()
    print("💾 Saving updated recipes...", flush=True)
    save_recipes(recipes_file, existing_recipes)

    print()
    print("=" * 70)
    print("BACKFILL SUMMARY")
    print("=" * 70)
    print(f"✅ Fixed:  {fixed_count} recipes")
    print(f"❌ Failed: {failed_count} recipes")
    print("=" * 70)


def main():
    """Main import function."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description="Import recipes from TheMealDB with nutrition generation"
    )
    parser.add_argument(
        '--limit',
        type=int,
        help='Limit number of recipes to import (useful for testing)'
    )
    parser.add_argument(
        '--backfill',
        action='store_true',
        help='Backfill nutrition for existing recipes with missing/zero nutrition'
    )
    parser.add_argument(
        '--skip-nutrition',
        action='store_true',
        help='Skip nutrition generation (import recipes only)'
    )
    args = parser.parse_args()

    print("=" * 70)
    print("TheMealDB Recipe Import Script")
    if args.limit:
        print(f"TEST MODE: Importing only {args.limit} recipe(s)")
    if args.backfill:
        print("BACKFILL MODE: Regenerating nutrition for recipes with missing data")
    if args.skip_nutrition:
        print("SKIP NUTRITION: Importing recipes without nutrition generation")
    print("=" * 70)
    print()

    # Load config
    recipes_file = Path(config.RECIPES_FILE)

    # Load existing recipes
    print(f"📁 Loading existing recipes from: {recipes_file}", flush=True)
    existing_recipes = load_recipes(recipes_file)
    existing_ids = {r.id for r in existing_recipes}
    existing_names = {r.name.lower() for r in existing_recipes}
    print(f"✅ Found {len(existing_recipes)} existing recipes")

    # Count recipes missing nutrition
    if args.backfill:
        missing_nutrition = [r for r in existing_recipes if not has_nutrition(r)]
        print(f"📊 Recipes missing nutrition: {len(missing_nutrition)}")
    print()

    # Backfill mode: regenerate nutrition for existing recipes
    if args.backfill:
        backfill_existing_nutrition(existing_recipes, recipes_file, args.limit)
        return

    # Fetch all TheMealDB recipes
    themealdb_recipes = fetch_all_themealdb_recipes(limit=args.limit)

    if not themealdb_recipes:
        print("No recipes fetched from TheMealDB!")
        return

    print()
    print("=" * 70)
    print("Processing and importing recipes...")
    print("=" * 70)
    print()

    # Initialize tools
    nutrition_gen = NutritionGenerator(api_key=config.USDA_API_KEY)
    tag_inferencer = TagInferencer()

    imported_count = 0
    skipped_count = 0
    failed_count = 0
    total = len(themealdb_recipes)

    for idx, meal_data in enumerate(themealdb_recipes, 1):
        recipe_name = meal_data["strMeal"]

        # Check if already exists (by name)
        if recipe_name.lower() in existing_names:
            print(f"[{idx}/{total}] ⏭️  Skipping: {recipe_name} (already exists)")
            skipped_count += 1
            continue

        try:
            print(f"\n[{idx}/{total}] 📥 Importing: {recipe_name}", flush=True)

            # Parse recipe
            print("   ⚙️  Parsing recipe...", end=" ", flush=True)
            parsed_recipe = parse_themealdb_recipe(meal_data)
            print("✅")

            # Backfill nutrition (unless --skip-nutrition is set)
            nutrition_added = False
            if not args.skip_nutrition:
                print("   ⚙️  Generating nutrition...", end=" ", flush=True)
                nutrition_added = backfill_nutrition(parsed_recipe, nutrition_gen)
                if nutrition_added:
                    print("✅")
                else:
                    print("⏭️  (skipped)")
            else:
                print("   ⏭️  Skipping nutrition (--skip-nutrition)")

            # Enhance tags
            print("   ⚙️  Inferring tags...", end=" ", flush=True)
            enhance_tags(parsed_recipe, tag_inferencer)
            print(f"✅ ({', '.join(parsed_recipe.tags[:3])}...)")

            # Generate unique ID
            recipe_id = generate_recipe_id(parsed_recipe.name, existing_ids)
            existing_ids.add(recipe_id)
            existing_names.add(recipe_name.lower())

            # Convert to Recipe
            recipe_dict = parsed_recipe.to_recipe_dict(recipe_id)
            new_recipe = Recipe.from_dict(recipe_dict)

            # Add to list
            existing_recipes.append(new_recipe)
            imported_count += 1

            print(f"   ✅ Success! ({imported_count} imported so far)")

            # Rate limit for USDA API (if generating nutrition)
            if nutrition_added:
                time.sleep(0.5)

        except Exception as e:
            print(f"   ❌ Error: {e}")
            failed_count += 1
            continue

    # Save all recipes
    print("=" * 60)
    print("Saving recipes to file...")
    save_recipes(recipes_file, existing_recipes)
    print(f"✅ Saved {len(existing_recipes)} total recipes")
    print()

    # Summary
    print("=" * 60)
    print("IMPORT SUMMARY")
    print("=" * 60)
    print(f"✅ Imported:    {imported_count} recipes")
    print(f"⏭️  Skipped:     {skipped_count} recipes (already exist)")
    print(f"❌ Failed:      {failed_count} recipes")
    print(f"📚 Total in DB: {len(existing_recipes)} recipes")
    print("=" * 60)


if __name__ == "__main__":
    main()
