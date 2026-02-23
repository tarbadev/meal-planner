# Meal Planner

A local meal planning application that generates weekly meal plans from a recipe database, tracks nutrition, and produces shopping lists with optional Google Sheets export.

## Features

- Generate 7-day meal plans with no recipe repeats
- Cook-once planning: automatically schedules leftovers and packed lunches
- Automatic portion scaling for household size (default: 2.75 portions)
- Nutrition tracking (calories, protein, carbs, fat, and micronutrients)
- Automatic nutrition generation from ingredients via the USDA FoodData Central API
- Recipe import from URLs, Instagram posts, images, and pasted text
- AI-powered extraction using GPT-4o (English & French)
- Shopping list generation with ingredient aggregation
- Web UI for all operations

## Tech Stack

- Python 3.12+
- FastAPI + Uvicorn
- PostgreSQL (via SQLAlchemy 2.0 async + psycopg3)
- Alembic for schema migrations
- uv for dependency management

---

## Local Setup

### 1. Install uv

```bash
# macOS
brew install uv

# Linux
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. Install dependencies

```bash
uv sync --dev
```

This creates a `.venv` and installs all runtime and dev dependencies from `uv.lock`.

### 3. Set up PostgreSQL

Install PostgreSQL if you don't have it:

```bash
# macOS
brew install postgresql@17
brew services start postgresql@17

# Ubuntu / Debian
sudo apt install postgresql
sudo systemctl start postgresql
```

Create the database:

```bash
createdb mealplanner
```

### 4. Configure environment

Copy the example file and fill in your values:

```bash
cp .env.example .env
```

Minimum required entries in `.env`:

```dotenv
DATABASE_URL=postgresql+psycopg://localhost/mealplanner
USDA_API_KEY=your-usda-key-here
OPENAI_API_KEY=sk-your-openai-key-here
```

- **USDA API key** — free, sign up at https://fdc.nal.usda.gov/api-key-signup.html
- **OpenAI API key** — required for recipe import (URL, Instagram, image, text); get one at https://platform.openai.com/api-keys

The app will refuse to start if either key is missing.

### 5. Run database migrations

```bash
uv run alembic upgrade head
```

### 6. Seed the recipe database

The repo ships with a pre-generated seed file containing ~850 recipes:

```bash
psql mealplanner -f scripts/seed_recipes.sql
```

To regenerate it from `data/recipes.json` (e.g. after editing recipes locally):

```bash
uv run python scripts/generate_seed_sql.py
psql mealplanner -f scripts/seed_recipes.sql
```

### 7. Start the server

```bash
uv run uvicorn app.main:app --reload
```

Open http://localhost:8000 in your browser.

---

## Running Tests

Tests use an in-memory SQLite database — no PostgreSQL connection required.

```bash
# Run all tests
uv run pytest

# Run only unit tests (fast, no HTTP)
uv run pytest tests/ --ignore=tests/integration

# Run only integration tests (HTTP + DB)
uv run pytest tests/integration/

# Run with verbose output
uv run pytest -v
```

---

## Configuration

Edit `app/config.py` to customise household size, meal schedule, and calorie targets:

```python
# Household portions
HOUSEHOLD_PORTIONS = {
    "adults": 2,
    "child_4y": 0.5,
    "toddler": 0.25,
}
TOTAL_PORTIONS = 2.75

# Meal schedule — which meal types are planned on each day
MEAL_SCHEDULE = {
    "Monday": ["dinner"],
    ...
    "Saturday": ["lunch", "dinner"],
    "Sunday": ["lunch", "dinner"],
}

