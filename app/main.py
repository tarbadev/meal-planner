from pathlib import Path
from flask import Flask, render_template, jsonify, request

import config
from app.recipes import load_recipes, save_recipes, update_recipe, Recipe, RecipeSaveError
from app.planner import MealPlanner
from app.shopping_list import generate_shopping_list
from app.sheets import SheetsWriter, SheetsError

app = Flask(__name__)

# Store the current plan in memory (v1 - simple approach)
current_plan = None
current_shopping_list = None


@app.route("/")
def index():
    """Render the web UI."""
    recipes_file = Path(config.RECIPES_FILE)
    recipes = load_recipes(recipes_file)

    return render_template(
        "index.html",
        recipes=recipes,
        current_plan=current_plan,
        current_shopping_list=current_shopping_list,
        household_portions=config.TOTAL_PORTIONS
    )


@app.route("/generate", methods=["POST"])
def generate():
    """Generate a new weekly meal plan."""
    global current_plan, current_shopping_list

    recipes_file = Path(config.RECIPES_FILE)
    recipes = load_recipes(recipes_file)

    planner = MealPlanner(household_portions=config.TOTAL_PORTIONS)
    current_plan = planner.generate_weekly_plan(recipes)
    current_shopping_list = generate_shopping_list(current_plan)

    return jsonify({
        "success": True,
        "message": "Weekly plan generated successfully"
    })


@app.route("/recipes")
def recipes():
    """List all available recipes."""
    recipes_file = Path(config.RECIPES_FILE)
    all_recipes = load_recipes(recipes_file)

    return jsonify({
        "recipes": [
            {
                "id": r.id,
                "name": r.name,
                "servings": r.servings,
                "prep_time_minutes": r.prep_time_minutes,
                "cook_time_minutes": r.cook_time_minutes,
                "total_time_minutes": r.total_time_minutes,
                "calories_per_serving": r.calories_per_serving,
                "protein_per_serving": r.protein_per_serving,
                "tags": r.tags
            }
            for r in all_recipes
        ]
    })


@app.route("/recipes/<recipe_id>", methods=["GET"])
def get_recipe(recipe_id: str):
    """Fetch single recipe for editing."""
    recipes_file = Path(config.RECIPES_FILE)
    all_recipes = load_recipes(recipes_file)

    # Find recipe by ID
    recipe = None
    for r in all_recipes:
        if r.id == recipe_id:
            recipe = r
            break

    if recipe is None:
        return jsonify({
            "error": "Recipe not found",
            "message": f"No recipe found with ID '{recipe_id}'"
        }), 404

    # Return full recipe data including ingredients
    return jsonify({
        "id": recipe.id,
        "name": recipe.name,
        "servings": recipe.servings,
        "prep_time_minutes": recipe.prep_time_minutes,
        "cook_time_minutes": recipe.cook_time_minutes,
        "calories_per_serving": recipe.calories_per_serving,
        "protein_per_serving": recipe.protein_per_serving,
        "carbs_per_serving": recipe.carbs_per_serving,
        "fat_per_serving": recipe.fat_per_serving,
        "tags": recipe.tags,
        "ingredients": recipe.ingredients
    })


