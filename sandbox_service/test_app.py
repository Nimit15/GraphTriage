"""
Test suite for sandbox_service/app.py.
Contains intentionally failing tests for incident resolver testing.
"""
import pytest
from sandbox_service.app import (
    calculate_distance,
    process_user_data,
    validate_credit_card,
    calculate_compound_interest,
    UserService,
)


def test_calculate_distance():
    """Test Euclidean distance calculation."""
    result = calculate_distance(0, 0, 3, 4)
    assert result == 5.0


def test_process_user_data_with_valid_users():
    """Test processing valid user data."""
    users = [
        {"name": "Alice", "age": 30, "income": 50000},
        {"name": "Bob", "age": 40, "income": 60000},
    ]
    result = process_user_data(users)
    assert result["count"] == 2
    assert result["avg_age"] == 35.0
    assert result["total_income"] == 110000


def test_process_user_data_with_missing_field():
    """Test processing user data with missing required field.
    This test SHOULD FAIL - demonstrating the bug in process_user_data.
    """
    users = [
        {"name": "Alice", "age": 30},  # Missing 'income' field
        {"name": "Bob", "age": 40, "income": 60000},
    ]
    # This will raise KeyError because 'income' is missing
    result = process_user_data(users)
    assert result["count"] == 2


def test_validate_credit_card_valid():
    """Test valid credit card number."""
    assert validate_credit_card("4532015112830366") is True


def test_validate_credit_card_invalid():
    """Test invalid credit card number."""
    assert validate_credit_card("1234567890123456") is False


def test_calculate_compound_interest():
    """Test compound interest calculation.
    This test SHOULD FAIL - demonstrating the bug in calculate_compound_interest.
    """
    # Expected: P(1 + r/n)^(n*t)
    # Actual: P(1 + r/n) * (n*t) - missing exponentiation
    result = calculate_compound_interest(1000, 0.05, 2, n=1)
    # Correct result should be 1000 * (1.05)^2 = 1102.5
    assert result == pytest.approx(1102.5, rel=1e-3)


def test_user_service_add_user():
    """Test adding user to service."""
    service = UserService()
    service.add_user({"name": "Test", "email": "test@example.com"})
    assert len(service.users) == 1


def test_user_service_get_user_by_email():
    """Test retrieving user by email."""
    service = UserService()
    service.add_user({"name": "Test", "email": "test@example.com"})
    user = service.get_user_by_email("test@example.com")
    assert user is not None
    assert user["name"] == "Test"


def test_user_service_calculate_growth_rate():
    """Test CAGR calculation.
    This test SHOULD FAIL - demonstrating the bug in calculate_growth_rate.
    """
    service = UserService()
    # Expected: (final/initial)^(1/periods) - 1
    # Actual: (final/initial)^(1/periods) - 1 using XOR instead of power
    result = service.calculate_growth_rate(100, 121, 2)
    # Correct result: (121/100)^(1/2) - 1 = 1.1 - 1 = 0.1 (10%)
    assert result == pytest.approx(0.1, rel=1e-3)


def test_process_user_data_empty():
    """Test processing empty user list."""
    result = process_user_data([])
    assert result["count"] == 0
    assert result["avg_age"] == 0
    assert result["total_income"] == 0