DAILY_CALORIE_LIMIT = 1600       # per person per day; None to disable
COOK_ONCE_PLANNING = True        # schedule leftovers and packed lunches automatically
COOK_ONCE_MAX_DERIVED = 2        # max re-uses per cooked batch
```

---

## Project Structure

```
meal-planner/
├── app/
│   ├── main.py                  # FastAPI app, lifespan, router includes
│   ├── config.py                # All configuration constants
│   ├── logging_config.py        # Structured JSON logging setup
│   ├── api/
│   │   ├── pages.py             # GET /, /health, /share-recipe
│   │   ├── recipes.py           # /api/recipes, /recipes, /recipe/<id>
│   │   ├── planner.py           # /generate, /current-plan, /manual-plan/*
│   │   ├── shopping.py          # /shopping-list/*, /excluded-ingredients
│   │   └── import_routes.py     # /import-recipe, /import-recipe-text, /import-recipe-image
│   ├── db/
│   │   ├── engine.py            # Async engine, get_db dependency
│   │   ├── models.py            # SQLAlchemy ORM models
│   │   ├── crud.py              # Async CRUD helpers (used by routes)
│   │   └── crud_sync.py         # Sync CRUD helpers (used by scripts)
│   ├── planner.py               # Meal planning logic
│   ├── recipes.py               # Recipe dataclass
│   ├── shopping_list.py         # Shopping list generation
│   ├── shopping_normalizer.py   # LLM-based ingredient normalisation
│   ├── nutrition_generator.py   # USDA nutrition lookup
│   ├── tag_inference.py         # AI tag suggestions
│   ├── instagram_parser.py      # Instagram recipe extraction
│   ├── recipe_parser.py         # URL recipe scraping
│   └── templates/
│       └── index.html           # Single-page web UI
├── alembic/
│   ├── env.py
│   └── versions/
│       └── 001_initial_schema.py
├── scripts/
│   ├── generate_seed_sql.py     # Regenerates seed_recipes.sql from data/recipes.json
│   ├── seed_recipes.sql         # Pre-generated seed data (~850 recipes)
│   ├── import_spoonacular_daily.py
│   ├── import_themealdb.py
│   └── migrate_nutrition.py
├── tests/
│   ├── conftest.py
│   ├── test_planner.py
│   ├── test_cook_once.py
│   ├── test_shopping_list.py
│   └── integration/
│       ├── test_health.py
│       ├── test_recipes.py
│       ├── test_planner.py
│       ├── test_manual_plan.py
│       ├── test_shopping.py
│       └── test_import.py
├── data/
│   └── recipes.json             # Source of truth for seed data
├── pyproject.toml
├── uv.lock
└── .env.example
```

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Web UI |
| `GET` | `/health` | DB health check |
| `GET` | `/api/recipes` | Paginated recipe list (search, tags, sort, calorie/time filters) |
| `GET` | `/recipes` | Full recipe list (for plan generation) |
| `GET` | `/recipes/{id}` | Get a single recipe |
| `PUT` | `/recipes/{id}` | Update a recipe |
| `POST` | `/recipes` | Create a recipe |
| `POST` | `/generate` | Generate a new weekly plan |
| `POST` | `/generate-with-schedule` | Generate with custom schedule and servings |
| `GET` | `/current-plan` | Get the current plan + shopping list |
| `PUT` | `/current-plan/meals` | Swap a meal slot |
| `POST` | `/manual-plan/add-meal` | Add a meal to the plan |
| `POST` | `/manual-plan/remove-meal` | Remove a meal from the plan |
| `POST` | `/manual-plan/update-servings` | Change servings for a meal |
| `POST` | `/manual-plan/regenerate-meal` | Re-roll a single meal slot |
| `POST` | `/manual-plan/clear` | Clear the current plan |
| `POST` | `/shopping-list/update-item` | Edit a shopping list item |
| `POST` | `/shopping-list/delete-item` | Remove a shopping list item |
| `POST` | `/shopping-list/add-item` | Add an item manually |
| `GET` | `/excluded-ingredients` | Get excluded ingredient list |
| `POST` | `/excluded-ingredients` | Update excluded ingredient list |
| `POST` | `/import-recipe` | Import from URL or Instagram |
| `POST` | `/import-recipe-text` | Import from pasted text |
| `POST` | `/import-recipe-image` | Import from photo |
---

## Raspberry Pi Deployment

### Install

```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone and install deps
git clone <your-repo-url> meal-planner
cd meal-planner
uv sync

# Install and start PostgreSQL
sudo apt install postgresql
sudo systemctl enable --now postgresql
sudo -u postgres createdb mealplanner

# Configure
cp .env.example .env
# Edit .env with your DATABASE_URL, USDA_API_KEY, OPENAI_API_KEY

# Run migrations and seed
uv run alembic upgrade head
psql mealplanner -f scripts/seed_recipes.sql
```

### Systemd service

Create `/etc/systemd/system/meal-planner.service`:

```ini
[Unit]
Description=Meal Planner
After=network.target postgresql.service

[Service]
User=pi
WorkingDirectory=/home/pi/meal-planner
EnvironmentFile=/home/pi/meal-planner/.env
ExecStart=/home/pi/meal-planner/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now meal-planner

# Check status / logs
sudo systemctl status meal-planner
sudo journalctl -u meal-planner -f
```

Access from any device on your network at `http://<pi-ip>:8000`.

---

## Troubleshooting

**App won't start — missing API key**
```
RuntimeError: USDA_API_KEY environment variable is required.
```
Set the variable in your `.env` file or shell environment.

**Database connection error**
```
sqlalchemy.exc.OperationalError: connection refused
```
Make sure PostgreSQL is running (`brew services start postgresql@17` on macOS) and the `DATABASE_URL` in `.env` is correct.

**Port already in use**
```bash
lsof -i :8000   # find what's using the port
# or start on a different port:
uv run uvicorn app.main:app --port 8001
```

