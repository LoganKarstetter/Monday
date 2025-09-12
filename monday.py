# -------------------------------
# Imports
# -------------------------------
import os
import re
import requests

from dataclasses import dataclass, field
from datetime import date, timedelta, datetime
from typing import List, Optional
from zoneinfo import ZoneInfo

# -------------------------------
# Constants
# -------------------------------
API_KEY = ''
API_URL = 'https://api.monday.com/v2'
BOARD_NAME = ''
QUERY_LIMIT = 25
SERIES = ['First', 'Second', 'Third', 'Fourth', 'Fifth', 'Sixth', 'Seventh', 'Eighth', 'Ninth', 'Tenth', 'Eleventh', 'Twelfth']
WEEKDAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
LOCAL_TIMEZONE = ZoneInfo("America/Chicago")

# -------------------------------
# Data Models
# -------------------------------
@dataclass
class Column:
    """
    Represents a column in a Monday.com board.

    Attributes:
        id (str): Unique ID of the column.
        title (str): Human-readable name of the column.
    """
    id: str
    title: str

@dataclass
class Item:
    """
    Represents an item (row) in a Monday.com board.

    Attributes:
        id (str): Unique ID of the item.
        values (dict): Dictionary of column_id -> value for this item, including 'name'.
    """
    id: str
    values: dict

@dataclass
class Board:
    """
    Represents a Monday.com board.

    Attributes:
        id (str): Unique ID of the board.
        name (str): Human-readable name of the board.
        columns (List[Column]): List of columns in the board.
        items (List[Item]): List of items (rows) in the board.
    """
    id: str
    name: str
    columns: List[Column] = field(default_factory=list)
    items: List[Item] = field(default_factory=list)

# -------------------------------
# Classes
# -------------------------------
class MondayClient():
    """Client for interacting with the Monday.com API."""

    def __init__(self, api_key: str):
        """
        Initialize the client.

        Args:
            api_key (str): API key for authenticating with Monday.com.
        """
        self.headers = {'Authorization': api_key}

    def post_query(self, query: str) -> dict:
        """
        Send a GraphQL query or mutation to the Monday.com API.

        Args:
            query (str): GraphQL query or mutation string.

        Returns:
            dict: The 'data' field from the API response.

        Raises:
            Exception: If the API returns errors.
        """
        response = requests.post(API_URL, json={'query': query}, headers=self.headers)
        data = response.json()
        if 'errors' in data:
            raise Exception(data)
        return data.get('data')
    
    def get_board_id(self, board_name: str) -> Optional[str]:
        """
        Fetch the ID of a board by its name.

        Args:
            board_name (str): The name of the board to search for.

        Returns:
            Optional[str]: The ID of the board if found, otherwise None.
        """
        page = 1
        while True:
            query = f'{{ boards (limit: {QUERY_LIMIT}, page: {page}) {{ id name }} }}'
            data = self.post_query(query)
            boards = data.get('boards', [])

            for board_dict in boards:
                if board_dict.get('name') == board_name:
                    return board_dict.get('id')
            
            if len(boards) < QUERY_LIMIT:
                return None
            page += 1

    def get_board(self, board_id: str) -> Optional[Board]:
        """
        Fetch a board by ID.

        Args:
            board_id (str): The ID of the board to retrieve.

        Returns:
            Optional[Board]: A Board object if found, otherwise None.
        """
        query = f'{{ boards (ids: {board_id}) {{ name columns {{ id title }} }} }}'
        data = self.post_query(query)
        boards = data.get('boards', [])

        if len(boards):
            board_dict = boards[0]
            columns = [Column(column.get('id'), column.get('title')) for column in board_dict.get('columns', [])]
            return Board(board_id, board_dict.get('name'), columns)
        return None

    def get_items(self, board: Board):
        """
        Load items for a board and store them in the board object.

        Args:
            board (Board): The board to populate with items.
        """
        cursor = None
        while True:
            if cursor:
                query = f'{{ next_items_page (limit: {QUERY_LIMIT}, cursor: \"{cursor}\") {{ cursor items {{ id name column_values {{ id text }} }} }} }}'
                data = self.post_query(query)
                items_page = data.get('next_items_page', {})
            else:
                query = f'{{ boards (ids: {board.id}) {{ items_page (limit: {QUERY_LIMIT}) {{ cursor items {{ id name column_values {{ id text }} }} }} }} }}'
                data = self.post_query(query)
                items_page = data.get('boards', [])[0].get('items_page', {})

            items = items_page.get('items', [])
            for item in items:
                values = {column.get('id'): column.get('text') for column in item.get('column_values', [])} | {'name': item.get('name')}
                board.items.append(Item(item.get('id'), values))

            cursor = items_page.get('cursor')
            if not cursor:
                return

    def update_column_value(self, board_id: str, item_id: str, column_id: str, json_value: str):
        """
        Update a column value for a specific item on a board.

        Args:
            board_id (str): ID of the board containing the item.
            item_id (str): ID of the item to update.
            column_id (str): ID of the column to update.
            json_value (str): JSON-encoded value for the column.

        Returns:
            dict: API response from the mutation.
        """
        mutation = f'mutation {{ change_column_value (board_id: {board_id}, item_id: {item_id}, column_id: \"{column_id}\", value: \"{json_value}\") {{ id name }} }}'
        return self.post_query(mutation)

