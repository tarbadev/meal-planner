from pathlib import Path
from typing import Any

import gspread
from google.oauth2.service_account import Credentials
from gspread.exceptions import WorksheetNotFound

from app.planner import WeeklyPlan
from app.shopping_list import ShoppingList


class SheetsError(Exception):
    """Raised when there's an error with Google Sheets operations."""
    pass


class SheetsWriter:
    """Handles writing meal plans and shopping lists to Google Sheets."""

    MEAL_PLAN_SHEET = "Weekly Plan"
    SHOPPING_LIST_SHEET = "Shopping List"

    def __init__(self, credentials_file: str, spreadsheet_id: str):
        self.spreadsheet_id = spreadsheet_id
        self.credentials_file = Path(credentials_file)

        if not self.credentials_file.exists():
            raise SheetsError(
                f"Credentials file not found: {credentials_file}. "
                "Please follow the Google Sheets setup instructions."
            )

        # Authenticate with Google Sheets
        scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]

        creds = Credentials.from_service_account_file(
            str(self.credentials_file),
            scopes=scopes
        )

        self.client = gspread.authorize(creds)
        self.spreadsheet = self.client.open_by_key(spreadsheet_id)

    def _get_or_create_worksheet(self, title: str, rows: int = 100, cols: int = 10):
        """Get a worksheet by title, creating it if it doesn't exist."""
        try:
            return self.spreadsheet.worksheet(title)
        except WorksheetNotFound:
            return self.spreadsheet.add_worksheet(title=title, rows=rows, cols=cols)

    def write_meal_plan(self, weekly_plan: WeeklyPlan) -> None:
        """Write the weekly meal plan to the spreadsheet."""
        worksheet = self._get_or_create_worksheet(self.MEAL_PLAN_SHEET)

        # Clear existing data
        worksheet.clear()

        # Prepare header row
        headers = [
            "Day",
            "Meal",
            "Portions",
            "Calories",
            "Protein (g)",
            "Carbs (g)",
            "Fat (g)",
            "Prep Time (min)",
            "Cook Time (min)",
            "Total Time (min)"
        ]

        # Prepare meal rows
        rows = [headers]
        for meal in weekly_plan.meals:
            rows.append([
                meal.day,
                meal.recipe.name,
                f"{meal.portions:.2f}",
                f"{meal.calories:.0f}",
                f"{meal.protein:.0f}",
                f"{meal.carbs:.0f}",
                f"{meal.fat:.0f}",
                meal.recipe.prep_time_minutes,
                meal.recipe.cook_time_minutes,
                meal.recipe.total_time_minutes
            ])

        # Add summary rows
        rows.append([])  # Empty row
        rows.append(["WEEKLY TOTALS", "", "",
                     f"{weekly_plan.total_calories:.0f}",
                     f"{weekly_plan.total_protein:.0f}",
                     f"{weekly_plan.total_carbs:.0f}",
                     f"{weekly_plan.total_fat:.0f}"])

        rows.append(["DAILY AVERAGES", "", "",
                     f"{weekly_plan.avg_daily_calories:.0f}",
                     f"{weekly_plan.avg_daily_protein:.0f}",
                     f"{weekly_plan.avg_daily_carbs:.0f}",
                     f"{weekly_plan.avg_daily_fat:.0f}"])

        # Write to sheet
        worksheet.update(rows, "A1")

        # Format header row
        worksheet.format("A1:J1", {
            "backgroundColor": {"red": 0.2, "green": 0.6, "blue": 0.8},
            "textFormat": {"bold": True, "foregroundColor": {"red": 1, "green": 1, "blue": 1}}
        })

    def write_shopping_list(self, shopping_list: ShoppingList) -> None:
        """Write the shopping list to the spreadsheet."""
        worksheet = self._get_or_create_worksheet(self.SHOPPING_LIST_SHEET)

        # Clear existing data
        worksheet.clear()

        # Prepare header row
        headers = ["Category", "Item", "Quantity", "Unit"]

        # Prepare rows grouped by category
        rows = [headers]

        items_by_category = shopping_list.items_by_category()

        for category in sorted(items_by_category.keys()):
            items = items_by_category[category]

            # Add category header
            rows.append([category.upper(), "", "", ""])

            # Add items in this category
            for item in items:
                rows.append([
                    "",  # Empty category cell for items
                    item.item,
                    f"{item.quantity:.2f}",
                    item.unit
                ])

            # Add empty row between categories
            rows.append([])

        # Write to sheet
        worksheet.update(rows, "A1")

        # Format header row
        worksheet.format("A1:D1", {
            "backgroundColor": {"red": 0.2, "green": 0.6, "blue": 0.8},
            "textFormat": {"bold": True, "foregroundColor": {"red": 1, "green": 1, "blue": 1}}
        })

        # Format category headers (bold)
        # Note: This is a simplified version. In production, you'd iterate through
        # the rows to find category headers and format them individually.

    def write_all(self, weekly_plan: WeeklyPlan, shopping_list: ShoppingList) -> dict[str, Any]:
        """Write both the meal plan and shopping list to the spreadsheet.

        Returns a dict with success status and the spreadsheet URL.
        """
        try:
            self.write_meal_plan(weekly_plan)
            self.write_shopping_list(shopping_list)

            return {
                "success": True,
                "url": f"https://docs.google.com/spreadsheets/d/{self.spreadsheet_id}",
                "message": "Successfully wrote meal plan and shopping list to Google Sheets"
            }
        except Exception as e:
            raise SheetsError(f"Failed to write to Google Sheets: {e}") from e
