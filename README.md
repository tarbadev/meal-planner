# Meal Planner

A local meal planning application that generates weekly meal plans from a recipe database and outputs to Google Sheets with shopping lists.

## Features

- Generate 7-day meal plans with no recipe repeats
- Automatic portion scaling for household size (default: 2.75 portions)
- Nutrition tracking (calories, protein, carbs, fat)
- **Automatic nutrition generation** from ingredients using USDA FoodData Central API
- **Recipe import from URLs** with automatic parsing
- Automated shopping list generation with ingredient aggregation
- Google Sheets integration for easy sharing
- Web UI for easy access
- Designed to run on Raspberry Pi

## Tech Stack

- Python 3.11+
- Flask (web framework)
- Google Sheets API (gspread)
- JSON file storage for recipes

## Quick Start

### 1. Clone and Setup

```bash
cd /path/to/meal-planner

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure USDA API Key (REQUIRED)

**The app will not start without this!**

```bash
# Get your free API key from:
# https://fdc.nal.usda.gov/api-key-signup.html

# Then set it as an environment variable:
export USDA_API_KEY='your-api-key-here'
```

See [SETUP.md](SETUP.md) for detailed configuration options.

### 4. Run the App

```bash
# Start the Flask server
python -m flask --app app.main run --host=0.0.0.0 --port=5000

# Access the web UI
open http://localhost:5000
```

### 5. Generate a Meal Plan

1. Open http://localhost:5000 in your browser
2. Click "Generate New Weekly Plan"
3. View your meal plan and shopping list

## How Automatic Nutrition Generation Works

When you import a recipe from a URL:
- If the recipe already has nutrition data, it's preserved
- If nutrition data is missing (common on many recipe sites), the app will:
  - Look up each ingredient in the USDA database
  - Calculate nutrition based on quantities
  - Generate per-serving values
  - Tag the recipe with "nutrition-generated" for your reference

**Note**: The app will not start without a valid API key configured.

## Google Sheets Setup (Optional)

To enable Google Sheets integration:

### 1. Create Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project
3. Enable the Google Sheets API

### 2. Create Service Account

1. Go to "APIs & Services" > "Credentials"
2. Click "Create Credentials" > "Service Account"
3. Fill in the details and create
4. Click on the created service account
5. Go to "Keys" tab > "Add Key" > "Create New Key" > JSON
6. Download the JSON file and save it as `credentials.json` in the project root

### 3. Create and Share Spreadsheet

1. Create a new Google Sheet
2. Copy the spreadsheet ID from the URL:
   - URL: `https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/edit`
3. Share the spreadsheet with the service account email (found in `credentials.json`)
   - Give it "Editor" permissions

### 4. Configure the App

Edit `config.py`:

```python
GOOGLE_SHEETS_ID = "your-spreadsheet-id-here"
CREDENTIALS_FILE = "credentials.json"
```

### 5. Write to Sheets

After generating a meal plan:

```bash
curl -X POST http://localhost:5000/write-to-sheets
```

Or use the web UI (if integrated).

## Configuration

Edit `config.py` to customize:

```python
# Google Sheets
GOOGLE_SHEETS_ID = "your-spreadsheet-id"
CREDENTIALS_FILE = "credentials.json"

# Household portions
HOUSEHOLD_PORTIONS = {
    "adults": 2,
    "child_4y": 0.5,
    "toddler": 0.25
}
TOTAL_PORTIONS = 2.75  # Sum of above

