# Meal Planner Project Spec

## Overview

Build a local meal planning application that runs on a Raspberry Pi. It generates weekly meal plans from a recipe database and outputs to Google Sheets with a shopping list.

## Goals

- **Cheap**: Runs locally on a Pi, no cloud costs
- **Fast**: Local execution, quick response times
- **Simple**: Minimal viable product first, iterate later
- **Privacy**: All data stays local except Google Sheets output

## Family Context

- 2 adults
- 1 child (4.5 years old) — estimate ~0.5 adult portions
- 1 toddler (1.5 years old) — estimate ~0.25 adult portions
- **Total household multiplier**: ~2.75 adult portions

## Tech Stack

- **Language**: Python 3.11+
- **Web Framework**: Flask (lightweight, Pi-friendly)
- **Data Storage**: JSON file (v1), SQLite (v2)
- **Google Sheets**: `gspread` + Google Service Account
- **Deployment**: Runs on Raspberry Pi

## Project Structure

```
meal-planner/
├── app/
│   ├── __init__.py
│   ├── recipes.py           # Recipe dataclass + loading (done)
│   ├── config.py            # Configuration settings
│   ├── main.py              # Flask app entry point
│   ├── planner.py           # Meal planning logic
│   ├── sheets.py            # Google Sheets integration
│   └── templates/
│       └── index.html       # Simple web UI
├── data/
│   └── recipes.json         # Recipe database (5 recipes done)
├── tests/
│   ├── __init__.py
│   └── test_recipes.py      # Recipe loading tests (done)
├── requirements.txt
├── README.md
└── credentials.json         # Google service account (gitignored)
```

## Recipe Schema (JSON)

```json
{
  "recipes": [
    {
      "id": "pasta-bolognese",
      "name": "Pasta Bolognese",
      "servings": 4,
      "prep_time_minutes": 15,
      "cook_time_minutes": 30,
      "calories_per_serving": 450,
      "protein_per_serving": 25,
      "carbs_per_serving": 55,
      "fat_per_serving": 12,
      "tags": ["italian", "kid-friendly", "batch-cooking"],
      "ingredients": [
        {"item": "ground beef", "quantity": 500, "unit": "g"},
        {"item": "pasta", "quantity": 400, "unit": "g"},
        {"item": "tomato sauce", "quantity": 500, "unit": "ml"},
        {"item": "onion", "quantity": 1, "unit": "whole"},
        {"item": "garlic", "quantity": 3, "unit": "cloves"}
      ]
    }
  ]
}
```

## Core Features (MVP)

### 1. Generate Weekly Meal Plan

- Select 7 dinners from recipe database
- No repeats within the week
- Random selection (v1), smarter optimization later
- Calculate total portions needed per recipe (household multiplier)

### 2. Nutrition Summary

- Sum calories, protein, carbs, fat for the week
- Show daily averages
- Per-meal breakdown

### 3. Shopping List Generation

- Aggregate all ingredients across selected meals
- Combine same items (e.g., 2 recipes need onions → sum quantities)
- Group by category if possible (produce, meat, pantry, dairy)

### 4. Google Sheets Output

Create a spreadsheet with two tabs:

**Tab 1: Weekly Plan**
| Day | Meal | Servings | Calories | Protein | Prep Time |
|-----|------|----------|----------|---------|-----------|
| Monday | Pasta Bolognese | 2.75 | 450 | 25g | 45min |
| ... | ... | ... | ... | ... | ... |

**Tab 2: Shopping List**
| Item | Quantity | Unit | Category |
|------|----------|------|----------|
| ground beef | 500 | g | meat |
| pasta | 400 | g | pantry |
| ... | ... | ... | ... |

### 5. Simple Web UI

Single page with:
- "Generate New Plan" button
- Display current week's plan
- Link to generated Google Sheet
- List of available recipes

## Google Sheets Setup - Detailed Guide

### Overview
This guide will walk you through setting up Google Sheets integration so your meal plans and shopping lists automatically sync to a Google Spreadsheet.

**Time required:** ~10 minutes
**Cost:** Free (Google Cloud free tier)

---

### Step 1: Create a Google Cloud Project

1. **Go to Google Cloud Console**
   - Visit: https://console.cloud.google.com/
   - Sign in with your Google account

