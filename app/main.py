import logging
import math
import threading
import time
import uuid
from pathlib import Path

from flask import Flask, jsonify, render_template, request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf.csrf import CSRFProtect

from app import config
from app.logging_config import configure_logging
from app.nutrition_generator import NutritionGenerator
from app.planner import MealPlanner
from app.recipes import Recipe, RecipeSaveError, load_recipes, save_recipes, update_recipe
from app.sheets import SheetsError, SheetsWriter
from app.shopping_list import ShoppingList, generate_shopping_list
from app.shopping_normalizer import (
    apply_exclusions,
    llm_normalize,
    load_excluded_ingredients,
    save_excluded_ingredients,
)
from app.tag_inference import TagInferencer

configure_logging()
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config["SECRET_KEY"] = config.SECRET_KEY
csrf = CSRFProtect(app)
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[],          # no global limit; apply per-route only
    storage_uri="memory://",
)

# ---------------------------------------------------------------------------
# Image magic-bytes validation (defence against extension-only spoofing)
# ---------------------------------------------------------------------------

_IMAGE_MAGIC: list[tuple[bytes, bytes | None, int, int]] = [
    # (prefix, suffix_at_offset, suffix_offset, suffix_len)
    (b"\x89PNG\r\n\x1a\n", None, 0, 0),   # PNG
    (b"\xff\xd8\xff", None, 0, 0),          # JPEG
    (b"GIF87a", None, 0, 0),                # GIF87a
    (b"GIF89a", None, 0, 0),                # GIF89a
    (b"RIFF", b"WEBP", 8, 4),               # WebP: RIFF????WEBP
]


def _is_valid_image_bytes(data: bytes) -> bool:
    """Return True if *data* starts with magic bytes for a supported image format."""
    for prefix, suffix, suffix_offset, suffix_len in _IMAGE_MAGIC:
        if data[: len(prefix)] == prefix:
            if suffix is None:
                return True
            if data[suffix_offset: suffix_offset + suffix_len] == suffix:
                return True
    return False


# Module-level service singletons (stateless, created once to avoid per-request overhead)
_nutrition_gen = NutritionGenerator(api_key=config.USDA_API_KEY)
_tag_inferencer = TagInferencer()

# Store the current plan in memory (v1 - simple approach)
current_plan = None
current_shopping_list = None
# Manual meal plan storage: {day: {meal_type: {recipe_id, servings}}}
manual_plan = {}

# ---------------------------------------------------------------------------
# Background normalization task tracking
# ---------------------------------------------------------------------------
_norm_tasks: dict[str, dict] = {}  # task_id → {status, items}
_norm_lock = threading.Lock()


def _norm_task_run(task_id: str, snapshot: ShoppingList) -> None:
    """Background thread: LLM-normalize `snapshot` (parallel per category) and store."""
    global current_shopping_list
    try:
        result = llm_normalize(snapshot)
        with _norm_lock:
            current_shopping_list = result
            _norm_tasks[task_id] = {
                "status": "done",
                "created_at": _norm_tasks.get(task_id, {}).get("created_at", time.time()),
                "items": [
                    {"item": i.item, "quantity": i.quantity, "unit": i.unit, "category": i.category}
                    for i in result.items
                ],
            }
    except Exception:
        logger.exception("Background normalization failed", extra={"task_id": task_id})
        with _norm_lock:
            _norm_tasks[task_id] = {
                "status": "failed",
                "created_at": _norm_tasks.get(task_id, {}).get("created_at", time.time()),
                "items": None,
            }


_NORM_TASK_TTL = 3600  # seconds — completed tasks are pruned after this


def _start_normalization() -> str:
    """Snapshot current_shopping_list under the lock, kick off a background thread."""
    task_id = str(uuid.uuid4())
    now = time.time()
    with _norm_lock:
        snapshot = current_shopping_list  # atomic snapshot while holding the lock
        # Prune stale tasks so the dict doesn't grow unboundedly on long-running servers.
        stale = [k for k, v in _norm_tasks.items() if now - v.get("created_at", now) > _NORM_TASK_TTL]
        for k in stale:
            del _norm_tasks[k]
        _norm_tasks[task_id] = {"status": "pending", "items": None, "created_at": now}
    t = threading.Thread(target=_norm_task_run, args=(task_id, snapshot), daemon=True)
    t.start()
    return task_id


def _convert_plan_to_manual_plan(plan) -> dict:
    """Serialize a WeeklyPlan into the manual_plan dict format."""
    result = {}
    for meal in plan.meals:
        result.setdefault(meal.day, {})[meal.meal_type] = {
            "recipe_id": meal.recipe.id,
            "servings": meal.household_portions,
            "meal_source": meal.meal_source,
            "linked_meal": meal.linked_meal,
        }
    return result


