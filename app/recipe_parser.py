import json
import re
from dataclasses import dataclass

import requests
from bs4 import BeautifulSoup

from app.ingredient_parser import IngredientParser


@dataclass
class ParsedRecipe:
    """Intermediate representation of parsed recipe data."""
    name: str
    servings: int | None = None
    prep_time_minutes: int | None = None
    cook_time_minutes: int | None = None
    # Core nutrition fields
    calories_per_serving: int | None = None
    protein_per_serving: float | None = None
    carbs_per_serving: float | None = None
    fat_per_serving: float | None = None
    # Extended nutrition fields
    saturated_fat_per_serving: float | None = None
    polyunsaturated_fat_per_serving: float | None = None
    monounsaturated_fat_per_serving: float | None = None
    sodium_per_serving: float | None = None
    potassium_per_serving: float | None = None
    fiber_per_serving: float | None = None
    sugar_per_serving: float | None = None
    vitamin_a_per_serving: float | None = None
    vitamin_c_per_serving: float | None = None
    calcium_per_serving: float | None = None
    iron_per_serving: float | None = None
    # Other fields
    tags: list[str] = None
    ingredients: list[dict] = None
    instructions: list[str] = None
    source_url: str = None
    image_url: str | None = None

    def to_recipe_dict(self, generated_id: str) -> dict:
        """Convert to Recipe dict format with defaults for missing values.

        Raises:
            RecipeParseError: If ingredients or instructions are missing/empty
        """
        # CRITICAL: Validate that ingredients and instructions were extracted
        if not self.ingredients or len(self.ingredients) == 0:
            raise RecipeParseError(
                "Could not extract ingredients from this recipe. "
                "The recipe may have an unusual format. "
                "Please try a different URL or add the recipe manually."
            )

        if not self.instructions or len(self.instructions) == 0:
            raise RecipeParseError(
                "Could not extract cooking instructions from this recipe. "
                "The recipe may have an unusual format. "
                "Please try a different URL or add the recipe manually."
            )

        # Build nested nutrition structure
        nutrition_per_serving = {
            "calories": self.calories_per_serving or 0,
            "protein": self.protein_per_serving or 0.0,
            "carbs": self.carbs_per_serving or 0.0,
            "fat": self.fat_per_serving or 0.0,
            "saturated_fat": self.saturated_fat_per_serving,
            "polyunsaturated_fat": self.polyunsaturated_fat_per_serving,
            "monounsaturated_fat": self.monounsaturated_fat_per_serving,
            "sodium": self.sodium_per_serving,
            "potassium": self.potassium_per_serving,
            "fiber": self.fiber_per_serving,
            "sugar": self.sugar_per_serving,
            "vitamin_a": self.vitamin_a_per_serving,
            "vitamin_c": self.vitamin_c_per_serving,
            "calcium": self.calcium_per_serving,
            "iron": self.iron_per_serving
        }

        return {
            "id": generated_id,
            "name": self.name,
            "servings": self.servings or 4,  # Default to 4 servings
            "prep_time_minutes": self.prep_time_minutes or 0,
            "cook_time_minutes": self.cook_time_minutes or 0,
            "nutrition_per_serving": nutrition_per_serving,
            "tags": self.tags or ["imported"],
            "ingredients": self.ingredients,
            "instructions": self.instructions,
            "source_url": self.source_url,
            "image_url": self.image_url
        }


class RecipeParseError(Exception):
    """Raised when recipe parsing fails."""
    pass


