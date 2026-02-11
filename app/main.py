from pathlib import Path

from flask import Flask, jsonify, render_template, request

from app import config
from app.planner import MealPlanner
from app.recipes import Recipe, RecipeSaveError, load_recipes, save_recipes, update_recipe
from app.sheets import SheetsError, SheetsWriter
from app.shopping_list import generate_shopping_list
from app.tag_inference import TagInferencer

app = Flask(__name__)

# Store the current plan in memory (v1 - simple approach)
current_plan = None
current_shopping_list = None
# Manual meal plan storage: {day: {meal_type: {recipe_id, servings}}}
manual_plan = {}


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
        household_portions=config.TOTAL_PORTIONS,
        config=config
    )


@app.route("/recipe/<recipe_id>")
def recipe_detail(recipe_id: str):
    """Display detailed recipe page."""
    recipes_file = Path(config.RECIPES_FILE)
    all_recipes = load_recipes(recipes_file)

    # Find recipe by ID
    recipe = None
    for r in all_recipes:
        if r.id == recipe_id:
            recipe = r
            break

    if recipe is None:
        return render_template(
            "error.html",
            error_title="Recipe Not Found",
            error_message=f"No recipe found with ID '{recipe_id}'"
        ), 404

    return render_template("recipe_detail.html", recipe=recipe)


@app.route("/share-recipe", methods=["POST"])
def share_recipe():
    """Handle PWA share target for recipe URLs and text.

    This endpoint receives shared content from the browser's share menu
    (Android Chrome, iOS Safari with Web Share Target API).
    """
    from urllib.parse import quote

    from flask import redirect, url_for

    # Get form data from share target
    url = request.form.get('url', '').strip()
    title = request.form.get('title', '').strip()
    text = request.form.get('text', '').strip()

    # Priority 1: If URL is shared, redirect to import with pre-filled URL
    if url:
        # Redirect to home page with import_url query parameter
        return redirect(url_for('index', import_url=url, _external=False))

    # Priority 2: If text is shared (but no URL), redirect to text import
    if text:
        # Redirect to home page with import_text query parameter
        return redirect(url_for('index', import_text=quote(text), _external=False))

    # Priority 3: Use title if available
    if title:
        return redirect(url_for('index', import_text=quote(title), _external=False))

    # Fallback: No content to share, just go to home page
    return redirect(url_for('index', _external=False))


@app.route("/generate", methods=["POST"])
def generate():
    """Generate a new weekly meal plan."""
    global current_plan, current_shopping_list

    recipes_file = Path(config.RECIPES_FILE)
    recipes = load_recipes(recipes_file)

    planner = MealPlanner(
        household_portions=config.TOTAL_PORTIONS,
        meal_schedule=config.MEAL_SCHEDULE,
        daily_calorie_limit=config.DAILY_CALORIE_LIMIT
    )
    current_plan = planner.generate_weekly_plan(recipes)
    current_shopping_list = generate_shopping_list(current_plan)

    return jsonify({
        "success": True,
        "message": "Weekly plan generated successfully"
    })


@app.route("/generate-with-schedule", methods=["POST"])
def generate_with_schedule():
    """Generate a meal plan with custom schedule and per-meal servings."""
    global manual_plan, current_plan, current_shopping_list
    import random

    try:
        data = request.get_json()
    except Exception:
        return jsonify({"error": "Invalid JSON"}), 400

    schedule = data.get("schedule", {})
    if not schedule:
        return jsonify({"error": "Schedule is required"}), 400

    recipes_file = Path(config.RECIPES_FILE)
    recipes = load_recipes(recipes_file)

    # Build meal slots from schedule
    meal_slots = []
    for day, day_meals in schedule.items():
        for meal_type, servings in day_meals.items():
            meal_slots.append((day, meal_type, servings))

    # Validate enough recipes
    if len(recipes) < len(meal_slots):
        return jsonify({
            "error": f"Need at least {len(meal_slots)} recipes. Only {len(recipes)} available."
        }), 400

    # Generate plan
    manual_plan = {}
    used_recipes = set()

    for day, meal_type, servings in meal_slots:
        # Try to find suitable recipe for this meal type
        suitable = [r for r in recipes if meal_type in r.tags and r.id not in used_recipes]

        # Fallback to any unused recipe
        if not suitable:
            suitable = [r for r in recipes if r.id not in used_recipes]

        if not suitable:
            return jsonify({"error": f"Not enough recipes for {day} {meal_type}"}), 400

        recipe = random.choice(suitable)
        used_recipes.add(recipe.id)

        # Add to manual plan
        if day not in manual_plan:
            manual_plan[day] = {}
        manual_plan[day][meal_type] = {
            "recipe_id": recipe.id,
            "servings": servings
        }

    # Regenerate plan from manual_plan
    _regenerate_from_manual_plan(recipes)

    return jsonify({
        "success": True,
        "message": f"Generated plan with {len(meal_slots)} meals"
    })


