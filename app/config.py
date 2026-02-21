import os
import secrets
import sys

GOOGLE_SHEETS_ID = "your-spreadsheet-id"

# Flask secret key — used for session signing and CSRF token generation.
# Set SECRET_KEY in the environment for production; a random key is
# generated on startup as a safe fallback (sessions won't survive restarts).
SECRET_KEY = os.environ.get("SECRET_KEY", secrets.token_hex(32))
CREDENTIALS_FILE = "credentials.json"

# Check if we're running in a test environment
def _is_testing():
    """Check if code is running under pytest."""
    return "pytest" in sys.modules or "PYTEST_CURRENT_TEST" in os.environ

# USDA FoodData Central API key (REQUIRED for nutrition generation)
# Get your free API key at: https://fdc.nal.usda.gov/api-key-signup.html
USDA_API_KEY = os.environ.get("USDA_API_KEY", "test-key" if _is_testing() else None)

if not USDA_API_KEY and not _is_testing():
    print("\n" + "=" * 70, file=sys.stderr)
    print("ERROR: USDA_API_KEY environment variable is required", file=sys.stderr)
    print("=" * 70, file=sys.stderr)
    print("\nThe USDA API key is required for automatic nutrition generation.", file=sys.stderr)
    print("Get your free API key at: https://fdc.nal.usda.gov/api-key-signup.html", file=sys.stderr)
    print("\nThen set the environment variable:", file=sys.stderr)
    print("  export USDA_API_KEY='your-api-key-here'", file=sys.stderr)
    print("\nOr add it to a .env file and load it before starting the app.", file=sys.stderr)
    print("=" * 70 + "\n", file=sys.stderr)
    sys.exit(1)

# OpenAI API key (REQUIRED for Instagram recipe import)
# Get your API key at: https://platform.openai.com/api-keys
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "test-key" if _is_testing() else None)

if not OPENAI_API_KEY and not _is_testing():
    print("\n" + "=" * 70, file=sys.stderr)
    print("ERROR: OPENAI_API_KEY environment variable is required", file=sys.stderr)
    print("=" * 70, file=sys.stderr)
    print("\nThe OpenAI API key is required for Instagram recipe imports.", file=sys.stderr)
    print("Get your API key at: https://platform.openai.com/api-keys", file=sys.stderr)
    print("\nThen set the environment variable:", file=sys.stderr)
    print("  export OPENAI_API_KEY='sk-...'", file=sys.stderr)
    print("\nOr add it to a .env file and load it before starting the app.", file=sys.stderr)
    print("=" * 70 + "\n", file=sys.stderr)
    sys.exit(1)

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

DEFAULT_PER_PAGE = 24
