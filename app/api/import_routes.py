"""Recipe import routes — URL, text, and image."""

import logging
import time

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app import config
from app.db import crud
from app.db.engine import get_db
from app.recipes import Recipe, RecipeSaveError

logger = logging.getLogger(__name__)
router = APIRouter()

# ---------------------------------------------------------------------------
# Image magic-bytes validation
# ---------------------------------------------------------------------------
_IMAGE_MAGIC: list[tuple[bytes, bytes | None, int, int]] = [
    (b"\x89PNG\r\n\x1a\n", None, 0, 0),
    (b"\xff\xd8\xff", None, 0, 0),
    (b"GIF87a", None, 0, 0),
    (b"GIF89a", None, 0, 0),
    (b"RIFF", b"WEBP", 8, 4),
]


def _is_valid_image_bytes(data: bytes) -> bool:
    for prefix, suffix, suffix_offset, suffix_len in _IMAGE_MAGIC:
        if data[: len(prefix)] == prefix:
            if suffix is None:
                return True
            if data[suffix_offset : suffix_offset + suffix_len] == suffix:
                return True
    return False


# ---------------------------------------------------------------------------
# Shared helper
# ---------------------------------------------------------------------------

async def _finalize_and_save_recipe(
    parsed_recipe,
    db: AsyncSession,
    source: str = "",
) -> dict:
    """Generate nutrition, infer tags, upsert to DB, return response dict."""
    from app.nutrition_generator import NutritionGenerator
    from app.tag_inference import TagInferencer

    nutrition_gen = NutritionGenerator(api_key=config.USDA_API_KEY)
    tag_inferencer = TagInferencer()

    if nutrition_gen.should_generate_nutrition(parsed_recipe):
        generated_nutrition = nutrition_gen.generate_from_ingredients(
            parsed_recipe.ingredients, parsed_recipe.servings or 4
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

            has_meaningful = (
                generated_nutrition.calories > 0
                or generated_nutrition.protein > 0
                or generated_nutrition.carbs > 0
                or generated_nutrition.fat > 0
            )
            if has_meaningful:
                if not parsed_recipe.tags:
                    parsed_recipe.tags = []
                parsed_recipe.tags.append("nutrition-generated")

    parsed_recipe.tags = tag_inferencer.enhance_tags(
        name=parsed_recipe.name,
        ingredients=parsed_recipe.ingredients or [],
        instructions=parsed_recipe.instructions or [],
        prep_time_minutes=parsed_recipe.prep_time_minutes or 0,
        cook_time_minutes=parsed_recipe.cook_time_minutes or 0,
        existing_tags=parsed_recipe.tags or [],
    )

    from app.recipe_parser import generate_recipe_id

    existing_recipes = await crud.get_recipes(db, config.DEFAULT_HOUSEHOLD_ID)
    existing_ids = {r.id for r in existing_recipes}
    recipe_id = generate_recipe_id(parsed_recipe.name, existing_ids)
    recipe_dict = parsed_recipe.to_recipe_dict(recipe_id)
    new_recipe = Recipe.from_dict(recipe_dict)
    await crud.upsert_recipe(db, new_recipe, config.DEFAULT_HOUSEHOLD_ID)

    logger.info(
        "Recipe imported successfully",
        extra={"recipe_id": new_recipe.id, "recipe_name": new_recipe.name},
    )

    suffix = f" {source}" if source else ""
    response_data: dict = {
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

    if hasattr(parsed_recipe, "ai_confidence"):
        response_data["recipe"]["ai_confidence"] = parsed_recipe.ai_confidence
        if parsed_recipe.ai_confidence < 0.7:
            response_data["warning"] = (
                "Recipe extraction confidence is low. "
                "Please review the imported data carefully."
            )

    return response_data


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post("/import-recipe")
async def import_recipe(request: Request, db: AsyncSession = Depends(get_db)):
    """Import a recipe from a URL."""
    logger.info("Importing recipe from URL")

    try:
        data = await request.json()
    except Exception:
        raise HTTPException(400, detail="Invalid JSON") from None

    if not data or "url" not in data:
        raise HTTPException(400, detail="URL is required")

    url = data["url"]
    if not url.startswith("http://") and not url.startswith("https://"):
        raise HTTPException(400, detail="URL must start with http:// or https://")

    try:
        from app.ai_recipe_extractor import AIExtractionError
        from app.instagram_fetcher import InstagramFetchError
        from app.recipe_parser import RecipeParseError, RecipeParser

        logger.info("Parsing recipe from URL", extra={"url": url})
        t0 = time.monotonic()
        parser = RecipeParser()
        parsed_recipe = parser.parse_from_url(url)
        logger.info(
            "LLM call completed",
            extra={"elapsed_s": round(time.monotonic() - t0, 2), "recipe_name": parsed_recipe.name},
        )
        return await _finalize_and_save_recipe(parsed_recipe, db)

    except Exception as e:
        from app.ai_recipe_extractor import AIExtractionError
        from app.instagram_fetcher import InstagramFetchError
        from app.recipe_parser import RecipeParseError

        if isinstance(e, InstagramFetchError):
            raise HTTPException(400, detail=str(e)) from e
        if isinstance(e, AIExtractionError):
            raise HTTPException(400, detail=str(e)) from e
        if isinstance(e, RecipeParseError):
            raise HTTPException(400, detail=str(e)) from e
        if isinstance(e, ValueError):
            raise HTTPException(400, detail=str(e)) from e
        if isinstance(e, RecipeSaveError):
            raise HTTPException(500, detail=f"Failed to save recipe: {e}") from e
        logger.exception("Unexpected error during recipe import", extra={"url": url})
        raise HTTPException(500, detail=f"Unexpected error: {e}") from e


@router.post("/import-recipe-text")
async def import_recipe_text(request: Request, db: AsyncSession = Depends(get_db)):
    """Import a recipe from manually pasted text."""
    logger.info("Importing recipe from text")

    try:
        data = await request.json()
    except Exception:
        raise HTTPException(400, detail="Invalid JSON") from None

    if not data or "text" not in data:
        raise HTTPException(400, detail="Text is required")

    text = data["text"]
    language = data.get("language", "auto")

    if not text or len(text.strip()) < 50:
        raise HTTPException(400, detail="Recipe text must be at least 50 characters long")

    try:
        from app.ai_recipe_extractor import AIExtractionError
        from app.instagram_parser import InstagramParser
        from app.recipe_parser import RecipeParseError

        instagram_parser = InstagramParser(openai_api_key=config.OPENAI_API_KEY)
        t0 = time.monotonic()
        parsed_recipe = instagram_parser.parse_from_text(text, language)
        logger.info(
            "LLM call completed",
            extra={"elapsed_s": round(time.monotonic() - t0, 2), "recipe_name": parsed_recipe.name},
        )
        return await _finalize_and_save_recipe(parsed_recipe, db, source="from text")

    except Exception as e:
        from app.ai_recipe_extractor import AIExtractionError
        from app.recipe_parser import RecipeParseError

        if isinstance(e, AIExtractionError):
            raise HTTPException(400, detail=str(e)) from e
        if isinstance(e, RecipeParseError):
            raise HTTPException(400, detail=str(e)) from e
        if isinstance(e, ValueError):
            raise HTTPException(400, detail=str(e)) from e
        if isinstance(e, RecipeSaveError):
            raise HTTPException(500, detail=f"Failed to save recipe: {e}") from e
        logger.exception("Unexpected error during text import")
        raise HTTPException(500, detail=f"Unexpected error: {e}") from e


@router.post("/import-recipe-image")
async def import_recipe_image(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Import a recipe from a photo."""
    logger.info("Importing recipe from image")

    form = await request.form()
    file: UploadFile | None = form.get("image")  # type: ignore[assignment]

    if file is None:
        raise HTTPException(400, detail="Image file is required")
    if not file.filename:
        raise HTTPException(400, detail="Please select an image file")

    allowed_extensions = {"png", "jpg", "jpeg", "gif", "webp"}
    file_ext = file.filename.rsplit(".", 1)[1].lower() if "." in file.filename else ""
    if file_ext not in allowed_extensions:
        raise HTTPException(
            400, detail=f"Allowed types: {', '.join(allowed_extensions)}"
        )

    image_data = await file.read()
    if len(image_data) == 0:
        raise HTTPException(400, detail="The uploaded image file is empty")

    if not _is_valid_image_bytes(image_data):
        raise HTTPException(400, detail="File does not appear to be a valid image")

    if not config.OPENAI_API_KEY:
        raise HTTPException(500, detail="Image import is not configured on the server")

    try:
        from app.image_recipe_extractor import ImageRecipeExtractor
        from app.recipe_parser import ParsedRecipe

        extractor = ImageRecipeExtractor(api_key=config.OPENAI_API_KEY)
        t0 = time.monotonic()
        extracted_data = extractor.extract_recipe(image_data, file_ext)
        logger.info(
            "LLM call completed",
            extra={
                "elapsed_s": round(time.monotonic() - t0, 2),
                "recipe_name": extracted_data.name,
                "confidence": extracted_data.confidence,
            },
        )
    except ValueError as e:
        raise HTTPException(400, detail=str(e)) from e
    except Exception as e:
        err = str(e)
        if "timeout" in err.lower():
            raise HTTPException(504, detail="Image processing timed out. Try a smaller image.") from e
        if "api" in err.lower() or "openai" in err.lower():
            raise HTTPException(502, detail=f"OpenAI API error: {err}") from e
        raise HTTPException(500, detail=f"An error occurred while processing the image: {err}") from e

    try:
        from app.recipe_parser import ParsedRecipe

        tags = extracted_data.tags + ["photo-imported"]
        instructions = extracted_data.instructions or []
        if extracted_data.notes:
            instructions = list(instructions) + [f"Note: {extracted_data.notes}"]

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
            fat_per_serving=None,
        )
        parsed_recipe.ai_confidence = extracted_data.confidence

        return await _finalize_and_save_recipe(parsed_recipe, db, source="from photo")

    except ValueError as e:
        raise HTTPException(400, detail=str(e)) from e
    except RecipeSaveError as e:
        raise HTTPException(500, detail=f"Failed to save recipe: {e}") from e
    except Exception as e:
        logger.exception("Unexpected error during image recipe conversion/saving")
        raise HTTPException(500, detail=f"Unexpected error: {e}") from e
