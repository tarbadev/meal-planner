"""Recipe CRUD routes."""

import logging
import math
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app import config
from app.db import crud
from app.db.engine import get_db
from app.recipes import Recipe

logger = logging.getLogger(__name__)
router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/api/recipes")
async def api_recipes(
    request: Request,
    page: int = 1,
    per_page: int = config.DEFAULT_PER_PAGE,
    search: str = "",
    tags: str = "",
    sort: str = "",
    max_calories: int | None = None,
    min_calories: int | None = None,
    max_time: int | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Paginated, searchable, filterable recipe listing."""
    logger.debug("Fetching paginated recipe list")

    tag_list = [t.strip().lower() for t in tags.split(",") if t.strip()] if tags else None
    all_recipes = await crud.get_recipes(
        db,
        config.DEFAULT_HOUSEHOLD_ID,
        search=search.lower(),
        tags=tag_list,
    )

    # Additional in-memory filters (calorie/time)
    filtered = all_recipes
    if min_calories is not None:
        filtered = [r for r in filtered if r.calories_per_serving >= min_calories]
    if max_calories is not None:
        filtered = [r for r in filtered if r.calories_per_serving <= max_calories]
    if max_time is not None:
        filtered = [r for r in filtered if r.total_time_minutes <= max_time]

    # Sorting
    if sort == "name_asc":
        filtered.sort(key=lambda r: r.name.lower())
    elif sort == "name_desc":
        filtered.sort(key=lambda r: r.name.lower(), reverse=True)
    elif sort == "calories_asc":
        filtered.sort(key=lambda r: r.calories_per_serving)
    elif sort == "calories_desc":
        filtered.sort(key=lambda r: r.calories_per_serving, reverse=True)
    elif sort == "time_asc":
        filtered.sort(key=lambda r: r.total_time_minutes)
    elif sort == "time_desc":
        filtered.sort(key=lambda r: r.total_time_minutes, reverse=True)

    total_recipes = len(filtered)
    total_pages = math.ceil(total_recipes / per_page) if total_recipes > 0 else 1
    start_idx = (page - 1) * per_page
    paginated = filtered[start_idx : start_idx + per_page]

    return {
        "recipes": [
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
                "nutrition_per_serving": r.nutrition_per_serving,
            }
            for r in paginated
        ],
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total_recipes": total_recipes,
            "total_pages": total_pages,
            "has_next": page < total_pages,
            "has_prev": page > 1,
        },
    }


@router.get("/recipe/{recipe_id}", response_class=HTMLResponse)
async def recipe_detail(
    recipe_id: str, request: Request, db: AsyncSession = Depends(get_db)
):
    """Display detailed recipe page."""
    logger.debug("Rendering recipe detail page", extra={"recipe_id": recipe_id})
    from app.ingredient_substitutions import get_substitutions

    recipe = await crud.get_recipe_by_id(db, recipe_id)
    if recipe is None:
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "error_title": "Recipe Not Found",
                "error_message": f"No recipe found with ID '{recipe_id}'",
            },
            status_code=404,
        )

    ingredient_substitutions: dict[int, Any] = {}
    for i, ingredient in enumerate(recipe.ingredients):
        subs = get_substitutions(ingredient["item"])
        if subs:
            ingredient_substitutions[i] = subs

    return templates.TemplateResponse(
        "recipe_detail.html",
        {
            "request": request,
            "recipe": recipe,
            "substitutions": ingredient_substitutions,
        },
    )


@router.get("/recipes")
async def list_recipes(db: AsyncSession = Depends(get_db)):
    """List all available recipes."""
    logger.debug("Listing all recipes")
    all_recipes = await crud.get_recipes(db, config.DEFAULT_HOUSEHOLD_ID)
    return {
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
                "tags": r.tags,
            }
            for r in all_recipes
        ]
    }


@router.post("/recipes")
async def create_recipe(request: Request, db: AsyncSession = Depends(get_db)):
    """Create a new recipe manually."""
    logger.info("Creating new recipe manually")

    try:
        data = await request.json()
    except Exception:
        raise HTTPException(400, detail="Invalid JSON") from None

    if not data:
        raise HTTPException(400, detail="Request body is required")

    # Validate required fields
    required_fields = ["name", "servings", "ingredients", "instructions"]
    missing_fields = [
        f for f in required_fields
        if f not in data
        or (f in ("ingredients", "instructions") and not data[f])
        or (f == "name" and not data[f].strip())
    ]
    if missing_fields:
        raise HTTPException(400, detail=f"Missing required fields: {', '.join(missing_fields)}")

    if not isinstance(data["ingredients"], list) or len(data["ingredients"]) == 0:
        raise HTTPException(400, detail="At least one ingredient is required")
    if not isinstance(data["instructions"], list) or len(data["instructions"]) == 0:
        raise HTTPException(400, detail="At least one instruction step is required")

    try:
        servings = int(data["servings"])
        if servings <= 0:
            raise HTTPException(400, detail="Servings must be a positive number")
    except (ValueError, TypeError):
        raise HTTPException(400, detail="Servings must be a valid number") from None

    prep_time_minutes = int(data.get("prep_time_minutes", 0))
    cook_time_minutes = int(data.get("cook_time_minutes", 0))
    if prep_time_minutes < 0 or cook_time_minutes < 0:
        raise HTTPException(400, detail="Time values cannot be negative")

    existing_recipes = await crud.get_recipes(db, config.DEFAULT_HOUSEHOLD_ID)
    existing_ids = {r.id for r in existing_recipes}

    from app.ingredient_parser import IngredientParser
    from app.recipe_parser import generate_recipe_id

    recipe_id = generate_recipe_id(data["name"], existing_ids)
    ingredient_parser = IngredientParser()
    parsed_ingredients = []
    for ing in data["ingredients"]:
        if isinstance(ing, str):
            parsed = ingredient_parser.parse(ing)
            parsed_ingredients.append(ingredient_parser.to_dict(parsed))
        elif isinstance(ing, dict):
            if "item" not in ing:
                raise HTTPException(400, detail="Each ingredient must have an 'item' field")
            parsed_ingredients.append(ing)
        else:
            raise HTTPException(400, detail="Ingredients must be strings or objects")

    recipe_dict = {
        "id": recipe_id,
        "name": data["name"],
        "servings": servings,
        "prep_time_minutes": prep_time_minutes,
        "cook_time_minutes": cook_time_minutes,
        "nutrition_per_serving": {
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
            "iron": None,
        },
        "tags": data.get("tags", ["manual-entry"]),
        "ingredients": parsed_ingredients,
        "instructions": data["instructions"],
        "source_url": data.get("source_url"),
        "image_url": data.get("image_url"),
    }

    try:
        new_recipe = Recipe.from_dict(recipe_dict)
    except ValueError as e:
        raise HTTPException(400, detail=str(e)) from e

    await crud.upsert_recipe(db, new_recipe, config.DEFAULT_HOUSEHOLD_ID)

    return {
        "success": True,
        "message": f"Recipe '{new_recipe.name}' created successfully",
        "recipe": {
            "id": new_recipe.id,
            "name": new_recipe.name,
            "servings": new_recipe.servings,
            "prep_time_minutes": new_recipe.prep_time_minutes,
            "cook_time_minutes": new_recipe.cook_time_minutes,
            "ingredient_count": len(new_recipe.ingredients),
            "instruction_count": len(new_recipe.instructions),
        },
    }


@router.get("/recipes/{recipe_id}")
async def get_recipe(recipe_id: str, db: AsyncSession = Depends(get_db)):
    """Fetch single recipe for editing."""
    logger.debug("Fetching single recipe", extra={"recipe_id": recipe_id})
    recipe = await crud.get_recipe_by_id(db, recipe_id)
    if recipe is None:
        raise HTTPException(404, detail=f"No recipe found with ID '{recipe_id}'")

    return {
        "id": recipe.id,
        "name": recipe.name,
        "servings": recipe.servings,
        "prep_time_minutes": recipe.prep_time_minutes,
        "cook_time_minutes": recipe.cook_time_minutes,
        "calories_per_serving": recipe.calories_per_serving,
        "protein_per_serving": recipe.protein_per_serving,
        "carbs_per_serving": recipe.carbs_per_serving,
        "fat_per_serving": recipe.fat_per_serving,
        "nutrition_per_serving": recipe.nutrition_per_serving,
        "tags": recipe.tags,
        "ingredients": recipe.ingredients,
    }


@router.put("/recipes/{recipe_id}")
async def update_recipe_endpoint(
    recipe_id: str, request: Request, db: AsyncSession = Depends(get_db)
):
    """Update existing recipe."""
    logger.info("Updating recipe", extra={"recipe_id": recipe_id})

    try:
        data = await request.json()
    except Exception:
        raise HTTPException(400, detail="Invalid JSON") from None

    if not data:
        raise HTTPException(400, detail="Request body is required")

    if data.get("id") != recipe_id:
        raise HTTPException(
            400,
            detail=f"Recipe ID in URL ('{recipe_id}') must match ID in body ('{data.get('id')}')",
        )

    existing = await crud.get_recipe_by_id(db, recipe_id)
    if existing is None:
        raise HTTPException(404, detail=f"No recipe found with ID '{recipe_id}'")

    try:
        updated_recipe = Recipe.from_dict(data)
    except ValueError as e:
        raise HTTPException(400, detail=str(e)) from e

    if updated_recipe.servings <= 0:
        raise HTTPException(400, detail="Servings must be positive")
    if updated_recipe.prep_time_minutes < 0:
        raise HTTPException(400, detail="Prep time cannot be negative")
    if updated_recipe.cook_time_minutes < 0:
        raise HTTPException(400, detail="Cook time cannot be negative")
    if updated_recipe.calories_per_serving < 0:
        raise HTTPException(400, detail="Calories cannot be negative")
    if updated_recipe.protein_per_serving < 0:
        raise HTTPException(400, detail="Protein cannot be negative")
    if updated_recipe.carbs_per_serving < 0:
        raise HTTPException(400, detail="Carbs cannot be negative")
    if updated_recipe.fat_per_serving < 0:
        raise HTTPException(400, detail="Fat cannot be negative")

    await crud.upsert_recipe(db, updated_recipe, config.DEFAULT_HOUSEHOLD_ID)

    return {
        "success": True,
        "message": f"Recipe '{updated_recipe.name}' updated successfully. Please regenerate your meal plan.",
    }
