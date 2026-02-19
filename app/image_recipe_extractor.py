"""Extract recipes from images using OpenAI Vision API."""

import base64
import logging
from dataclasses import dataclass

import openai

logger = logging.getLogger(__name__)


@dataclass
class ImageRecipeData:
    """Recipe data extracted from an image."""
    name: str
    servings: int
    prep_time_minutes: int | None
    cook_time_minutes: int | None
    ingredients: list[dict]
    instructions: list[str]
    tags: list[str]
    notes: str | None
    confidence: float


class ImageRecipeExtractor:
    """Extract recipe data from images using OpenAI Vision API."""

    def __init__(self, api_key: str):
        """Initialize the extractor with OpenAI API key."""
        self.client = openai.OpenAI(api_key=api_key)

    def extract_recipe(self, image_data: bytes, image_format: str = "jpeg") -> ImageRecipeData:
        """Extract recipe from image using GPT-4 Vision.

        Args:
            image_data: Image bytes
            image_format: Image format (jpeg, png, etc.)

        Returns:
            ImageRecipeData with extracted recipe information

        Raises:
            ValueError: If recipe cannot be extracted
        """
        logger.info("Starting image recipe extraction", extra={"size_bytes": len(image_data), "image_format": image_format})

        # Encode image to base64
        try:
            logger.debug("Encoding image to base64")
            base64_image = base64.b64encode(image_data).decode('utf-8')
            image_url = f"data:image/{image_format};base64,{base64_image}"
            logger.debug("Image base64 encoded", extra={"base64_length": len(base64_image)})
        except Exception as e:
            logger.exception("Failed to encode image to base64", extra={"image_format": image_format})
            raise ValueError(f"Failed to encode image: {e}") from e

        # Create prompt for recipe extraction
        prompt = self._build_extraction_prompt()

        import time
        try:
            # Call GPT-4 Vision API with a specific timeout
            logger.info("Calling OpenAI Vision API", extra={"model": "gpt-4o", "timeout_s": 90})
            t0 = time.monotonic()
            response = self.client.chat.completions.create(
                model="gpt-4o",  # gpt-4o has vision capabilities
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": prompt
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": image_url
                                }
                            }
                        ]
                    }
                ],
                max_tokens=2000,
                temperature=0.1,  # Low temperature for consistent extraction
                timeout=90.0      # Explicit timeout for the API call
            )
            elapsed = round(time.monotonic() - t0, 2)
            logger.info("OpenAI Vision API call successful", extra={"elapsed_s": elapsed})

            # Parse response
            content = response.choices[0].message.content
            logger.debug("Vision API response received", extra={"response_length": len(content)})

            result = self._parse_response(content)
            logger.info("Image recipe extraction complete", extra={"recipe_name": result.name, "confidence": result.confidence})
            return result

        except openai.APIError as e:
            logger.exception("OpenAI API error during image extraction")
            raise ValueError(f"API error: {e}") from e
        except openai.APITimeoutError as e:
            logger.exception("OpenAI API timeout during image extraction")
            raise ValueError(f"API timeout after 90 seconds: {e}") from e
        except openai.APIConnectionError as e:
            logger.exception("OpenAI API connection error during image extraction")
            raise ValueError(f"API connection error: {e}") from e
        except openai.RateLimitError as e:
            logger.exception("OpenAI API rate limit hit during image extraction")
            raise ValueError(f"API rate limit exceeded: {e}") from e
        except Exception as e:
            logger.exception("Unexpected error during image extraction")
            raise ValueError(f"Failed to extract recipe from image: {e}") from e

    def _build_extraction_prompt(self) -> str:
        """Build the prompt for recipe extraction."""
        return """Extract the recipe information from this image. Look for:
- Recipe name
- Number of servings
- Preparation time
- Cooking time
- List of ingredients (with quantities, units, and items)
- Step-by-step instructions
- Any tags/categories (e.g., "dinner", "italian", "quick", "vegetarian")
- Additional notes

Format your response EXACTLY as JSON with this structure:
{
  "name": "Recipe Name",
  "servings": 4,
  "prep_time_minutes": 15,
  "cook_time_minutes": 30,
  "ingredients": [
    {"quantity": 2, "unit": "cups", "item": "flour", "category": "grains"},
    {"quantity": 1, "unit": "tsp", "item": "salt", "category": "spices"}
  ],
  "instructions": [
    "Step 1: Do this",
    "Step 2: Do that"
  ],
  "tags": ["dinner", "italian"],
  "notes": "Any additional notes or tips",
  "confidence": 0.95
}

Important:
- Extract ALL visible text carefully
- Parse quantities and units separately
- If handwritten, do your best to read it
- If uncertain about a value, use your best guess but lower the confidence
- For servings: If not specified, estimate based on ingredient quantities (default to 4 if unclear)
- For times: Use null only if no time information is visible at all
- Confidence: 0-1 (0.9+ high confidence, 0.7-0.9 medium, <0.7 low)
- Return ONLY the JSON, no other text"""

    def _parse_response(self, content: str) -> ImageRecipeData:
        """Parse the API response into ImageRecipeData.

        Args:
            content: JSON response from API

        Returns:
            ImageRecipeData object
        """
        import json

        logger.debug("Parsing image extraction response")

        # Extract JSON from response (handles markdown code blocks)
        content = content.strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

        try:
            import json
            data = json.loads(content)
            logger.debug("Image extraction JSON parsed", extra={"keys": list(data.keys())})
        except json.JSONDecodeError as e:
            logger.exception("JSON decode error parsing image extraction response", extra={"content_preview": content[:200]})
            raise ValueError(f"Failed to parse JSON response: {e}") from e

        # Validate required fields
        required_fields = ["name", "servings", "ingredients", "instructions"]
        for field in required_fields:
            if field not in data:
                logger.error("Missing required field in image extraction response", extra={"missing_field": field, "available_fields": list(data.keys())})
                raise ValueError(f"Missing required field: {field}")

        logger.debug("All required fields present in image extraction response")

        # Create ImageRecipeData object
        try:
            # Handle null servings by defaulting to 4
            servings = data.get("servings")
            if servings is None:
                logger.warning("Servings is null in image extraction response, defaulting to 4")
                servings = 4
            else:
                servings = int(servings)

            result = ImageRecipeData(
                name=data["name"],
                servings=servings,
                prep_time_minutes=data.get("prep_time_minutes"),
                cook_time_minutes=data.get("cook_time_minutes"),
                ingredients=data["ingredients"],
                instructions=data["instructions"],
                tags=data.get("tags", []),
                notes=data.get("notes"),
                confidence=float(data.get("confidence", 0.8))
            )
            logger.debug("ImageRecipeData created", extra={"recipe_name": result.name})
            return result
        except Exception as e:
            logger.exception("Failed to create ImageRecipeData object")
            raise ValueError(f"Failed to create recipe data object: {e}") from e