2. **Create a new project**
   - Click the project dropdown at the top (next to "Google Cloud")
   - Click "NEW PROJECT"
   - Project name: `meal-planner` (or any name you like)
   - Organization: Leave as "No organization"
   - Click "CREATE"
   - Wait ~30 seconds for project creation

3. **Select your new project**
   - Click the project dropdown again
   - Select your newly created project

---

### Step 2: Enable Google Sheets API

1. **Open API Library**
   - In the left sidebar, click "APIs & Services" > "Library"
   - Or visit: https://console.cloud.google.com/apis/library

2. **Find and enable Google Sheets API**
   - In the search box, type: `Google Sheets API`
   - Click on "Google Sheets API"
   - Click the blue "ENABLE" button
   - Wait for it to enable (~10 seconds)

3. **Enable Google Drive API** (also needed)
   - Click "Library" in the left sidebar again
   - Search for: `Google Drive API`
   - Click on "Google Drive API"
   - Click "ENABLE"

---

### Step 3: Create a Service Account

1. **Go to Credentials page**
   - In the left sidebar: "APIs & Services" > "Credentials"
   - Or visit: https://console.cloud.google.com/apis/credentials

2. **Create Service Account**
   - Click "+ CREATE CREDENTIALS" at the top
   - Select "Service Account"

3. **Service Account Details**
   - Service account name: `meal-planner-bot`
   - Service account ID: (auto-filled) `meal-planner-bot@...`
   - Description: `Service account for meal planner app`
   - Click "CREATE AND CONTINUE"

4. **Grant Permissions** (Optional - can skip)
   - Role: Leave blank (not needed)
   - Click "CONTINUE"

5. **Grant Users Access** (Optional - can skip)
   - Click "DONE"

---

### Step 4: Create and Download Service Account Key

1. **Find your service account**
   - You should see your service account in the "Service Accounts" section
   - Email looks like: `meal-planner-bot@meal-planner-xxxxx.iam.gserviceaccount.com`
   - **COPY THIS EMAIL** - you'll need it in Step 6!

2. **Create a key**
   - Click on your service account email
   - Click the "KEYS" tab at the top
   - Click "ADD KEY" > "Create new key"

3. **Download JSON key**
   - Select "JSON" format
   - Click "CREATE"
   - A file named `meal-planner-xxxxx-xxxxxxxx.json` will download

4. **Rename and move the file**
   ```bash
   # Rename the downloaded file to credentials.json
   mv ~/Downloads/meal-planner-*.json ~/path/to/meal-planner/credentials.json
   ```

⚠️ **IMPORTANT:** Keep this file secure! It grants access to your spreadsheets.

---

### Step 5: Create a Google Spreadsheet

1. **Create new spreadsheet**
   - Go to: https://sheets.google.com
   - Click "+ Blank" to create a new spreadsheet
   - Name it: `Meal Planner` (top-left corner)

2. **Copy the Spreadsheet ID**
   - Look at the URL in your browser:
   ```
   https://docs.google.com/spreadsheets/d/1AbC123dEfGhIjKlMnOpQrStUvWxYz/edit
                                        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                                        This is your SPREADSHEET_ID
   ```
   - Copy the long string of letters/numbers between `/d/` and `/edit`

---

### Step 6: Share Spreadsheet with Service Account

1. **Click "Share" button** (top-right corner of your spreadsheet)

2. **Add service account email**
   - Paste the service account email from Step 4.1
   - Example: `meal-planner-bot@meal-planner-xxxxx.iam.gserviceaccount.com`