@app.route("/import-recipe", methods=["POST"])
def import_recipe():
    """Import a recipe from a URL."""
    global current_plan, current_shopping_list

    try:
        data = request.get_json()
    except Exception:
        return jsonify({
            "error": "Invalid JSON",
            "message": "Request body must be valid JSON"
        }), 400

    if not data or 'url' not in data:
        return jsonify({
            "error": "Invalid request",
            "message": "URL is required"
        }), 400

    url = data['url']

    # Validate URL format
    if not url.startswith('http://') and not url.startswith('https://'):
        return jsonify({
            "error": "Invalid URL",
            "message": "URL must start with http:// or https://"
        }), 400

    try:
        # Parse recipe from URL
        from app.ai_recipe_extractor import AIExtractionError
        from app.instagram_fetcher import InstagramFetchError
        from app.nutrition_generator import NutritionGenerator
        from app.recipe_parser import RecipeParseError, RecipeParser, generate_recipe_id

        parser = RecipeParser()
        parsed_recipe = parser.parse_from_url(url)

        # Generate nutrition if missing
        nutrition_gen = NutritionGenerator(api_key=config.USDA_API_KEY)
        if nutrition_gen.should_generate_nutrition(parsed_recipe):
            generated_nutrition = nutrition_gen.generate_from_ingredients(
                parsed_recipe.ingredients,
                parsed_recipe.servings or 4
            )

            if generated_nutrition:
                # Update parsed recipe with generated nutrition (all 15 fields)
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

                # Only add tag if meaningful nutrition was generated (not all zeros)
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

        # Infer additional tags based on recipe content
        tag_inferencer = TagInferencer()
        parsed_recipe.tags = tag_inferencer.enhance_tags(
            name=parsed_recipe.name,
            ingredients=parsed_recipe.ingredients or [],
            instructions=parsed_recipe.instructions or [],
            prep_time_minutes=parsed_recipe.prep_time_minutes or 0,
            cook_time_minutes=parsed_recipe.cook_time_minutes or 0,
            existing_tags=parsed_recipe.tags or []
        )

        # Load existing recipes
        recipes_file = Path(config.RECIPES_FILE)
        existing_recipes = load_recipes(recipes_file)
        existing_ids = {r.id for r in existing_recipes}

        # Generate unique ID
        recipe_id = generate_recipe_id(parsed_recipe.name, existing_ids)

        # Convert to Recipe dict
        recipe_dict = parsed_recipe.to_recipe_dict(recipe_id)

        # Validate using Recipe.from_dict
        new_recipe = Recipe.from_dict(recipe_dict)

        # Add to recipes list and save
        updated_recipes = existing_recipes + [new_recipe]
        save_recipes(recipes_file, updated_recipes)

        # Clear current plan to force regeneration
        current_plan = None
        current_shopping_list = None

        # Build response with optional AI confidence
        response_data = {
            "success": True,
            "message": f"Recipe '{new_recipe.name}' imported successfully",
            "recipe": {
                "id": new_recipe.id,
                "name": new_recipe.name,
                "servings": new_recipe.servings,
                "has_nutrition": (new_recipe.calories_per_serving > 0),
                "nutrition_generated": "nutrition-generated" in new_recipe.tags,
                "ingredient_count": len(new_recipe.ingredients),
                "instruction_count": len(new_recipe.instructions)
            }
        }

        # Add AI confidence if available (Instagram imports)
        if hasattr(parsed_recipe, 'ai_confidence'):
            response_data["recipe"]["ai_confidence"] = parsed_recipe.ai_confidence
            if parsed_recipe.ai_confidence < 0.7:
                response_data["warning"] = "Recipe extraction confidence is low. Please review the imported data carefully."

        return jsonify(response_data)

    except InstagramFetchError as e:
        return jsonify({
            "error": "Instagram fetch error",
            "message": str(e),
            "suggestion": "Try using 'Import from Text' by copying the post description manually"
        }), 400
    except AIExtractionError as e:
        return jsonify({
            "error": "AI extraction error",
            "message": str(e),
            "suggestion": "The recipe text may be unclear or incomplete. Please try a different post or add manually."
        }), 400
    except RecipeParseError as e:
        return jsonify({
            "error": "Parse error",
            "message": str(e)
        }), 400
    except ValueError as e:
        return jsonify({
            "error": "Validation error",
            "message": str(e)
        }), 400
    except RecipeSaveError as e:
        return jsonify({
            "error": "Save error",
            "message": f"Failed to save recipe: {str(e)}"
        }), 500
    except Exception as e:
        return jsonify({
            "error": "Import error",
            "message": f"Unexpected error: {str(e)}"
        }), 500