# -------------------------------
# Utility Classes
# -------------------------------
class Scheduler():
    """Provides static methods for calculating dates."""

    @staticmethod
    def get_next_weekday(weekday: str, from_date: date) -> date:
        """
        Get the next occurrence of a specific weekday from a given date.

        Args:
            weekday (str): Name of the weekday (e.g., "Monday").
            from_date (date): Date to start calculation from.

        Returns:
            date: Date of the next occurrence of the weekday.
        """
        days_until_next = (WEEKDAYS.index(weekday) - from_date.weekday() + len(WEEKDAYS)) % len(WEEKDAYS)
        return from_date + timedelta(days=days_until_next)
    
    @staticmethod
    def get_first_day_next_month(from_date: date) -> date:
        """
        Get the first day of the month following the given date.

        Args:
            from_date (date): Date to calculate from.

        Returns:
            date: First day of the next month.
        """
        # If the month is December (12), go to next year
        if from_date.month == 12:
            return date(year=from_date.year + 1, month=1, day=1)
        return date(year=from_date.year, month=from_date.month + 1, day=1)

    @staticmethod
    def get_next_every_other_weekday(weekday: str, today_date: date, existing_date: date) -> date:
        """
        Calculate the next date for an "Every Other <Weekday>" schedule.

        Args:
            weekday (str): Weekday name.
            today_date (date): Today's date.
            existing_date (date): Last scheduled date.

        Returns:
            date: Next scheduled date.
        """
        # Get the next date the weekday occurs
        next_weekday = Scheduler.get_next_weekday(weekday, today_date)

        # If less than a week passed since the existing date, skip a week forward
        days_passed = today_date - existing_date
        if days_passed.days < len(WEEKDAYS):
            next_weekday += timedelta(days=len(WEEKDAYS))

        return next_weekday

    @staticmethod
    def get_next_every_nth_weekday(weekday: str, today_date: date, n: int):
        """
        Get the date for the nth occurrence of a weekday in a month. 
        Accurate results are not guaranteed for n >= 5.

        Args:
            weekday (str): Weekday name.
            today_date (date): Current date.
            n (int): Occurrence number (1-based).

        Returns:
            date: Date of the nth occurrence of the weekday.
        """
        # Get the first date the weekday occurs this month 
        first_weekday = Scheduler.get_next_weekday(weekday, today_date.replace(day=1))

        # Add the number of days in the week (7) for each n (non-zero indexed)
        nth_weekday = first_weekday
        if n != 1:
            nth_weekday = first_weekday + timedelta(days=len(WEEKDAYS) * (n - 1))

        # If the nth weekday has passed, re-calculate for the next month
        if nth_weekday < today_date:
            first_weekday = Scheduler.get_next_weekday(weekday, Scheduler.get_first_day_next_month(today_date))

            nth_weekday = first_weekday
            if n != 1:
                nth_weekday = first_weekday + timedelta(days=len(WEEKDAYS) * (n - 1))

        return nth_weekday

    @staticmethod
    def get_next_date(frequency: str, existing_date: date) -> date:
        """
        Calculate the next scheduled date for a given frequency string.

        Args:
            frequency (str): Human-readable frequency (e.g., "Every Monday", "Every First Tuesday").
            existing_date (date): Currently scheduled date.

        Returns:
            Optional[date]: Next scheduled date, or None if unable to calculate.
        """
        today = date.today()
        frequency = frequency.strip()

        # Monday|Tuesday|Wednesday|...
        weekdays_pattern = '|'.join(WEEKDAYS)

        # First|Second|Third|Fourth|Fifth|...
        series_5_pattern = '|'.join(SERIES[:5])
        series_12_pattern = '|'.join(SERIES)

        # Regex patterns including only valid weekdays, ignoring leading/trailing whitespace
        nth_day_pattern = re.compile(rf'({series_5_pattern})\s+({weekdays_pattern})', re.IGNORECASE)
        nth_month_pattern = re.compile(rf'({series_12_pattern})\s+Month', re.IGNORECASE)
        other_pattern = re.compile(rf'Every\s+Other\s+({weekdays_pattern})', re.IGNORECASE)
        last_pattern = re.compile(rf'Every\s+Last\s+({weekdays_pattern})', re.IGNORECASE)
        every_pattern = re.compile(rf'Every\s+({weekdays_pattern}|(,|and|or|\s*))+$', re.IGNORECASE)
        day_pattern = re.compile(r'(\d+)', re.IGNORECASE)

        # Check "Every First/Second/Third/Fourth/Fifth Weekday"
        match = nth_day_pattern.search(frequency)
        if match:
            n = series_5_pattern.index(match.group(1).capitalize()) + 1
            weekday = match.group(2)
            return Scheduler.get_next_every_nth_weekday(weekday, today, n)

        # Check "Every First/Second/Third/Fourth/Fifth/... Month"
        match = nth_month_pattern.search(frequency)
        if match:
            n = SERIES.index(match.group(1).capitalize()) + 1
            if existing_date > today:
                return existing_date
            
            # Check "Xth, Yth, and/or Zth"
            matches = day_pattern.findall(frequency)
            if matches:
                # Get the first day, casting to int is safe because of regex
                day = min([int(day) for day in matches])

                # Set the day to a day every month has (1), skip n months forward
                closest_date = today.replace(day=1)
                for _ in range(n):
                    closest_date = Scheduler.get_first_day_next_month(closest_date)

                try:
                    closest_date = closest_date.replace(day=day)
                except ValueError:
                    # Thrown if date.replace() tried to set a day greater than the number of days in the month
                    # Get the last day of this month (this month isn't over, so the next_date < today doesn't apply)
                    closest_date = Scheduler.get_first_day_next_month(closest_date) - timedelta(days=1)

                return closest_date

        # Check "Every Other Weekday"
        match = other_pattern.search(frequency)
        if match:
            weekday = match.group(1)
            if existing_date > today:
                return existing_date
            return Scheduler.get_next_every_other_weekday(weekday, today, existing_date)

        # Check "Every Last Weekday"
        match = last_pattern.search(frequency)
        if match:
            weekday = match.group(1)

            # Return the closest date to today
            fourth_weekday = Scheduler.get_next_every_nth_weekday(weekday, today, 4)
            fifth_weekday = Scheduler.get_next_every_nth_weekday(weekday, today, 5)
            return min(fourth_weekday, fifth_weekday)
        
        # Check "Every Weekday, Weekday, and/or Weekday"
        match = every_pattern.search(frequency)
        if match:
            closest_weekday = None
            for weekday in WEEKDAYS:
                if weekday.casefold() in frequency.casefold():
                    next_weekday = Scheduler.get_next_weekday(weekday, today)

                    if not closest_weekday or next_weekday < closest_weekday:
                        closest_weekday = next_weekday

            return closest_weekday

        # Check "The Xth, Yth, and/or Zth of the month"
        matches = day_pattern.findall(frequency)
        if matches:
            # Get the days, casting to int is safe because of regex
            days = [int(day) for day in matches]

            closest_date = None
            for day in days:
                try:
                    # Get the date for this month
                    next_date = today.replace(day=day)

                    # If the date has passed, get the date for next month
                    if next_date < today:
                        next_date = Scheduler.get_first_day_next_month(today).replace(day=day)
                except ValueError:
                    # Thrown if date.replace() tried to set a day greater than the number of days in the month
                    # Get the last day of this month (this month isn't over, so the next_date < today doesn't apply)
                    next_date = Scheduler.get_first_day_next_month(today) - timedelta(days=1)

                if not closest_date or next_date < closest_date:
                    closest_date = next_date

            return closest_date

        # Frequency did not match any patterns
        return None

