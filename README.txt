Monday.py

Rules:
- Requires a Monday.com board with a 'Frequency', 'Next Time Added To Board', 'Due In X Days', and 'Due Date Added' column.
- The value of the 'Frequency' column must match one of the patterns described below. 
- The value of the 'Next Time Added To Board' column must be a date.
- The value of the 'Due In X Days' column must be a number.
- The value of the 'Due Date Added' column can be empty or a date.

Frequency Patterns:
- Every Monday, Tuesday, Wednesday, Thursday, Friday, Saturday, or Sunday
    - Can use any number of weekdays
    - Commas, "or", and "and" are not required

- Every Other Monday 
    - Can use any single weekday
    - Calculates "Other" based on the "Next Time Added To Board" column

- Every First Monday
    - Can use First, Second, Third, Fourth, Fifth
    - Can use any single weekday

- Every Last Monday
    - Can use any single weekday

- The 1st, 2nd, and 3rd of the Month
    - Can use any number of days
    - Commas, "or", and "and" are not required
    - Prefixes are not required ("st", "nd", "rd", etc.)

- The 1st, 2nd, and 3rd of Every First Month
    - Can use any number of days
    - Commas, "or", and "and" are not required
    - Can use First, Second, Third, Fourth, Fifth, Sixth, Seventh, Eighth, Ninth, Tenth, Eleventh, or Twelfth
    - Calculates "First, Second, Third..." based on the "Next Time Added To Board" column