@app.route("/import-recipe-text", methods=["POST"])
def import_recipe_text():
    """Import a recipe from manually pasted text (Instagram fallback)."""
    global current_plan, current_shopping_list

    try:
        data = request.get_json()
    except Exception:
        return jsonify({
            "error": "Invalid JSON",
            "message": "Request body must be valid JSON"
        }), 400

    if not data or 'text' not in data:
        return jsonify({
            "error": "Invalid request",
            "message": "Text is required"
        }), 400

    text = data['text']
    language = data.get('language', 'auto')

    if not text or len(text.strip()) < 50:
        return jsonify({
            "error": "Invalid text",
            "message": "Recipe text must be at least 50 characters long"
        }), 400

    try:
        # Parse recipe from text using AI
        from app.ai_recipe_extractor import AIExtractionError
        from app.instagram_parser import InstagramParser
        from app.nutrition_generator import NutritionGenerator
        from app.recipe_parser import RecipeParseError, generate_recipe_id

        print("Init of instagram_parser")
        instagram_parser = InstagramParser(
            openai_api_key=config.OPENAI_API_KEY
        )
        print("Init of instagram_parser")
        parsed_recipe = instagram_parser.parse_from_text(text, language)

        # Generate nutrition if missing
        nutrition_gen = NutritionGenerator(api_key=config.USDA_API_KEY)
        if nutrition_gen.should_generate_nutrition(parsed_recipe):
            generated_nutrition = nutrition_gen.generate_from_ingredients(
                parsed_recipe.ingredients,
                parsed_recipe.servings or 4
            )

            if generated_nutrition:
                # Update parsed recipe with generated nutrition (all 15 fields)
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

                # Only add tag if meaningful nutrition was generated (not all zeros)
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

        # Infer additional tags based on recipe content
        tag_inferencer = TagInferencer()
        parsed_recipe.tags = tag_inferencer.enhance_tags(
            name=parsed_recipe.name,
            ingredients=parsed_recipe.ingredients or [],
            instructions=parsed_recipe.instructions or [],
            prep_time_minutes=parsed_recipe.prep_time_minutes or 0,
            cook_time_minutes=parsed_recipe.cook_time_minutes or 0,
            existing_tags=parsed_recipe.tags or []
        )

        # Load existing recipes
        recipes_file = Path(config.RECIPES_FILE)
        existing_recipes = load_recipes(recipes_file)
        existing_ids = {r.id for r in existing_recipes}

        # Generate unique ID
        recipe_id = generate_recipe_id(parsed_recipe.name, existing_ids)

        # Convert to Recipe dict
        recipe_dict = parsed_recipe.to_recipe_dict(recipe_id)

        # Validate using Recipe.from_dict
        new_recipe = Recipe.from_dict(recipe_dict)

        # Add to recipes list and save
        updated_recipes = existing_recipes + [new_recipe]
        save_recipes(recipes_file, updated_recipes)

        # Clear current plan to force regeneration
        current_plan = None
        current_shopping_list = None

        # Build response with AI confidence
        response_data = {
            "success": True,
            "message": f"Recipe '{new_recipe.name}' imported successfully from text",
            "recipe": {
                "id": new_recipe.id,
                "name": new_recipe.name,
                "servings": new_recipe.servings,
                "has_nutrition": (new_recipe.calories_per_serving > 0),
                "nutrition_generated": "nutrition-generated" in new_recipe.tags,
                "ingredient_count": len(new_recipe.ingredients),
                "instruction_count": len(new_recipe.instructions)
            }
        }

        # Add AI confidence
        if hasattr(parsed_recipe, 'ai_confidence'):
            response_data["recipe"]["ai_confidence"] = parsed_recipe.ai_confidence
            if parsed_recipe.ai_confidence < 0.7:
                response_data["warning"] = "Recipe extraction confidence is low. Please review the imported data carefully."

        return jsonify(response_data)

    except AIExtractionError as e:
        return jsonify({
            "error": "AI extraction error",
            "message": str(e),
            "suggestion": "The recipe text may be unclear or incomplete. Please try different text or add manually."
        }), 400
    except RecipeParseError as e:
        return jsonify({
            "error": "Parse error",
            "message": str(e)
        }), 400
    except ValueError as e:
        return jsonify({
            "error": "Validation error",
            "message": str(e)
        }), 400
    except RecipeSaveError as e:
        return jsonify({
            "error": "Save error",
            "message": f"Failed to save recipe: {str(e)}"
        }), 500
    except Exception as e:
        return jsonify({
            "error": "Import error",
            "message": f"Unexpected error: {str(e)}"
        }), 500