def _serialize_plan(plan):
    """Serialize a WeeklyPlan object to dict for JSON."""
    if plan is None:
        return None

    return {
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
                "total_time": meal.recipe.total_time_minutes,
                "meal_source": meal.meal_source,
                "linked_meal": meal.linked_meal,
                "image_url": meal.recipe.image_url,
            }
            for meal in plan.meals
        ],
        "totals": {
            "calories": plan.total_calories,
            "protein": plan.total_protein,
            "carbs": plan.total_carbs,
            "fat": plan.total_fat,
            "saturated_fat": plan.total_saturated_fat,
            "polyunsaturated_fat": plan.total_polyunsaturated_fat,
            "monounsaturated_fat": plan.total_monounsaturated_fat,
            "sodium": plan.total_sodium,
            "potassium": plan.total_potassium,
            "fiber": plan.total_fiber,
            "sugar": plan.total_sugar,
            "vitamin_a": plan.total_vitamin_a,
            "vitamin_c": plan.total_vitamin_c,
            "calcium": plan.total_calcium,
            "iron": plan.total_iron
        },
        "daily_averages": {
            "calories": plan.avg_daily_calories,
            "protein": plan.avg_daily_protein,
            "carbs": plan.avg_daily_carbs,
            "fat": plan.avg_daily_fat,
            "saturated_fat": plan.avg_daily_saturated_fat,
            "polyunsaturated_fat": plan.avg_daily_polyunsaturated_fat,
            "monounsaturated_fat": plan.avg_daily_monounsaturated_fat,
            "sodium": plan.avg_daily_sodium,
            "potassium": plan.avg_daily_potassium,
            "fiber": plan.avg_daily_fiber,
            "sugar": plan.avg_daily_sugar,
            "vitamin_a": plan.avg_daily_vitamin_a,
            "vitamin_c": plan.avg_daily_vitamin_c,
            "calcium": plan.avg_daily_calcium,
            "iron": plan.avg_daily_iron
        },
        "daily_nutrition": plan.get_daily_nutrition(),
        "daily_calorie_limit": plan.daily_calorie_limit
    }


@app.route("/")
def index():
    """Render the web UI."""
    logger.debug("Rendering index page")
    return render_template(
        "index.html",
        current_plan=_serialize_plan(current_plan),
        current_shopping_list=current_shopping_list,
        household_portions=config.TOTAL_PORTIONS,
        config=config
    )


@app.route("/api/recipes")
def api_recipes():
    """API endpoint for paginated, searchable, filterable recipe listing."""
    logger.debug("Fetching paginated recipe list")
    # Load all recipes
    recipes_file = Path(config.RECIPES_FILE)
    all_recipes = load_recipes(recipes_file)

    # Get query parameters
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', config.DEFAULT_PER_PAGE))
    search = request.args.get('search', '').lower()
    tags_param = request.args.get('tags', '')
    sort = request.args.get('sort', '')
    max_calories = request.args.get('max_calories', type=int)
    min_calories = request.args.get('min_calories', type=int)
    max_time = request.args.get('max_time', type=int)

    # Filter recipes
    filtered_recipes = all_recipes

    # Search filter — uses a pre-computed blob so each recipe is a single O(1) check
    if search:
        filtered_recipes = [r for r in filtered_recipes if search in r.search_blob]

    # Tag filter (AND logic)
    if tags_param:
        required_tags = [tag.strip().lower() for tag in tags_param.split(',')]
        filtered_recipes = [
            r for r in filtered_recipes
            if all(req_tag in [t.lower() for t in r.tags] for req_tag in required_tags)
        ]

    # Calorie filters
    if min_calories is not None:
        filtered_recipes = [
            r for r in filtered_recipes
            if r.calories_per_serving >= min_calories
        ]

    if max_calories is not None:
        filtered_recipes = [
            r for r in filtered_recipes
            if r.calories_per_serving <= max_calories
        ]

    # Time filter
    if max_time is not None:
        filtered_recipes = [
            r for r in filtered_recipes
            if r.total_time_minutes <= max_time
        ]

    # Sorting
    if sort == 'name_asc':
        filtered_recipes.sort(key=lambda r: r.name.lower())
    elif sort == 'name_desc':
        filtered_recipes.sort(key=lambda r: r.name.lower(), reverse=True)
    elif sort == 'calories_asc':
        filtered_recipes.sort(key=lambda r: r.calories_per_serving)
    elif sort == 'calories_desc':
        filtered_recipes.sort(key=lambda r: r.calories_per_serving, reverse=True)
    elif sort == 'time_asc':
        filtered_recipes.sort(key=lambda r: r.total_time_minutes)
    elif sort == 'time_desc':
        filtered_recipes.sort(key=lambda r: r.total_time_minutes, reverse=True)

    # Pagination
    total_recipes = len(filtered_recipes)
    total_pages = math.ceil(total_recipes / per_page) if total_recipes > 0 else 1

    # Calculate slice indices
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page

    # Get page of recipes
    paginated_recipes = filtered_recipes[start_idx:end_idx]

    # Serialize recipes
    serialized_recipes = [
        {
            "id": r.id,
            "name": r.name,
            "servings": r.servings,
            "prep_time_minutes": r.prep_time_minutes,
            "cook_time_minutes": r.cook_time_minutes,
            "total_time_minutes": r.total_time_minutes,
            "tags": r.tags,
            "image_url": r.image_url,
            "source_url": r.source_url,
            "nutrition_per_serving": r.nutrition_per_serving
        }
        for r in paginated_recipes
    ]

    # Build response
    response = {
        "recipes": serialized_recipes,
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total_recipes": total_recipes,
            "total_pages": total_pages,
            "has_next": page < total_pages,
            "has_prev": page > 1
        }
    }

    return jsonify(response)


