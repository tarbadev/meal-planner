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
├── config.py                # Configuration (sheets ID, etc.)
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

## Google Sheets Setup

1. Create a Google Cloud project
2. Enable Google Sheets API
3. Create a Service Account
4. Download credentials.json
5. Share target spreadsheet with service account email

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

## Future Enhancements (v2+)

- [ ] SQLite database for recipes
- [ ] Recipe CRUD in web UI
- [ ] Nutrition targets/constraints (min protein, max calories)
- [ ] Meal type variety (don't repeat cuisine 2 days in a row)
- [ ] Prep time constraints (quick meals on weekdays)
- [ ] Leftover planning (batch cooking awareness)
- [ ] Ingredient seasonality
- [ ] Cost tracking
- [ ] Favorite/rating system
- [ ] Import recipes from URLs (scraping)
- [ ] Nutrition estimation from ingredients (API integration)

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