@app.route("/import-recipe-image", methods=["POST"])
def import_recipe_image():
    """Import a recipe from a photo."""
    global current_plan, current_shopping_list

    # Check if image file is present
    if 'image' not in request.files:
        return jsonify({
            "error": "No image provided",
            "message": "Image file is required"
        }), 400

    file = request.files['image']

    if file.filename == '':
        return jsonify({
            "error": "No file selected",
            "message": "Please select an image file"
        }), 400

    # Validate file type
    allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
    file_ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''
    if file_ext not in allowed_extensions:
        return jsonify({
            "error": "Invalid file type",
            "message": f"Allowed types: {', '.join(allowed_extensions)}"
        }), 400

    try:
        # Read image data
        image_data = file.read()

        # Extract recipe from image using Vision API
        from app.image_recipe_extractor import ImageRecipeExtractor
        from app.nutrition_generator import NutritionGenerator
        from app.recipe_parser import ParsedRecipe, generate_recipe_id

        extractor = ImageRecipeExtractor(api_key=config.OPENAI_API_KEY)
        extracted_data = extractor.extract_recipe(image_data, file_ext)
    except ValueError as e:
        return jsonify({
            "error": "Extraction failed",
            "message": str(e)
        }), 422
    except Exception as e:
        # Check if it looks like a timeout
        error_msg = str(e)
        if "timeout" in error_msg.lower():
            return jsonify({
                "error": "Timeout",
                "message": "The image processing took too long. Please try again with a smaller or clearer image."
            }), 504
        return jsonify({
            "error": "Processing failed",
            "message": f"An error occurred while processing the image: {error_msg}"
        }), 500

    try:
        # Convert to ParsedRecipe format
        parsed_recipe = ParsedRecipe(
            name=extracted_data.name,
            servings=extracted_data.servings,
            prep_time_minutes=extracted_data.prep_time_minutes,
            cook_time_minutes=extracted_data.cook_time_minutes,
            total_time_minutes=(extracted_data.prep_time_minutes or 0) + (extracted_data.cook_time_minutes or 0) if extracted_data.prep_time_minutes or extracted_data.cook_time_minutes else None,
            ingredients=extracted_data.ingredients,
            instructions=extracted_data.instructions,
            tags=extracted_data.tags + ["photo-imported"],
            source_url=None,
            notes=extracted_data.notes,
            calories_per_serving=None,
            protein_per_serving=None,
            carbs_per_serving=None,
            fat_per_serving=None
        )
        parsed_recipe.ai_confidence = extracted_data.confidence

        # Generate nutrition if missing
        nutrition_gen = NutritionGenerator(api_key=config.USDA_API_KEY)
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

        # Infer additional tags
        tag_inferencer = TagInferencer()
        parsed_recipe.tags = tag_inferencer.enhance_tags(
            name=parsed_recipe.name,
            ingredients=parsed_recipe.ingredients or [],
            instructions=parsed_recipe.instructions or [],
            prep_time_minutes=parsed_recipe.prep_time_minutes or 0,
            cook_time_minutes=parsed_recipe.cook_time_minutes or 0,
            existing_tags=parsed_recipe.tags or []
        )

        # Load existing recipes
        recipes_file = Path(config.RECIPES_FILE)
        existing_recipes = load_recipes(recipes_file)
        existing_ids = {r.id for r in existing_recipes}

        # Generate unique ID
        recipe_id = generate_recipe_id(parsed_recipe.name, existing_ids)

        # Convert to Recipe dict
        recipe_dict = parsed_recipe.to_recipe_dict(recipe_id)

        # Validate using Recipe.from_dict
        new_recipe = Recipe.from_dict(recipe_dict)

        # Add to recipes list and save
        updated_recipes = existing_recipes + [new_recipe]
        save_recipes(recipes_file, updated_recipes)

        # Clear current plan
        current_plan = None
        current_shopping_list = None

        # Build response
        response_data = {
            "success": True,
            "message": f"Recipe '{new_recipe.name}' imported successfully from photo",
            "recipe": {
                "id": new_recipe.id,
                "name": new_recipe.name,
                "servings": new_recipe.servings,
                "has_nutrition": (new_recipe.calories_per_serving > 0),
                "nutrition_generated": "nutrition-generated" in new_recipe.tags,
                "ingredient_count": len(new_recipe.ingredients),
                "instruction_count": len(new_recipe.instructions),
                "ai_confidence": extracted_data.confidence
            }
        }

        if extracted_data.confidence < 0.7:
            response_data["warning"] = "Recipe extraction confidence is low. Please review the imported data carefully."

        return jsonify(response_data)

    except ValueError as e:
        return jsonify({
            "error": "Extraction error",
            "message": str(e),
            "suggestion": "The image may be unclear or not contain a recipe. Please try a clearer photo."
        }), 400
    except RecipeSaveError as e:
        return jsonify({
            "error": "Save error",
            "message": f"Failed to save recipe: {str(e)}"
        }), 500
    except Exception as e:
        return jsonify({
            "error": "Import error",
            "message": f"Unexpected error: {str(e)}"
        }), 500


