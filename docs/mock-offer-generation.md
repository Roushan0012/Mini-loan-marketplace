# Mock Loan Offer Generation & Comparison APIs

## 1. Overview & Purpose

In the Mini Loan Marketplace, **Offer Generation** is the stage following multi-lender underwriting matching. Once a customer's loan application has been evaluated across active mock lender policies, offer generation synthesizes commercial pricing terms for all eligible outcomes.

```
+---------------------------+       +---------------------------+       +---------------------------+
|    Loan Application       | ----> |     Matching Engine       | ----> |      Offer Service        |
|  - customer_id            |       |  - Evaluates rules        |       |  - SELECT FOR UPDATE lock |
|  - status: "matched"      |       |  - Creates MatchRun       |       |  - Loads eligible decs    |
|  - Active Consents Check  |       |  - Creates LenderDecision |       |  - min(requested, max)    |
|                           |       |    (eligible/ineligible)  |       |  - Calculates EMI         |
+---------------------------+       +---------------------------+       |  - Persists Offer records |
                                                                        +---------------------------+
```

### Key Responsibilities
1. **Locking & Validation**: Serializes concurrent requests using row-level `SELECT ... FOR UPDATE` on the parent `loan_applications` record.
2. **Readiness Verification**: Validates that application lifecycle status is strictly `"matched"` and both required statutory consent purposes (`eligibility_matching`, `sharing_with_mock_lenders`) remain actively granted on current notice versions.
3. **Eligible Evaluation**: Scopes offer generation strictly to decisions where `decision_status == 'eligible'` from the latest completed `MatchRun`.
4. **Exact Version Integrity**: Evaluates the exact policy version pinned in `decision.policy_version_snapshot`—never substituting an unpinned or unverified policy record.
5. **Commercial Amortisation**: Applies the reducing-balance EMI formula using exact `Decimal` arithmetic.
6. **Safe Idempotency**: Guarantees repeatable execution without duplicating rows or mutating existing terms.

---

## 2. Eligibility Rules vs. Commercial Offer Terms

Underwriting and pricing are strictly segregated in the architecture:

| Aspect | Eligibility Rules (`rules` JSONB) | Offer Terms (`offer_terms` JSONB) |
| :--- | :--- | :--- |
| **Domain Purpose** | Underwriting qualification ("*Can* this customer borrow?") | Commercial pricing ("*What* are the borrowing terms?") |
| **Evaluated In** | Matching Engine ([`matching_service.py`](../backend/app/services/matching_service.py)) | Offer Generator ([`offer_service.py`](../backend/app/services/offer_service.py)) |
| **Input Parameters** | `min_age`, `min_monthly_income`, `allowed_work_types` | `apr_percent`, `term_months`, `max_loan_amount` |
| **Database Entity** | Stored in `lender_decisions.decision_status` | Stored in `offers` table linked 1-to-1 to decision |
| **Lifecycle Impact** | Determines eligibility outcome (`eligible` / `ineligible`) | Produces financial amortisation and monthly installment |

---

## 3. Exact Policy Version Selection

A common defect in multi-version systems is evaluating an applicant against version $A$ during matching, but pricing against version $B$ during offer generation.

To guarantee deterministic version integrity:
1. Each decision records `decision.policy_version_snapshot` (e.g. `"v1.0"`).
2. During offer generation, the engine loads the referenced `LenderPolicy` row and validates:
   $$\text{policy.policy\_version} == \text{decision.policy\_version\_snapshot}$$
3. If a policy has been updated or removed such that the versions diverge, the service refuses to generate ambiguous terms and raises a configuration conflict (HTTP 503).
4. All eligible decisions are pre-validated before any `Offer` row is created, eliminating partial-batch inconsistencies.

---

## 4. Financial Calculations & Precision

### Offer Amount Determination
The principal amount extended to the applicant is calculated as:
$$\text{offer\_amount} = \min(\text{application.requested\_amount}, \text{policy\_terms.max\_loan\_amount})$$

- If an applicant requests ₹2,00,000 and the lender's cap is ₹2,50,000, the offer amount is ₹2,00,000.
- If an applicant requests ₹2,00,000 and the lender's cap is ₹1,50,000 (e.g. `STERLING_LOANS`), the offer amount is capped at ₹1,50,000.

### Equated Monthly Installment (EMI) Formula
The monthly installment is computed using the reducing-balance amortisation equation:
$$\text{EMI} = P \times \frac{r \times (1 + r)^n}{(1 + r)^n - 1}$$

where:
- $P$ = Offer principal amount (`Decimal`, 2 decimal places)
- $r$ = Monthly interest rate = $\frac{\text{apr\_percent}}{1200}$ (`Decimal`)
- $n$ = Loan tenure in months (`term_months`, strictly positive integer)

When $\text{apr\_percent} = 0$, linear principal division is evaluated:
$$\text{EMI} = \frac{P}{n}$$

