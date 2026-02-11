"""Extract recipes from images using OpenAI Vision API."""

import base64
from dataclasses import dataclass

import openai


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
        print(f"[IMAGE EXTRACTOR] Starting extraction, image size: {len(image_data)} bytes, format: {image_format}", flush=True)

        # Encode image to base64
        try:
            print("[IMAGE EXTRACTOR] Encoding image to base64...", flush=True)
            base64_image = base64.b64encode(image_data).decode('utf-8')
            image_url = f"data:image/{image_format};base64,{base64_image}"
            print(f"[IMAGE EXTRACTOR] Base64 encoded, length: {len(base64_image)}", flush=True)
        except Exception as e:
            print(f"[IMAGE EXTRACTOR ERROR] Failed to encode image: {type(e).__name__}: {str(e)}", flush=True)
            raise ValueError(f"Failed to encode image: {e}") from e

        # Create prompt for recipe extraction
        prompt = self._build_extraction_prompt()

        try:
            # Call GPT-4 Vision API with a specific timeout
            print("[IMAGE EXTRACTOR] Calling OpenAI Vision API (model: gpt-4o, timeout: 90s)...", flush=True)
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
            print("[IMAGE EXTRACTOR] OpenAI API call successful", flush=True)

            # Parse response
            content = response.choices[0].message.content
            print(f"[IMAGE EXTRACTOR] Response received, length: {len(content)} chars", flush=True)
            print(f"[IMAGE EXTRACTOR] Response preview: {content[:200]}...", flush=True)

            result = self._parse_response(content)
            print(f"[IMAGE EXTRACTOR] Parsing successful: {result.name}, confidence: {result.confidence}", flush=True)
            return result

        except openai.APIError as e:
            error_msg = f"OpenAI API error: {type(e).__name__}: {str(e)}"
            print(f"[IMAGE EXTRACTOR ERROR] {error_msg}", flush=True)
            raise ValueError(f"API error: {e}") from e
        except openai.APITimeoutError as e:
            error_msg = f"OpenAI API timeout: {str(e)}"
            print(f"[IMAGE EXTRACTOR ERROR] {error_msg}", flush=True)
            raise ValueError(f"API timeout after 90 seconds: {e}") from e
        except openai.APIConnectionError as e:
            error_msg = f"OpenAI API connection error: {str(e)}"
            print(f"[IMAGE EXTRACTOR ERROR] {error_msg}", flush=True)
            raise ValueError(f"API connection error: {e}") from e
        except openai.RateLimitError as e:
            error_msg = f"OpenAI API rate limit: {str(e)}"
            print(f"[IMAGE EXTRACTOR ERROR] {error_msg}", flush=True)
            raise ValueError(f"API rate limit exceeded: {e}") from e
        except Exception as e:
            error_msg = f"Unexpected error: {type(e).__name__}: {str(e)}"
            print(f"[IMAGE EXTRACTOR ERROR] {error_msg}", flush=True)
            import traceback
            print(f"[IMAGE EXTRACTOR ERROR] Traceback: {traceback.format_exc()}", flush=True)
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

        print("[IMAGE EXTRACTOR] Parsing response...", flush=True)

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
            print("[IMAGE EXTRACTOR] Loading JSON...", flush=True)
            data = json.loads(content)
            print(f"[IMAGE EXTRACTOR] JSON loaded, keys: {list(data.keys())}", flush=True)
        except json.JSONDecodeError as e:
            print(f"[IMAGE EXTRACTOR ERROR] JSON decode error: {str(e)}", flush=True)
            print(f"[IMAGE EXTRACTOR ERROR] Content that failed to parse: {content[:500]}", flush=True)
            raise ValueError(f"Failed to parse JSON response: {e}") from e

        # Validate required fields
        required_fields = ["name", "servings", "ingredients", "instructions"]
        for field in required_fields:
            if field not in data:
                print(f"[IMAGE EXTRACTOR ERROR] Missing required field: {field}", flush=True)
                print(f"[IMAGE EXTRACTOR ERROR] Available fields: {list(data.keys())}", flush=True)
                raise ValueError(f"Missing required field: {field}")

        print("[IMAGE EXTRACTOR] All required fields present", flush=True)

        # Create ImageRecipeData object
        try:
            result = ImageRecipeData(
                name=data["name"],
                servings=int(data["servings"]),
                prep_time_minutes=data.get("prep_time_minutes"),
                cook_time_minutes=data.get("cook_time_minutes"),
                ingredients=data["ingredients"],
                instructions=data["instructions"],
                tags=data.get("tags", []),
                notes=data.get("notes"),
                confidence=float(data.get("confidence", 0.8))
            )
            print("[IMAGE EXTRACTOR] ImageRecipeData created successfully", flush=True)
            return result
        except Exception as e:
            print(f"[IMAGE EXTRACTOR ERROR] Failed to create ImageRecipeData: {type(e).__name__}: {str(e)}", flush=True)
            raise ValueError(f"Failed to create recipe data object: {e}") from e
