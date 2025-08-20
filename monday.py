# -------------------------------
# Imports
# -------------------------------
import re
import requests

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import List, Optional

# -------------------------------
# Constants
# -------------------------------
API_KEY = ""
API_URL = "https://api.monday.com/v2"
BOARD_NAME = ""
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

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
        return data['data']
    
    def get_board(self, board_name: str) -> Optional[Board]:
        """
        Fetch a board by name.

        Args:
            board_name (str): Name of the board to retrieve.

        Returns:
            Optional[Board]: Board object if found, else None.
        """
        query = '{ boards { id name columns { id title } } }'
        data = self.post_query(query)

        for board_dict in data['boards']:
            if board_dict['name'] == board_name:
                columns = [Column(column['id'], column['title']) for column in board_dict['columns']]
                return Board(board_dict['id'], board_name, columns)
        return None
    
    def get_items(self, board: Board):
        """
        Load items for a board and store them in the board object.

        Args:
            board (Board): The board to populate with items.
        """
        query = f'{{ boards (ids: {board.id}) {{ items_page {{ items {{ id name column_values {{ id text }} }} }} }} }}'
        data = self.post_query(query)

        items = data['boards'][0]['items_page']['items']
        for item in items:
            values = {column['id']: column['text'] for column in item['column_values']} | {"name": item["name"]}
            board.items.append(Item(item['id'], values))

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

        # Regex patterns including only valid weekdays, ignoring leading/trailing whitespace
        nth_pattern = re.compile(rf'(First|Second|Third|Fourth|Fifth)\s+({weekdays_pattern})', re.IGNORECASE)
        other_pattern = re.compile(rf'Every\s+Other\s+({weekdays_pattern})', re.IGNORECASE)
        last_pattern = re.compile(rf'Every\s+Last\s+({weekdays_pattern})', re.IGNORECASE)
        every_pattern = re.compile(rf'Every\s+({weekdays_pattern}|(,|and|or|\s*))+', re.IGNORECASE)
        month_day_pattern = re.compile(r'([0-9]{1,2})+', re.IGNORECASE)

        # Check "Every First/Second/Third/Fourth/Fifth Weekday"
        match = nth_pattern.search(frequency)
        if match:
            nth_map = {"First": 1, "Second": 2, "Third": 3, "Fourth": 4, "Fifth": 5}
            n = nth_map[match.group(1).capitalize()]
            weekday = match.group(2)
            return Scheduler.get_next_every_nth_weekday(weekday, today, n)

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
            fourth_weekday = Scheduler.get_next_every_nth_weekday(weekday, today, 4)
            fifth_weekday = Scheduler.get_next_every_nth_weekday(weekday, today, 5)
            return fifth_weekday if fourth_weekday.month == fifth_weekday.month else fourth_weekday
        
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

        # Check "The Xth, Yth, and Zth of the month"
        matches = month_day_pattern.findall(frequency)
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
        4. Identify the 'Frequency' and 'Next Time Added To Board' columns.
        5. Iterate over each item:
            a. Validate that frequency and existing next-date are available.
            b. Calculate the next scheduled date using Scheduler.get_next_date().
            c. If the date has changed, update the column value on Monday.com.
            d. Print the result for each item.
    """
    client = MondayClient(API_KEY)

    board = client.get_board(BOARD_NAME)
    if not board:
        raise ValueError(f'Error: \'{BOARD_NAME}\' board was not found')

    client.get_items(board)

    frequency_column = next((column for column in board.columns if column.title == 'Frequency'), None)
    next_time_column = next((column for column in board.columns if column.title == 'Next Time Added To Board'), None)

    if frequency_column or not next_time_column:
        for item in board.items:
            item_name = item.values.get('name', 'Unknown')

            frequency = item.values.get(frequency_column.id)
            if not frequency:
                print(f'Error {item_name}: \'Frequency\' is missing')
                continue

            existing_date = date.fromisoformat(item.values.get(next_time_column.id))
            if not existing_date:
                print(f'Error {item_name}: \'Next Time Date Added\' is missing')
                continue

            next_date = Scheduler.get_next_date(frequency, existing_date)
            if not next_date:
                print(f'Error {item_name}: \'Frequency\' does not match supported patterns: {frequency}')
                continue

            if next_date != existing_date:
                json_value = f'{{\\"date\\": \\"{next_date}\\"}}'
                client.update_column_value(board.id, item.id, next_time_column.id, json_value)

            print(f'Updated {item_name}: \'Next Time Date Added\': {existing_date.strftime("%b %d")} -> {next_date.strftime("%b %d")}')
