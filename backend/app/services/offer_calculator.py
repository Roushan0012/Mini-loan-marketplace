from decimal import Decimal, ROUND_HALF_UP, getcontext

# Set Decimal precision high enough for exact intermediate power and division steps
getcontext().prec = 35


def calculate_monthly_installment(
    principal: Decimal,
    apr_percent: Decimal,
    term_months: int,
) -> Decimal:
    """Calculate the reducing-balance monthly installment (EMI) using exact Decimal arithmetic.

    Formula:
        EMI = P * r * (1 + r)^n / ((1 + r)^n - 1)

    where:
        P = principal loan amount
        r = monthly periodic interest rate = apr_percent / 1200
        n = loan tenure in months (term_months)

    Zero-Interest (0% APR) Handling:
        When apr_percent == 0, interest is zero and the installment simplifies to:
        EMI = P / n

    Financial Assumptions & Disclosures:
        - Nominal Annual Rate: apr_percent is treated as a simple nominal annual interest rate.
        - Reducing Balance: The formula assumes standard monthly reducing-balance amortisation.
        - No Ancillary Fees: Does not account for upfront processing fees, insurance premiums,
          origination charges, administrative costs, stamp duty, or applicable taxes.
        - Illustrative Training Model: All figures and calculations are designed strictly for
          educational and training simulation in software development. This does not constitute
          an actual loan quote, credit agreement, or regulatory Key Fact Statement (KFS).

    Validation:
        - principal > 0
        - 0 <= apr_percent <= 100
        - 1 <= term_months <= 360
        - Decimal arithmetic throughout, rounded to 2 decimal places using ROUND_HALF_UP.

    Raises:
        ValueError: If input parameters violate positive bounds or range limits.
    """
    if not isinstance(principal, Decimal):
        raise ValueError("Principal must be a Decimal instance.")
    if not isinstance(apr_percent, Decimal):
        raise ValueError("APR percent must be a Decimal instance.")
    if not isinstance(term_months, int) or isinstance(term_months, bool):
        raise ValueError("Term months must be an integer.")

    if principal <= Decimal("0"):
        raise ValueError(f"Principal loan amount must be strictly positive, got {principal}.")
    if apr_percent < Decimal("0") or apr_percent > Decimal("100"):
        raise ValueError(f"APR percent must be between 0 and 100 inclusive, got {apr_percent}.")
    if term_months < 1 or term_months > 360:
        raise ValueError(f"Term months must be between 1 and 360 inclusive, got {term_months}.")

    if apr_percent == Decimal("0"):
        emi = principal / Decimal(term_months)
        return emi.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    r = apr_percent / Decimal("1200")
    n = Decimal(term_months)
    factor = (Decimal("1") + r) ** n
    emi = principal * r * factor / (factor - Decimal("1"))
    return emi.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def calculate_offer_amount(
    requested_amount: Decimal,
    maximum_amount: Decimal,
) -> Decimal:
    """Determine the effective offer principal as the smaller of requested and policy maximum amounts.

    Requires:
        requested_amount > 0
        maximum_amount > 0

    Returns:
        The smaller of the two positive Decimal amounts quantized to 2 decimal places.

    Raises:
        ValueError: If either amount is non-positive or invalid.
    """
    if not isinstance(requested_amount, Decimal) or not isinstance(maximum_amount, Decimal):
        raise ValueError("Both requested_amount and maximum_amount must be Decimal instances.")
    if requested_amount <= Decimal("0"):
        raise ValueError(f"Requested loan amount must be positive, got {requested_amount}.")
    if maximum_amount <= Decimal("0"):
        raise ValueError(f"Policy maximum loan amount must be positive, got {maximum_amount}.")

    offer_amount = min(requested_amount, maximum_amount)
    return offer_amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
