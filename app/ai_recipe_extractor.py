"""
AI-powered recipe extraction from unstructured text using OpenAI GPT-4o.

Extracts structured recipe data from Instagram post descriptions and other
unstructured recipe text in both English and French.
"""

import json
from dataclasses import dataclass
from typing import Any

from openai import OpenAI


class AIExtractionError(Exception):
    """Raised when AI recipe extraction fails."""
    pass


@dataclass
class ExtractedRecipeData:
    """AI-extracted recipe data with confidence score."""
    name: str
    servings: int | None
    prep_time_minutes: int | None
    cook_time_minutes: int | None
    ingredients: list[dict[str, Any]]  # [{"item": str, "quantity": float, "unit": str, "category": str}]
    instructions: list[str]
    tags: list[str]
    language: str  # 'en' or 'fr'
    confidence: float  # 0-1


class AIRecipeExtractor:
    """Orchestrates AI-powered recipe extraction."""

    def __init__(self, openai_api_key: str):
        """
        Initialize AI recipe extractor.

        Args:
            openai_api_key: OpenAI API key
        """
        self.client = OpenAI(api_key=openai_api_key)

    def _build_extraction_prompt(self, text: str) -> str:
        """
        Build extraction prompt with few-shot examples.

        Args:
            text: Unstructured recipe text

        Returns:
            System prompt for GPT-4o
        """
        return """You are a recipe extraction expert. Extract structured recipe data from unstructured text.

OUTPUT FORMAT (JSON):
{
  "name": "Recipe name",
  "servings": 4,
  "prep_time_minutes": 15,
  "cook_time_minutes": 30,
  "ingredients": [
    {"item": "spaghetti", "quantity": 400, "unit": "g", "category": "grains"},
    {"item": "eggs", "quantity": 4, "unit": "whole", "category": "dairy"}
  ],
  "instructions": ["Step 1: ...", "Step 2: ..."],
  "tags": ["italian", "pasta", "quick"],
  "language": "en",
  "confidence": 0.92
}

INSTRUCTIONS:
1. **Ingredients**: Separate quantity, unit, and item. If quantity is missing, use null. If unit is missing, use "whole" for countable items or "to taste" for seasonings.
2. **Categories**: meat, produce, dairy, grains, spices, pantry, other
3. **Times**: Extract prep and cook time in minutes. If not specified, use null.
4. **Instructions**: Extract as ordered list of steps. Preserve original numbering if present.
5. **Tags**: Infer cuisine type, dietary info, cooking method, meal type (max 5 tags)
6. **Language**: Detect language - return "en" for English, "fr" for French
7. **Confidence**: Score 0-1 based on clarity and completeness (0.9+ = very clear, 0.7-0.9 = good, 0.5-0.7 = ambiguous, <0.5 = very unclear)
8. **Handle missing data**: Use null for numeric fields, empty arrays for lists, "Unknown Recipe" for missing name

EXAMPLES:

Input (English):
"Creamy Carbonara 🍝
Serves 4 | Prep: 10 min | Cook: 15 min

Ingredients:
- 400g spaghetti
- 4 eggs
- 200g pancetta
- 100g Parmesan, grated
- Black pepper to taste

Instructions:
1. Cook pasta in salted boiling water
2. Fry pancetta until crispy
3. Beat eggs with Parmesan
4. Drain pasta, mix with pancetta, remove from heat
5. Add egg mixture, toss quickly
6. Season with pepper and serve"

Output:
{
  "name": "Creamy Carbonara",
  "servings": 4,
  "prep_time_minutes": 10,
  "cook_time_minutes": 15,
  "ingredients": [
    {"item": "spaghetti", "quantity": 400, "unit": "g", "category": "grains"},
    {"item": "eggs", "quantity": 4, "unit": "whole", "category": "dairy"},
    {"item": "pancetta", "quantity": 200, "unit": "g", "category": "meat"},
    {"item": "Parmesan cheese", "quantity": 100, "unit": "g", "category": "dairy"},
    {"item": "black pepper", "quantity": null, "unit": "to taste", "category": "spices"}
  ],
  "instructions": [
    "Cook pasta in salted boiling water",
    "Fry pancetta until crispy",
    "Beat eggs with Parmesan",
    "Drain pasta, mix with pancetta, remove from heat",
    "Add egg mixture, toss quickly",
    "Season with pepper and serve"
  ],
  "tags": ["italian", "pasta", "quick", "comfort-food"],
  "language": "en",
  "confidence": 0.95
}

Input (French):
"Soupe à l'oignon gratinée
Pour 4 personnes | Préparation: 20 min | Cuisson: 45 min

Ingrédients:
- 6 gros oignons
- 50g de beurre
- 1L de bouillon de bœuf
- 200g de gruyère râpé
- 4 tranches de pain
- Sel et poivre

Étapes:
1. Émincer les oignons finement
2. Faire fondre dans le beurre pendant 30 min
3. Ajouter le bouillon, mijoter 15 min
4. Verser dans des bols, ajouter pain et fromage
5. Gratiner au four 10 min à 200°C"

Output:
{
  "name": "Soupe à l'oignon gratinée",
  "servings": 4,
  "prep_time_minutes": 20,
  "cook_time_minutes": 45,
  "ingredients": [
    {"item": "oignons", "quantity": 6, "unit": "whole", "category": "produce"},
    {"item": "beurre", "quantity": 50, "unit": "g", "category": "dairy"},
    {"item": "bouillon de bœuf", "quantity": 1, "unit": "L", "category": "pantry"},
    {"item": "gruyère râpé", "quantity": 200, "unit": "g", "category": "dairy"},
    {"item": "pain", "quantity": 4, "unit": "tranches", "category": "grains"},
    {"item": "sel", "quantity": null, "unit": "to taste", "category": "spices"},
    {"item": "poivre", "quantity": null, "unit": "to taste", "category": "spices"}
  ],
  "instructions": [
    "Émincer les oignons finement",
    "Faire fondre dans le beurre pendant 30 min",
    "Ajouter le bouillon, mijoter 15 min",
    "Verser dans des bols, ajouter pain et fromage",
    "Gratiner au four 10 min à 200°C"
  ],
  "tags": ["french", "soup", "comfort-food", "cheese"],
  "language": "fr",
  "confidence": 0.93
}

Now extract the recipe from the following text:"""

    def extract_recipe(self, text: str, source_hint: str = "instagram") -> ExtractedRecipeData:
        """
        Extract recipe from unstructured text using AI.

        Args:
            text: Unstructured recipe text (e.g., Instagram caption)
            source_hint: Hint about text source (for context)

        Returns:
            ExtractedRecipeData object

        Raises:
            AIExtractionError: If extraction fails
        """
        try:
            # Build prompt
            system_prompt = self._build_extraction_prompt(text)

            # Call OpenAI API
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text}
                ],
                response_format={"type": "json_object"},
                temperature=0.3,  # Lower temperature for more consistent extraction
                max_tokens=2000
            )

            # Parse response
            result_text = response.choices[0].message.content
            result = json.loads(result_text)

            # Validate required fields
            if not result.get("name"):
                result["name"] = "Unknown Recipe"

            if not result.get("ingredients"):
                raise AIExtractionError(
                    "Could not extract ingredients from text. "
                    "Please ensure the recipe includes an ingredients list."
                )

            if not result.get("instructions"):
                raise AIExtractionError(
                    "Could not extract instructions from text. "
                    "Please ensure the recipe includes cooking steps."
                )

            # Build ExtractedRecipeData
            return ExtractedRecipeData(
                name=result.get("name", "Unknown Recipe"),
                servings=result.get("servings"),
                prep_time_minutes=result.get("prep_time_minutes"),
                cook_time_minutes=result.get("cook_time_minutes"),
                ingredients=result.get("ingredients", []),
                instructions=result.get("instructions", []),
                tags=result.get("tags", []),
                language=result.get("language", "en"),
                confidence=result.get("confidence", 0.5)
            )

        except json.JSONDecodeError as e:
            raise AIExtractionError(f"Failed to parse AI response as JSON: {str(e)}") from e
        except Exception as e:
            if isinstance(e, AIExtractionError):
                raise
            raise AIExtractionError(f"AI extraction failed: {str(e)}") from e
