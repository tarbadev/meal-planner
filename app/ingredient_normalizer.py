"""
Post-processing to normalize AI-extracted ingredients (bilingual support).

Standardizes units, handles fractions, and infers categories for ingredients.
"""

from typing import Any

# Bilingual unit mapping (English and French)
UNIT_MAPPING = {
    # Volume - English
    'cup': 'cup', 'cups': 'cup', 'c': 'cup', 'c.': 'cup',
    'tablespoon': 'tbsp', 'tablespoons': 'tbsp', 'tbsp': 'tbsp', 'tbs': 'tbsp', 'T': 'tbsp',
    'teaspoon': 'tsp', 'teaspoons': 'tsp', 'tsp': 'tsp', 't': 'tsp',
    'fluid ounce': 'fl oz', 'fluid ounces': 'fl oz', 'fl oz': 'fl oz', 'fl. oz.': 'fl oz',
    'pint': 'pint', 'pints': 'pint', 'pt': 'pint',
    'quart': 'quart', 'quarts': 'quart', 'qt': 'quart',
    'gallon': 'gallon', 'gallons': 'gallon', 'gal': 'gallon',
    'milliliter': 'ml', 'milliliters': 'ml', 'ml': 'ml', 'mL': 'ml',
    'liter': 'L', 'liters': 'L', 'l': 'L', 'L': 'L',
    'deciliter': 'dl', 'deciliters': 'dl', 'dl': 'dl', 'dL': 'dl',

    # Volume - French
    'tasse': 'cup', 'tasses': 'cup',
    'cuillère à soupe': 'tbsp', 'cuillères à soupe': 'tbsp', 'c. à soupe': 'tbsp', 'càs': 'tbsp',
    'cuillère à café': 'tsp', 'cuillères à café': 'tsp', 'c. à café': 'tsp', 'càc': 'tsp',
    'cuillère à thé': 'tsp', 'cuillères à thé': 'tsp', 'c. à thé': 'tsp',
    'millilitre': 'ml', 'millilitres': 'ml',
    'litre': 'L', 'litres': 'L',
    'décilitre': 'dl', 'décilitres': 'dl',

    # Weight - English
    'gram': 'g', 'grams': 'g', 'g': 'g', 'gr': 'g',
    'kilogram': 'kg', 'kilograms': 'kg', 'kg': 'kg', 'kilo': 'kg', 'kilos': 'kg',
    'ounce': 'oz', 'ounces': 'oz', 'oz': 'oz', 'oz.': 'oz',
    'pound': 'lb', 'pounds': 'lb', 'lb': 'lb', 'lbs': 'lb',

    # Weight - French
    'gramme': 'g', 'grammes': 'g',
    'kilogramme': 'kg', 'kilogrammes': 'kg',

    # Count/Whole
    'piece': 'whole', 'pieces': 'whole', 'whole': 'whole',
    'item': 'whole', 'items': 'whole',
    'unit': 'whole', 'units': 'whole',

    # Count - French
    'pièce': 'whole', 'pièces': 'whole',
    'unité': 'whole', 'unités': 'whole',

    # Special units
    'slice': 'slice', 'slices': 'slice',
    'clove': 'clove', 'cloves': 'clove',
    'bunch': 'bunch', 'bunches': 'bunch',
    'can': 'can', 'cans': 'can',
    'package': 'package', 'packages': 'package', 'pkg': 'package',
    'pinch': 'pinch', 'pinches': 'pinch',
    'dash': 'dash', 'dashes': 'dash',
    'to taste': 'to taste',

    # Special units - French
    'tranche': 'slice', 'tranches': 'slice',
    'gousse': 'clove', 'gousses': 'clove',
    'botte': 'bunch', 'bottes': 'bunch',
    'boîte': 'can', 'boîtes': 'can',
    'paquet': 'package', 'paquets': 'package',
    'pincée': 'pinch', 'pincées': 'pinch',
    'au goût': 'to taste',
}

