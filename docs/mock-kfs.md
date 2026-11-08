# Mock Key Facts Statement (KFS) Details

## 1. Overview & Purpose

In financial credit systems, a **Key Facts Statement (KFS)** is a standardized disclosure document designed to provide prospective borrowers with clear, transparent, and concise information regarding a credit offer before formal acceptance.

In the Mini Loan Marketplace training platform, the **Mock KFS Endpoint** serves as a simulated disclosure API. It allows an authenticated customer to inspect comprehensive commercial terms, installment amounts, estimated repayment obligations, and statutory simulation disclosures for any retained loan offer.

```
+-----------------------------------------------------------------------------------------+
|                                    LOAN APPLICATION                                     |
|  - customer_id: 101                                                                     |
+-----------------------------------------------------------------------------------------+
                                             |
                                             v
+-----------------------------------------------------------------------------------------+
|                                 COMPLETED MATCH RUN                                     |
|  - run_number: 1 (or historical runs)                                                   |
+-----------------------------------------------------------------------------------------+
                                             |
                                             v
+-----------------------------------------------------------------------------------------+
|                                   LENDER DECISION                                       |
|  - decision_status: 'eligible'                                                          |
|  - policy_version_snapshot: 'v1.0'                                                      |
+-----------------------------------------------------------------------------------------+
                                             |
                                             v
+-----------------------------------------------------------------------------------------+
|                                     SAVED OFFER                                         |
|  - loan_amount, apr, term_months, monthly_installment, mock_kfs_reference               |
+-----------------------------------------------------------------------------------------+
                                             |
                                             v  GET /applications/{app_id}/offers/{id}/kfs
+-----------------------------------------------------------------------------------------+
|                                   MOCK KFS RESPONSE                                     |
|  - Document metadata, lender details, exact snapshot version, financial amortisation    |
|  - Explicit simulation disclosures (fees unmodeled, illustrative estimates)             |
+-----------------------------------------------------------------------------------------+
```

> [!CAUTION]
> **FICTIONAL SIMULATION DISCLOSURE**: This is a software training simulation only.
> - The mock document is **not** an actual credit agreement, legal disclosure, or regulatory Key Facts Statement (KFS) under RBI guidelines or any other financial regulatory regime.
> - No real lenders, banks, Non-Banking Financial Companies (NBFCs), or credit bureaus are involved.
> - No legally binding credit relationship or disbursal obligation is established by retrieving or reading this simulated disclosure.

---

## 2. API Contract & Security

### Endpoint
- **Method & Path**: `GET /api/v1/applications/{application_id}/offers/{offer_id}/kfs`
- **Authentication**: Bearer JWT token required
- **Authorization**: `customer` role only (non-customer roles such as `caller` and `admin` receive `403 Forbidden`)

### Strict Ownership & Scope Isolation
- The backend verifies that `LoanApplication.customer_id` matches the authenticated `current_user.id`.
- The database query explicitly enforces the relationship chain:
  $$\text{Offer} \rightarrow \text{LenderDecision} \rightarrow \text{MatchRun} \rightarrow \text{LoanApplication}$$
- If the application does not exist or belongs to another customer, the endpoint returns `404 Not Found` (`"Loan application not found."`).
- If the offer does not exist or belongs to a different application, the endpoint returns `404 Not Found` (`"Offer not found."`).
- The existence of another customer's application or offer is never leaked.

### Example Response
```json
{
  "document_type": "TRAINING_ONLY_MOCK_KFS",
  "document_version": "training-v1",
  "mock_kfs_reference": "TRAINING-MOCK-KFS-D201",
  "offer_id": 42,
  "application_id": 105,
  "lender_code": "APEX_FINANCIAL",
  "lender_name": "Apex Financial",
  "policy_version": "v1.0",
  "offer_status": "available",
  "offer_created_at": "2026-11-08T10:00:00Z",
  "valid_until": null,
  "loan_amount": "200000.00",
  "nominal_annual_apr_percent": "18.0000",
  "term_months": 24,
  "number_of_installments": 24,
  "payment_frequency": "Monthly",
  "monthly_installment": "9984.82",
  "estimated_total_repayment": "239635.68",
  "estimated_total_interest": "39635.68",
  "amortization_method": "Monthly reducing-balance",
  "fee_disclosure": "Processing fees, origination charges, insurance premiums, taxes, late payment fees, penalties, and other ancillary charges are not modeled or included in this training simulation.",
  "calculation_disclosure": "Monthly installment and repayment totals are illustrative calculations based on the stored offer terms. Monetary values are rounded to two decimal places. In rare low-positive-APR cases, estimated repayment is floored at principal to prevent displaying negative estimated interest caused by cent rounding. Final-installment adjustments and additional charges are not modeled.",
  "training_disclosure": "This is a fictional software-training document only. It is not an actual credit offer, loan agreement, legal disclosure, or regulatory Key Facts Statement. No real lender or financial institution is involved."
}
```

