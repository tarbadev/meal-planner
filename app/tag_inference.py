"""Automatic tag inference for recipes based on content."""

import logging

logger = logging.getLogger(__name__)


class TagInferencer:
    """Infer tags for recipes based on name, ingredients, and instructions."""

    # Keywords for different tag categories
    TAG_KEYWORDS = {
        'dessert': {
            'names': ['cake', 'cookie', 'brownie', 'cupcake', 'tart', 'pie', 'pudding',
                     'ice cream', 'sorbet', 'mousse', 'cheesecake', 'macaron', 'truffle',
                     'fudge', 'candy', 'sweet', 'dessert', 'pastry', 'donut', 'muffin'],
            'ingredients': ['sugar', 'chocolate', 'cocoa', 'frosting', 'icing',
                          'vanilla extract', 'confectioner', 'powdered sugar',
                          'chocolate chip', 'candy', 'caramel', 'marshmallow']
        },
        'breakfast': {
            'names': ['pancake', 'waffle', 'french toast', 'omelette', 'omelet',
                     'scrambled eggs', 'breakfast', 'cereal', 'oatmeal', 'granola',
                     'smoothie bowl', 'breakfast burrito', 'eggs benedict'],
            'ingredients': ['maple syrup', 'breakfast sausage', 'bacon', 'oatmeal']
        },
        'soup': {
            'names': ['soup', 'stew', 'chowder', 'bisque', 'broth', 'pho', 'ramen',
                     'minestrone', 'gazpacho', 'chili'],
            'ingredients': ['stock', 'broth', 'bouillon']
        },
        'salad': {
            'names': ['salad', 'slaw', 'coleslaw'],
            'ingredients': ['lettuce', 'mixed greens', 'arugula', 'spinach leaves',
                          'vinaigrette', 'salad dressing']
        },
        'pasta': {
            'names': ['pasta', 'spaghetti', 'linguine', 'penne', 'fettuccine',
                     'lasagna', 'ravioli', 'gnocchi', 'mac and cheese', 'macaroni'],
            'ingredients': ['pasta', 'spaghetti', 'penne', 'linguine', 'noodles',
                          'lasagna noodles', 'macaroni']
        },
        'vegetarian': {
            'ingredients': [],  # Determined by absence of meat
        },
        'vegan': {
            'ingredients': [],  # Determined by absence of animal products
        },
        'quick': {
            'total_time': 30  # 30 minutes or less
        },
        'slow-cooker': {
            'names': ['slow cooker', 'slow-cooker', 'crock pot', 'crockpot'],
            'instructions': ['slow cooker', 'crock pot']
        },
        'instant-pot': {
            'names': ['instant pot', 'instant-pot', 'pressure cooker'],
            'instructions': ['instant pot', 'pressure cooker']
        },
        'baking': {
            'names': ['baked', 'roasted', 'bread', 'biscuit'],
            'instructions': ['bake', 'oven', 'preheat'],
            'ingredients': ['baking powder', 'baking soda', 'yeast', 'flour']
        },
        'grilling': {
            'names': ['grilled', 'bbq', 'barbecue'],
            'instructions': ['grill', 'barbecue', 'bbq', 'charcoal']
        },
    }

    # Animal products for vegetarian/vegan detection
    MEAT_INGREDIENTS = [
        'beef', 'chicken', 'pork', 'turkey', 'lamb', 'veal', 'duck',
        'bacon', 'sausage', 'ham', 'meat', 'fish', 'salmon', 'tuna',
        'shrimp', 'seafood', 'anchovy', 'prosciutto', 'pepperoni'
    ]

    ANIMAL_PRODUCTS = MEAT_INGREDIENTS + [
        'egg', 'milk', 'cream', 'butter', 'cheese', 'yogurt',
        'sour cream', 'cream cheese', 'honey', 'gelatin'
    ]

    def infer_tags(
        self,
        name: str,
        ingredients: list[dict],
        instructions: list[str] = None,
        prep_time_minutes: int = 0,
        cook_time_minutes: int = 0,
        existing_tags: list[str] = None
    ) -> list[str]:
        """Infer tags for a recipe based on its content.

        Args:
            name: Recipe name
            ingredients: List of ingredient dicts with 'item' key
            instructions: List of instruction strings
            prep_time_minutes: Preparation time
            cook_time_minutes: Cooking time
            existing_tags: Tags already assigned to the recipe

        Returns:
            List of inferred tags (does not include existing_tags)
        """
        inferred = []
        name_lower = name.lower()
        instructions_text = ' '.join(instructions or []).lower()
        ingredient_items = [ing.get('item', '').lower() for ing in ingredients]

        # Check each tag category
        for tag, criteria in self.TAG_KEYWORDS.items():
            # Skip if tag already exists
            if existing_tags and tag in existing_tags:
                continue

            # Check name keywords
            if 'names' in criteria:
                if any(keyword in name_lower for keyword in criteria['names']):
                    inferred.append(tag)
                    continue

            # Check ingredient keywords
            if 'ingredients' in criteria and criteria['ingredients']:
                if any(
                    any(keyword in item for keyword in criteria['ingredients'])
                    for item in ingredient_items
                ):
                    inferred.append(tag)
                    continue

            # Check instruction keywords
            if 'instructions' in criteria:
                if any(keyword in instructions_text for keyword in criteria['instructions']):
                    inferred.append(tag)
                    continue

            # Check total time
            if 'total_time' in criteria:
                total_time = prep_time_minutes + cook_time_minutes
                if total_time > 0 and total_time <= criteria['total_time']:
                    inferred.append(tag)
                    continue

        # Vegetarian detection (no meat)
        has_meat = any(
            any(meat in item for meat in self.MEAT_INGREDIENTS)
            for item in ingredient_items
        )
        if not has_meat and 'vegetarian' not in (existing_tags or []):
            inferred.append('vegetarian')

        # Vegan detection (no animal products)
        has_animal_products = any(
            any(product in item for product in self.ANIMAL_PRODUCTS)
            for item in ingredient_items
        )
        if not has_animal_products and 'vegan' not in (existing_tags or []):
            inferred.append('vegan')

        return inferred

    def enhance_tags(
        self,
        name: str,
        ingredients: list[dict],
        instructions: list[str] = None,
        prep_time_minutes: int = 0,
        cook_time_minutes: int = 0,
        existing_tags: list[str] = None
    ) -> list[str]:
        """Enhance existing tags with inferred tags.

        Returns:
            Combined list of existing and inferred tags (no duplicates)
        """
        existing_tags = existing_tags or []
        inferred = self.infer_tags(
            name=name,
            ingredients=ingredients,
            instructions=instructions,
            prep_time_minutes=prep_time_minutes,
            cook_time_minutes=cook_time_minutes,
            existing_tags=existing_tags
        )

        # Combine and deduplicate
        all_tags = existing_tags + [tag for tag in inferred if tag not in existing_tags]
        logger.debug(
            "Tags inferred",
            extra={"recipe": name, "tags_added": list(set(inferred) - set(existing_tags))},
        )
        return all_tags