# Category keywords for ingredient classification
CATEGORY_KEYWORDS = {
    'meat': [
        'chicken', 'beef', 'pork', 'lamb', 'turkey', 'duck', 'veal', 'sausage',
        'bacon', 'ham', 'prosciutto', 'salami', 'pepperoni', 'ground beef',
        'ground pork', 'ground turkey', 'steak', 'chop', 'tenderloin', 'breast',
        'thigh', 'wing', 'ribs', 'brisket', 'pancetta', 'chorizo',
        # French
        'poulet', 'bœuf', 'porc', 'agneau', 'dinde', 'canard', 'veau',
        'saucisse', 'lard', 'jambon', 'viande', 'côtelette', 'filet',
    ],
    'seafood': [
        'fish', 'salmon', 'tuna', 'cod', 'tilapia', 'halibut', 'trout', 'bass',
        'shrimp', 'prawns', 'crab', 'lobster', 'scallops', 'clams', 'mussels',
        'oysters', 'squid', 'octopus', 'anchovies', 'sardines',
        # French
        'poisson', 'saumon', 'thon', 'morue', 'truite', 'crevette', 'crevettes',
        'crabe', 'homard', 'pétoncles', 'moules', 'huîtres', 'calamar',
    ],
    'produce': [
        'tomato', 'onion', 'garlic', 'carrot', 'celery', 'potato', 'pepper',
        'bell pepper', 'jalapeño', 'chili', 'cucumber', 'lettuce', 'spinach',
        'kale', 'cabbage', 'broccoli', 'cauliflower', 'zucchini', 'eggplant',
        'mushroom', 'corn', 'peas', 'green beans', 'asparagus', 'artichoke',
        'avocado', 'apple', 'banana', 'orange', 'lemon', 'lime', 'strawberry',
        'blueberry', 'raspberry', 'mango', 'pineapple', 'peach', 'pear',
        'cherry', 'grape', 'watermelon', 'melon', 'ginger', 'herb', 'parsley',
        'cilantro', 'basil', 'thyme', 'rosemary', 'oregano', 'mint', 'dill',
        # French
        'tomate', 'oignon', 'ail', 'carotte', 'céleri', 'pomme de terre',
        'poivron', 'concombre', 'laitue', 'épinards', 'chou', 'brocoli',
        'courgette', 'aubergine', 'champignon', 'maïs', 'petits pois',
        'asperge', 'avocat', 'pomme', 'banane', 'citron', 'fraise', 'mangue',
        'ananas', 'pêche', 'poire', 'cerise', 'raisin', 'melon', 'gingembre',
        'persil', 'basilic', 'thym', 'romarin', 'origan', 'menthe',
    ],
    'dairy': [
        'milk', 'cream', 'heavy cream', 'sour cream', 'half and half',
        'butter', 'cheese', 'cheddar', 'mozzarella', 'parmesan', 'feta',
        'ricotta', 'cream cheese', 'cottage cheese', 'goat cheese', 'brie',
        'swiss', 'provolone', 'gouda', 'yogurt', 'greek yogurt', 'egg', 'eggs',
        # French
        'lait', 'crème', 'crème fraîche', 'beurre', 'fromage', 'parmesan',
        'mozzarella', 'feta', 'ricotta', 'chèvre', 'gruyère', 'yaourt', 'œuf', 'œufs',
    ],
    'grains': [
        'pasta', 'spaghetti', 'penne', 'rigatoni', 'fettuccine', 'linguine',
        'macaroni', 'noodles', 'rice', 'basmati', 'jasmine', 'arborio', 'wild rice',
        'quinoa', 'couscous', 'bulgur', 'barley', 'oats', 'bread', 'baguette',
        'roll', 'tortilla', 'pita', 'naan', 'flour', 'cornmeal', 'breadcrumbs',
        # French
        'pâtes', 'spaghetti', 'riz', 'quinoa', 'couscous', 'boulgour',
        'avoine', 'pain', 'farine', 'chapelure',
    ],
    'spices': [
        'salt', 'pepper', 'black pepper', 'white pepper', 'cayenne', 'paprika',
        'cumin', 'coriander', 'turmeric', 'cinnamon', 'nutmeg', 'cloves',
        'cardamom', 'bay leaf', 'chili powder', 'curry powder', 'garam masala',
        'italian seasoning', 'herbs de provence', 'vanilla', 'extract',
        # French
        'sel', 'poivre', 'poivre noir', 'paprika', 'cumin', 'coriandre',
        'curcuma', 'cannelle', 'muscade', 'clou de girofle', 'feuille de laurier',
        'vanille', 'extrait',
    ],
    'pantry': [
        'oil', 'olive oil', 'vegetable oil', 'coconut oil', 'sesame oil',
        'vinegar', 'balsamic', 'wine vinegar', 'apple cider vinegar',
        'soy sauce', 'fish sauce', 'worcestershire', 'hot sauce', 'sriracha',
        'ketchup', 'mustard', 'mayo', 'mayonnaise', 'honey', 'maple syrup',
        'sugar', 'brown sugar', 'powdered sugar', 'molasses', 'jam', 'jelly',
        'peanut butter', 'tahini', 'stock', 'broth', 'bouillon', 'tomato paste',
        'tomato sauce', 'coconut milk', 'condensed milk', 'evaporated milk',
        'beans', 'chickpeas', 'lentils', 'kidney beans', 'black beans',
        'white beans', 'pinto beans', 'nuts', 'almonds', 'walnuts', 'pecans',
        'cashews', 'peanuts', 'pine nuts', 'seeds', 'sesame seeds', 'pumpkin seeds',
        # French
        'huile', "huile d'olive", 'vinaigre', 'vinaigre balsamique', 'sauce soja',
        'miel', 'sirop', "sirop d'érable", 'sucre', 'sucre brun', 'confiture',
        'beurre de cacahuète', 'bouillon', 'lait de coco', 'haricots',
        'pois chiches', 'lentilles', 'noix', 'amandes', 'noix de cajou',
        'graines', 'graines de sésame',
    ],
}