---

## 3. Data Mapping & Version Integrity

The KFS does not re-evaluate lender policies or recompute the initial EMI from external definitions. Instead, it reflects the **exact, immutable commercial terms committed to the database** during offer generation:

| KFS Field | Data Source | Notes |
| :--- | :--- | :--- |
| `mock_kfs_reference` | `Offer.mock_kfs_reference` | Stable identifier (format: `TRAINING-MOCK-KFS-D{decision_id}`) |
| `offer_id` | `Offer.id` | Primary key of the selected offer |
| `application_id` | `LoanApplication.id` | Scoped parent application ID |
| `lender_code` | `LenderPolicy.lender_code` | Derived from `LenderDecision.lender_policy` |
| `lender_name` | `LenderPolicy.lender_name` | Derived from `LenderDecision.lender_policy` |
| `policy_version` | `LenderDecision.policy_version_snapshot` | Immutable snapshot version recorded at evaluation time |
| `offer_status` | `Offer.status` | Stored lifecycle status (`available`, etc.) |
| `loan_amount` | `Offer.loan_amount` | Exact stored principal extended (`Decimal`) |
| `nominal_annual_apr_percent` | `Offer.apr` | Stored nominal APR percentage (`Decimal`) |
| `term_months` | `Offer.term_months` | Stored loan tenure in months |
| `number_of_installments` | `Offer.term_months` | Number of scheduled payments |
| `monthly_installment` | `Offer.monthly_installment` | Stored monthly installment (`Decimal`) |

---

## 4. Financial Calculations & Assumptions

All calculations are performed using Python's `Decimal` type. Floating-point arithmetic (`float`) is strictly prohibited.

### Estimated Total Repayment
$$\text{installment\_total} = \text{Offer.monthly\_installment} \times \text{Offer.term\_months}$$
$$\text{estimated\_total\_repayment} = \max(\text{installment\_total}, \text{Offer.loan\_amount})$$
- Quantized to `Decimal("0.01")` using `ROUND_HALF_UP`.
- In rare low-positive-APR cases with long repayment tenures, rounding the monthly installment to cents can cause $\text{installment\_total}$ to evaluate slightly below principal. In such boundary conditions, estimated repayment is floored at principal ($\max$) to prevent displaying negative estimated interest.
- Example: $₹9,984.82 \times 24 = ₹2,39,635.68$.

### Estimated Total Interest
- **For Positive APR ($\text{apr} > 0$)**:
  $$\text{estimated\_total\_interest} = \text{estimated\_total\_repayment} - \text{Offer.loan\_amount}$$
  Example: $₹2,39,635.68 - ₹2,00,000.00 = ₹39,635.68$.
- **For Zero APR ($\text{apr} = 0$)**:
  $$\text{estimated\_total\_interest} = \text{Decimal("0.00")}$$
  $$\text{estimated\_total\_repayment} = \text{Offer.loan\_amount}$$

### Illustrative Nature & Unmodeled Charges
1. **Simplified Amortization Model**: Figures are illustrative estimates derived from the stored rounded monthly installment. A final-installment penny adjustment (often used in production banking systems to reconcile rounding fractions) is deliberately not modeled.
2. **Unmodeled Ancillary Charges**: Real-world loan agreements include processing fees, origination charges, credit insurance premiums, GST/taxes, documentation charges, pre-payment penalties, and late fee schedules. None of these charges are modeled in this training simulation.

---

## 5. Architectural Principles

### Read-Only Operation
The mock KFS endpoint is purely idempotent and non-destructive:
- It does not modify, recreate, delete, or transition the status of the `Offer` record.
- It creates zero new database rows (`MatchRun`, `LenderDecision`, and `Offer` counts remain identical).
- It does not re-execute matching rules or re-trigger the offer generation service.

### Historical Offer Accessibility
In credit applications, a customer might update application details and run multi-lender matching a second time (e.g., `run_number: 2`). Prior match runs and their associated offers remain permanently preserved in PostgreSQL.
The KFS endpoint supports any historical offer associated with an owned application, allowing the applicant to audit earlier quotes without requiring the offer to belong exclusively to the latest match run.

### Why No PDF or Separate KFS Table
1. **Source of Truth**: The `offers` table, linked to `lender_decisions` and `lender_policies`, already stores all required commercial terms and audit references (`mock_kfs_reference`). Storing duplicate columns in a second `kfs_documents` table would introduce data redundancy and state synchronisation risks.
2. **On-Demand Representation**: Rather than generating static PDF files and managing file system or object store lifecycles for a simulation, the KFS is served as a structured JSON API response that consumers (or a subsequent UI layer) can render dynamically.
