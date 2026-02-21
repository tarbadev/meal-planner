"""
Main orchestrator for Instagram recipe import.

Combines fetching, AI extraction, and normalization to parse Instagram recipes.
"""

import logging

from app.ai_recipe_extractor import AIExtractionError, AIRecipeExtractor
from app.ingredient_normalizer import normalize_ingredient
from app.instagram_fetcher import InstagramFetcher, InstagramFetchError
from app.recipe_parser import ParsedRecipe

logger = logging.getLogger(__name__)


class InstagramParser:
    """Coordinates all Instagram import steps."""

    def __init__(self, openai_api_key: str, instagram_session_file: str | None = None):
        """
        Initialize Instagram parser.

        Args:
            openai_api_key: OpenAI API key for AI extraction
            instagram_session_file: Path to Instagram session file (optional)
        """
        self.fetcher = InstagramFetcher(session_file=instagram_session_file)
        self.extractor = AIRecipeExtractor(openai_api_key=openai_api_key)

    def parse(self, url: str) -> ParsedRecipe:
        """
        Parse recipe from Instagram URL.

        Args:
            url: Instagram post or reel URL

        Returns:
            ParsedRecipe object compatible with existing system

        Raises:
            InstagramFetchError: If Instagram post cannot be fetched
            AIExtractionError: If AI extraction fails
        """
        # Step 1: Fetch Instagram post
        logger.info("Fetching Instagram post", extra={"url": url})
        try:
            post = self.fetcher.fetch_post(url)
        except InstagramFetchError:
            logger.exception("Failed to fetch Instagram post", extra={"url": url})
            raise

        logger.info("Instagram post fetched successfully", extra={"url": url, "has_owner_comments": post.has_owner_comments})

        # Step 2: Extract recipe using AI
        try:
            extracted = self.extractor.extract_recipe(
                text=post.description,
                source_hint="instagram"
            )
        except AIExtractionError:
            logger.exception("AI extraction failed for Instagram post", extra={"url": url})
            raise

        # Step 3: Normalize ingredients
        normalized_ingredients = []
        for ingredient in extracted.ingredients:
            normalized = normalize_ingredient(ingredient)
            normalized_ingredients.append(normalized)

        # Step 4: Build tags
        tags = ["instagram", "ai-extracted"]
        tags.extend(extracted.tags)

        # Add tag if recipe was extracted from comments
        if post.has_owner_comments:
            tags.append("from-comments")

        # Add confidence tag if low
        if extracted.confidence < 0.7:
            tags.append("low-confidence")

        # Step 5: Convert to ParsedRecipe
        parsed = ParsedRecipe(
            name=extracted.name,
            servings=extracted.servings or 4,  # Default to 4 if not specified
            prep_time_minutes=extracted.prep_time_minutes,
            cook_time_minutes=extracted.cook_time_minutes,
            ingredients=normalized_ingredients,
            instructions=extracted.instructions,
            tags=tags,
            source_url=url,
            reheats_well=extracted.reheats_well,
            stores_days=extracted.stores_days,
            packs_well_as_lunch=extracted.packs_well_as_lunch,
        )

        # Store additional metadata
        parsed.ai_confidence = extracted.confidence
        parsed.language = extracted.language

        return parsed

    def parse_from_text(self, text: str, language: str = "auto") -> ParsedRecipe:
        """
        Parse recipe from manually pasted text (fallback method).

        Args:
            text: Recipe text (e.g., manually copied Instagram caption)
            language: Language hint ("en", "fr", or "auto")

        Returns:
            ParsedRecipe object

        Raises:
            AIExtractionError: If AI extraction fails
        """
        # Step 1: Extract recipe using AI
        logger.info("Parsing recipe from manually pasted text", extra={"text_length": len(text), "language": language})
        try:
            extracted = self.extractor.extract_recipe(
                text=text,
                source_hint="manual_paste"
            )
        except AIExtractionError:
            logger.exception("AI extraction failed for manually pasted text", extra={"text_length": len(text)})
            raise

        # Step 2: Normalize ingredients
        normalized_ingredients = []
        for ingredient in extracted.ingredients:
            normalized = normalize_ingredient(ingredient)
            normalized_ingredients.append(normalized)

        # Step 3: Build tags
        tags = ["manual-import", "ai-extracted"]
        tags.extend(extracted.tags)

        if extracted.confidence < 0.7:
            tags.append("low-confidence")

        # Step 4: Convert to ParsedRecipe
        parsed = ParsedRecipe(
            name=extracted.name,
            servings=extracted.servings or 4,
            prep_time_minutes=extracted.prep_time_minutes,
            cook_time_minutes=extracted.cook_time_minutes,
            ingredients=normalized_ingredients,
            instructions=extracted.instructions,
            tags=tags,
            source_url=None,  # No URL for manual paste
            reheats_well=extracted.reheats_well,
            stores_days=extracted.stores_days,
            packs_well_as_lunch=extracted.packs_well_as_lunch,
        )

        # Store additional metadata
        parsed.ai_confidence = extracted.confidence
        parsed.language = extracted.language

        return parsed
