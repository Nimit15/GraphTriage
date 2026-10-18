"""
Failing incident test with realistic stack trace.
Simulates a production bug scenario where:
1. process_user_data fails with KeyError when user data missing 'income' field
2. UserService.calculate_growth_rate fails using XOR instead of power operator
3. calculate_compound_interest missing exponentiation

Run with: pytest sandbox_service/test_failing_incident.py -v
"""
import pytest
from sandbox_service.app import process_user_data, UserService, calculate_compound_interest


# --- Incident Scenario: Missing 'income' field causes KeyError ---

def test_incident_process_user_data_missing_income():
    """
    Incident: process_user_data raises KeyError when user records lack 'income'.

    Stack trace:
        File "/app/sandbox_service/app.py", line 14, in process_user_data
            total_income += user['income']  # KeyError: 'income'
    KeyError: 'income'

    Expected fix: Use user.get('income', 0) to handle missing fields gracefully.
    """
    users = [
        {"name": "Alice", "age": 30},      # Missing 'income'
        {"name": "Bob", "age": 40, "income": 60000},
    ]
    result = process_user_data(users)
    assert result["count"] == 2
    assert result["total_income"] == 60000


# --- Incident Scenario: XOR operator used instead of power ---

def test_incident_calculate_growth_rate_xor_bug():
    """
    Incident: UserService.calculate_growth_rate uses XOR (^) instead of power (**).

    Stack trace:
        File "/app/sandbox_service/app.py", line 52, in calculate_growth_rate
            return (final/initial)^(1/periods) - 1

    Expected fix: Use ** operator instead of ^ for exponentiation.
    """
    service = UserService()
    result = service.calculate_growth_rate(100, 121, 2)
    # Expected: (121/100)^(1/2) - 1 = 1.1 - 1 = 0.1
    assert result == pytest.approx(0.1, rel=1e-3)


# --- Incident Scenario: Missing exponentiation in compound interest ---

def test_incident_compound_interest_missing_exponentiation():
    """
    Incident: calculate_compound_interest missing exponentiation operator.

    Stack trace:
        File "/app/sandbox_service/app.py", line 43, in calculate_compound_interest
            return principal * (1 + rate/n) * (n * time)

    Expected fix: Use ** operator: principal * (1 + rate/n) ** (n * time)
    """
    result = calculate_compound_interest(1000, 0.05, 2, n=1)
    # Expected: 1000 * (1.05)**(1*2) = 1102.5
    assert result == pytest.approx(1102.5, rel=1e-3)