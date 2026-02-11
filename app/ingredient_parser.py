"""Advanced ingredient parsing with quantity extraction, categorization, and notes separation."""

import re
from dataclasses import dataclass


@dataclass
class ParsedIngredient:
    """Structured ingredient data."""
    item: str
    quantity: float
    unit: str
    category: str
    notes: str | None = None  # Preparation details like "melted and cooled"


class IngredientParser:
    """Parse ingredient strings into structured format."""

    # Weight units (preferred)
    WEIGHT_UNITS = {
        'g', 'gram', 'grams', 'kg', 'kilogram', 'kilograms',
        'oz', 'ounce', 'ounces', 'lb', 'lbs', 'pound', 'pounds'
    }

    # Volume units
    VOLUME_UNITS = {
        'cup', 'cups', 'c',
        'tbsp', 'tablespoon', 'tablespoons', 'tbs', 'T',
        'tsp', 'teaspoon', 'teaspoons',
        'ml', 'milliliter', 'milliliters',
        'l', 'liter', 'liters',
        'fl oz', 'fluid ounce', 'fluid ounces',
        'pint', 'pints', 'pt',
        'quart', 'quarts', 'qt',
        'gallon', 'gallons', 'gal'
    }

    # Count units
    COUNT_UNITS = {
        'whole', 'piece', 'pieces', 'clove', 'cloves',
        'slice', 'slices', 'can', 'cans', 'package', 'packages',
        'bunch', 'bunches', 'head', 'heads', 'stalk', 'stalks'
    }

    # Ingredient categorization
    INGREDIENT_CATEGORIES = {
        'meat': [
            'beef', 'chicken', 'pork', 'turkey', 'lamb', 'veal', 'duck',
            'bacon', 'sausage', 'ham', 'steak', 'ground beef', 'ground turkey',
            'ground chicken', 'ground pork', 'meatball', 'meat'
        ],
        'produce': [
            'onion', 'garlic', 'tomato', 'potato', 'carrot', 'celery',
            'pepper', 'bell pepper', 'broccoli', 'spinach', 'lettuce',
            'cucumber', 'zucchini', 'mushroom', 'corn', 'peas',
            'green bean', 'cabbage', 'kale', 'apple', 'banana',
            'lemon', 'lime', 'orange', 'berry', 'strawberry', 'blueberry',
            'avocado', 'ginger', 'parsley', 'cilantro', 'basil',
            'thyme', 'rosemary', 'dill', 'mint', 'scallion', 'shallot',
            'leek', 'eggplant', 'squash', 'pumpkin', 'beet', 'radish',
            'turnip', 'parsnip', 'asparagus', 'artichoke', 'brussels sprout',
            'cauliflower', 'chard', 'arugula', 'watercress', 'endive',
            'radicchio', 'fennel', 'okra', 'bok choy'
        ],
        'dairy': [
            'milk', 'cream', 'butter', 'cheese', 'yogurt', 'sour cream',
            'cream cheese', 'cottage cheese', 'ricotta', 'mozzarella',
            'parmesan', 'cheddar', 'feta', 'goat cheese', 'swiss',
            'provolone', 'brie', 'blue cheese', 'mascarpone', 'whipped cream',
            'half and half', 'heavy cream', 'whipping cream', 'buttermilk',
            'egg', 'eggs', 'egg white', 'egg yolk'
        ],
        'grains': [
            'flour', 'bread', 'pasta', 'rice', 'oat', 'quinoa', 'barley',
            'couscous', 'bulgur', 'farro', 'wheat', 'cornmeal', 'polenta',
            'noodle', 'spaghetti', 'penne', 'tortilla', 'pita', 'bagel',
            'roll', 'bun', 'cracker', 'breadcrumb', 'cereal', 'granola',
            'cornstarch', 'corn starch'
        ],
        'pantry': [
            'oil', 'olive oil', 'vegetable oil', 'coconut oil', 'canola oil',
            'vinegar', 'balsamic', 'soy sauce', 'worcestershire',
            'hot sauce', 'ketchup', 'mustard', 'mayonnaise', 'mayo',
            'honey', 'maple syrup', 'syrup', 'molasses', 'agave',
            'sugar', 'brown sugar', 'powdered sugar', 'confectioner',
            'salt', 'pepper', 'black pepper', 'sea salt', 'kosher salt',
            'stock', 'broth', 'bouillon', 'tomato paste', 'tomato sauce',
            'salsa', 'beans', 'chickpea', 'lentil', 'kidney bean',
            'black bean', 'pinto bean', 'white bean', 'cannellini',
            'peanut butter', 'almond butter', 'tahini', 'nut', 'nuts',
            'almond', 'walnut', 'pecan', 'cashew', 'pistachio', 'pine nut',
            'peanut', 'hazelnut', 'macadamia', 'seed', 'sesame', 'sunflower',
            'pumpkin seed', 'chia', 'flax', 'coconut', 'vanilla extract',
            'vanilla', 'almond extract', 'baking powder', 'baking soda',
            'yeast', 'gelatin', 'cocoa', 'chocolate', 'chocolate chip',
            'raisin', 'dried fruit', 'date', 'fig', 'cranberry'
        ],
        'spices': [
            'cumin', 'paprika', 'chili powder', 'cayenne', 'turmeric',
            'coriander', 'cinnamon', 'nutmeg', 'clove', 'cardamom',
            'allspice', 'ginger', 'garlic powder', 'onion powder',
            'oregano', 'basil', 'thyme', 'rosemary', 'sage', 'bay leaf',
            'dill', 'tarragon', 'marjoram', 'curry', 'garam masala',
            'italian seasoning', 'herbes de provence', 'five spice',
            'red pepper flake', 'crushed red pepper', 'sesame seed',
            'poppy seed', 'mustard seed', 'celery seed', 'fennel seed',
            'caraway', 'anise', 'saffron', 'vanilla bean', 'peppercorn'
        ]
    }

    # Common preparation words to separate from ingredient name
    PREPARATION_WORDS = [
        'chopped', 'diced', 'minced', 'sliced', 'shredded', 'grated',
        'melted', 'softened', 'cooled', 'room temperature', 'cold',
        'frozen', 'thawed', 'cooked', 'boiled', 'roasted', 'toasted',
        'crushed', 'ground', 'fresh', 'dried', 'canned', 'peeled',
        'seeded', 'deveined', 'boneless', 'skinless', 'trimmed',
        'halved', 'quartered', 'cubed', 'julienned', 'blanched',
        'sifted', 'beaten', 'whisked', 'at room temperature',
        'plus more', 'or more', 'season to taste', 'to taste', 'optional', 'for serving',
        'for garnish', 'if desired', 'as needed'
    ]

    def parse(self, ingredient_str: str) -> ParsedIngredient:
        """Parse ingredient string into structured format.

        Examples:
            "all-purpose flour (1 cup | 120 g)" → 120g flour
            "unsalted butter (¼ cup | 57 g), melted" → 57g butter, notes: "melted"
            "2 large eggs, beaten" → 2 whole eggs, notes: "beaten"
        """
        ingredient_str = ingredient_str.strip()

        # Step 1: Extract all measurements (prefer weight over volume)
        measurements = self._extract_measurements(ingredient_str)

        # Step 2: Prefer weight measurements over volume
        quantity, unit = self._select_best_measurement(measurements)

        # Step 3: Extract item name and preparation notes
        item, notes = self._extract_item_and_notes(ingredient_str)

        # Step 4: Categorize ingredient
        category = self._categorize(item)

        return ParsedIngredient(
            item=item,
            quantity=quantity,
            unit=unit,
            category=category,
            notes=notes
        )

    def _extract_measurements(self, text: str) -> list[tuple[float, str]]:
        """Extract all measurements from text.

        Returns list of (quantity, unit) tuples.
        """
        measurements = []

        # Pattern: number + optional fraction + unit
        # Handles: "1 cup", "120 g", "1/4 tsp", "1 1/2 cups", "¼ cup", "1½ cups"
        patterns = [
            # Integer + unicode fraction: "1½"
            r'(\d+[¼½¾⅓⅔⅛⅜⅝⅞])\s*([a-zA-Z]+)',
            # Just unicode fraction: "¼"
            r'([¼½¾⅓⅔⅛⅜⅝⅞])\s*([a-zA-Z]+)',
            # Standard fractions: "1/4", "1 1/2"
            r'(\d+\s+\d+/\d+)\s*([a-zA-Z]+)',
            r'(\d+/\d+)\s*([a-zA-Z]+)',
            # Decimal or integer: "120 g", "1.5 cups"
            r'([\d.]+)\s*([a-zA-Z]+)',
        ]

        for pattern in patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                quantity_str, unit = match.groups()
                quantity = self._parse_quantity(quantity_str)
                if quantity and self._is_valid_unit(unit):
                    measurements.append((quantity, unit.lower()))

        return measurements

    def _parse_quantity(self, quantity_str: str) -> float | None:
        """Parse quantity string to float.

        Handles: "1", "1.5", "1/4", "1 1/2", "¼", "1½"
        """
        quantity_str = quantity_str.strip()

        # Unicode fractions
        unicode_fractions = {
            '¼': 0.25, '½': 0.5, '¾': 0.75,
            '⅓': 0.333, '⅔': 0.667,
            '⅛': 0.125, '⅜': 0.375, '⅝': 0.625, '⅞': 0.875
        }

        # Check for integer + unicode fraction: "1½"
        for frac_char, frac_value in unicode_fractions.items():
            if frac_char in quantity_str:
                # Split on the fraction character
                parts = quantity_str.split(frac_char)
                if parts[0]:  # There's a whole number before the fraction
                    try:
                        whole = float(parts[0])
                        return whole + frac_value
                    except ValueError:
                        pass
                else:  # Just the fraction
                    return frac_value

        # Just unicode fraction
        if quantity_str in unicode_fractions:
            return unicode_fractions[quantity_str]

        # Mixed number: "1 1/2"
        if ' ' in quantity_str and '/' in quantity_str:
            parts = quantity_str.split()
            whole = float(parts[0])
            frac = self._parse_quantity(parts[1])
            return whole + (frac or 0)

        # Simple fraction: "1/2"
        if '/' in quantity_str:
            try:
                num, denom = quantity_str.split('/')
                return float(num) / float(denom)
            except (ValueError, ZeroDivisionError):
                return None

        # Decimal or integer
        try:
            return float(quantity_str)
        except ValueError:
            return None

    def _is_valid_unit(self, unit: str) -> bool:
        """Check if unit is a recognized measurement unit."""
        unit_lower = unit.lower()
        return (
            unit_lower in self.WEIGHT_UNITS or
            unit_lower in self.VOLUME_UNITS or
            unit_lower in self.COUNT_UNITS
        )

    def _select_best_measurement(self, measurements: list[tuple[float, str]]) -> tuple[float, str]:
        """Select best measurement, preferring weight over volume.

        Returns (quantity, unit) tuple.
        """
        if not measurements:
            return (1.0, 'serving')

        # Separate by type
        weight_measurements = [
            (q, u) for q, u in measurements
            if u.lower() in self.WEIGHT_UNITS
        ]
        volume_measurements = [
            (q, u) for q, u in measurements
            if u.lower() in self.VOLUME_UNITS
        ]
        count_measurements = [
            (q, u) for q, u in measurements
            if u.lower() in self.COUNT_UNITS
        ]

        # Prefer weight, then volume, then count
        if weight_measurements:
            return weight_measurements[0]
        elif volume_measurements:
            return volume_measurements[0]
        elif count_measurements:
            return count_measurements[0]
        else:
            return measurements[0]

    def _extract_item_and_notes(self, text: str) -> tuple[str, str | None]:
        """Extract ingredient name and separate preparation notes.

        Examples:
            "all-purpose flour (1 cup | 120 g)" → ("all-purpose flour", None)
            "unsalted butter, melted and cooled" → ("unsalted butter", "melted and cooled")
            "2 large eggs, beaten" → ("large eggs", "beaten")
            "Tbsp. Avocado Oil" → ("Avocado Oil", None)
        """
        # Remove measurement patterns from text
        clean_text = text

        # Remove parenthetical measurements: "(1 cup | 120 g)", "(¾ tsp)", etc.
        # This regex matches parentheses containing numbers, fractions, or units
        clean_text = re.sub(r'\s*\([^)]*[\d¼½¾⅓⅔⅛⅜⅝⅞][^)]*\)', '', clean_text)

        # Remove leading measurements: "2 cups", "120 g", "1/4 tsp", "1½ tsp"
        clean_text = re.sub(r'^\s*[\d¼½¾⅓⅔⅛⅜⅝⅞./\s]+[a-zA-Z]+\.?\s+', '', clean_text)

        # Remove leading unit without number: "Tbsp. ", "Tsp. ", etc.
        all_units = list(self.WEIGHT_UNITS) + list(self.VOLUME_UNITS) + list(self.COUNT_UNITS)
        # Sort by length (longest first) to match "tablespoon" before "tbsp"
        all_units_sorted = sorted(all_units, key=len, reverse=True)
        for unit in all_units_sorted:
            # Case-insensitive match for unit at start, optionally followed by period
            pattern = rf'^\s*{re.escape(unit)}\.?\s+'
            clean_text = re.sub(pattern, '', clean_text, flags=re.IGNORECASE)
            if clean_text != text:  # If we made a change, we're done
                break

        # Remove leading quantity without unit: "2 large eggs" → "large eggs"
        clean_text = re.sub(r'^\s*\d+\s+', '', clean_text)

        # Remove leading unicode fraction without unit: "½ teaspoon" → "teaspoon"
        clean_text = re.sub(r'^\s*[¼½¾⅓⅔⅛⅜⅝⅞]\s+', '', clean_text)

        clean_text = clean_text.strip()

        # Look for comma or other separators that indicate notes
        separators = [',', '-']
        item = clean_text
        notes = None

        for sep in separators:
            if sep in clean_text:
                parts = clean_text.split(sep, 1)
                potential_item = parts[0].strip()
                potential_notes = parts[1].strip().rstrip(')')

                # Check if the second part contains preparation words
                if any(word in potential_notes.lower() for word in self.PREPARATION_WORDS):
                    item = potential_item
                    notes = potential_notes
                    break

        # If no separator found, check for preparation words without separators
        # Example: "Lawry's Seasoned Salt season to taste"
        # Sort by length (longest first) to match "season to taste" before "to taste"
        if notes is None:
            prep_words_sorted = sorted(self.PREPARATION_WORDS, key=len, reverse=True)
            for prep_word in prep_words_sorted:
                if prep_word in clean_text.lower():
                    # Find where the prep word starts
                    idx = clean_text.lower().find(prep_word)
                    if idx > 0:  # Not at the very start
                        item = clean_text[:idx].strip()
                        notes = clean_text[idx:].strip().rstrip(')')
                        break

        # Clean up item name
        item = item.strip()

        # Remove trailing "and" or "or"
        item = re.sub(r'\s+(and|or)\s*$', '', item, flags=re.IGNORECASE)

        # Remove any remaining parentheses or pipes
        item = re.sub(r'[|()]', '', item).strip()

        return (item, notes)

    def _categorize(self, item: str) -> str:
        """Categorize ingredient based on name."""
        item_lower = item.lower()

        for category, keywords in self.INGREDIENT_CATEGORIES.items():
            for keyword in keywords:
                if keyword in item_lower:
                    return category

        return 'other'

    def to_dict(self, parsed: ParsedIngredient) -> dict:
        """Convert ParsedIngredient to dict format."""
        result = {
            'item': parsed.item,
            'quantity': parsed.quantity,
            'unit': parsed.unit,
            'category': parsed.category
        }
        if parsed.notes:
            result['notes'] = parsed.notes
        return result