@app.route("/recipes", methods=["GET"])
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


@app.route("/recipes", methods=["POST"])
def create_recipe():
    """Create a new recipe manually."""
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

    # Validate required fields
    required_fields = ["name", "servings", "ingredients", "instructions"]
    missing_fields = []
    for field in required_fields:
        if field not in data:
            missing_fields.append(field)
        elif field in ["ingredients", "instructions"] and not data[field]:
            # For lists, check if empty
            missing_fields.append(field)
        elif field == "name" and not data[field].strip():
            # For name, check if empty string
            missing_fields.append(field)
        # Note: servings can be 0, so we don't check "not data[field]" for it

    if missing_fields:
        return jsonify({
            "error": "Validation error",
            "message": f"Missing required fields: {', '.join(missing_fields)}"
        }), 400

    # Validate ingredients (must be non-empty list)
    if not isinstance(data["ingredients"], list) or len(data["ingredients"]) == 0:
        return jsonify({
            "error": "Validation error",
            "message": "At least one ingredient is required"
        }), 400

    # Validate instructions (must be non-empty list)
    if not isinstance(data["instructions"], list) or len(data["instructions"]) == 0:
        return jsonify({
            "error": "Validation error",
            "message": "At least one instruction step is required"
        }), 400

    # Validate numeric fields
    try:
        servings = int(data["servings"])
        if servings <= 0:
            return jsonify({
                "error": "Validation error",
                "message": "Servings must be a positive number"
            }), 400
    except (ValueError, TypeError):
        return jsonify({
            "error": "Validation error",
            "message": "Servings must be a valid number"
        }), 400

    prep_time_minutes = data.get("prep_time_minutes", 0)
    cook_time_minutes = data.get("cook_time_minutes", 0)

    try:
        prep_time_minutes = int(prep_time_minutes)
        cook_time_minutes = int(cook_time_minutes)
        if prep_time_minutes < 0 or cook_time_minutes < 0:
            return jsonify({
                "error": "Validation error",
                "message": "Time values cannot be negative"
            }), 400
    except (ValueError, TypeError):
        return jsonify({
            "error": "Validation error",
            "message": "Time values must be valid numbers"
        }), 400

    # Load existing recipes
    recipes_file = Path(config.RECIPES_FILE)
    existing_recipes = load_recipes(recipes_file)
    existing_ids = {r.id for r in existing_recipes}

    # Generate unique ID
    from app.recipe_parser import generate_recipe_id
    recipe_id = generate_recipe_id(data["name"], existing_ids)

    # Parse ingredients using ingredient parser
    from app.ingredient_parser import IngredientParser
    ingredient_parser = IngredientParser()
    parsed_ingredients = []

    for ing in data["ingredients"]:
        if isinstance(ing, str):
            # Parse string ingredient
            parsed = ingredient_parser.parse(ing)
            parsed_ingredients.append(ingredient_parser.to_dict(parsed))
        elif isinstance(ing, dict):
            # Already structured - validate it has required fields
            if "item" not in ing:
                return jsonify({
                    "error": "Validation error",
                    "message": "Each ingredient must have an 'item' field"
                }), 400
            # Use structured ingredient directly
            parsed_ingredients.append(ing)
        else:
            return jsonify({
                "error": "Validation error",
                "message": "Ingredients must be strings or objects"
            }), 400

    # Build nutrition_per_serving (initialize with zeros - can be edited later)
    nutrition_per_serving = {
        "calories": 0,
        "protein": 0.0,
        "carbs": 0.0,
        "fat": 0.0,
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

    # Build recipe dict
    recipe_dict = {
        "id": recipe_id,
        "name": data["name"],
        "servings": servings,
        "prep_time_minutes": prep_time_minutes,
        "cook_time_minutes": cook_time_minutes,
        "nutrition_per_serving": nutrition_per_serving,
        "tags": data.get("tags", ["manual-entry"]),
        "ingredients": parsed_ingredients,
        "instructions": data["instructions"],
        "source_url": data.get("source_url"),
        "image_url": data.get("image_url")
    }

    # Create Recipe object with validation
    try:
        new_recipe = Recipe.from_dict(recipe_dict)
    except ValueError as e:
        return jsonify({
            "error": "Validation error",
            "message": str(e)
        }), 400
    except Exception as e:
        return jsonify({
            "error": "Processing error",
            "message": f"Failed to process recipe data: {str(e)}"
        }), 500

    # Add to recipes list and save
    updated_recipes = existing_recipes + [new_recipe]
    try:
        save_recipes(recipes_file, updated_recipes)
    except RecipeSaveError as e:
        return jsonify({
            "error": "Save error",
            "message": f"Failed to save recipe: {str(e)}"
        }), 500

    # Clear current plan to force regeneration
    current_plan = None
    current_shopping_list = None

    return jsonify({
        "success": True,
        "message": f"Recipe '{new_recipe.name}' created successfully",
        "recipe": {
            "id": new_recipe.id,
            "name": new_recipe.name,
            "servings": new_recipe.servings,
            "prep_time_minutes": new_recipe.prep_time_minutes,
            "cook_time_minutes": new_recipe.cook_time_minutes,
            "ingredient_count": len(new_recipe.ingredients),
            "instruction_count": len(new_recipe.instructions)
        }
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
    # For backward compatibility, return both nested and flat nutrition structure
    return jsonify({
        "id": recipe.id,
        "name": recipe.name,
        "servings": recipe.servings,
        "prep_time_minutes": recipe.prep_time_minutes,
        "cook_time_minutes": recipe.cook_time_minutes,
        # Flat fields for backward compatibility with edit form
        "calories_per_serving": recipe.calories_per_serving,
        "protein_per_serving": recipe.protein_per_serving,
        "carbs_per_serving": recipe.carbs_per_serving,
        "fat_per_serving": recipe.fat_per_serving,
        # Nested structure (new format)
        "nutrition_per_serving": recipe.nutrition_per_serving,
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
                    "meal_type": meal.meal_type,
                    "recipe_id": meal.recipe.id,
                    "recipe_name": meal.recipe.name,
                    "portions": meal.portions,
                    "calories": meal.calories,
                    "protein": meal.protein,
                    "carbs": meal.carbs,
                    "fat": meal.fat,
                    # Extended nutrition fields
                    "saturated_fat": meal.saturated_fat,
                    "polyunsaturated_fat": meal.polyunsaturated_fat,
                    "monounsaturated_fat": meal.monounsaturated_fat,
                    "sodium": meal.sodium,
                    "potassium": meal.potassium,
                    "fiber": meal.fiber,
                    "sugar": meal.sugar,
                    "vitamin_a": meal.vitamin_a,
                    "vitamin_c": meal.vitamin_c,
                    "calcium": meal.calcium,
                    "iron": meal.iron,
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
                "fat": current_plan.total_fat,
                # Extended nutrition totals
                "saturated_fat": current_plan.total_saturated_fat,
                "polyunsaturated_fat": current_plan.total_polyunsaturated_fat,
                "monounsaturated_fat": current_plan.total_monounsaturated_fat,
                "sodium": current_plan.total_sodium,
                "potassium": current_plan.total_potassium,
                "fiber": current_plan.total_fiber,
                "sugar": current_plan.total_sugar,
                "vitamin_a": current_plan.total_vitamin_a,
                "vitamin_c": current_plan.total_vitamin_c,
                "calcium": current_plan.total_calcium,
                "iron": current_plan.total_iron
            },
            "daily_averages": {
                "calories": current_plan.avg_daily_calories,
                "protein": current_plan.avg_daily_protein,
                "carbs": current_plan.avg_daily_carbs,
                "fat": current_plan.avg_daily_fat,
                # Extended nutrition averages
                "saturated_fat": current_plan.avg_daily_saturated_fat,
                "polyunsaturated_fat": current_plan.avg_daily_polyunsaturated_fat,
                "monounsaturated_fat": current_plan.avg_daily_monounsaturated_fat,
                "sodium": current_plan.avg_daily_sodium,
                "potassium": current_plan.avg_daily_potassium,
                "fiber": current_plan.avg_daily_fiber,
                "sugar": current_plan.avg_daily_sugar,
                "vitamin_a": current_plan.avg_daily_vitamin_a,
                "vitamin_c": current_plan.avg_daily_vitamin_c,
                "calcium": current_plan.avg_daily_calcium,
                "iron": current_plan.avg_daily_iron
            },
            "daily_nutrition": current_plan.get_daily_nutrition(),
            "daily_calorie_limit": current_plan.daily_calorie_limit
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
                for category, items in current_shopping_list.items_by_category.items()
            }
        }
    })


