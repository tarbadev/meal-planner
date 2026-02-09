#!/usr/bin/env python3
"""Migration script to convert recipes.json from flat to nested nutrition structure.

This script converts recipes from the old format:
    {
        "calories_per_serving": 500,
        "protein_per_serving": 25.0,
        "carbs_per_serving": 50.0,
        "fat_per_serving": 20.0
    }

To the new format:
    {
        "nutrition_per_serving": {
            "calories": 500,
            "protein": 25.0,
            "carbs": 50.0,
            "fat": 20.0,
            "saturated_fat": null,
            ... (11 more extended fields)
        }
    }

The script is idempotent - it can be run multiple times safely.
"""

import json
import sys
from pathlib import Path


def migrate_recipe(recipe: dict) -> dict:
    """Migrate a single recipe from old to new format.

    Args:
        recipe: Recipe dict (may be old or new format)

    Returns:
        Recipe dict in new format
    """
    # Check if already migrated
    if "nutrition_per_serving" in recipe:
        print(f"  ✓ Recipe '{recipe['name']}' already migrated")
        return recipe

    # Migrate from old format
    print(f"  → Migrating recipe '{recipe['name']}'")

    # Extract old fields
    calories = recipe.pop("calories_per_serving", 0)
    protein = recipe.pop("protein_per_serving", 0.0)
    carbs = recipe.pop("carbs_per_serving", 0.0)
    fat = recipe.pop("fat_per_serving", 0.0)

    # Create new nested structure
    recipe["nutrition_per_serving"] = {
        "calories": calories,
        "protein": protein,
        "carbs": carbs,
        "fat": fat,
        # New fields default to None
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

    return recipe


def migrate_recipes_file(file_path: Path) -> bool:
    """Migrate recipes.json file from old to new format.

    Args:
        file_path: Path to recipes.json

    Returns:
        True if migration was successful
    """
    print(f"Reading recipes from {file_path}...")

    # Check if file exists
    if not file_path.exists():
        print(f"Error: File not found: {file_path}")
        return False

    # Load current recipes
    try:
        with open(file_path) as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in {file_path}: {e}")
        return False

    if "recipes" not in data:
        print("Error: recipes.json must contain a 'recipes' key")
        return False

    recipes = data["recipes"]
    print(f"Found {len(recipes)} recipes")

    # Migrate each recipe
    print("\nMigrating recipes...")
    migrated_recipes = []
    for recipe in recipes:
        migrated_recipe = migrate_recipe(recipe)
        migrated_recipes.append(migrated_recipe)

    # Save back to file
    print(f"\nSaving migrated recipes to {file_path}...")
    data["recipes"] = migrated_recipes

    try:
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2)
        print("✓ Migration complete!")
        return True
    except OSError as e:
        print(f"Error: Failed to write to {file_path}: {e}")
        return False


def main():
    """Main entry point for migration script."""
    # Default to data/recipes.json
    if len(sys.argv) > 1:
        file_path = Path(sys.argv[1])
    else:
        # Assume script is in scripts/ directory, recipes.json in data/
        script_dir = Path(__file__).parent
        project_root = script_dir.parent
        file_path = project_root / "data" / "recipes.json"

    print("=" * 60)
    print("Nutrition Migration Script")
    print("=" * 60)
    print(f"Target file: {file_path}")
    print()

    # Perform migration
    success = migrate_recipes_file(file_path)

    if success:
        print()
        print("=" * 60)
        print("Migration completed successfully!")
        print("=" * 60)
        sys.exit(0)
    else:
        print()
        print("=" * 60)
        print("Migration failed!")
        print("=" * 60)
        sys.exit(1)


if __name__ == "__main__":
    main()