@app.route("/recipe/<recipe_id>")
def recipe_detail(recipe_id: str):
    """Display detailed recipe page."""
    logger.debug("Rendering recipe detail page", extra={"recipe_id": recipe_id})
    from app.ingredient_substitutions import get_substitutions

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

    ingredient_substitutions = {}
    for i, ingredient in enumerate(recipe.ingredients):
        subs = get_substitutions(ingredient["item"])
        if subs:
            ingredient_substitutions[i] = subs

    return render_template(
        "recipe_detail.html",
        recipe=recipe,
        substitutions=ingredient_substitutions
    )


@app.route("/share-recipe", methods=["POST"])
def share_recipe():
    """Handle PWA share target for recipe URLs and text.

    This endpoint receives shared content from the browser's share menu
    (Android Chrome, iOS Safari with Web Share Target API).
    """
    logger.info("Received PWA share-recipe request")
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
    logger.info("Generating weekly meal plan")
    global current_plan, current_shopping_list, manual_plan

    recipes_file = Path(config.RECIPES_FILE)
    recipes = load_recipes(recipes_file)

    planner = MealPlanner(
        household_portions=config.TOTAL_PORTIONS,
        meal_schedule=config.MEAL_SCHEDULE,
        daily_calorie_limit=config.DAILY_CALORIE_LIMIT,
        meal_calorie_splits=config.MEAL_CALORIE_SPLITS,
    )
    plan = planner.generate_weekly_plan(recipes)
    if config.COOK_ONCE_PLANNING:
        from app.planner import add_cook_once_slots
        plan = add_cook_once_slots(plan, adult_portions=config.PACKED_LUNCH_PORTIONS)
    current_plan = plan
    manual_plan = _convert_plan_to_manual_plan(plan)
    raw_list = generate_shopping_list(current_plan)
    current_shopping_list = apply_exclusions(raw_list, load_excluded_ingredients())
    norm_task_id = _start_normalization()

    return jsonify({
        "success": True,
        "message": "Weekly plan generated successfully",
        "normalization_task_id": norm_task_id,
    })


@app.route("/generate-with-schedule", methods=["POST"])
def generate_with_schedule():
    """Generate a meal plan with custom schedule and per-meal servings."""
    logger.info("Generating weekly plan with schedule")
    global manual_plan, current_plan, current_shopping_list
    import random

    try:
        data = request.get_json()
    except Exception:
        return jsonify({"error": "Invalid JSON"}), 400

    schedule = data.get("schedule", {})
    if not schedule:
        return jsonify({"error": "Schedule is required"}), 400

    # Accept optional portions and calorie_limit overrides
    portions = data.get("portions", config.TOTAL_PORTIONS)
    calorie_limit = data.get("calorie_limit", config.DAILY_CALORIE_LIMIT)

    recipes_file = Path(config.RECIPES_FILE)
    recipes = load_recipes(recipes_file)

    # Build meal slots from schedule
    meal_slots = []
    no_cook_slots: set[tuple[str, str]] = set()
    for day, day_meals in schedule.items():
        for meal_type, slot_data in day_meals.items():
            if isinstance(slot_data, dict):
                servings = slot_data.get("servings", portions)
                can_cook = slot_data.get("can_cook", True)
            else:
                servings = slot_data  # backward compat: plain float
                can_cook = True
            meal_slots.append((day, meal_type, servings, can_cook))
            if not can_cook:
                no_cook_slots.add((day, meal_type))

    # Validate enough recipes
    if len(recipes) < len(meal_slots):
        return jsonify({
            "error": f"Need at least {len(meal_slots)} recipes. Only {len(recipes)} available."
        }), 400

    # Generate plan
    manual_plan = {}
    used_recipes = set()

    for day, meal_type, servings, can_cook in meal_slots:
        # Try to find suitable recipe for this meal type
        suitable = [r for r in recipes if meal_type in r.tags and r.id not in used_recipes]

        # Fallback to any unused recipe
        if not suitable:
            suitable = [r for r in recipes if r.id not in used_recipes]

        if not suitable:
            return jsonify({"error": f"Not enough recipes for {day} {meal_type}"}), 400

        if not can_cook:
            reheatable = [r for r in suitable if r.reheats_well]
            if reheatable:
                suitable = reheatable

        recipe = random.choice(suitable)
        used_recipes.add(recipe.id)

        # Add to manual plan
        if day not in manual_plan:
            manual_plan[day] = {}
        manual_plan[day][meal_type] = {
            "recipe_id": recipe.id,
            "servings": servings
        }

    # Regenerate plan from manual_plan with optional overrides
    _regenerate_from_manual_plan(recipes, calorie_limit=calorie_limit)

    # Apply cook-once slots (leftovers + packed lunches)
    if config.COOK_ONCE_PLANNING and current_plan:
        from app.planner import add_cook_once_slots
        current_plan = add_cook_once_slots(
            current_plan,
            adult_portions=config.PACKED_LUNCH_PORTIONS,
            no_cook_slots=frozenset(no_cook_slots),
        )
        manual_plan = _convert_plan_to_manual_plan(current_plan)
        raw_list = generate_shopping_list(current_plan)
        current_shopping_list = apply_exclusions(raw_list, load_excluded_ingredients())

    norm_task_id = _start_normalization()

    return jsonify({
        "success": True,
        "message": f"Generated plan with {len(meal_slots)} meals",
        "portions": portions,
        "calorie_limit": calorie_limit,
        "normalization_task_id": norm_task_id,
    })


