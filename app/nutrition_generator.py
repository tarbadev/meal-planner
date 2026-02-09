"""Automatic nutrition generation from ingredients using USDA FoodData Central API."""

import re
from dataclasses import dataclass

import requests


@dataclass
class NutritionData:
    """Represents nutrition information with all 15 fields."""
    # Core macronutrients
    calories: float
    protein: float
    carbs: float
    fat: float
    # Extended nutrients
    saturated_fat: float | None = None
    polyunsaturated_fat: float | None = None
    monounsaturated_fat: float | None = None
    sodium: float | None = None
    potassium: float | None = None
    fiber: float | None = None
    sugar: float | None = None
    vitamin_a: float | None = None
    vitamin_c: float | None = None
    calcium: float | None = None
    iron: float | None = None
    # Metadata
    confidence: float = 1.0  # 0.0 to 1.0


@dataclass
class IngredientNutrition:
    """Nutrition for a single ingredient."""
    item: str
    nutrition: NutritionData | None
    matched_food: str | None  # USDA food description
    confidence: float


class UnitConverter:
    """Convert various units to grams."""

    # Weight conversions (to grams)
    WEIGHT_TO_GRAMS = {
        'g': 1.0,
        'gram': 1.0,
        'grams': 1.0,
        'kg': 1000.0,
        'kilogram': 1000.0,
        'oz': 28.35,
        'ounce': 28.35,
        'ounces': 28.35,
        'lb': 453.592,
        'pound': 453.592,
        'pounds': 453.592,
    }

    # Volume to weight (assumes water density for liquids)
    # For specific ingredients, use ingredient-specific densities
    VOLUME_TO_ML = {
        'ml': 1.0,
        'milliliter': 1.0,
        'l': 1000.0,
        'liter': 1000.0,
        'cup': 236.588,
        'cups': 236.588,
        'tbsp': 14.787,
        'tablespoon': 14.787,
        'tsp': 4.929,
        'teaspoon': 4.929,
        'fl oz': 29.574,
    }

    # Ingredient-specific densities (grams per cup)
    INGREDIENT_DENSITIES = {
        'flour': 120,
        'all-purpose flour': 120,
        'bread flour': 127,
        'sugar': 200,
        'brown sugar': 220,
        'butter': 227,
        'oil': 218,
        'olive oil': 216,
        'milk': 244,
        'water': 237,
        'rice': 185,
        'oats': 90,
        'honey': 340,
    }

    # Count to weight (average weights in grams)
    COUNT_TO_GRAMS = {
        'egg': 50,
        'eggs': 50,
        'clove': 3,  # garlic clove
        'cloves': 3,
        'whole': 150,  # generic whole item (onion, potato)
        'piece': 100,
        'pieces': 100,
    }

    def convert_to_grams(self, quantity: float, unit: str, item: str = '') -> float | None:
        """Convert ingredient quantity to grams.

        Args:
            quantity: Amount of ingredient
            unit: Unit of measurement
            item: Ingredient name (for specific conversions)

        Returns:
            Weight in grams, or None if conversion not possible
        """
        unit_lower = unit.lower().strip()
        item_lower = item.lower().strip()

        # Direct weight conversion
        if unit_lower in self.WEIGHT_TO_GRAMS:
            return quantity * self.WEIGHT_TO_GRAMS[unit_lower]

        # Count conversion
        if unit_lower in self.COUNT_TO_GRAMS:
            return quantity * self.COUNT_TO_GRAMS[unit_lower]

        # Volume conversion (requires density lookup)
        if unit_lower in self.VOLUME_TO_ML:
            ml = quantity * self.VOLUME_TO_ML[unit_lower]

            # Try ingredient-specific density
            for key, density_per_cup in self.INGREDIENT_DENSITIES.items():
                if key in item_lower:
                    # Convert density to grams per ml
                    grams_per_ml = density_per_cup / 236.588
                    return ml * grams_per_ml

            # Default: assume water density (1g/ml for liquids)
            return ml

        # Default: assume "pieces" or "serving" units
        if unit_lower in ['serving', 'servings', '']:
            return 100  # Assume 100g per serving

        return None