@app.route("/recipes/<recipe_id>", methods=["PUT"])
def update_recipe_endpoint(recipe_id: str):
    """Update existing recipe."""
    global current_plan, current_shopping_list

    # Parse request JSON
    try:
        data = request.get_json()
    except Exception:
        return jsonify({
            "error": "Invalid JSON",
            "message": "Request body must be valid JSON"
        }), 400

    if not data:
        return jsonify({
            "error": "Invalid request",
            "message": "Request body is required"
        }), 400

    # Validate recipe_id matches body
    if data.get("id") != recipe_id:
        return jsonify({
            "error": "ID mismatch",
            "message": f"Recipe ID in URL ('{recipe_id}') must match ID in body ('{data.get('id')}')"
        }), 400

    # Load recipes
    recipes_file = Path(config.RECIPES_FILE)
    all_recipes = load_recipes(recipes_file)

    # Check if recipe exists
    recipe_exists = any(r.id == recipe_id for r in all_recipes)
    if not recipe_exists:
        return jsonify({
            "error": "Recipe not found",
            "message": f"No recipe found with ID '{recipe_id}'"
        }), 404

    # Create Recipe object with validation
    try:
        updated_recipe = Recipe.from_dict(data)
    except ValueError as e:
        return jsonify({
            "error": "Validation error",
            "message": str(e)
        }), 400

    # Additional validation: positive numbers
    if updated_recipe.servings <= 0:
        return jsonify({
            "error": "Validation error",
            "message": "Servings must be positive"
        }), 400

    if updated_recipe.prep_time_minutes < 0:
        return jsonify({
            "error": "Validation error",
            "message": "Prep time cannot be negative"
        }), 400

    if updated_recipe.cook_time_minutes < 0:
        return jsonify({
            "error": "Validation error",
            "message": "Cook time cannot be negative"
        }), 400

    if updated_recipe.calories_per_serving < 0:
        return jsonify({
            "error": "Validation error",
            "message": "Calories cannot be negative"
        }), 400

    if updated_recipe.protein_per_serving < 0:
        return jsonify({
            "error": "Validation error",
            "message": "Protein cannot be negative"
        }), 400

    if updated_recipe.carbs_per_serving < 0:
        return jsonify({
            "error": "Validation error",
            "message": "Carbs cannot be negative"
        }), 400

    if updated_recipe.fat_per_serving < 0:
        return jsonify({
            "error": "Validation error",
            "message": "Fat cannot be negative"
        }), 400

    # Update recipe in list
    try:
        updated_recipes = update_recipe(all_recipes, updated_recipe)
    except ValueError as e:
        return jsonify({
            "error": "Update error",
            "message": str(e)
        }), 404

    # Save to file
    try:
        save_recipes(recipes_file, updated_recipes)
    except RecipeSaveError as e:
        return jsonify({
            "error": "Save error",
            "message": f"Failed to save recipe: {str(e)}"
        }), 500

    # Clear current_plan (force regeneration)
    current_plan = None
    current_shopping_list = None

    return jsonify({
        "success": True,
        "message": f"Recipe '{updated_recipe.name}' updated successfully. Please regenerate your meal plan."
    })


@app.route("/current-plan")
def get_current_plan():
    """Get the current weekly plan."""
    if current_plan is None:
        return jsonify({
            "plan": None,
            "message": "No plan generated yet"
        })

    return jsonify({
        "plan": {
            "meals": [
                {
                    "day": meal.day,
                    "recipe_name": meal.recipe.name,
                    "portions": meal.portions,
                    "calories": meal.calories,
                    "protein": meal.protein,
                    "carbs": meal.carbs,
                    "fat": meal.fat,
                    "prep_time": meal.recipe.prep_time_minutes,
                    "cook_time": meal.recipe.cook_time_minutes,
                    "total_time": meal.recipe.total_time_minutes
                }
                for meal in current_plan.meals
            ],
            "totals": {
                "calories": current_plan.total_calories,
                "protein": current_plan.total_protein,
                "carbs": current_plan.total_carbs,
                "fat": current_plan.total_fat
            },
            "daily_averages": {
                "calories": current_plan.avg_daily_calories,
                "protein": current_plan.avg_daily_protein,
                "carbs": current_plan.avg_daily_carbs,
                "fat": current_plan.avg_daily_fat
            }
        },
        "shopping_list": {
            "items": [
                {
                    "item": item.item,
                    "quantity": round(item.quantity, 2),
                    "unit": item.unit,
                    "category": item.category
                }
                for item in current_shopping_list.items
            ],
            "items_by_category": {
                category: [
                    {
                        "item": item.item,
                        "quantity": round(item.quantity, 2),
                        "unit": item.unit
                    }
                    for item in items
                ]
                for category, items in current_shopping_list.items_by_category().items()
            }
        }
    })


@app.route("/write-to-sheets", methods=["POST"])
def write_to_sheets():
    """Write the current plan to Google Sheets."""
    if current_plan is None or current_shopping_list is None:
        return jsonify({
            "success": False,
            "message": "No plan generated yet. Generate a plan first."
        }), 400

    try:
        # Check if credentials exist
        creds_path = Path(config.CREDENTIALS_FILE)
        if not creds_path.exists():
            return jsonify({
                "success": False,
                "message": "Google Sheets credentials not configured. See README for setup instructions."
            }), 400

        writer = SheetsWriter(
            credentials_file=config.CREDENTIALS_FILE,
            spreadsheet_id=config.GOOGLE_SHEETS_ID
        )

        result = writer.write_all(current_plan, current_shopping_list)

        return jsonify(result)

    except SheetsError as e:
        return jsonify({
            "success": False,
            "message": f"Error writing to Google Sheets: {str(e)}"
        }), 500
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"Unexpected error: {str(e)}"
        }), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
