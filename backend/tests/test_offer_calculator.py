from decimal import Decimal
import pytest

from app.services.offer_calculator import (
    calculate_monthly_installment,
    calculate_offer_amount,
)


def test_emi_case_1():
    """1. EMI for 200,000 principal, 18% APR, 24 months tenure."""
    emi = calculate_monthly_installment(
        principal=Decimal("200000.00"),
        apr_percent=Decimal("18.0000"),
        term_months=24,
    )
    assert emi == Decimal("9984.82")


def test_emi_case_2():
    """2. EMI for 200,000 principal, 16% APR, 36 months tenure."""
    emi = calculate_monthly_installment(
        principal=Decimal("200000.00"),
        apr_percent=Decimal("16.0000"),
        term_months=36,
    )
    assert emi == Decimal("7031.41")


def test_emi_case_3():
    """3. EMI for 150,000 principal, 20% APR, 18 months tenure."""
    emi = calculate_monthly_installment(
        principal=Decimal("150000.00"),
        apr_percent=Decimal("20.0000"),
        term_months=18,
    )
    assert emi == Decimal("9714.48")


def test_zero_interest_emi():
    """4. Zero-interest (0% APR) EMI."""
    emi = calculate_monthly_installment(
        principal=Decimal("120000.00"),
        apr_percent=Decimal("0.0000"),
        term_months=12,
    )
    assert emi == Decimal("10000.00")

    # Non-integer division check
    emi_fraction = calculate_monthly_installment(
        principal=Decimal("100000.00"),
        apr_percent=Decimal("0.0000"),
        term_months=3,
    )
    assert emi_fraction == Decimal("33333.33")


def test_round_half_up_behaviour():
    """5. Correct two-decimal ROUND_HALF_UP behaviour."""
    # Test a case where rounding direction matters
    # E.g. 1000 principal, 0% APR, 3 months = 333.3333... -> 333.33
    emi = calculate_monthly_installment(
        principal=Decimal("1000.00"),
        apr_percent=Decimal("0.0000"),
        term_months=3,
    )
    assert emi == Decimal("333.33")

    # 100 principal, 0% APR, 6 months = 16.6666... -> 16.67
    emi2 = calculate_monthly_installment(
        principal=Decimal("100.00"),
        apr_percent=Decimal("0.0000"),
        term_months=6,
    )
    assert emi2 == Decimal("16.67")


def test_invalid_zero_principal():
    """6. Invalid zero principal is rejected."""
    with pytest.raises(ValueError) as exc:
        calculate_monthly_installment(
            principal=Decimal("0.00"),
            apr_percent=Decimal("15.0000"),
            term_months=12,
        )
    assert "strictly positive" in str(exc.value)


def test_negative_principal():
    """7. Negative principal is rejected."""
    with pytest.raises(ValueError) as exc:
        calculate_monthly_installment(
            principal=Decimal("-50000.00"),
            apr_percent=Decimal("15.0000"),
            term_months=12,
        )
    assert "strictly positive" in str(exc.value)


def test_negative_apr():
    """8. Negative APR is rejected."""
    with pytest.raises(ValueError) as exc:
        calculate_monthly_installment(
            principal=Decimal("100000.00"),
            apr_percent=Decimal("-1.0000"),
            term_months=12,
        )
    assert "between 0 and 100 inclusive" in str(exc.value)


def test_apr_above_100():
    """9. APR above 100 is rejected."""
    with pytest.raises(ValueError) as exc:
        calculate_monthly_installment(
            principal=Decimal("100000.00"),
            apr_percent=Decimal("100.0001"),
            term_months=12,
        )
    assert "between 0 and 100 inclusive" in str(exc.value)


def test_zero_term():
    """10. Zero term in months is rejected."""
    with pytest.raises(ValueError) as exc:
        calculate_monthly_installment(
            principal=Decimal("100000.00"),
            apr_percent=Decimal("15.0000"),
            term_months=0,
        )
    assert "between 1 and 360 inclusive" in str(exc.value)


def test_term_above_360():
    """11. Term in months above 360 is rejected."""
    with pytest.raises(ValueError) as exc:
        calculate_monthly_installment(
            principal=Decimal("100000.00"),
            apr_percent=Decimal("15.0000"),
            term_months=361,
        )
    assert "between 1 and 360 inclusive" in str(exc.value)


def test_calculate_offer_amount_when_requested_below_max():
    """12. Calculate offer amount when requested is below maximum permitted."""
    amount = calculate_offer_amount(
        requested_amount=Decimal("150000.00"),
        maximum_amount=Decimal("250000.00"),
    )
    assert amount == Decimal("150000.00")


def test_calculate_offer_amount_when_requested_above_max():
    """13. Calculate offer amount when requested is above maximum permitted."""
    amount = calculate_offer_amount(
        requested_amount=Decimal("300000.00"),
        maximum_amount=Decimal("250000.00"),
    )
    assert amount == Decimal("250000.00")


def test_reject_invalid_offer_amounts():
    """14. Reject non-positive or invalid offer amounts."""
    with pytest.raises(ValueError) as exc1:
        calculate_offer_amount(
            requested_amount=Decimal("0.00"),
            maximum_amount=Decimal("100000.00"),
        )
    assert "Requested loan amount must be positive" in str(exc1.value)

    with pytest.raises(ValueError) as exc2:
        calculate_offer_amount(
            requested_amount=Decimal("50000.00"),
            maximum_amount=Decimal("-1000.00"),
        )
    assert "Policy maximum loan amount must be positive" in str(exc2.value)