class USDAFoodDataClient:
    """Client for USDA FoodData Central API."""

    BASE_URL = 'https://api.nal.usda.gov/fdc/v1'

    def __init__(self, api_key: str | None = None):
        """Initialize USDA API client.

        Args:
            api_key: Optional USDA FoodData Central API key.
                     Get a free key at: https://fdc.nal.usda.gov/api-key-signup.html
        """
        self.session = requests.Session()
        self.api_key = api_key

    def search_foods(self, query: str, page_size: int = 5) -> list[dict]:
        """Search for foods in USDA database.

        Args:
            query: Search term (e.g., "ground beef")
            page_size: Number of results to return

        Returns:
            List of food items with fdcId, description, score
        """
        try:
            params = {
                'query': query,
                'pageSize': page_size,
                'dataType': ['SR Legacy', 'Foundation']  # Prefer high-quality data
            }

            # Add API key if available
            if self.api_key:
                params['api_key'] = self.api_key

            response = self.session.get(
                f'{self.BASE_URL}/foods/search',
                params=params,
                timeout=10
            )
            response.raise_for_status()
            data = response.json()
            return data.get('foods', [])
        except requests.RequestException as e:
            print(f"USDA API search error: {e}")
            return []

    def get_food_details(self, fdc_id: int) -> dict | None:
        """Get detailed nutrition for a specific food.

        Args:
            fdc_id: USDA FoodData Central ID

        Returns:
            Food details with nutrition data, or None if error
        """
        try:
            params = {}
            # Add API key if available
            if self.api_key:
                params['api_key'] = self.api_key

            response = self.session.get(
                f'{self.BASE_URL}/foods/{fdc_id}',
                params=params if params else None,
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"USDA API details error: {e}")
            return None

    def extract_nutrition(self, food_data: dict) -> NutritionData | None:
        """Extract nutrition from USDA food data.

        All values are per 100g.

        Args:
            food_data: Food details from get_food_details()

        Returns:
            NutritionData with values per 100g (all 15 fields)
        """
        nutrients = food_data.get('foodNutrients', [])

        # Map nutrient IDs to values
        nutrient_map = {}
        for nutrient_obj in nutrients:
            nutrient = nutrient_obj.get('nutrient', {})
            nutrient_id = nutrient.get('id')
            amount = nutrient_obj.get('amount', 0)
            nutrient_map[nutrient_id] = amount

        # Extract all nutrients (nutrient IDs from USDA FoodData Central)
        # Core macronutrients
        # 1008 = Energy (kcal)
        # 1003 = Protein (g)
        # 1005 = Carbohydrate (g)
        # 1004 = Total lipid/fat (g)
        calories = nutrient_map.get(1008, 0)
        protein = nutrient_map.get(1003, 0)
        carbs = nutrient_map.get(1005, 0)
        fat = nutrient_map.get(1004, 0)

        # Extended nutrients
        # 1258 = Saturated fatty acids (g)
        # 1257 = Polyunsaturated fatty acids (g)
        # 1292 = Monounsaturated fatty acids (g)
        # 1093 = Sodium (mg)
        # 1092 = Potassium (mg)
        # 1079 = Fiber (g)
        # 2000 = Total sugars (g)
        # 1106 = Vitamin A (IU)
        # 1162 = Vitamin C (mg)
        # 1087 = Calcium (mg)
        # 1089 = Iron (mg)
        saturated_fat = nutrient_map.get(1258)
        polyunsaturated_fat = nutrient_map.get(1257)
        monounsaturated_fat = nutrient_map.get(1292)
        sodium = nutrient_map.get(1093)
        potassium = nutrient_map.get(1092)
        fiber = nutrient_map.get(1079)
        sugar = nutrient_map.get(2000)
        vitamin_a = nutrient_map.get(1106)
        vitamin_c = nutrient_map.get(1162)
        calcium = nutrient_map.get(1087)
        iron = nutrient_map.get(1089)

        # If no nutrition data found, return None
        if all(v == 0 for v in [calories, protein, carbs, fat]):
            return None

        return NutritionData(
            calories=float(calories),
            protein=float(protein),
            carbs=float(carbs),
            fat=float(fat),
            saturated_fat=float(saturated_fat) if saturated_fat else None,
            polyunsaturated_fat=float(polyunsaturated_fat) if polyunsaturated_fat else None,
            monounsaturated_fat=float(monounsaturated_fat) if monounsaturated_fat else None,
            sodium=float(sodium) if sodium else None,
            potassium=float(potassium) if potassium else None,
            fiber=float(fiber) if fiber else None,
            sugar=float(sugar) if sugar else None,
            vitamin_a=float(vitamin_a) if vitamin_a else None,
            vitamin_c=float(vitamin_c) if vitamin_c else None,
            calcium=float(calcium) if calcium else None,
            iron=float(iron) if iron else None,
            confidence=1.0  # High confidence from USDA
        )