def normalize_ingredient(ai_ingredient: dict[str, Any]) -> dict[str, Any]:
    """
    Normalize AI-extracted ingredient.

    Args:
        ai_ingredient: Raw ingredient from AI ({"item": str, "quantity": float, "unit": str, "category": str})

    Returns:
        Normalized ingredient dict
    """
    normalized = ai_ingredient.copy()

    # Standardize unit
    if 'unit' in normalized and normalized['unit']:
        normalized['unit'] = standardize_unit(normalized['unit'])

    # Infer category if missing or set to "other"
    if not normalized.get('category') or normalized['category'] == 'other':
        item = normalized.get('item', '').lower()
        normalized['category'] = infer_category(item)

    # Handle quantity: ensure it's a number or None
    if 'quantity' in normalized:
        try:
            if normalized['quantity'] is not None:
                normalized['quantity'] = float(normalized['quantity'])
        except (ValueError, TypeError):
            normalized['quantity'] = None

    return normalized


def standardize_unit(unit: str) -> str:
    """
    Standardize unit across English and French.

    Args:
        unit: Raw unit string

    Returns:
        Standardized unit
    """
    if not unit:
        return 'whole'

    # Normalize: lowercase, strip whitespace
    unit_lower = unit.lower().strip()

    # Direct mapping
    if unit_lower in UNIT_MAPPING:
        return UNIT_MAPPING[unit_lower]

    # Handle plural forms not in mapping
    if unit_lower.endswith('s') and unit_lower[:-1] in UNIT_MAPPING:
        return UNIT_MAPPING[unit_lower[:-1]]

    # Return as-is if no mapping found
    return unit


def infer_category(item: str) -> str:
    """
    Infer ingredient category from item name.

    Args:
        item: Ingredient name

    Returns:
        Category: 'meat', 'seafood', 'produce', 'dairy', 'grains', 'spices', 'pantry', or 'other'
    """
    if not item:
        return 'other'

    item_lower = item.lower()

    # Check each category
    for category, keywords in CATEGORY_KEYWORDS.items():
        for keyword in keywords:
            if keyword in item_lower:
                return category

    # Default to other if no match
    return 'other'