### Decimal Precision & Context Isolation
- All monetary amounts and rates use Python's `Decimal` type; `float` primitives are strictly forbidden.
- Calculations execute inside an isolated decimal context (`with decimal.localcontext() as ctx: ctx.prec = 35`), ensuring intermediate precision without polluting global interpreter settings.
- Final monthly installment amounts are rounded to 2 decimal places using `ROUND_HALF_UP`.

---

## 5. Idempotency & Lifecycle Preservation

### Why Only Eligible Decisions Receive Offers
Ineligible decisions represent applications rejected during underwriting (e.g., age below minimum, income threshold unmet, or disallowed employment category). In credit systems, issuing commercial borrowing terms against an ineligible assessment violates regulatory and operational boundaries. Consequently, `decision_status == 'eligible'` is a strict precondition for offer creation.

### Idempotent Execution
Calling the offer generation endpoint multiple times:
- Reuses existing `Offer` records matching each `LenderDecision`.
- Returns HTTP 200 with `generated_count: 0` and the complete list of existing offers.
- Preserves all financial terms (`loan_amount`, `apr`, `term_months`, `monthly_installment`), audit timestamps (`created_at`), and status (`available`).
- The database enforces a `UNIQUE` constraint on `offers.lender_decision_id` as the final database-level guarantee.

### Match Run History Preservation
- When a customer updates their application profile and re-executes matching, a new `MatchRun` is created (e.g., `run_number: 2`).
- Offers generated from prior match runs remain permanently stored in the `offers` table for regulatory auditability and historical tracking.
- The comparison endpoint `GET /api/v1/applications/{application_id}/offers` resolves exclusively to offers linked to the latest completed match run.

---

## 6. API Endpoints & Contract

### 1. Generate Offers
- **Path**: `POST /api/v1/applications/{application_id}/offers/generate`
- **Access**: Authenticated `customer` (application owner only)
- **Status Code**: `200 OK`

#### Example Request
```http
POST /api/v1/applications/42/offers/generate HTTP/1.1
Host: localhost:8000
Authorization: Bearer <customer_jwt>
```

#### Example Response
```json
{
  "application_id": 42,
  "match_run_id": 105,
  "run_number": 1,
  "generated_count": 3,
  "offers": [
    {
      "id": 1,
      "lender_decision_id": 201,
      "lender_code": "APEX_FINANCIAL",
      "lender_name": "Apex Financial",
      "policy_version": "v1.0",
      "loan_amount": "200000.00",
      "apr": "18.0000",
      "term_months": 24,
      "monthly_installment": "9984.82",
      "mock_kfs_reference": "TRAINING-MOCK-KFS-D201",
      "status": "available",
      "created_at": "2026-11-08T10:00:00Z",
      "valid_until": null
    },
    {
      "id": 2,
      "lender_decision_id": 202,
      "lender_code": "HORIZON_CREDIT",
      "lender_name": "Horizon Credit",
      "policy_version": "v1.0",
      "loan_amount": "200000.00",
      "apr": "16.0000",
      "term_months": 36,
      "monthly_installment": "7031.41",
      "mock_kfs_reference": "TRAINING-MOCK-KFS-D202",
      "status": "available",
      "created_at": "2026-11-08T10:00:00Z",
      "valid_until": null
    },
    {
      "id": 3,
      "lender_decision_id": 203,
      "lender_code": "STERLING_LOANS",
      "lender_name": "Sterling Loans",
      "policy_version": "v1.0",
      "loan_amount": "150000.00",
      "apr": "20.0000",
      "term_months": 18,
      "monthly_installment": "9714.48",
      "mock_kfs_reference": "TRAINING-MOCK-KFS-D203",
      "status": "available",
      "created_at": "2026-11-08T10:00:00Z",
      "valid_until": null
    }
  ]
}
```

### 2. List & Compare Offers
- **Path**: `GET /api/v1/applications/{application_id}/offers`
- **Access**: Authenticated `customer` (application owner only)
- **Status Code**: `200 OK`
- **Ordering**: Deterministic ascending order by `lender_code`.
- **Response**: Array of `OfferResponse` objects for the latest completed match run. Returns `[]` if no completed run or no offers exist.

---

## 7. Fictional Training Disclosures

> [!CAUTION]
> **SIMULATION ONLY**: The Mini Loan Marketplace is an educational training system.
> - All lender entities (`Apex Financial`, `Horizon Credit`, `Sterling Loans`), underwriting criteria, APR percentages, and installment amounts are **entirely fictional**.
> - **No real money, actual credit agreements, bank transfers, or credit bureau checks occur**.
> - The mock Key Fact Statement reference string (e.g. `TRAINING-MOCK-KFS-D201`) is a placeholder identifier for future training modules. It is **not** a legally binding or regulatory Key Fact Statement (KFS) under RBI or any financial regulatory authority guidelines.