# Meal planning
MEALS_PER_WEEK = 7
RECIPES_FILE = "data/recipes.json"
```

## Project Structure

```
meal-planner/
├── app/
│   ├── __init__.py
│   ├── main.py              # Flask app
│   ├── recipes.py           # Recipe loading and validation
│   ├── planner.py           # Meal planning logic
│   ├── shopping_list.py     # Shopping list generation
│   ├── sheets.py            # Google Sheets integration
│   └── templates/
│       └── index.html       # Web UI
├── data/
│   └── recipes.json         # Recipe database (7 recipes)
├── tests/
│   ├── test_recipes.py
│   ├── test_planner.py
│   ├── test_shopping_list.py
│   └── test_sheets.py
├── config.py                # Configuration
├── requirements.txt
└── README.md
```

## Adding Recipes

Edit `data/recipes.json` to add new recipes:

```json
{
  "recipes": [
    {
      "id": "unique-recipe-id",
      "name": "Recipe Name",
      "servings": 4,
      "prep_time_minutes": 15,
      "cook_time_minutes": 30,
      "calories_per_serving": 450,
      "protein_per_serving": 25,
      "carbs_per_serving": 55,
      "fat_per_serving": 12,
      "tags": ["italian", "kid-friendly"],
      "ingredients": [
        {
          "item": "ground beef",
          "quantity": 500,
          "unit": "g",
          "category": "meat"
        }
      ]
    }
  ]
}
```

## API Endpoints

- `GET  /` - Web UI
- `POST /generate` - Generate new weekly plan
- `GET  /recipes` - List all available recipes
- `GET  /recipes/<id>` - Get a specific recipe
- `PUT  /recipes/<id>` - Update a recipe
- `POST /import-recipe` - Import recipe from URL with automatic nutrition generation
- `GET  /current-plan` - Get current weekly plan with shopping list
- `POST /write-to-sheets` - Write current plan to Google Sheets

### Importing Recipes

Import a recipe from any URL:

```bash
curl -X POST http://localhost:5000/import-recipe \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com/recipe"}'
```

The importer supports:
- Schema.org Recipe markup (most recipe sites)
- WP Recipe Maker plugin
- Generic HTML parsing (fallback)

Nutrition will be automatically generated if missing (requires USDA API key).

## Running Tests

```bash
# Activate virtual environment
source .venv/bin/activate

# Run all tests
python -m pytest tests/ -v

# Run specific test file
python -m pytest tests/test_planner.py -v

# Run with coverage
python -m pytest tests/ --cov=app --cov-report=html
```

Current test coverage: 40 tests passing

## Development

### Adding a New Feature

1. Write tests first (TDD approach)
2. Implement the feature
3. Run tests to verify
4. Commit with a descriptive message

### Code Style

- Use type hints throughout
- Keep functions small and testable
- Follow PEP 8 guidelines

## Raspberry Pi Deployment

### 1. Install on Pi

```bash
# SSH into your Pi
ssh pi@raspberrypi.local

# Clone the repository
git clone <your-repo-url> meal-planner
cd meal-planner

# Setup virtual environment
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Copy credentials if using Google Sheets
scp credentials.json pi@raspberrypi.local:~/meal-planner/
```

### 2. Create Systemd Service

Create `/etc/systemd/system/meal-planner.service`:

```ini
[Unit]
Description=Meal Planner Flask App
After=network.target

[Service]
User=pi
WorkingDirectory=/home/pi/meal-planner
Environment="PATH=/home/pi/meal-planner/.venv/bin"
Environment="USDA_API_KEY=your-api-key-here"
ExecStart=/home/pi/meal-planner/.venv/bin/python -m flask --app app.main run --host=0.0.0.0 --port=5000

[Install]
WantedBy=multi-user.target
```

**Note**: Replace `your-api-key-here` with your actual USDA API key for automatic nutrition generation.

### 3. Enable and Start Service

```bash
sudo systemctl daemon-reload
sudo systemctl enable meal-planner
sudo systemctl start meal-planner

# Check status
sudo systemctl status meal-planner

# View logs
sudo journalctl -u meal-planner -f
```

### 4. Access from Local Network

Find your Pi's IP address:

```bash
hostname -I
```

Access from any device on your network:
```
http://<pi-ip-address>:5000
```

## Troubleshooting

### Google Sheets Authentication Error

- Verify `credentials.json` is in the project root
- Check that the spreadsheet is shared with the service account email
- Ensure the spreadsheet ID in `config.py` is correct

### No Recipes Found

- Verify `data/recipes.json` exists and is valid JSON
- Check that the path in `config.py` is correct

### Port Already in Use

```bash
# Find process using port 5000
lsof -i :5000

# Kill the process
kill -9 <PID>

# Or use a different port
python -m flask --app app.main run --port=5001
```

## Future Enhancements

See `meal-planner-spec.md` for planned features:

- SQLite database for recipes
- Recipe CRUD in web UI (edit, delete)
- Nutrition targets/constraints
- Meal variety optimization
- Prep time constraints
- Leftover planning
- Cost tracking
- Manual ingredient-to-USDA food matching UI
- Nutrition confidence indicators in UI

## License

MIT License - feel free to use and modify!

## Contributing

Contributions welcome! Please:

1. Write tests for new features
2. Follow existing code style
3. Update documentation
4. Submit a pull request

## Support

For issues and questions, please open an issue on GitHub.