3. **Set permissions**
   - Role: "Editor" (the app needs to write to the sheet)
   - **UNCHECK** "Notify people" (it's a bot, no need to send email)

4. **Click "Share" or "Send"**

---

### Step 7: Configure the Meal Planner App

1. **Edit app/config.py**
   ```python
   # Open: meal-planner/app/config.py

   GOOGLE_SHEETS_ID = "1AbC123dEfGhIjKlMnOpQrStUvWxYz"  # Your ID from Step 5
   CREDENTIALS_FILE = "credentials.json"  # Should already be set
   ```

2. **Verify credentials.json is in the right place**
   ```bash
   ls meal-planner/credentials.json
   # Should show: credentials.json
   ```

---

### Step 8: Test the Integration

1. **Start your app**
   ```bash
   cd meal-planner
   source .venv/bin/activate
   python -m flask --app app.main run
   ```

2. **Generate a meal plan**
   - Open: http://localhost:5000
   - Click "Generate New Weekly Plan"

3. **Write to Google Sheets**
   ```bash
   curl -X POST http://localhost:5000/write-to-sheets
   ```

   Or add a "Export to Google Sheets" button in the web UI (future enhancement)

4. **Check your spreadsheet**
   - Go back to your Google Spreadsheet
   - You should see two new tabs:
     - **Weekly Plan** - Your meal schedule with nutrition
     - **Shopping List** - Ingredients grouped by category

---

### Troubleshooting

#### Error: "Credentials file not found"
- Check that `credentials.json` is in the project root directory
- Verify the path in `config.py` is correct

#### Error: "Permission denied" or "Insufficient permissions"
- Make sure you shared the spreadsheet with the service account email
- Verify the service account has "Editor" role (not "Viewer")
- Double-check the spreadsheet ID in `config.py`

#### Error: "API not enabled"
- Go back to API Library and enable both:
  - Google Sheets API
  - Google Drive API

#### Spreadsheet is empty after writing
- Check the browser console for errors
- Verify the spreadsheet ID is correct
- Try creating a new spreadsheet and sharing it again

#### Error: "Invalid credentials"
- Make sure you downloaded the JSON key (not P12)
- Try creating a new service account key
- Verify the credentials.json file is valid JSON (open it in a text editor)

---

### Security Best Practices

1. **Never commit credentials.json to Git**
   - It's already in `.gitignore`
   - Never share this file publicly

2. **Limit spreadsheet access**
   - Only share the spreadsheet with people who need access
   - The service account should only have Editor access to this specific sheet

3. **Rotate keys periodically**
   - Consider creating a new service account key every 6-12 months
   - Delete old keys from Google Cloud Console

4. **Use environment variables (optional)**
   ```bash
   # Instead of hardcoding in config.py:
   export GOOGLE_SHEETS_ID="your-spreadsheet-id"
   export CREDENTIALS_FILE="/path/to/credentials.json"
   ```

---

### Video Tutorial (Future)

For a visual walkthrough, we could create a screen recording showing:
- Creating the Google Cloud project
- Downloading the credentials
- Setting up the spreadsheet
- Testing the integration

Would you like help creating this video?

## Configuration (config.py)

```python
GOOGLE_SHEETS_ID = "your-spreadsheet-id"
CREDENTIALS_FILE = "credentials.json"
HOUSEHOLD_PORTIONS = {
    "adults": 2,
    "child_4y": 0.5,
    "toddler": 0.25
}
TOTAL_PORTIONS = 2.75  # Sum of above
MEALS_PER_WEEK = 7
```

## API Endpoints

```
GET  /                  → Web UI
POST /generate          → Generate new weekly plan
GET  /recipes           → List all recipes
GET  /current-plan      → Get current week's plan
```

## Implementation Steps

### Step 1: Project Setup
- [x] Initialize project structure
- [x] Create requirements.txt (flask, gspread, google-auth, pytest)
- [x] Set up basic Flask app

### Step 2: Recipe Data
- [x] Create recipes.json with 5 sample recipes
- [x] Implement recipe loading function (`app/recipes.py`)
- [x] Add recipe validation (with tests in `tests/test_recipes.py`)

### Step 3: Planner Logic
- [x] Implement random meal selection (no repeats)
- [x] Calculate portions based on household size
- [x] Aggregate nutrition info

### Step 4: Shopping List
- [x] Aggregate ingredients across meals
- [x] Combine duplicate items
- [x] Sort by category

### Step 5: Google Sheets Integration
- [x] Set up gspread authentication
- [x] Create/update weekly plan tab
- [x] Create/update shopping list tab

### Step 6: Web UI
- [x] Simple HTML template with Jinja2
- [x] Generate button
- [x] Display results

### Step 7: Pi Deployment
- [x] systemd service file
- [x] Auto-start on boot
- [x] Local network access

## Sample Recipes to Include

1. [x] Pasta Bolognese (Italian, kid-friendly)
2. [x] Chicken Stir Fry (Asian, quick)
3. [x] Fish Fingers with Mashed Potatoes (kid-friendly, easy)
4. [x] Vegetable Curry with Rice (vegetarian option)
5. [x] Homemade Pizza (weekend, fun with kids)
6. [ ] Salmon with Roasted Vegetables (healthy)
7. [x] Tacos (Mexican, customizable)
8. [ ] Chicken Soup (comfort food, batch)
9. [x] Mac and Cheese (kid favorite)
10. [ ] Grilled Chicken with Quinoa (healthy, simple)

## Future Enhancements

Features organized by **Priority** (High/Med/Low) and **Complexity** (Low/Med/High).

---

### HIGH PRIORITY - LOW COMPLEXITY (Quick Wins) ⭐

These provide immediate value and are relatively simple to implement.

#### Recipe Management Improvements
- [ ] **Recipe favorites/rating system** - Star ratings and favorites filter
- [ ] **Edit recipes in web UI** - Update existing recipes without editing JSON
- [ ] **Delete recipes** - Remove recipes from database
- [ ] **Duplicate recipe** - Clone and modify existing recipes
- [ ] **Search/filter recipe list** - Search by name, tags, ingredients
- [ ] **Recipe tags filter** - Generate plans using only certain tags (e.g., "quick", "kid-friendly")

#### UI/UX Enhancements
- [ ] **Print-friendly meal plan view** - Clean layout for printing
- [ ] **Weekly prep time estimate** - Total time needed for the week
- [ ] **Recipe difficulty rating** - Easy/Medium/Hard indicator
- [ ] **Cooking method tags** - slow-cooker, instant-pot, one-pan, etc.
- [ ] **Regenerate specific day** - Replace just one meal instead of whole week

#### Google Sheets Setup
- [ ] **Step-by-step Sheets setup guide** - Interactive wizard in web UI
- [ ] **Test credentials button** - Verify Google Sheets connection
- [ ] **Auto-detect spreadsheet** - List available sheets to choose from

---

### HIGH PRIORITY - MEDIUM COMPLEXITY (Core Features) 🎯

These are essential features that require more work but provide major value.

#### Multi-Meal Type Planning ⭐⭐⭐ (USER REQUESTED)
- [ ] **Multiple meal types** - Plan for breakfast, lunch, dinner, snacks
- [ ] **Per-meal household configuration** - Define who eats which meals
  - Example: Adults eat lunch at work (not included), kids need lunch at home
  - Configure portions per meal type: "Dinner: 2.75 portions, Lunch: 1.25 portions"
- [ ] **Flexible meal scheduling** - Some days need lunch, some don't
- [ ] **Meal type preferences** - Different recipe pools for breakfast vs dinner

#### Recipe Database Management
- [ ] **SQLite database migration** - Move from JSON to SQLite for better CRUD
- [ ] **Recipe categories/types** - Breakfast, lunch, dinner, snack, dessert
- [ ] **Recipe versioning** - Track changes to recipes over time
- [ ] **Batch operations** - Import/export multiple recipes at once

#### Smart Planning Features
- [ ] **Manual meal selection** - Choose specific recipes instead of random
- [ ] **Meal plan history** - Archive past plans with notes
- [ ] **Recipe rotation intelligence** - Avoid repeating recipes too soon
- [ ] **Cuisine variety constraint** - Don't repeat Italian 3 days in row
- [ ] **Weekday/weekend preferences** - Quick meals on weekdays, complex on weekends
- [ ] **Regenerate plan with constraints** - Keep some days, regenerate others

#### Shopping List Enhancements
- [ ] **Check off items** - Mark items as purchased in web UI
- [ ] **Organize by store layout** - Custom category ordering
- [ ] **Ingredient notes** - "Get ripe bananas" or "organic preferred"
- [ ] **Common pantry items** - Auto-exclude items you always have (salt, oil, etc.)

---

### HIGH PRIORITY - HIGH COMPLEXITY (Major Features) 🚀

These are game-changers but require significant development effort.

#### Recipe Import from External Sources ⭐⭐⭐ (USER REQUESTED)
- [ ] **Import recipe from URL** - Web scraping with recipe schema detection
  - Support popular sites (AllRecipes, Food Network, NYT Cooking, etc.)
  - Extract: name, ingredients, instructions, nutrition, images
  - Handle different HTML structures with fallback parsers
  - Library: `recipe-scrapers` Python package

- [ ] **Import recipe from image/photo** ⭐⭐⭐ (USER REQUESTED)
  - OCR text extraction from cookbook photos
  - AI parsing to extract structured recipe data
  - Approach 1: Claude API with vision for recipe parsing
  - Approach 2: GPT-4 Vision API
  - Approach 3: Local OCR (Tesseract) + Claude API for structuring
  - Handle: handwritten recipes, printed cookbooks, recipe cards
  - Validate and allow editing before saving

#### Ingredient Intelligence
- [ ] **Ingredient inventory tracking** - Track what's in your pantry/fridge
- [ ] **Use-it-up mode** - Generate plans to use expiring ingredients
- [ ] **Leftover tracking** - Account for batch cooking and leftovers
- [ ] **Smart shopping list** - Only include items not in inventory

#### Nutrition & Dietary
- [ ] **Nutrition goals** - Target calories/protein per day or week
- [ ] **Dietary restrictions** - Vegetarian, vegan, gluten-free, dairy-free
- [ ] **Allergen tracking** - Mark and avoid specific allergens
- [ ] **Macros optimization** - Generate plans meeting macro targets

---

### MEDIUM PRIORITY - LOW COMPLEXITY (Nice to Have) ✨

- [ ] **Export meal plan to PDF** - Downloadable formatted document
- [ ] **Email meal plan** - Send plan to family members
- [ ] **Recipe source tracking** - Where did this recipe come from?
- [ ] **Serving size calculator** - Scale recipe for different portion counts
- [ ] **Prep ahead suggestions** - What can be prepped the night before
- [ ] **Recipe collections** - Group recipes into themed collections
- [ ] **Dark mode** - UI theme toggle

---

### MEDIUM PRIORITY - MEDIUM COMPLEXITY (Quality of Life) 💡

#### Recipe Enhancement
- [ ] **Recipe notes/modifications** - Track your tweaks and adjustments
- [ ] **Recipe images** - Upload and display photos
- [ ] **Cooking instructions** - Step-by-step directions (currently only ingredients)
- [ ] **Ingredient substitutions** - Suggest alternatives (e.g., "out of milk? use cream")
- [ ] **Nutrition auto-calculation** - Calculate nutrition from ingredients using API

#### Planning Intelligence
- [ ] **Batch cooking optimizer** - Identify recipes to cook in bulk
- [ ] **Ingredient overlap optimizer** - Choose recipes that share ingredients
- [ ] **Season-aware suggestions** - Prefer seasonal recipes
- [ ] **Weather-based suggestions** - Soup on cold days, salads on hot days

#### Social Features
- [ ] **Share meal plans** - Send read-only link to family
- [ ] **Recipe sharing** - Share specific recipes with others
- [ ] **Meal plan templates** - Save and reuse favorite weekly plans

---

### MEDIUM PRIORITY - HIGH COMPLEXITY (Advanced) 🔬

#### Cost Management
- [ ] **Cost tracking per recipe** - Track ingredient costs
- [ ] **Budget constraints** - Generate plans within weekly budget
- [ ] **Price comparison** - Compare costs across stores
- [ ] **Cost trends** - Track how recipe costs change over time

#### Smart Recommendations
- [ ] **AI meal suggestions** - ML-based recipe recommendations
- [ ] **Taste preference learning** - Learn what family likes/dislikes
- [ ] **Variety scoring** - Ensure good mix of proteins, cuisines, cooking methods
- [ ] **Nutrition trend analysis** - Track nutrition over time

---

### LOW PRIORITY (Future Vision) 🔮

- [ ] **Multi-week planning** - Plan 2-4 weeks ahead
- [ ] **Calendar integration** - Sync with Google Calendar
- [ ] **Mobile app** - Native iOS/Android apps
- [ ] **Voice control** - "Alexa, what's for dinner?"
- [ ] **Grocery delivery integration** - One-click order from Instacart/Amazon Fresh
- [ ] **Smart home integration** - Send recipe to smart oven
- [ ] **Meal prep service export** - Export recipes in format for meal prep companies
- [ ] **Multi-household support** - Manage plans for multiple families
- [ ] **Recipe video links** - Link to YouTube cooking tutorials

---

## Recommended Implementation Order (Next 6 Features)

Based on user needs and value/effort ratio:

1. **Multi-Meal Type Planning** (High value for user) - ~1-2 weeks
2. **Recipe Import from URL** (High value, frequently requested) - ~1 week
3. **Step-by-step Google Sheets Setup Guide** (Improves onboarding) - ~2-3 days
4. **Recipe CRUD in Web UI** (Essential for usability) - ~3-4 days
5. **Recipe Import from Image** (Unique feature, high wow factor) - ~1-2 weeks
6. **Manual Meal Selection** (User control over randomness) - ~2-3 days

---

## Technical Considerations

### Recipe Import from URL
**Libraries:**
- `recipe-scrapers` - Supports 100+ recipe websites
- `beautifulsoup4` - HTML parsing fallback
- `requests` - HTTP client

**Implementation:**
```python
from recipe_scrapers import scrape_me_2

scraper = scrape_me_2('https://www.allrecipes.com/recipe/...')
recipe = {
    'name': scraper.title(),
    'ingredients': scraper.ingredients(),
    'instructions': scraper.instructions(),
    'prep_time': scraper.prep_time(),
    'cook_time': scraper.cook_time(),
    'image': scraper.image()
}
```

### Recipe Import from Image
**Approach 1: Claude API (Recommended)**
```python
import anthropic

# Send image to Claude with structured prompt
response = client.messages.create(
    model="claude-sonnet-4-5",
    messages=[{
        "role": "user",
        "content": [
            {"type": "image", "source": {"type": "base64", "data": base64_image}},
            {"type": "text", "text": "Extract recipe as JSON with name, ingredients, instructions..."}
        ]
    }]
)
```

**Approach 2: OCR + AI**
```python
import pytesseract
from PIL import Image

# Extract text with OCR
text = pytesseract.image_to_string(Image.open('recipe.jpg'))

# Parse with Claude API
recipe_json = claude_parse_recipe_text(text)
```

### Multi-Meal Planning
**Database Schema Changes:**
```python
@dataclass
class MealType(Enum):
    BREAKFAST = "breakfast"
    LUNCH = "lunch"
    DINNER = "dinner"
    SNACK = "snack"

@dataclass
class HouseholdConfig:
    meal_type: MealType
    portions: float
    days_needed: list[str]  # ["Monday", "Tuesday", ...]

@dataclass
class PlannedMeal:
    day: str
    meal_type: MealType  # NEW
    recipe: Recipe
    portions: float
```

---

## Questions for User

Before implementing next features, consider:

1. **Multi-meal planning priorities:**
   - Which meal types are most important? (breakfast, lunch, dinner, snacks)
   - Should different family members have different meal schedules?
   - Do you want to plan all meal types at once or separately?

2. **Recipe import priorities:**
   - More important: URL import or image import?
   - Any specific recipe websites you use frequently?
   - What format are your cookbook photos? (phone photos, scanned pages, etc.)

3. **Recipe database:**
   - Ready to migrate to SQLite or keep JSON for now?
   - How many recipes do you plan to have eventually? (10s, 100s, 1000s)

4. **Shopping list needs:**
   - Do you shop at multiple stores?
   - Need to track pantry inventory?
   - Want to track costs?

## Commands to Run

```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run tests
python -m pytest tests/ -v

# Run locally
flask run --host=0.0.0.0 --port=5000

# On Pi, access via http://<pi-ip>:5000
```

## Requirements.txt

```
flask>=3.0.0
gspread>=6.0.0
google-auth>=2.0.0
google-auth-oauthlib>=1.0.0
pytest>=8.0.0
```

## Notes for Development

- Start with hardcoded recipes, don't over-engineer data input
- Use type hints throughout
- Keep functions small and testable
- No database until we actually need CRUD operations
- Prioritize working software over perfect architecture

## Success Criteria (MVP)

1. [x] Can load recipes from JSON file
2. [x] Can generate a 7-day plan with no repeats
3. [x] Can calculate shopping list with combined quantities
4. [x] Can write both to Google Sheet
5. [x] Can trigger via simple web UI
6. [x] Runs on Raspberry Pi without issues (deployment instructions provided)
