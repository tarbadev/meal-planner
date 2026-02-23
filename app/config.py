import os
import secrets

# Secret key — used for session signing.
# Set SECRET_KEY in the environment for production; a random key is
# generated on startup as a safe fallback (sessions won't survive restarts).
SECRET_KEY = os.environ.get("SECRET_KEY", secrets.token_hex(32))

# USDA FoodData Central API key (REQUIRED for nutrition generation)
# Get your free API key at: https://fdc.nal.usda.gov/api-key-signup.html
USDA_API_KEY = os.environ.get("USDA_API_KEY")

# OpenAI API key (REQUIRED for Instagram recipe import)
# Get your API key at: https://platform.openai.com/api-keys
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

# Instagram session file (optional, for automatic fetching)
INSTAGRAM_SESSION_FILE = os.environ.get("INSTAGRAM_SESSION_FILE")

# Spoonacular API key (OPTIONAL - only needed for bulk recipe import scripts)
# Get your free API key at: https://spoonacular.com/food-api/console#Dashboard
SPOONACULAR_API_KEY = os.environ.get("SPOONACULAR_API_KEY")

HOUSEHOLD_PORTIONS = {
    "adults": 2,
    "child_4y": 0.5,
    "toddler": 0.25
}
TOTAL_PORTIONS = 2.75  # Sum of above
MEALS_PER_WEEK = 7
RECIPES_FILE = "data/recipes.json"

# Database configuration
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+psycopg://localhost/mealplanner"
)

# Default household UUID — created at startup if it doesn't exist.
# All data belongs to this household until multi-user support is added.
DEFAULT_HOUSEHOLD_ID = os.environ.get(
    "DEFAULT_HOUSEHOLD_ID", "00000000-0000-0000-0000-000000000001"
)

# Meal schedule configuration
# Default: Dinners on weekdays, Lunch + Dinner on weekends (9 meals total)
# For backward compatibility with 7 meals, use: {day: ["dinner"] for day in DAYS_OF_WEEK}
DAYS_OF_WEEK = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
MEAL_SCHEDULE = {
    "Monday": ["dinner"],
    "Tuesday": ["dinner"],
    "Wednesday": ["dinner"],
    "Thursday": ["dinner"],
    "Friday": ["dinner"],
    "Saturday": ["lunch", "dinner"],
    "Sunday": ["lunch", "dinner"]
}

# Daily calorie limit for meal planning (per person, per day).
# Set to None to disable calorie tracking.
DAILY_CALORIE_LIMIT = 1600

# Proportional calorie budget per meal type.
# Values are relative weights normalised across whichever meal types are
# scheduled for a given day, so they don't need to sum to 1.0.
# Example: a day with lunch + dinner gives lunch 35/(35+40)=46 % of the
# daily limit, dinner the remaining 54 %.
#
# Defaults follow general dietary guidance:
#   Breakfast ~25 %,  Lunch ~35 %,  Dinner ~40 %
# Sources: Harvard T.H. Chan School of Public Health meal-timing research;
#          general recommendations from registered dietitians.
MEAL_CALORIE_SPLITS: dict[str, float] = {
    "breakfast": 0.25,
    "lunch":     0.35,
    "dinner":    0.40,
    "snack":     0.10,
}

COOK_ONCE_PLANNING: bool = True
PACKED_LUNCH_PORTIONS: float = float(HOUSEHOLD_PORTIONS["adults"])  # 2.0
# Maximum derived meals (leftover + packed-lunch combined) per cooked dinner.
# 1 = same recipe at most twice (cook + one re-use); 2 = up to three times (default).
COOK_ONCE_MAX_DERIVED: int = 2

DEFAULT_PER_PAGE = 24