@app.route("/manual-plan/add-meal", methods=["POST"])
def add_meal_to_plan():
    """Add a meal to the manual meal plan."""
    global manual_plan, current_plan, current_shopping_list

    try:
        data = request.get_json()
    except Exception:
        return jsonify({"error": "Invalid JSON"}), 400

    # Validate required fields
    required = ["day", "meal_type", "recipe_id", "servings"]
    for field in required:
        if field not in data:
            return jsonify({"error": f"Missing required field: {field}"}), 400

    day = data["day"]
    meal_type = data["meal_type"]
    recipe_id = data["recipe_id"]
    servings = data["servings"]

    # Validate recipe exists
    recipes_file = Path(config.RECIPES_FILE)
    recipes = load_recipes(recipes_file)
    recipe = next((r for r in recipes if r.id == recipe_id), None)
    if not recipe:
        return jsonify({"error": f"Recipe not found: {recipe_id}"}), 404

    # Add meal to manual plan
    if day not in manual_plan:
        manual_plan[day] = {}
    manual_plan[day][meal_type] = {
        "recipe_id": recipe_id,
        "servings": servings
    }

    # Regenerate plan and shopping list from manual plan
    _regenerate_from_manual_plan(recipes)

    return jsonify({
        "success": True,
        "message": f"Added {recipe.name} to {day} {meal_type}"
    })


