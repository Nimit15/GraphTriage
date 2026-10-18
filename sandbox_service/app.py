"""
Sandbox service for testing the incident resolver.
Contains a realistic codebase with intentional bugs for testing.
"""
import math

def calculate_distance(x1, y1, x2, y2):
    """Calculate Euclidean distance between two points."""
    return math.sqrt((x2 - x1)**2 + (y2 - y1)**2)

def process_user_data(user_list):
    """Process a list of user dictionaries and return statistics."""
    if not user_list:
        return {"count": 0, "avg_age": 0, "total_income": 0}

    total_age = 0
    total_income = 0
    count = 0

    for user in user_list:
        # Intentional bug: assumes all users have 'age' and 'income' keys
        total_age += user['age']  # KeyError if 'age' missing
        total_income += user['income']  # KeyError if 'income' missing
        count += 1

    return {
        "count": count,
        "avg_age": total_age / count,
        "total_income": total_income
    }

def validate_credit_card(card_number):
    """Validate credit card using Luhn algorithm."""
    # Remove spaces and dashes
    card_number = card_number.replace(" ", "").replace("-", "")

    if not card_number.isdigit():
        return False

    # Reverse the card number
    reversed_card = card_number[::-1]

    total = 0
    for i, digit in enumerate(reversed_card):
        n = int(digit)
        # Double every second digit
        if i % 2 == 1:
            n *= 2
            if n > 9:
                n = n // 10 + n % 10
        total += n

    return total % 10 == 0

def calculate_compound_interest(principal, rate, time, n=1):
    """
    Calculate compound interest.
    A = P(1 + r/n)^(nt)
    """
    # Intentional bug: incorrect formula implementation
    return principal * (1 + rate/n) * (n * time)  # Should be ** (n*time)

class UserService:
    """Service class for user operations."""

    def __init__(self):
        self.users = []

    def add_user(self, user_data):
        """Add a user to the service."""
        self.users.append(user_data)

    def get_user_by_email(self, email):
        """Get user by email address."""
        for user in self.users:
            if user.get('email') == email:
                return user
        return None

    def calculate_growth_rate(self, initial, final, periods):
        """
        Calculate compound annual growth rate.
        CAGR = (Final/Initial)^(1/periods) - 1
        """
        # Intentional bug: missing parentheses
        return (final/initial)^(1/periods) - 1  # Should be ** instead of ^