# Recipe Import Scripts

Automated scripts to build your recipe database using free APIs.

## Overview

- **`import_themealdb.py`**: One-time bulk import of ~300 recipes from TheMealDB
- **`import_spoonacular_daily.py`**: Daily import of 50 recipes from Spoonacular (free tier)

Both scripts automatically generate nutrition data and ensure variety across cuisines and meal types.

---

## Prerequisites

### 1. API Keys Required

#### For TheMealDB (Script 1)
- ✅ **No API key needed** - TheMealDB is completely free
- ✅ You already have USDA API key for nutrition generation

#### For Spoonacular (Script 2)
- ⚠️ **Requires Spoonacular API key** (free tier: 50 requests/day)
- Get your free key at: https://spoonacular.com/food-api/console#Dashboard

### 2. Python Environment

Make sure you're in your project directory with the virtual environment activated:

```bash
cd /Users/tony/workspace/meal-planner
source .venv/bin/activate  # Or your venv activation command
```

### 3. Environment Variables

Add your Spoonacular API key to your `.env` file:

```bash
# Add this line to your .env file
SPOONACULAR_API_KEY=your_spoonacular_key_here
```

---

## Script 1: TheMealDB Bulk Import

### What It Does

- Fetches **~300 recipes** from TheMealDB
- Generates nutrition data using USDA API
- Adds tags based on cuisine, category, and ingredients
- Skips duplicates (checks by recipe name)
- Takes ~20-30 minutes to complete (due to nutrition API rate limiting)

### How to Run

```bash
# From project root
python scripts/import_themealdb.py
```

### Expected Output

```
==============================================================
TheMealDB Recipe Import Script
==============================================================

Loading existing recipes from: data/recipes.json
Found 0 existing recipes

Fetching all recipes from TheMealDB...
------------------------------------------------------------
Found 14 categories: Beef, Chicken, Dessert, Lamb, Miscellaneous...

Fetching recipes from category: Beef
  Found 38 recipes in Beef
...

==============================================================
Processing and importing recipes...
==============================================================

📥 Importing: Beef and Mustard Pie
  ✅ Nutrition generated
  🏷️  Tags: beef, british, dinner, high-protein
  ✅ Imported successfully!

...

==============================================================
IMPORT SUMMARY
==============================================================
✅ Imported:    287 recipes
⏭️  Skipped:     13 recipes (already exist)
❌ Failed:      0 recipes
📚 Total in DB: 287 recipes
==============================================================
```

### Troubleshooting

**Problem**: "No recipes fetched from TheMealDB!"
- Check your internet connection
- TheMealDB API might be down (rare)

**Problem**: Many nutrition generation failures
- Check that USDA_API_KEY is set correctly
- USDA API has rate limits (~100 requests/minute)

**Problem**: Script takes too long
- This is normal! Nutrition generation is slow (~0.5s per recipe)
- Go grab a coffee ☕ - it'll finish in 20-30 minutes

---

## Script 2: Spoonacular Daily Import

### What It Does

- Fetches **50 recipes per day** from Spoonacular (free tier limit)
- Automatically rotates through:
  - 27 different cuisines (Italian, Mexican, Thai, etc.)
  - 14 meal types (dinner, dessert, breakfast, etc.)
  - 9 dietary preferences (vegan, keto, gluten-free, etc.)
- Tracks imported recipes to avoid duplicates across days
- Includes full nutrition data from Spoonacular (no USDA calls needed)
- Takes ~5-10 minutes per run

### How to Run

#### Option A: Manual Daily Run (Recommended to Start)

Run once per day manually:

```bash
# From project root
python scripts/import_spoonacular_daily.py
```

#### Option B: Automated Daily Run (Using Cron)

Set up a cron job to run automatically every day at 3 AM:

```bash
# Edit your crontab
crontab -e

# Add this line (adjust path to your project):
0 3 * * * cd /Users/tony/workspace/meal-planner && .venv/bin/python scripts/import_spoonacular_daily.py >> logs/spoonacular_import.log 2>&1
```

#### Option C: Automated on Railway (Cloud Deployment)

If your app is deployed on Railway, you can use Railway Cron:

1. Add to your Railway service:
   ```bash
   # Railway.json or railway.toml
   [cron]
   schedule = "0 3 * * *"
   command = "python scripts/import_spoonacular_daily.py"
   ```

2. Or use a separate worker service that runs the script

### Expected Output

```
======================================================================
Spoonacular Daily Recipe Import
Run Time: 2026-02-11 03:00:00
======================================================================

Loading existing recipes from: data/recipes.json
Found 287 existing recipes
Previously imported 0 Spoonacular recipes

🎲 Today's variety filters:
   Cuisine: italian
   Meal Type: main course
   Diet: None (general recipes)

======================================================================
Fetching recipes from Spoonacular...
======================================================================

Searching with offset 0...
📥 Importing: Pasta Carbonara
  🏷️  Tags: italian, pasta, main-course, dinner
  ✅ Imported successfully! (1/50)

📥 Importing: Chicken Parmesan
  🏷️  Tags: italian, chicken, main-course, dinner
  ✅ Imported successfully! (2/50)

...

======================================================================
DAILY IMPORT SUMMARY
======================================================================
✅ Imported:    50 recipes
⏭️  Skipped:     3 recipes (duplicates)
❌ Failed:      0 recipes
📚 Total in DB: 337 recipes
======================================================================
```