if __name__ == '__main__':
    """
    Main script execution: fetches the specified board from Monday.com, loads its items, 
    calculates the next scheduled date for each item based on its 'Frequency' column, 
    and updates the 'Next Time Added To Board' column if necessary.
    
    Workflow:
        1. Initialize MondayClient with API_KEY.
        2. Retrieve the board named BOARD_NAME.
        3. Load all items and their column values into the board object.
        4. Identify the 'Frequency', 'Next Time Added To Board', 'Due In X Days', and 'Due Date Added' columns.
        5. Iterate over each item:
            a. Validate that the column values are available.
            b. Calculate the new 'Next Time Added To Board' date.
            c. If the date has changed, update the column value on Monday.com.
            d. Print the result.
            e. Calculate the new 'Due Date Added' by adding 'Due In X Days' to the new 'Next Time Added To Board' date.
            f. Update the column value on Monday.com.
            g. Print the result.
    """
    # Try loading secrets from .env if they're not hardcoded in script
    if not API_KEY:
        try:
            from dotenv import load_dotenv
            load_dotenv()
            API_KEY = os.environ.get("MONDAY_API_KEY")
        except ImportError:
            print("Error: python-dotenv is not installed. Run `pip install python-dotenv` from command line.")
            exit(1)
        if not API_KEY:
            print("Error: MONDAY_API_KEY is not set in the environment or .env file.")
            exit(1)

    if not BOARD_NAME:
        try:
            from dotenv import load_dotenv
            load_dotenv()
            BOARD_NAME = os.environ.get("MONDAY_BOARD_NAME")
        except ImportError:
            print("Error: python-dotenv is not installed. Run `pip install python-dotenv` from command line.")
            exit(1)
        if not BOARD_NAME:
            print("Error: MONDAY_BOARD_NAME is not set in the environment or .env file.")
            exit(1)

    client = MondayClient(API_KEY)

    board_id = client.get_board_id(BOARD_NAME)
    if not board_id:
        raise ValueError(f'Error: \'{BOARD_NAME}\' board was not found')
    
    board = client.get_board(board_id)
    if not board:
        raise ValueError(f'Error: \'{BOARD_NAME}\' board with ID \'{board_id}\' was not found')

    client.get_items(board)

    frequency_column = next((column for column in board.columns if column.title == 'Frequency'), None)
    next_time_column = next((column for column in board.columns if column.title == 'Next Time Added To Board'), None)
    due_in_x_column = next((column for column in board.columns if column.title == 'Due In X Days'), None)
    due_date_column = next((column for column in board.columns if column.title == 'Due Date Added'), None)
    time_due_column = next((column for column in board.columns if column.title == 'Time Due'), None)

    if frequency_column and next_time_column and due_in_x_column and due_date_column: # Keeping 'Time Due' column optional
        for item in board.items:
            item_name = item.values.get('name', 'Unknown')

            # Get the 'Frequency' value
            frequency = item.values.get(frequency_column.id)
            if not frequency:
                print(f'Error {item_name}: \'Frequency\' is missing')
                continue

            # Get the 'Next Time Added To Board' value
            try:
                next_time_added_date = date.fromisoformat(item.values.get(next_time_column.id))
            except ValueError:
                print(f'Error {item_name}: \'Next Time Date Added\' has an invalid date: {next_time_added_date}')
                continue

            # Get the 'Due In X Days' value
            try:
                due_in_x_days = int(item.values.get(due_in_x_column.id))
            except:
                print(f'Error {item_name}: \'Due In X Days\' has a non-numerical value: {item.values.get(due_in_x_column.id)}')
                continue

            # Get the 'Due Date Added' value
            try:
                due_date_added_date = date.fromisoformat(item.values.get(due_date_column.id))
            except:
                due_date_added_date = None

            # Calculate the new 'Next Time Added To Board' value
            next_date = Scheduler.get_next_date(frequency, next_time_added_date)
            if not next_date:
                print(f'Error {item_name}: \'Frequency\' does not match supported patterns: {frequency}')
                continue

            if next_date != next_time_added_date:
                json_value = f'{{\\"date\\": \\"{next_date}\\"}}'
                client.update_column_value(board.id, item.id, next_time_column.id, json_value)

            print(f'Updated {item_name}: \'Next Time Date Added\': {next_time_added_date.strftime("%b %d")} -> {next_date.strftime("%b %d")}')

            # Calculate the new 'Due Date Added' value
            next_due_date = next_date + timedelta(days=due_in_x_days)

            # Calculate the 'Time Due' to add to board
            try:
                dt_str = f"{next_due_date} {item.values.get(time_due_column.id)}"  # e.g., '2025-09-12 08:30 AM'
                local_dt = datetime.strptime(dt_str, "%Y-%m-%d %I:%M %p").replace(tzinfo=LOCAL_TIMEZONE)
                utc_time_due = local_dt.astimezone(ZoneInfo("UTC")).time()
            except Exception as e:
                utc_time_due = None
                
            if utc_time_due:
                json_value = f'{{\\"date\\": \\"{next_due_date}\\", \\"time\\": \\"{utc_time_due.strftime("%H:%M:%S")}\\"}}'
            else:
                json_value = f'{{\\"date\\": \\"{next_due_date}\\"}}'
            client.update_column_value(board.id, item.id, due_date_column.id, json_value)

            print(f'Updated {item_name}: \'Due Date Added\': {due_date_added_date.strftime("%b %d") if due_date_added_date else 'Unknown'} -> {next_due_date.strftime("%b %d")}')