# ---------------------------------------------------------------------------
# Shared recipe-import helper
# ---------------------------------------------------------------------------

def _finalize_and_save_recipe(parsed_recipe, source: str = ""):
    """Generate nutrition, infer tags, save the recipe and return a JSON response.

    Shared by all three recipe-import handlers (URL, text, image).
    Raises RecipeSaveError / ValueError on failure so callers can translate
    to the appropriate HTTP status code.
    """
    global current_plan, current_shopping_list

    from app.recipe_parser import generate_recipe_id

    # Generate nutrition if missing
    if _nutrition_gen.should_generate_nutrition(parsed_recipe):
        generated_nutrition = _nutrition_gen.generate_from_ingredients(
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
    parsed_recipe.tags = _tag_inferencer.enhance_tags(
        name=parsed_recipe.name,
        ingredients=parsed_recipe.ingredients or [],
        instructions=parsed_recipe.instructions or [],
        prep_time_minutes=parsed_recipe.prep_time_minutes or 0,
        cook_time_minutes=parsed_recipe.cook_time_minutes or 0,
        existing_tags=parsed_recipe.tags or []
    )

    # Load, ID, convert, validate, save
    recipes_file = Path(config.RECIPES_FILE)
    existing_recipes = load_recipes(recipes_file)
    existing_ids = {r.id for r in existing_recipes}
    recipe_id = generate_recipe_id(parsed_recipe.name, existing_ids)
    recipe_dict = parsed_recipe.to_recipe_dict(recipe_id)
    new_recipe = Recipe.from_dict(recipe_dict)
    save_recipes(recipes_file, existing_recipes + [new_recipe])

    current_plan = None
    current_shopping_list = None
    logger.info("Recipe imported successfully", extra={"recipe_id": new_recipe.id, "recipe_name": new_recipe.name})

    suffix = f" {source}" if source else ""
    response_data = {
        "success": True,
        "message": f"Recipe '{new_recipe.name}' imported successfully{suffix}",
        "recipe": {
            "id": new_recipe.id,
            "name": new_recipe.name,
            "servings": new_recipe.servings,
            "has_nutrition": (new_recipe.calories_per_serving > 0),
            "nutrition_generated": "nutrition-generated" in new_recipe.tags,
            "ingredient_count": len(new_recipe.ingredients),
            "instruction_count": len(new_recipe.instructions),
        },
    }

    if hasattr(parsed_recipe, 'ai_confidence'):
        response_data["recipe"]["ai_confidence"] = parsed_recipe.ai_confidence
        if parsed_recipe.ai_confidence < 0.7:
            response_data["warning"] = "Recipe extraction confidence is low. Please review the imported data carefully."

    return jsonify(response_data)


@app.route("/import-recipe", methods=["POST"])
@limiter.limit("10 per minute")
def import_recipe():
    """Import a recipe from a URL."""
    logger.info("Importing recipe from URL")

    try:
        data = request.get_json(silent=False)
    except (ValueError, TypeError):
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
        from app.recipe_parser import RecipeParseError, RecipeParser

        logger.info("Parsing recipe from URL", extra={"url": url})
        t0 = time.monotonic()
        parser = RecipeParser()
        parsed_recipe = parser.parse_from_url(url)
        logger.info("LLM call completed", extra={"elapsed_s": round(time.monotonic() - t0, 2), "recipe_name": parsed_recipe.name})

        return _finalize_and_save_recipe(parsed_recipe)

    except InstagramFetchError as e:
        logger.exception("Instagram fetch error during import", extra={"url": url})
        return jsonify({
            "error": "Instagram fetch error",
            "message": str(e),
            "suggestion": "Try using 'Import from Text' by copying the post description manually"
        }), 400
    except AIExtractionError as e:
        logger.exception("AI extraction error during import", extra={"url": url})
        return jsonify({
            "error": "AI extraction error",
            "message": str(e),
            "suggestion": "The recipe text may be unclear or incomplete. Please try a different post or add manually."
        }), 400
    except RecipeParseError as e:
        logger.exception("Recipe parse error during import", extra={"url": url})
        return jsonify({
            "error": "Parse error",
            "message": str(e)
        }), 400
    except ValueError as e:
        logger.exception("Validation error during import", extra={"url": url})
        return jsonify({
            "error": "Validation error",
            "message": str(e)
        }), 400
    except RecipeSaveError as e:
        logger.exception("Save error during import", extra={"url": url})
        return jsonify({
            "error": "Save error",
            "message": f"Failed to save recipe: {str(e)}"
        }), 500
    except Exception as e:
        logger.exception("Unexpected error during recipe import", extra={"url": url})
        return jsonify({
            "error": "Import error",
            "message": f"Unexpected error: {str(e)}"
        }), 500


@app.route("/import-recipe-text", methods=["POST"])
@limiter.limit("10 per minute")
def import_recipe_text():
    """Import a recipe from manually pasted text (Instagram fallback)."""
    logger.info("Importing recipe from text")

    try:
        data = request.get_json(silent=False)
    except (ValueError, TypeError):
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
        from app.recipe_parser import RecipeParseError

        logger.debug("Initialising InstagramParser")
        instagram_parser = InstagramParser(
            openai_api_key=config.OPENAI_API_KEY
        )
        logger.info("Calling LLM to parse recipe from text", extra={"text_length": len(text), "language": language})
        t0 = time.monotonic()
        parsed_recipe = instagram_parser.parse_from_text(text, language)
        logger.info("LLM call completed", extra={"elapsed_s": round(time.monotonic() - t0, 2), "recipe_name": parsed_recipe.name})

        return _finalize_and_save_recipe(parsed_recipe, source="from text")

    except AIExtractionError as e:
        logger.exception("AI extraction error during text import", extra={"text_length": len(text)})
        return jsonify({
            "error": "AI extraction error",
            "message": str(e),
            "suggestion": "The recipe text may be unclear or incomplete. Please try different text or add manually."
        }), 400
    except RecipeParseError as e:
        logger.exception("Recipe parse error during text import", extra={"text_length": len(text)})
        return jsonify({
            "error": "Parse error",
            "message": str(e)
        }), 400
    except ValueError as e:
        logger.exception("Validation error during text import", extra={"text_length": len(text)})
        return jsonify({
            "error": "Validation error",
            "message": str(e)
        }), 400
    except RecipeSaveError as e:
        logger.exception("Save error during text import", extra={"text_length": len(text)})
        return jsonify({
            "error": "Save error",
            "message": f"Failed to save recipe: {str(e)}"
        }), 500
    except Exception as e:
        logger.exception("Unexpected error during text import", extra={"text_length": len(text)})
        return jsonify({
            "error": "Import error",
            "message": f"Unexpected error: {str(e)}"
        }), 500


@app.route("/import-recipe-image", methods=["POST"])
@limiter.limit("10 per minute")
def import_recipe_image():
    """Import a recipe from a photo."""
    logger.info("Importing recipe from image")

    logger.debug("Image import request received", extra={
        "content_type": request.content_type,
        "files": list(request.files.keys()),
        "form_keys": list(request.form.keys()),
    })

    # Check if image file is present
    if 'image' not in request.files:
        logger.warning("Image import request missing image file")
        return jsonify({
            "error": "No image provided",
            "message": "Image file is required"
        }), 400

    file = request.files['image']
    logger.debug("Image file received", extra={"upload_filename": file.filename})

    if file.filename == '':
        logger.warning("Image import request has empty filename")
        return jsonify({
            "error": "No file selected",
            "message": "Please select an image file"
        }), 400

    # Validate file type
    allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
    file_ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''
    logger.debug("Image file extension detected", extra={"file_ext": file_ext})

    if file_ext not in allowed_extensions:
        logger.warning("Invalid image file type", extra={"file_ext": file_ext})
        return jsonify({
            "error": "Invalid file type",
            "message": f"Allowed types: {', '.join(allowed_extensions)}"
        }), 400

    try:
        # Read image data
        logger.debug("Reading image data")
        image_data = file.read()
        logger.debug("Image data read", extra={"size_bytes": len(image_data)})

        # Check for empty file
        if len(image_data) == 0:
            logger.warning("Uploaded image file is empty")
            return jsonify({
                "error": "Empty file",
                "message": "The uploaded image file is empty"
            }), 400

        # Check file size (log warning if > 10MB)
        if len(image_data) > 10 * 1024 * 1024:
            logger.warning("Large image file uploaded", extra={"size_mb": round(len(image_data) / (1024 * 1024), 2)})

        # Validate magic bytes — reject files whose content doesn't match an image
        # format even if their extension is valid (e.g. malicious.php.png).
        if not _is_valid_image_bytes(image_data):
            logger.warning(
                "Image upload rejected: magic bytes do not match any supported format",
                extra={"file_ext": file_ext, "size_bytes": len(image_data)},
            )
            return jsonify({
                "error": "Invalid file content",
                "message": "File does not appear to be a valid image"
            }), 400

        # Extract recipe from image using Vision API
        from app.image_recipe_extractor import ImageRecipeExtractor
        from app.recipe_parser import ParsedRecipe

        if not config.OPENAI_API_KEY:
            logger.error("OpenAI API key not configured for image import")
            return jsonify({
                "error": "Configuration error",
                "message": "Image import is not configured on the server"
            }), 500
        logger.info("OpenAI API key configured")

        logger.debug("Initialising ImageRecipeExtractor")
        extractor = ImageRecipeExtractor(api_key=config.OPENAI_API_KEY)

        logger.info("Starting OpenAI Vision API call", extra={"size_bytes": len(image_data), "file_ext": file_ext})
        t0 = time.monotonic()
        extracted_data = extractor.extract_recipe(image_data, file_ext)
        logger.info("LLM call completed", extra={
            "elapsed_s": round(time.monotonic() - t0, 2),
            "recipe_name": extracted_data.name,
            "confidence": extracted_data.confidence,
            "ingredient_count": len(extracted_data.ingredients),
        })

    except ValueError as e:
        logger.exception("ValueError during image extraction", extra={"upload_filename": file.filename})
        return jsonify({
            "error": "Extraction failed",
            "message": str(e)
        }), 400
    except Exception as e:
        logger.exception("Exception during image extraction", extra={"upload_filename": file.filename})

        # Check if it looks like a timeout
        error_str = str(e)
        if "timeout" in error_str.lower():
            return jsonify({
                "error": "Timeout",
                "message": "The image processing took too long. Please try again with a smaller or clearer image."
            }), 504

        # Check for API errors
        if "api" in error_str.lower() or "openai" in error_str.lower():
            return jsonify({
                "error": "API error",
                "message": f"OpenAI API error: {error_str}"
            }), 502

        return jsonify({
            "error": "Processing failed",
            "message": f"An error occurred while processing the image: {error_str}"
        }), 500

    try:
        # Convert to ParsedRecipe format
        logger.debug("Converting extracted data to ParsedRecipe", extra={"recipe_name": extracted_data.name})
        # Build tags list - include notes as a tag if present
        tags = extracted_data.tags + ["photo-imported"]
        if extracted_data.notes:
            # Notes can be added to instructions as a final note
            instructions = extracted_data.instructions.copy() if extracted_data.instructions else []
            instructions.append(f"Note: {extracted_data.notes}")
        else:
            instructions = extracted_data.instructions

        parsed_recipe = ParsedRecipe(
            name=extracted_data.name,
            servings=extracted_data.servings,
            prep_time_minutes=extracted_data.prep_time_minutes,
            cook_time_minutes=extracted_data.cook_time_minutes,
            ingredients=extracted_data.ingredients,
            instructions=instructions,
            tags=tags,
            source_url=None,
            calories_per_serving=None,
            protein_per_serving=None,
            carbs_per_serving=None,
            fat_per_serving=None
        )
        parsed_recipe.ai_confidence = extracted_data.confidence
        logger.debug("ParsedRecipe created", extra={"recipe_name": parsed_recipe.name})

        return _finalize_and_save_recipe(parsed_recipe, source="from photo")

    except ValueError as e:
        logger.exception("ValueError during image recipe conversion/saving", extra={"recipe_name": extracted_data.name})
        return jsonify({
            "error": "Extraction error",
            "message": str(e),
            "suggestion": "The image may be unclear or not contain a recipe. Please try a clearer photo."
        }), 400
    except RecipeSaveError as e:
        logger.exception("RecipeSaveError during image recipe saving", extra={"recipe_name": extracted_data.name})
        return jsonify({
            "error": "Save error",
            "message": f"Failed to save recipe: {str(e)}"
        }), 500
    except Exception as e:
        logger.exception("Unexpected error during image recipe conversion/saving", extra={"recipe_name": extracted_data.name})
        return jsonify({
            "error": "Import error",
            "message": f"Unexpected error: {str(e)}"
        }), 500


@app.route("/recipes", methods=["GET"])
def recipes():
    """List all available recipes."""
    logger.debug("Listing all recipes")
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
    logger.info("Creating new recipe manually")
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
    logger.debug("Fetching single recipe", extra={"recipe_id": recipe_id})
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
    logger.info("Updating recipe", extra={"recipe_id": recipe_id})
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
    logger.debug("Fetching current plan")
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
                    "total_time": meal.recipe.total_time_minutes,
                    "meal_source": meal.meal_source,
                    "linked_meal": meal.linked_meal,
                    "image_url": meal.recipe.image_url,
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
                    "quantity": round(item.quantity, 2) if item.quantity is not None else None,
                    "unit": item.unit,
                    "category": item.category
                }
                for item in current_shopping_list.items
            ],
            "items_by_category": {
                category: [
                    {
                        "item": item.item,
                        "quantity": round(item.quantity, 2) if item.quantity is not None else None,
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
    logger.info("Adding meal to manual plan")
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

    if not isinstance(servings, (int, float)) or servings <= 0:
        return jsonify({"error": "servings must be a positive number"}), 400

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
    logger.info("Removing meal from manual plan")
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
    logger.info("Updating meal servings in manual plan")
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

    if not isinstance(servings, (int, float)) or servings <= 0:
        return jsonify({"error": "servings must be a positive number"}), 400

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
    logger.info("Regenerating a specific meal")
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
    logger.info("Clearing manual meal plan")
    global manual_plan, current_plan, current_shopping_list

    manual_plan = {}
    current_plan = None
    current_shopping_list = None

    return jsonify({
        "success": True,
        "message": "Manual meal plan cleared"
    })


def _regenerate_from_manual_plan(recipes: list[Recipe], calorie_limit: float | None = None):
    """Regenerate current_plan and shopping list from manual_plan."""
    global current_plan, current_shopping_list
    from app.planner import PlannedMeal, WeeklyPlan

    if not manual_plan:
        current_plan = None
        current_shopping_list = None
        return

    effective_calorie_limit = calorie_limit if calorie_limit is not None else config.DAILY_CALORIE_LIMIT

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
                    household_portions=servings,
                    meal_source=meal_data.get("meal_source", "fresh"),
                    linked_meal=meal_data.get("linked_meal"),
                ))

    # Create WeeklyPlan from manually planned meals
    current_plan = WeeklyPlan(
        meals=meals,
        daily_calorie_limit=effective_calorie_limit
    )

    # Generate shopping list
    raw_list = generate_shopping_list(current_plan)
    current_shopping_list = apply_exclusions(raw_list, load_excluded_ingredients())


@app.route("/current-plan/meals", methods=["PUT"])
def update_current_plan_meal():
    """Update a specific meal slot in the current plan."""
    logger.info("Updating meal slot in current plan")
    global manual_plan, current_plan, current_shopping_list

    try:
        data = request.get_json()
    except Exception:
        return jsonify({"error": "Invalid JSON"}), 400

    if not data:
        return jsonify({"error": "Request body is required"}), 400

    # Validate required fields
    required = ["day", "meal_type", "recipe_id"]
    for field in required:
        if field not in data:
            return jsonify({"error": f"Missing required field: {field}"}), 400

    day = data["day"]
    meal_type = data["meal_type"]
    recipe_id = data["recipe_id"]
    servings = data.get("servings", config.TOTAL_PORTIONS)

    # Validate recipe exists
    recipes_file = Path(config.RECIPES_FILE)
    recipes = load_recipes(recipes_file)
    recipe = next((r for r in recipes if r.id == recipe_id), None)
    if not recipe:
        return jsonify({"error": f"Recipe not found: {recipe_id}"}), 404

    # Update the meal slot in manual_plan
    if day not in manual_plan:
        manual_plan[day] = {}
    manual_plan[day][meal_type] = {
        "recipe_id": recipe_id,
        "servings": servings
    }

    # Regenerate plan and shopping list
    _regenerate_from_manual_plan(recipes)

    return jsonify({
        "success": True,
        "message": f"Added {recipe.name} to {day} {meal_type}"
    })


@app.route("/shopping-list/update-item", methods=["POST"])
def update_shopping_item():
    """Update quantity or name of a shopping list item."""
    logger.debug("Updating shopping list item")
    global current_shopping_list

    # Snapshot under the lock so the bounds check and item access use the same list.
    with _norm_lock:
        sl = current_shopping_list

    if sl is None:
        return jsonify({"error": "No shopping list available"}), 404

    try:
        data = request.get_json()
    except Exception:
        return jsonify({"error": "Invalid JSON"}), 400

    item_index = data.get("index")
    new_quantity = data.get("quantity")
    new_name = data.get("name")

    if item_index is None:
        return jsonify({"error": "Missing item index"}), 400

    if item_index < 0 or item_index >= len(sl.items):
        return jsonify({"error": "Invalid item index"}), 400

    item = sl.items[item_index]

    if new_quantity is not None:
        try:
            item.quantity = float(new_quantity)
        except ValueError:
            return jsonify({"error": "Invalid quantity"}), 400

    if new_name is not None:
        item.item = new_name.strip()

    return jsonify({
        "success": True,
        "message": "Item updated",
        "item": {
            "item": item.item,
            "quantity": item.quantity,
            "unit": item.unit,
            "category": item.category
        }
    })


@app.route("/shopping-list/delete-item", methods=["POST"])
def delete_shopping_item():
    """Delete an item from the shopping list."""
    logger.debug("Deleting shopping list item")
    global current_shopping_list

    # Snapshot under the lock so the bounds check and pop use the same list.
    with _norm_lock:
        sl = current_shopping_list

    if sl is None:
        return jsonify({"error": "No shopping list available"}), 404

    try:
        data = request.get_json()
    except Exception:
        return jsonify({"error": "Invalid JSON"}), 400

    item_index = data.get("index")

    if item_index is None:
        return jsonify({"error": "Missing item index"}), 400

    if item_index < 0 or item_index >= len(sl.items):
        return jsonify({"error": "Invalid item index"}), 400

    deleted_item = sl.items.pop(item_index)

    return jsonify({
        "success": True,
        "message": f"Deleted {deleted_item.item}",
        "deleted_item": deleted_item.item
    })


@app.route("/shopping-list/add-item", methods=["POST"])
def add_shopping_item():
    """Add a custom item to the shopping list."""
    logger.debug("Adding custom item to shopping list")
    global current_shopping_list
    from app.shopping_list import ShoppingListItem

    # Snapshot under the lock so we operate on a consistent list reference.
    with _norm_lock:
        sl = current_shopping_list

    if sl is None:
        return jsonify({"error": "No shopping list available"}), 404

    try:
        data = request.get_json()
    except Exception:
        return jsonify({"error": "Invalid JSON"}), 400

    item_name = data.get("name")
    quantity = data.get("quantity", 1)
    unit = data.get("unit", "")
    raw_category = data.get("category", "other")

    if not item_name or not item_name.strip():
        return jsonify({"error": "Item name is required"}), 400

    try:
        quantity = float(quantity)
        if quantity <= 0:
            return jsonify({"error": "Quantity must be positive"}), 400
    except ValueError:
        return jsonify({"error": "Invalid quantity"}), 400

    from app.ingredient_normalizer import canonicalise_category
    category = canonicalise_category(raw_category)

    new_item = ShoppingListItem(
        item=item_name.strip(),
        quantity=quantity,
        unit=unit.strip(),
        category=category
    )

    sl.items.append(new_item)
    sl.items.sort(key=lambda x: (x.category, x.item))

    return jsonify({
        "success": True,
        "message": f"Added {item_name}",
        "item": {
            "item": new_item.item,
            "quantity": new_item.quantity,
            "unit": new_item.unit,
            "category": new_item.category
        }
    })


@app.route("/write-to-sheets", methods=["POST"])
def write_to_sheets():
    """Write the current plan to Google Sheets."""
    logger.info("Writing current plan to Google Sheets")
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
        logger.exception("Google Sheets write error")
        return jsonify({
            "success": False,
            "message": f"Error writing to Google Sheets: {str(e)}"
        }), 500
    except Exception as e:
        logger.exception("Unexpected error writing to Google Sheets")
        return jsonify({
            "success": False,
            "message": f"Unexpected error: {str(e)}"
        }), 500


@app.route("/shopping-list/normalize/<task_id>", methods=["GET"])
def get_normalization_status(task_id: str):
    """Poll the status of a background normalization task.

    Returns {status: 'pending'|'done'|'failed', items: [...] | null}
    """
    logger.debug("Polling normalization status", extra={"task_id": task_id})
    with _norm_lock:
        task = dict(_norm_tasks.get(task_id, {"status": "not_found", "items": None}))
    return jsonify(task)


@app.route("/excluded-ingredients", methods=["GET"])
def get_excluded_ingredients():
    """Return the list of excluded ingredients."""
    logger.debug("Fetching excluded ingredients")
    return jsonify(load_excluded_ingredients())


@app.route("/excluded-ingredients", methods=["POST"])
def update_excluded_ingredients():
    """Replace the excluded ingredients list."""
    logger.info("Updating excluded ingredients list")
    data = request.get_json()
    items = data.get("items", [])
    if not isinstance(items, list):
        return jsonify({"success": False, "message": "items must be a list"}), 400
    save_excluded_ingredients([str(i).strip() for i in items if str(i).strip()])
    return jsonify({"success": True})


if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_ENV") != "production"
    app.run(host="0.0.0.0", port=port, debug=debug)
