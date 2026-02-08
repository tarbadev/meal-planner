import pytest
from unittest.mock import Mock, MagicMock, patch
from pathlib import Path

from app.sheets import SheetsWriter, SheetsError
from app.planner import PlannedMeal, WeeklyPlan
from app.recipes import Recipe
from app.shopping_list import ShoppingList, ShoppingListItem


@pytest.fixture
def sample_weekly_plan():
    recipe1 = Recipe(
        id="recipe-1",
        name="Test Recipe 1",
        servings=4,
        prep_time_minutes=10,
        cook_time_minutes=20,
        calories_per_serving=400,
        protein_per_serving=20,
        carbs_per_serving=50,
        fat_per_serving=10,
        tags=["tag1"],
        ingredients=[{"item": "pasta", "quantity": 400, "unit": "g", "category": "pantry"}]
    )

    meals = [
        PlannedMeal(day="Monday", meal_type="dinner", recipe=recipe1, household_portions=2.75)
        for _ in range(7)
    ]

    return WeeklyPlan(meals=meals)


@pytest.fixture
def sample_shopping_list():
    return ShoppingList(items=[
        ShoppingListItem(item="pasta", quantity=400, unit="g", category="pantry"),
        ShoppingListItem(item="onion", quantity=2, unit="whole", category="produce"),
        ShoppingListItem(item="chicken", quantity=500, unit="g", category="meat"),
    ])


class TestSheetsWriter:
    @patch('app.sheets.Credentials')
    @patch('app.sheets.gspread')
    @patch('app.sheets.Path.exists', return_value=True)
    def test_sheets_writer_initialization(self, mock_exists, mock_gspread, mock_creds):
        mock_creds.from_service_account_file.return_value = Mock()
        mock_client = Mock()
        mock_gspread.authorize.return_value = mock_client
        mock_client.open_by_key.return_value = Mock()

        writer = SheetsWriter(
            credentials_file="test_creds.json",
            spreadsheet_id="test-sheet-id"
        )

        assert writer.spreadsheet_id == "test-sheet-id"

    def test_sheets_writer_raises_error_if_credentials_missing(self):
        with patch('app.sheets.Path.exists', return_value=False):
            with pytest.raises(SheetsError) as exc_info:
                SheetsWriter(
                    credentials_file="nonexistent.json",
                    spreadsheet_id="test-id"
                )
            assert "credentials" in str(exc_info.value).lower()

    @patch('app.sheets.Credentials')
    @patch('app.sheets.gspread')
    @patch('app.sheets.Path.exists', return_value=True)
    def test_write_meal_plan_creates_worksheet_data(
        self, mock_exists, mock_gspread, mock_creds, sample_weekly_plan
    ):
        # Setup mocks
        mock_creds.from_service_account_file.return_value = Mock()

        mock_client = Mock()
        mock_gspread.authorize.return_value = mock_client

        mock_spreadsheet = Mock()
        mock_client.open_by_key.return_value = mock_spreadsheet

        mock_worksheet = Mock()
        mock_spreadsheet.worksheet.return_value = mock_worksheet

        # Create writer and write plan
        writer = SheetsWriter(
            credentials_file="test_creds.json",
            spreadsheet_id="test-id"
        )
        writer.write_meal_plan(sample_weekly_plan)

        # Verify worksheet operations
        mock_spreadsheet.worksheet.assert_called()
        mock_worksheet.clear.assert_called()
        mock_worksheet.update.assert_called()

    @patch('app.sheets.Credentials')
    @patch('app.sheets.gspread')
    @patch('app.sheets.Path.exists', return_value=True)
    def test_write_shopping_list_creates_worksheet_data(
        self, mock_exists, mock_gspread, mock_creds, sample_shopping_list
    ):
        # Setup mocks
        mock_creds.from_service_account_file.return_value = Mock()

        mock_client = Mock()
        mock_gspread.authorize.return_value = mock_client

        mock_spreadsheet = Mock()
        mock_client.open_by_key.return_value = mock_spreadsheet

        mock_worksheet = Mock()
        mock_spreadsheet.worksheet.return_value = mock_worksheet

        # Create writer and write shopping list
        writer = SheetsWriter(
            credentials_file="test_creds.json",
            spreadsheet_id="test-id"
        )
        writer.write_shopping_list(sample_shopping_list)

        # Verify worksheet operations
        mock_spreadsheet.worksheet.assert_called()
        mock_worksheet.clear.assert_called()
        mock_worksheet.update.assert_called()

    @patch('app.sheets.Credentials')
    @patch('app.sheets.gspread')
    @patch('app.sheets.Path.exists', return_value=True)
    def test_write_all_writes_both_sheets(
        self, mock_exists, mock_gspread, mock_creds,
        sample_weekly_plan, sample_shopping_list
    ):
        # Setup mocks
        mock_creds.from_service_account_file.return_value = Mock()

        mock_client = Mock()
        mock_gspread.authorize.return_value = mock_client

        mock_spreadsheet = Mock()
        mock_client.open_by_key.return_value = mock_spreadsheet

        mock_worksheet = Mock()
        mock_spreadsheet.worksheet.return_value = mock_worksheet

        # Create writer and write all
        writer = SheetsWriter(
            credentials_file="test_creds.json",
            spreadsheet_id="test-id"
        )
        result = writer.write_all(sample_weekly_plan, sample_shopping_list)

        # Should write to two different worksheets
        assert mock_spreadsheet.worksheet.call_count == 2
        assert result["success"] is True
        assert "url" in result

    @patch('app.sheets.Credentials')
    @patch('app.sheets.gspread')
    @patch('app.sheets.Path.exists', return_value=True)
    def test_write_creates_worksheets_if_missing(
        self, mock_exists, mock_gspread, mock_creds, sample_weekly_plan
    ):
        # Setup mocks
        mock_creds.from_service_account_file.return_value = Mock()

        mock_client = Mock()
        mock_gspread.authorize.return_value = mock_client

        mock_spreadsheet = Mock()
        mock_client.open_by_key.return_value = mock_spreadsheet

        # Simulate worksheet not found, then create it
        from gspread.exceptions import WorksheetNotFound
        mock_spreadsheet.worksheet.side_effect = [
            WorksheetNotFound("not found"),
        ]
        mock_new_worksheet = Mock()
        mock_spreadsheet.add_worksheet.return_value = mock_new_worksheet

        # Create writer and write plan
        writer = SheetsWriter(
            credentials_file="test_creds.json",
            spreadsheet_id="test-id"
        )
        writer.write_meal_plan(sample_weekly_plan)

        # Verify worksheet was created
        mock_spreadsheet.add_worksheet.assert_called()
