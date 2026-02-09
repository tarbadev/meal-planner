import os
import sys

GOOGLE_SHEETS_ID = "your-spreadsheet-id"
CREDENTIALS_FILE = "credentials.json"

# USDA FoodData Central API key (REQUIRED for nutrition generation)
# Get your free API key at: https://fdc.nal.usda.gov/api-key-signup.html
USDA_API_KEY = os.environ.get("USDA_API_KEY")

if not USDA_API_KEY:
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
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

if not OPENAI_API_KEY:
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