class RecipeParser:
    """Parse recipes from URLs using multiple strategies."""

    def _is_instagram_url(self, url: str) -> bool:
        """Check if URL is an Instagram post or reel."""
        return 'instagram.com' in url.lower() and ('/p/' in url or '/reel/' in url)

    def parse_from_url(self, url: str) -> ParsedRecipe:
        """Main entry point - parse recipe from URL."""
        # Check if this is an Instagram URL
        if self._is_instagram_url(url):
            from app import config
            from app.instagram_parser import InstagramParser
            print("Init of instagram_parser")
            instagram_parser = InstagramParser(
                openai_api_key=config.OPENAI_API_KEY,
                instagram_session_file=config.INSTAGRAM_SESSION_FILE
            )
            return instagram_parser.parse(url)

        # Regular recipe website parsing
        try:
            # Fetch the page with a proper user agent
            headers = {
                'User-Agent': 'Mozilla/5.0 (compatible; RecipeImporter/1.0)'
            }
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            html = response.text

            # Try parsing strategies in priority order
            recipe = (
                self._parse_wprm(html) or          # WP Recipe Maker plugin
                self._parse_schema_org(html) or    # Schema.org JSON-LD
                self._parse_html_patterns(html) or  # HTML fallback
                None
            )

            if not recipe:
                raise RecipeParseError("Could not extract recipe data from URL")

            recipe.source_url = url
            return recipe

        except requests.RequestException as e:
            raise RecipeParseError(f"Failed to fetch URL: {str(e)}") from e
        except Exception as e:
            raise RecipeParseError(f"Failed to fetch URL: {str(e)}") from e

    def _parse_schema_org(self, html: str) -> ParsedRecipe | None:
        """Extract recipe from schema.org JSON-LD markup."""
        soup = BeautifulSoup(html, 'html.parser')

        # Find JSON-LD script tags
        for script in soup.find_all('script', type='application/ld+json'):
            try:
                data = json.loads(script.string)

                # Handle @graph structure
                if isinstance(data, dict) and '@graph' in data:
                    recipes = [item for item in data['@graph'] if item.get('@type') == 'Recipe']
                    if recipes:
                        data = recipes[0]

                # Check if it's a Recipe type
                if isinstance(data, dict) and data.get('@type') == 'Recipe':
                    return self._extract_from_schema_org(data)

            except (json.JSONDecodeError, KeyError):
                continue

        return None

    def _extract_from_schema_org(self, data: dict) -> ParsedRecipe:
        """Extract recipe fields from schema.org data."""
        # Helper to parse ISO 8601 duration to minutes
        def parse_duration(duration_str: str) -> int:
            if not duration_str:
                return 0
            match = re.search(r'PT(?:(\d+)H)?(?:(\d+)M)?', duration_str)
            if match:
                hours = int(match.group(1) or 0)
                minutes = int(match.group(2) or 0)
                return hours * 60 + minutes
            return 0

        # Extract nutrition
        nutrition = data.get('nutrition', {})

        # Parse ingredients
        ingredients_raw = data.get('recipeIngredient', [])
        ingredients = []
        for ing in ingredients_raw:
            parsed = self._parse_ingredient(ing)
            if parsed:
                ingredients.append(parsed)

        # Parse instructions
        instructions = []
        instructions_raw = data.get('recipeInstructions', [])

        # Handle different formats of recipeInstructions
        if isinstance(instructions_raw, str):
            # Single string - split by newlines or periods
            instructions = [s.strip() for s in instructions_raw.split('\n') if s.strip()]
        elif isinstance(instructions_raw, list):
            for instruction in instructions_raw:
                if isinstance(instruction, str):
                    instructions.append(instruction.strip())
                elif isinstance(instruction, dict):
                    # HowToStep schema
                    text = instruction.get('text', '')
                    if text:
                        instructions.append(text.strip())

        return ParsedRecipe(
            name=data.get('name', 'Unnamed Recipe'),
            servings=self._extract_servings(data.get('recipeYield')),
            prep_time_minutes=parse_duration(data.get('prepTime', '')),
            cook_time_minutes=parse_duration(data.get('cookTime', '')),
            # Core nutrition fields
            calories_per_serving=self._extract_calories(nutrition),
            protein_per_serving=self._extract_nutrient(nutrition, 'proteinContent'),
            carbs_per_serving=self._extract_nutrient(nutrition, 'carbohydrateContent'),
            fat_per_serving=self._extract_nutrient(nutrition, 'fatContent'),
            # Extended nutrition fields from schema.org
            saturated_fat_per_serving=self._extract_nutrient(nutrition, 'saturatedFatContent'),
            # Note: schema.org uses 'unsaturatedFatContent' but we map to polyunsaturated
            polyunsaturated_fat_per_serving=self._extract_nutrient(nutrition, 'unsaturatedFatContent'),
            monounsaturated_fat_per_serving=self._extract_nutrient(nutrition, 'monounsaturatedFatContent'),
            sodium_per_serving=self._extract_nutrient(nutrition, 'sodiumContent'),
            potassium_per_serving=self._extract_nutrient(nutrition, 'potassiumContent'),
            fiber_per_serving=self._extract_nutrient(nutrition, 'fiberContent'),
            sugar_per_serving=self._extract_nutrient(nutrition, 'sugarContent'),
            vitamin_a_per_serving=self._extract_nutrient(nutrition, 'vitaminAContent'),
            vitamin_c_per_serving=self._extract_nutrient(nutrition, 'vitaminCContent'),
            calcium_per_serving=self._extract_nutrient(nutrition, 'calciumContent'),
            iron_per_serving=self._extract_nutrient(nutrition, 'ironContent'),
            tags=[],  # Could extract from recipeCategory or recipeCuisine
            ingredients=ingredients,
            instructions=instructions,
            image_url=self._extract_image_url(data.get('image'))
        )

    def _extract_servings(self, yield_value) -> int | None:
        """Extract servings from recipeYield (can be string or number)."""
        if isinstance(yield_value, int):
            return yield_value
        if isinstance(yield_value, str):
            # Extract first number from string like "4 servings" or "Serves 6"
            match = re.search(r'(\d+)', yield_value)
            if match:
                return int(match.group(1))
        return None

    def _extract_calories(self, nutrition: dict) -> int | None:
        """Extract calories from nutrition object."""
        cal_str = nutrition.get('calories', '')
        if isinstance(cal_str, str):
            match = re.search(r'(\d+)', cal_str)
            if match:
                return int(match.group(1))
        return None

    def _extract_nutrient(self, nutrition: dict, key: str) -> float | None:
        """Extract nutrient value (protein, carbs, fat) from nutrition object."""
        value_str = nutrition.get(key, '')
        if isinstance(value_str, str):
            # Extract number from strings like "25.5 g" or "25g"
            match = re.search(r'([\d.]+)', value_str)
            if match:
                return float(match.group(1))
        return None

    def _extract_image_url(self, image_data) -> str | None:
        """Extract image URL from schema.org image field.

        Image can be:
        - A string (URL)
        - An object with 'url' property
        - An array of strings or objects
        """
        if not image_data:
            return None

        # Handle string URL
        if isinstance(image_data, str):
            return image_data

        # Handle object with url property
        if isinstance(image_data, dict):
            return image_data.get('url')

        # Handle array (take first image)
        if isinstance(image_data, list) and len(image_data) > 0:
            first_image = image_data[0]
            if isinstance(first_image, str):
                return first_image
            if isinstance(first_image, dict):
                return first_image.get('url')

        return None

    def _parse_ingredient(self, ingredient_str: str) -> dict | None:
        """Parse ingredient string into structured format."""
        parser = IngredientParser()
        parsed = parser.parse(ingredient_str)
        return parser.to_dict(parsed)

    def _parse_wprm(self, html: str) -> ParsedRecipe | None:
        """Parse WP Recipe Maker (WPRM) plugin data from window.wprm_recipes."""
        # Look for window.wprm_recipes JavaScript variable
        match = re.search(r'window\.wprm_recipes\s*=\s*(\{.+?\});', html, re.DOTALL)
        if not match:
            return None

        try:
            wprm_data = json.loads(match.group(1))

            # Get first recipe (usually only one)
            recipe_data = next(iter(wprm_data.values()))

            # Extract ingredients
            ingredients = []
            ingredient_parser = IngredientParser()
            for ing_group in recipe_data.get('ingredients', []):
                for ing in ing_group.get('ingredients', []):
                    # Use structured data from WPRM but improve item name and category
                    item_name = ing.get('name', '')
                    if not item_name:
                        continue

                    # Parse the item name to extract clean name and notes
                    item_clean, notes = ingredient_parser._extract_item_and_notes(item_name)

                    parsed = {
                        "item": item_clean,
                        "quantity": self._parse_fraction(ing.get('amount', '1')),
                        "unit": ing.get('unit', 'pieces'),
                        "category": ingredient_parser._categorize(item_clean)
                    }
                    if notes:
                        parsed["notes"] = notes

                    ingredients.append(parsed)

            # Extract instructions
            instructions = []
            for inst_group in recipe_data.get('instructions', []):
                for inst in inst_group.get('instructions', []):
                    text = inst.get('text', '')
                    if text:
                        instructions.append(text.strip())

            # Extract nutrition (per serving)
            nutrition = recipe_data.get('nutrition', {})

            return ParsedRecipe(
                name=recipe_data.get('name', 'Unnamed Recipe'),
                servings=recipe_data.get('servings', 4),
                prep_time_minutes=recipe_data.get('prep_time', 0),
                cook_time_minutes=recipe_data.get('cook_time', 0),
                # Core nutrition fields
                calories_per_serving=nutrition.get('calories', 0),
                protein_per_serving=self._extract_grams(nutrition.get('protein')),
                carbs_per_serving=self._extract_grams(nutrition.get('carbohydrates')),
                fat_per_serving=self._extract_grams(nutrition.get('fat')),
                # Extended nutrition fields from WPRM
                saturated_fat_per_serving=self._extract_grams(nutrition.get('saturated_fat')),
                polyunsaturated_fat_per_serving=self._extract_grams(nutrition.get('polyunsaturated_fat')),
                monounsaturated_fat_per_serving=self._extract_grams(nutrition.get('monounsaturated_fat')),
                sodium_per_serving=self._extract_grams(nutrition.get('sodium')),
                potassium_per_serving=self._extract_grams(nutrition.get('potassium')),
                fiber_per_serving=self._extract_grams(nutrition.get('fiber')),
                sugar_per_serving=self._extract_grams(nutrition.get('sugar')),
                vitamin_a_per_serving=self._extract_grams(nutrition.get('vitamin_a')),
                vitamin_c_per_serving=self._extract_grams(nutrition.get('vitamin_c')),
                calcium_per_serving=self._extract_grams(nutrition.get('calcium')),
                iron_per_serving=self._extract_grams(nutrition.get('iron')),
                tags=[],
                ingredients=ingredients,
                instructions=instructions
            )

        except (json.JSONDecodeError, KeyError, StopIteration):
            return None

    def _parse_fraction(self, amount_str: str) -> float:
        """Parse fraction strings like '1/2' or '1 1/2' to float."""
        if not amount_str or amount_str.strip() == '':
            return 1.0

        amount_str = str(amount_str).strip()

        # Handle mixed numbers (e.g., "1 1/2")
        if ' ' in amount_str:
            whole, frac = amount_str.split(' ', 1)
            return float(whole) + self._parse_fraction(frac)

        # Handle simple fractions (e.g., "1/2")
        if '/' in amount_str:
            try:
                num, denom = amount_str.split('/')
                return float(num) / float(denom)
            except (ValueError, ZeroDivisionError):
                return 1.0

        # Handle regular numbers
        try:
            return float(amount_str)
        except ValueError:
            return 1.0

    def _extract_grams(self, nutrient_value) -> float:
        """Extract grams from nutrition values (could be int, float, or string)."""
        if isinstance(nutrient_value, (int, float)):
            return float(nutrient_value)
        if isinstance(nutrient_value, str):
            match = re.search(r'([\d.]+)', nutrient_value)
            if match:
                return float(match.group(1))
        return 0.0

    def _parse_html_patterns(self, html: str) -> ParsedRecipe | None:
        """Fallback parser for common HTML patterns on sites without structured data."""
        soup = BeautifulSoup(html, 'html.parser')

        # Try to find recipe name (common patterns)
        name = None
        for selector in ['h1', 'h2.recipe-title', '.recipe-name', 'article h1']:
            elem = soup.select_one(selector)
            if elem:
                name = elem.get_text().strip()
                break

        if not name:
            return None  # Can't parse without at least a name

        # Try to extract cook/prep times from text patterns
        prep_time = 0
        cook_time = 0
        text = soup.get_text()

        prep_match = re.search(r'Prep Time:?\s*(\d+)\s*min', text, re.IGNORECASE)
        if prep_match:
            prep_time = int(prep_match.group(1))

        cook_match = re.search(r'Cook Time:?\s*(\d+)\s*min', text, re.IGNORECASE)
        if cook_match:
            cook_time = int(cook_match.group(1))

        # Try to extract servings
        servings = 4  # Default
        servings_match = re.search(r'Serving Size:?\s*(\d+)', text, re.IGNORECASE)
        if servings_match:
            servings = int(servings_match.group(1))

        # Try to extract nutrition (look for common patterns)
        calories = 0
        protein = 0.0
        carbs = 0.0
        fat = 0.0

        cal_match = re.search(r'Calories:?\s*(\d+)', text, re.IGNORECASE)
        if cal_match:
            calories = int(cal_match.group(1))

        protein_match = re.search(r'Protein:?\s*([\d.]+)', text, re.IGNORECASE)
        if protein_match:
            protein = float(protein_match.group(1))

        carbs_match = re.search(r'Carbs:?\s*([\d.]+)', text, re.IGNORECASE)
        if carbs_match:
            carbs = float(carbs_match.group(1))

        fat_match = re.search(r'Fat:?\s*([\d.]+)', text, re.IGNORECASE)
        if fat_match:
            fat = float(fat_match.group(1))

        # Try to extract ingredients (look for lists)
        ingredients = []
        found_ingredients_list = None
        for ul in soup.find_all(['ul', 'ol']):
            # Check if this looks like an ingredient list
            parent_text = ul.parent.get_text().lower() if ul.parent else ''
            list_text = ul.get_text().lower()

            if ('ingredient' in parent_text or 'ingredient' in list_text) and len(ul.find_all('li')) > 2:
                found_ingredients_list = ul
                for li in ul.find_all('li'):
                    ing_text = li.get_text().strip()
                    if ing_text:
                        parsed = self._parse_ingredient(ing_text)
                        if parsed:
                            ingredients.append(parsed)
                break

        # Try to extract instructions (look for ordered lists or numbered steps)
        instructions = []
        for ol in soup.find_all(['ol', 'ul']):
            # Skip the ingredients list
            if ol == found_ingredients_list:
                continue

            # Check if this looks like instructions
            parent_text = ol.parent.get_text().lower() if ol.parent else ''
            list_items = ol.find_all('li')

            if ('direction' in parent_text or 'instruction' in parent_text or 'step' in parent_text) and len(list_items) > 1:
                for li in list_items:
                    step_text = li.get_text().strip()
                    if step_text and len(step_text) > 10:  # Filter out short non-instructional text
                        instructions.append(step_text)
                break

        # If no instructions found in lists, try to find numbered paragraphs
        if not instructions:
            paragraphs = soup.find_all('p')
            for p in paragraphs:
                text = p.get_text().strip()
                # Look for patterns like "1. " or "Step 1:" at the start
                if re.match(r'^(\d+\.|Step \d+:)', text):
                    instructions.append(text)

        return ParsedRecipe(
            name=name,
            servings=servings,
            prep_time_minutes=prep_time,
            cook_time_minutes=cook_time,
            calories_per_serving=calories,
            protein_per_serving=protein,
            carbs_per_serving=carbs,
            fat_per_serving=fat,
            tags=[],
            ingredients=ingredients,
            instructions=instructions
        )


def generate_recipe_id(name: str, existing_ids: set[str]) -> str:
    """Generate unique slugified ID from recipe name."""
    # Convert to lowercase and replace spaces/special chars with hyphens
    slug = re.sub(r'[^\w\s-]', '', name.lower())
    slug = re.sub(r'[-\s]+', '-', slug).strip('-')

    # Ensure uniqueness
    if slug not in existing_ids:
        return slug

    # Add number suffix if conflict
    counter = 2
    while f"{slug}-{counter}" in existing_ids:
        counter += 1
    return f"{slug}-{counter}"
