# Versioned Mock Offer Terms & EMI Calculator

## 1. Overview & Architectural Separation

In the Mini Loan Marketplace, underwriting eligibility evaluation and loan offer calculation represent two distinct stages in the credit lifecycle:

```
+---------------------------+       +---------------------------+       +---------------------------+
|    Loan Application       | ----> |    Matching Engine        | ----> |     Offer Generator       |
|  - age                    |       |  - Evaluates rules        |       |  - Uses offer_terms       |
|  - monthly_income         |       |    (min_age, min_income,  |       |  - Calculates EMI         |
|  - work_type              |       |     allowed_work_types)   |       |  - Bounds max loan amount |
|  - requested_amount       |       |  - Determines eligibility |       |  - Generates Offer row    |
+---------------------------+       +---------------------------+       +---------------------------+
```

### Why Rules and Terms Are Kept Separate

1. **Decoupled Concerns**: A lender's underwriting policy dictates *who* qualifies (`rules`: minimum age, minimum income, permissible employment types). In contrast, commercial pricing terms dictate *what* terms are extended upon qualification (`offer_terms`: APR, tenure in months, maximum borrowable limit).
2. **Independent Policy Evolution**: Lenders frequently adjust commercial rates (APRs) without altering baseline borrower eligibility criteria, and vice-versa.
3. **Database Column Isolation**: Storing `rules` and `offer_terms` as separate JSONB columns in `lender_policies` ensures that evaluation logic remains lightweight and independent from loan amortisation calculations.

> [!IMPORTANT]
> **TRAINING DEMO DISCLOSURE**: All lender identities, lender codes (`APEX_FINANCIAL`, `HORIZON_CREDIT`, `STERLING_LOANS`), interest rates (APRs), maximum loan caps, tenures, and formulas are **fictional training simulations**. No real financial institution, bank, non-banking financial company (NBFC), or credit bureau is contacted or modeled.

---

## 2. Versioned Offer Terms Configuration

Offer terms are defined within the `offer_terms` JSONB column on the `lender_policies` table. The Pydantic model [`MockOfferTerms`](../backend/app/schemas/offer.py) validates the payload structure:

```python
class MockOfferTerms(BaseModel):
    model_config = ConfigDict(extra="forbid")

    apr_percent: Decimal = Field(..., ge=Decimal("0.0000"), le=Decimal("100.0000"), max_digits=7, decimal_places=4)
    term_months: int = Field(..., gt=0, le=360)
    max_loan_amount: Decimal = Field(..., gt=Decimal("0.00"), max_digits=12, decimal_places=2)
```

### Fictional Training Lender Configurations (v1.0)

| Lender Code | Policy Version | APR (%) | Tenure (Months) | Max Loan Amount (₹) |
| :--- | :--- | :--- | :--- | :--- |
| `APEX_FINANCIAL` | `v1.0` | `18.0000%` | `24` | `₹2,50,000.00` |
| `HORIZON_CREDIT` | `v1.0` | `16.0000%` | `36` | `₹3,00,000.00` |
| `STERLING_LOANS` | `v1.0` | `20.0000%` | `18` | `₹1,50,000.00` |

---

## 3. The Equated Monthly Installment (EMI) Formula

The monthly installment is computed using the standard reducing-balance amortisation equation:

$$\text{EMI} = P \times \frac{r \times (1 + r)^n}{(1 + r)^n - 1}$$

where:
- $P$ = Principal loan amount extended (`Decimal`)
- $r$ = Monthly periodic interest rate = $\frac{\text{apr\_percent}}{1200}$ (`Decimal`)
- $n$ = Loan tenure in months (`term_months`)

### Decimal Arithmetic & Float Prohibition

- Python's standard `float` type uses IEEE-754 binary floating-point representation, which introduces rounding anomalies (e.g. `0.1 + 0.2 != 0.3`).
- In financial computing, all calculations use Python's [`Decimal`](../backend/app/services/offer_calculator.py) with global context precision set to 35 decimal places.
- Inputs passed as `float` are strictly rejected by the validator to enforce exact monetary precision.

### Zero-Interest Handling (0% APR)

When $\text{apr\_percent} = 0$, evaluating the general formula would result in a division by zero error ($0 / 0$). The calculator intercepts this boundary case and evaluates linear principal amortisation:

$$\text{EMI} = \frac{P}{n}$$

### Rounding: `ROUND_HALF_UP`

The resulting calculated instalment is quantized to two decimal places using [`ROUND_HALF_UP`](../backend/app/services/offer_calculator.py), rounding half values upward (e.g. `33333.3333...` rounds to `33333.33`, and `16.6666...` rounds to `16.67`).

---

## 4. Loan Offer Amount Calculation

When an applicant requests an amount ($A_{\text{req}}$), the extended offer principal ($P$) cannot exceed the lender's policy maximum ($A_{\text{max}}$):

$$P = \min(A_{\text{req}}, A_{\text{max}})$$

Implemented in [`calculate_offer_amount()`](../backend/app/services/offer_calculator.py):
- If the applicant requests ₹1,50,000.00 and Apex Financial's maximum is ₹2,50,000.00, the offer amount is ₹1,50,000.00.
- If the applicant requests ₹3,00,000.00 and Sterling Loans' maximum is ₹1,50,000.00, the offer amount is capped at ₹1,50,000.00.

---

## 5. Standard Financial Test Vectors

| Principal ($P$) | APR (%) | Tenure ($n$) | Calculated Monthly EMI | Note |
| :--- | :--- | :--- | :--- | :--- |
| ₹2,00,000.00 | 18.0000% | 24 months | **₹9,984.82** | Standard Apex terms test |
| ₹2,00,000.00 | 16.0000% | 36 months | **₹7,031.41** | Standard Horizon terms test |
| ₹1,50,000.00 | 20.0000% | 18 months | **₹9,714.48** | Standard Sterling terms test |
| ₹1,20,000.00 | 0.0000% | 12 months | **₹10,000.00** | Zero-interest baseline |
| ₹1,00,000.00 | 0.0000% | 3 months | **₹33,333.33** | Half-up non-exact division |

---

## 6. Financial Assumptions, Scope & Limitations

1. **Nominal Annual Percentage Rate**: The `apr_percent` is treated purely as a nominal annual rate divided by 1,200 to establish the monthly periodic interest rate.
2. **Reducing Balance Amortisation**: The calculator assumes fixed monthly reducing-balance amortisation with equal monthly payments.
3. **No Fees or Taxes**: Calculations do not incorporate loan origination fees, upfront processing charges, insurance premiums, stamp duty, GST, or late payment penalties.
4. **Not a Regulatory Key Fact Statement (KFS)**: This calculation serves solely as an illustrative simulation for marketplace software testing. It does not constitute a legally binding loan quote, credit agreement, or regulatory disclosure.
5. **Future Use (Step 9B)**: In Step 9B, the upcoming offer generation service will invoke `calculate_offer_amount()` and `calculate_monthly_installment()` for eligible decisions to persist formal `Offer` records.