@app.route("/manual-plan/remove-meal", methods=["POST"])
def remove_meal_from_plan():
    """Remove a meal from the manual meal plan."""
    global manual_plan, current_plan, current_shopping_list

    try:
        data = request.get_json()
    except Exception:
        return jsonify({"error": "Invalid JSON"}), 400

    day = data.get("day")
    meal_type = data.get("meal_type")

    if not day or not meal_type:
        return jsonify({"error": "Missing day or meal_type"}), 400

    # Remove meal from manual plan
    if day in manual_plan and meal_type in manual_plan[day]:
        del manual_plan[day][meal_type]
        if not manual_plan[day]:  # Remove day if no meals left
            del manual_plan[day]

    # Regenerate plan and shopping list
    recipes_file = Path(config.RECIPES_FILE)
    recipes = load_recipes(recipes_file)
    _regenerate_from_manual_plan(recipes)

    return jsonify({
        "success": True,
        "message": f"Removed meal from {day} {meal_type}"
    })


@app.route("/manual-plan/update-servings", methods=["POST"])
def update_meal_servings():
    """Update servings for a meal in the manual plan."""
    global manual_plan, current_plan, current_shopping_list

    try:
        data = request.get_json()
    except Exception:
        return jsonify({"error": "Invalid JSON"}), 400

    day = data.get("day")
    meal_type = data.get("meal_type")
    servings = data.get("servings")

    if not day or not meal_type or servings is None:
        return jsonify({"error": "Missing required fields"}), 400

    if day not in manual_plan or meal_type not in manual_plan[day]:
        return jsonify({"error": "Meal not found in plan"}), 404

    # Update servings
    manual_plan[day][meal_type]["servings"] = servings

    # Regenerate plan and shopping list
    recipes_file = Path(config.RECIPES_FILE)
    recipes = load_recipes(recipes_file)
    _regenerate_from_manual_plan(recipes)

    return jsonify({
        "success": True,
        "message": f"Updated servings for {day} {meal_type}"
    })


