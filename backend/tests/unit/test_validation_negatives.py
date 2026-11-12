"""Regression: found by the mutation benchmark (backend/benchmarks/engine_and_validator.py).

Text writes a loss or a negative return with its digits only ("lost ₹6,470", "returned -0.9%":
the minus is not part of the number the validator reads). Before the fix, every such correct
sentence was rejected, so 90 of 1,548 correct texts fell back to the template.
"""

from app.insights.validation import validate_explanation


def _finding(evidence, measured=0.05, threshold=0.03):
    return {
        "measured_value": measured,
        "threshold": threshold,
        "evidence": evidence,
        "data_date": "2026-10-09",
    }


def test_a_loss_written_without_its_minus_sign_passes():
    f = _finding({"hurt_profit": -6470.0})
    ok, reason = validate_explanation("Bharat Digital Services Ltd lost ₹6,470.", f)
    assert ok, reason


def test_a_negative_return_passes():
    f = _finding({"portfolio_annualized": -0.009, "benchmark_annualized": 0.149})
    ok, reason = validate_explanation(
        "The portfolio returned -0.9% a year against 14.9% for the benchmark.", f
    )
    assert ok, reason


def test_a_wrong_number_is_still_rejected():
    f = _finding({"hurt_profit": -6470.0})
    assert not validate_explanation("It lost ₹6,480.", f)[0]
