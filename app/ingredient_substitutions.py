"""Ingredient substitution suggestions for meal planning flexibility."""

from typing import Optional


# Comprehensive ingredient substitution database
SUBSTITUTIONS = {
    # Dairy
    "milk": [
        {"substitute": "almond milk", "ratio": "1:1", "note": "Best for most recipes"},
        {"substitute": "soy milk", "ratio": "1:1", "note": "Higher protein content"},
        {"substitute": "oat milk", "ratio": "1:1", "note": "Creamy texture"},
        {"substitute": "coconut milk", "ratio": "1:1", "note": "Rich, tropical flavor"},
    ],
    "butter": [
        {"substitute": "coconut oil", "ratio": "1:1", "note": "For baking and cooking"},
        {"substitute": "olive oil", "ratio": "3/4 cup oil per 1 cup butter", "note": "For savory dishes"},
        {"substitute": "margarine", "ratio": "1:1", "note": "Vegan option"},
        {"substitute": "applesauce", "ratio": "1/2 cup per 1 cup butter", "note": "For baking, reduces fat"},
    ],
    "heavy cream": [
        {"substitute": "coconut cream", "ratio": "1:1", "note": "Vegan, rich texture"},
        {"substitute": "cashew cream", "ratio": "1:1", "note": "Blend cashews with water"},
        {"substitute": "milk + butter", "ratio": "1 cup milk + 2 tbsp butter", "note": "Mix together"},
    ],
    "sour cream": [
        {"substitute": "greek yogurt", "ratio": "1:1", "note": "Higher protein"},
        {"substitute": "coconut cream", "ratio": "1:1", "note": "Vegan option"},
        {"substitute": "cashew cream", "ratio": "1:1", "note": "Blend with lemon juice"},
    ],
    "cream cheese": [
        {"substitute": "greek yogurt", "ratio": "1:1", "note": "Lighter option"},
        {"substitute": "cottage cheese", "ratio": "Blend until smooth", "note": "Lower fat"},
        {"substitute": "silken tofu", "ratio": "Blend with lemon juice", "note": "Vegan option"},
    ],
    "parmesan cheese": [
        {"substitute": "pecorino romano", "ratio": "1:1", "note": "Sharper flavor"},
        {"substitute": "nutritional yeast", "ratio": "2:1", "note": "Vegan, nutty flavor"},
        {"substitute": "asiago cheese", "ratio": "1:1", "note": "Milder taste"},
    ],

    # Eggs
    "egg": [
        {"substitute": "flax egg", "ratio": "1 tbsp ground flax + 3 tbsp water per egg", "note": "Let sit 5 min"},
        {"substitute": "chia egg", "ratio": "1 tbsp chia seeds + 3 tbsp water per egg", "note": "Let sit 5 min"},
        {"substitute": "applesauce", "ratio": "1/4 cup per egg", "note": "For baking"},
        {"substitute": "banana", "ratio": "1/4 cup mashed per egg", "note": "Adds sweetness"},
        {"substitute": "silken tofu", "ratio": "1/4 cup blended per egg", "note": "For dense baked goods"},
    ],

    # Flour & Grains
    "all-purpose flour": [
        {"substitute": "whole wheat flour", "ratio": "1:1", "note": "More fiber, denser texture"},
        {"substitute": "almond flour", "ratio": "1:1", "note": "Gluten-free, add binding agent"},
        {"substitute": "oat flour", "ratio": "1:1 + 1 tsp", "note": "Gluten-free, slightly sweet"},
        {"substitute": "coconut flour", "ratio": "1/4 to 1/3 cup per 1 cup", "note": "Very absorbent, use less"},
    ],
    "bread crumbs": [
        {"substitute": "crushed crackers", "ratio": "1:1", "note": "Similar texture"},
        {"substitute": "panko", "ratio": "1:1", "note": "Lighter and crispier"},
        {"substitute": "rolled oats", "ratio": "1:1", "note": "Pulse in food processor"},
        {"substitute": "crushed cornflakes", "ratio": "1:1", "note": "Extra crispy"},
    ],
    "white rice": [
        {"substitute": "brown rice", "ratio": "1:1", "note": "More fiber, longer cook time"},
        {"substitute": "quinoa", "ratio": "1:1", "note": "Higher protein"},
        {"substitute": "cauliflower rice", "ratio": "1:1", "note": "Low-carb option"},
    ],

    # Sweeteners
    "sugar": [
        {"substitute": "honey", "ratio": "3/4 cup per 1 cup sugar", "note": "Reduce liquid by 1/4 cup"},
        {"substitute": "maple syrup", "ratio": "3/4 cup per 1 cup sugar", "note": "Reduce liquid by 3 tbsp"},
        {"substitute": "coconut sugar", "ratio": "1:1", "note": "Caramel-like flavor"},
        {"substitute": "stevia", "ratio": "1 tsp per 1 cup sugar", "note": "Very sweet, no bulk"},
    ],
    "brown sugar": [
        {"substitute": "white sugar + molasses", "ratio": "1 cup sugar + 1 tbsp molasses", "note": "Mix well"},
        {"substitute": "coconut sugar", "ratio": "1:1", "note": "Similar moisture"},
        {"substitute": "white sugar", "ratio": "1:1", "note": "Less moisture and flavor"},
    ],

    # Oils & Fats
    "vegetable oil": [
        {"substitute": "canola oil", "ratio": "1:1", "note": "Neutral flavor"},
        {"substitute": "coconut oil", "ratio": "1:1", "note": "Solid at room temp"},
        {"substitute": "olive oil", "ratio": "1:1", "note": "Fruity flavor"},
        {"substitute": "applesauce", "ratio": "1/2 cup per 1 cup oil", "note": "For baking, lower fat"},
    ],
    "olive oil": [
        {"substitute": "avocado oil", "ratio": "1:1", "note": "Higher smoke point"},
        {"substitute": "grapeseed oil", "ratio": "1:1", "note": "Neutral flavor"},
        {"substitute": "vegetable oil", "ratio": "1:1", "note": "More neutral"},
    ],

    # Proteins
    "ground beef": [
        {"substitute": "ground turkey", "ratio": "1:1", "note": "Leaner option"},
        {"substitute": "ground chicken", "ratio": "1:1", "note": "Very lean"},
        {"substitute": "lentils", "ratio": "1 cup cooked per 1 lb meat", "note": "Vegetarian, high fiber"},
        {"substitute": "mushrooms", "ratio": "Finely chopped, 1:1", "note": "Meaty texture"},
    ],
    "chicken breast": [
        {"substitute": "turkey breast", "ratio": "1:1", "note": "Similar texture"},
        {"substitute": "pork tenderloin", "ratio": "1:1", "note": "Slightly richer"},
        {"substitute": "tofu", "ratio": "Press and marinate", "note": "Vegetarian option"},
        {"substitute": "cauliflower", "ratio": "In florets", "note": "Vegetarian, roast well"},
    ],
    "bacon": [
        {"substitute": "turkey bacon", "ratio": "1:1", "note": "Lower fat"},
        {"substitute": "prosciutto", "ratio": "1:1", "note": "Italian style"},
        {"substitute": "tempeh bacon", "ratio": "Marinated and cooked", "note": "Vegan option"},
        {"substitute": "coconut bacon", "ratio": "Baked coconut flakes", "note": "Vegan, crunchy"},
    ],

    # Aromatics & Seasonings
    "garlic": [
        {"substitute": "garlic powder", "ratio": "1/8 tsp per clove", "note": "Less fresh flavor"},
        {"substitute": "shallots", "ratio": "1:1", "note": "Milder, sweeter"},
        {"substitute": "garlic scapes", "ratio": "1:1", "note": "Milder, seasonal"},
    ],
    "onion": [
        {"substitute": "shallots", "ratio": "3 shallots per 1 onion", "note": "Milder and sweeter"},
        {"substitute": "leeks", "ratio": "1 cup sliced per 1 onion", "note": "Milder flavor"},
        {"substitute": "onion powder", "ratio": "1 tbsp per 1 medium onion", "note": "Convenience option"},
    ],
    "fresh herbs": [
        {"substitute": "dried herbs", "ratio": "1 tsp dried per 1 tbsp fresh", "note": "More concentrated"},
        {"substitute": "herb paste", "ratio": "1:1", "note": "Convenient"},
        {"substitute": "frozen herbs", "ratio": "1:1", "note": "Better than dried"},
    ],

    # Liquids
    "chicken broth": [
        {"substitute": "vegetable broth", "ratio": "1:1", "note": "Vegetarian option"},
        {"substitute": "bouillon cube + water", "ratio": "1 cube per cup", "note": "More sodium"},
        {"substitute": "water + soy sauce", "ratio": "Add 1 tbsp soy per cup", "note": "Umami flavor"},
    ],
    "wine": [
        {"substitute": "broth", "ratio": "1:1", "note": "Non-alcoholic"},
        {"substitute": "apple cider vinegar", "ratio": "1/4 cup per cup wine", "note": "Add water to fill"},
        {"substitute": "grape juice", "ratio": "1:1", "note": "Sweeter option"},
    ],
    "soy sauce": [
        {"substitute": "tamari", "ratio": "1:1", "note": "Gluten-free"},
        {"substitute": "coconut aminos", "ratio": "1:1", "note": "Soy-free, sweeter"},
        {"substitute": "worcestershire sauce", "ratio": "1:1", "note": "Different flavor profile"},
    ],

    # Acids
    "lemon juice": [
        {"substitute": "lime juice", "ratio": "1:1", "note": "Similar acidity"},
        {"substitute": "white wine vinegar", "ratio": "1:1", "note": "More sharp"},
        {"substitute": "apple cider vinegar", "ratio": "1:1", "note": "Fruitier"},
    ],
    "vinegar": [
        {"substitute": "lemon juice", "ratio": "1:1", "note": "Fresh flavor"},
        {"substitute": "lime juice", "ratio": "1:1", "note": "Citrus note"},
    ],
}


def get_substitutions(ingredient: str) -> Optional[list[dict]]:
    """
    Get substitution suggestions for an ingredient.

    Args:
        ingredient: The ingredient name to find substitutions for

    Returns:
        List of substitution dictionaries with 'substitute', 'ratio', and 'note' keys,
        or None if no substitutions are available
    """
    ingredient_lower = ingredient.lower().strip()

    # Direct match
    if ingredient_lower in SUBSTITUTIONS:
        return SUBSTITUTIONS[ingredient_lower]

    # Partial match (e.g., "whole milk" matches "milk")
    for key in SUBSTITUTIONS:
        if key in ingredient_lower or ingredient_lower in key:
            return SUBSTITUTIONS[key]

    return None


def format_substitution(sub: dict) -> str:
    """Format a substitution dict into a readable string."""
    return f"{sub['substitute']} ({sub['ratio']}) - {sub['note']}"