class NutritionGenerator:
    """Generate nutrition data from ingredient list."""

    def __init__(self, api_key: str | None = None):
        """Initialize nutrition generator.

        Args:
            api_key: Optional USDA FoodData Central API key.
        """
        self.usda_client = USDAFoodDataClient(api_key=api_key)
        self.unit_converter = UnitConverter()

    def should_generate_nutrition(self, parsed_recipe) -> bool:
        """Check if nutrition should be generated.

        Generate if all nutrition values are zero or None.
        """
        return (
            not parsed_recipe.calories_per_serving or
            parsed_recipe.calories_per_serving == 0
        ) and (
            not parsed_recipe.protein_per_serving or
            parsed_recipe.protein_per_serving == 0.0
        )

    def generate_from_ingredients(
        self,
        ingredients: list[dict],
        servings: int
    ) -> NutritionData | None:
        """Generate nutrition data from ingredient list.

        Args:
            ingredients: List of ingredient dicts with item, quantity, unit
            servings: Number of servings in recipe

        Returns:
            NutritionData per serving, or None if generation fails
        """
        if not ingredients or servings <= 0:
            return None

        # Calculate nutrition for each ingredient
        ingredient_nutritions: list[IngredientNutrition] = []

        for ingredient in ingredients:
            ing_nutrition = self._calculate_ingredient_nutrition(ingredient)
            if ing_nutrition:
                ingredient_nutritions.append(ing_nutrition)

        # If we couldn't match any ingredients, fail
        if not ingredient_nutritions:
            return None

        # Sum all nutrition fields across ingredients
        total_calories = sum(ing.nutrition.calories for ing in ingredient_nutritions if ing.nutrition)
        total_protein = sum(ing.nutrition.protein for ing in ingredient_nutritions if ing.nutrition)
        total_carbs = sum(ing.nutrition.carbs for ing in ingredient_nutritions if ing.nutrition)
        total_fat = sum(ing.nutrition.fat for ing in ingredient_nutritions if ing.nutrition)

        # Sum extended nutrients (handle None values)
        def safe_sum(field_name):
            """Sum a field across all ingredient nutritions, skipping None values."""
            values = [getattr(ing.nutrition, field_name) for ing in ingredient_nutritions
                     if ing.nutrition and getattr(ing.nutrition, field_name) is not None]
            return sum(values) if values else None

        total_saturated_fat = safe_sum('saturated_fat')
        total_polyunsaturated_fat = safe_sum('polyunsaturated_fat')
        total_monounsaturated_fat = safe_sum('monounsaturated_fat')
        total_sodium = safe_sum('sodium')
        total_potassium = safe_sum('potassium')
        total_fiber = safe_sum('fiber')
        total_sugar = safe_sum('sugar')
        total_vitamin_a = safe_sum('vitamin_a')
        total_vitamin_c = safe_sum('vitamin_c')
        total_calcium = safe_sum('calcium')
        total_iron = safe_sum('iron')

        # Calculate average confidence
        confidences = [ing.confidence for ing in ingredient_nutritions]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0

        # Divide by servings to get per-serving nutrition
        return NutritionData(
            calories=round(total_calories / servings),
            protein=round(total_protein / servings, 1),
            carbs=round(total_carbs / servings, 1),
            fat=round(total_fat / servings, 1),
            saturated_fat=round(total_saturated_fat / servings, 1) if total_saturated_fat else None,
            polyunsaturated_fat=round(total_polyunsaturated_fat / servings, 1) if total_polyunsaturated_fat else None,
            monounsaturated_fat=round(total_monounsaturated_fat / servings, 1) if total_monounsaturated_fat else None,
            sodium=round(total_sodium / servings, 1) if total_sodium else None,
            potassium=round(total_potassium / servings, 1) if total_potassium else None,
            fiber=round(total_fiber / servings, 1) if total_fiber else None,
            sugar=round(total_sugar / servings, 1) if total_sugar else None,
            vitamin_a=round(total_vitamin_a / servings, 1) if total_vitamin_a else None,
            vitamin_c=round(total_vitamin_c / servings, 1) if total_vitamin_c else None,
            calcium=round(total_calcium / servings, 1) if total_calcium else None,
            iron=round(total_iron / servings, 1) if total_iron else None,
            confidence=avg_confidence
        )

    def _calculate_ingredient_nutrition(self, ingredient: dict) -> IngredientNutrition | None:
        """Calculate nutrition for a single ingredient.

        Args:
            ingredient: Dict with item, quantity, unit

        Returns:
            IngredientNutrition with nutrition data, or None if not found
        """
        item = ingredient.get('item', '')
        quantity = ingredient.get('quantity', 0)
        unit = ingredient.get('unit', '')

        # Skip negligible quantities
        if quantity <= 0:
            return None

        # Clean ingredient name for search
        clean_item = self._clean_ingredient_name(item)

        # Convert to grams
        grams = self.unit_converter.convert_to_grams(quantity, unit, clean_item)
        if grams is None or grams <= 0:
            return IngredientNutrition(
                item=item,
                nutrition=None,
                matched_food=None,
                confidence=0
            )

        # Skip ingredients with negligible nutrition impact
        if grams < 5:  # Less than 5g (e.g., spices, "to taste")
            return None

        # Search USDA database
        search_results = self.usda_client.search_foods(clean_item)
        if not search_results:
            return IngredientNutrition(
                item=item,
                nutrition=None,
                matched_food=None,
                confidence=0
            )

        # Take best match (highest score)
        best_match = search_results[0]
        fdc_id = best_match['fdcId']
        matched_description = best_match['description']
        match_score = best_match.get('score', 0.5)

        # Get detailed nutrition
        food_details = self.usda_client.get_food_details(fdc_id)
        if not food_details:
            return IngredientNutrition(
                item=item,
                nutrition=None,
                matched_food=matched_description,
                confidence=0
            )

        # Extract nutrition per 100g
        nutrition_per_100g = self.usda_client.extract_nutrition(food_details)
        if not nutrition_per_100g:
            return IngredientNutrition(
                item=item,
                nutrition=None,
                matched_food=matched_description,
                confidence=0
            )

        # Scale nutrition to ingredient quantity
        scale_factor = grams / 100.0

        def scale_value(val):
            """Scale a value if it's not None."""
            return val * scale_factor if val is not None else None

        scaled_nutrition = NutritionData(
            calories=nutrition_per_100g.calories * scale_factor,
            protein=nutrition_per_100g.protein * scale_factor,
            carbs=nutrition_per_100g.carbs * scale_factor,
            fat=nutrition_per_100g.fat * scale_factor,
            saturated_fat=scale_value(nutrition_per_100g.saturated_fat),
            polyunsaturated_fat=scale_value(nutrition_per_100g.polyunsaturated_fat),
            monounsaturated_fat=scale_value(nutrition_per_100g.monounsaturated_fat),
            sodium=scale_value(nutrition_per_100g.sodium),
            potassium=scale_value(nutrition_per_100g.potassium),
            fiber=scale_value(nutrition_per_100g.fiber),
            sugar=scale_value(nutrition_per_100g.sugar),
            vitamin_a=scale_value(nutrition_per_100g.vitamin_a),
            vitamin_c=scale_value(nutrition_per_100g.vitamin_c),
            calcium=scale_value(nutrition_per_100g.calcium),
            iron=scale_value(nutrition_per_100g.iron),
            confidence=match_score
        )

        return IngredientNutrition(
            item=item,
            nutrition=scaled_nutrition,
            matched_food=matched_description,
            confidence=match_score
        )

    def _clean_ingredient_name(self, item: str) -> str:
        """Clean ingredient name for USDA search.

        Removes descriptors and preparation methods.

        Args:
            item: Raw ingredient name

        Returns:
            Cleaned name suitable for search
        """
        # Remove common descriptors and preparations
        descriptors = [
            'fresh', 'frozen', 'dried', 'canned', 'raw', 'cooked',
            'chopped', 'diced', 'minced', 'sliced', 'shredded', 'grated',
            'large', 'medium', 'small', 'extra',
            'to taste', 'optional', 'if desired',
            'boneless', 'skinless', 'trimmed',
        ]

        cleaned = item.lower()

        # Remove descriptors
        for descriptor in descriptors:
            cleaned = re.sub(rf'\b{descriptor}\b', '', cleaned)

        # Remove parenthetical notes
        cleaned = re.sub(r'\([^)]*\)', '', cleaned)

        # Remove extra whitespace
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()

        return cleaned