@app.route("/manual-plan/regenerate-meal", methods=["POST"])
def regenerate_meal():
    """Regenerate a specific meal with a new random recipe."""
    global manual_plan, current_plan, current_shopping_list
    import random

    try:
        data = request.get_json()
    except Exception:
        return jsonify({"error": "Invalid JSON"}), 400

    day = data.get("day")
    meal_type = data.get("meal_type")

    if not day or not meal_type:
        return jsonify({"error": "Missing day or meal_type"}), 400

    if day not in manual_plan or meal_type not in manual_plan[day]:
        return jsonify({"error": "Meal not found in plan"}), 404

    current_servings = manual_plan[day][meal_type]["servings"]
    current_recipe_id = manual_plan[day][meal_type]["recipe_id"]

    recipes_file = Path(config.RECIPES_FILE)
    recipes = load_recipes(recipes_file)
    available_recipes = [r for r in recipes if r.id != current_recipe_id]

    if not available_recipes:
        return jsonify({"error": "No other recipes available"}), 400

    matching_recipes = [r for r in available_recipes if meal_type.lower() in [t.lower() for t in r.tags]]
    if matching_recipes:
        new_recipe = random.choice(matching_recipes)
    else:
        new_recipe = random.choice(available_recipes)

    manual_plan[day][meal_type] = {
        "recipe_id": new_recipe.id,
        "servings": current_servings
    }

    _regenerate_from_manual_plan(recipes)

    return jsonify({
        "success": True,
        "message": f"Regenerated {day} {meal_type}",
        "recipe_name": new_recipe.name
    })


@app.route("/manual-plan/clear", methods=["POST"])
def clear_manual_plan():
    """Clear the entire manual meal plan."""
    global manual_plan, current_plan, current_shopping_list

    manual_plan = {}
    current_plan = None
    current_shopping_list = None

    return jsonify({
        "success": True,
        "message": "Manual meal plan cleared"
    })


def _regenerate_from_manual_plan(recipes: list[Recipe]):
    """Regenerate current_plan and shopping list from manual_plan."""
    global current_plan, current_shopping_list
    from app.planner import PlannedMeal, WeeklyPlan

    if not manual_plan:
        current_plan = None
        current_shopping_list = None
        return

    # Build list of PlannedMeal objects from manual_plan
    meals = []
    for day, day_meals in manual_plan.items():
        for meal_type, meal_data in day_meals.items():
            recipe_id = meal_data["recipe_id"]
            servings = meal_data["servings"]

            # Find recipe
            recipe = next((r for r in recipes if r.id == recipe_id), None)
            if recipe:
                meals.append(PlannedMeal(
                    day=day,
                    meal_type=meal_type,
                    recipe=recipe,
                    household_portions=servings
                ))

    # Create WeeklyPlan from manually planned meals
    current_plan = WeeklyPlan(
        meals=meals,
        daily_calorie_limit=config.DAILY_CALORIE_LIMIT
    )

    # Generate shopping list
    current_shopping_list = generate_shopping_list(current_plan)


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
    import os
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_ENV") != "production"
    app.run(host="0.0.0.0", port=port, debug=debug)