### Variety System

The script automatically rotates through filters each day:

- **Day 1**: Italian main courses, general diet
- **Day 2**: Asian side dishes, vegetarian
- **Day 3**: Mexican desserts, vegan
- **Day 4**: French appetizers, gluten-free
- ...and so on

This ensures your database has diverse recipes instead of all similar types.

### Tracking File

The script creates `scripts/spoonacular_imported.json` to track:
- Which Spoonacular recipe IDs have been imported
- Current variety rotation state
- Last update timestamp

**Don't delete this file!** It prevents re-importing the same recipes.

### Troubleshooting

**Problem**: "Error: OPENAI_API_KEY not configured"
- You need to set `SPOONACULAR_API_KEY` in your `.env` file
- Get a free key at: https://spoonacular.com/food-api/console#Dashboard

**Problem**: "Did not reach target of 50 recipes"
- Current variety filters may have limited recipes
- Many recipes might already be imported
- The script will use different filters tomorrow

**Problem**: "Rate limit exceeded"
- You've hit Spoonacular's daily limit (50 requests on free tier)
- Wait until tomorrow (resets at midnight UTC)
- Consider upgrading to paid plan if needed

**Problem**: Script runs multiple times per day accidentally
- The script will skip already-imported recipes
- Free tier limit is per day, not per run
- If you run 5 times, you only get 10 recipes per run (50 total/day)

---

## Recommended Workflow

### Week 1: Bootstrap Your Database

**Day 1** (Today):
```bash
# Import TheMealDB (one-time)
python scripts/import_themealdb.py

# Run first Spoonacular import
python scripts/import_spoonacular_daily.py
```

**Result**: ~337 recipes in your database

**Days 2-7**:
```bash
# Run daily
python scripts/import_spoonacular_daily.py
```

**End of Week 1**: ~637 recipes

### Month 1: Steady Growth

Run Spoonacular daily import every day (manually or automated).

**End of Month 1**: ~1,787 recipes (287 + 1,500 from Spoonacular)

### Month 6: Large Database

Continue daily imports.

**End of Month 6**: ~9,287 recipes (287 + 9,000 from Spoonacular)

### Year 1: Production-Ready Database

**End of Year 1**: ~18,537 recipes

---

## Monitoring & Maintenance

### Check Import Status

```bash
# See how many recipes you have
grep -o '"id":' data/recipes.json | wc -l

# Check Spoonacular tracking
cat scripts/spoonacular_imported.json
```

### View Logs (if using cron)

```bash
# Create logs directory first
mkdir -p logs

# View recent imports
tail -f logs/spoonacular_import.log
```

### Reset Spoonacular Tracking (if needed)

⚠️ **Only do this if you want to re-import recipes**

```bash
rm scripts/spoonacular_imported.json
```

---

## Cost Analysis

### Current Setup (Free)

- **TheMealDB**: $0 (completely free)
- **Spoonacular**: $0 (free tier, 50/day)
- **USDA API**: $0 (free, for nutrition)

**Total Cost**: $0/month

**Total Recipes After 1 Year**: ~18,500 recipes

### If You Want Faster Imports

Upgrade to Spoonacular paid plan:

- **Cook Plan** ($29/month): 1,500 recipes/day
  - Build 10,000+ recipes in **7 days**
  - Then cancel and keep recipes forever
  - One-time cost: $29

---

## Advanced: Customizing Variety

Want to focus on specific cuisines or meal types? Edit `import_spoonacular_daily.py`:

```python
# Line 23-50: Customize these lists
CUISINES = [
    "italian", "mexican", "thai"  # Only these cuisines
]

MEAL_TYPES = [
    "main course", "dessert"  # Only these types
]

DIETS = [
    "vegetarian", "vegan"  # Only these diets
]
```

---

## Questions?

- **How do I get my Spoonacular API key?**
  Visit https://spoonacular.com/food-api/console#Dashboard and sign up

- **Can I run both scripts at the same time?**
  Yes, but run TheMealDB first to get your starter set

- **What if I want more than 50 recipes per day?**
  Upgrade to Spoonacular paid plan or be patient with free tier

- **Can I import from other sources too?**
  Yes! You can still use your existing URL/text/image import features

- **Do I need to keep running these forever?**
  No - once you have enough recipes, you can stop. Recipes stay in your database

---

## Summary

1. ✅ Get Spoonacular API key (free): https://spoonacular.com/food-api/console#Dashboard
2. ✅ Add `SPOONACULAR_API_KEY` to `.env`
3. ✅ Run TheMealDB import (one-time): `python scripts/import_themealdb.py`
4. ✅ Run Spoonacular import (daily): `python scripts/import_spoonacular_daily.py`
5. ✅ Set up cron job (optional, for automation)
6. ✅ Wait and watch your database grow! 🚀

Your database will grow from 0 to 18,000+ recipes over the next year, completely free.
