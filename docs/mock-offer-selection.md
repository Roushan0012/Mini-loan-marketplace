# Step 10: Mock Offer Selection Documentation

## 1. Why the Customer Selects One Offer

In a credit marketplace, loan matching generates illustrative pre-qualified offers from multiple lenders (such as Apex Financial, Horizon Credit, and Sterling Loans). Before proceeding to formal loan origination or submission, the customer must evaluate the available choices, inspect the Key Facts Statements (KFS), and select **exactly one** offer that matches their financial preference in loan amount, APR, tenure, and monthly installment (EMI).

Choosing a single offer commits the loan application to that specific product configuration, preventing ambiguous multi-lender processing and enabling structured progression through downstream verification.

---

## 2. Selection API Endpoint and Response Contract

### Route Specification
- **Method**: `POST`
- **Path**: `/api/v1/applications/{application_id}/offers/{offer_id}/select`
- **Request Body**: None (the target application and offer are uniquely identified in the path)
- **Status Code**: `200 OK` (on both fresh selection and idempotent retry)

### Response Payload (`OfferSelectionResponse`)
```json
{
  "application_id": 101,
  "application_status": "offer_selected",
  "selected_offer": {
    "id": 501,
    "lender_decision_id": 301,
    "lender_code": "APEX_FINANCIAL",
    "lender_name": "Apex Financial",
    "policy_version": "v1.0",
    "loan_amount": "200000.00",
    "apr": "18.0000",
    "term_months": 24,
    "monthly_installment": "9984.82",
    "mock_kfs_reference": "TRAINING-MOCK-KFS-D301",
    "status": "selected",
    "created_at": "2026-11-08T18:00:00Z",
    "valid_until": null
  },
  "withdrawn_offer_count": 2,
  "selection_result": "selected"
}
```

When an already-selected offer is submitted again by the customer:
- `selection_result`: `"already_selected"`
- `withdrawn_offer_count`: `0`
- `status_code`: `200 OK`

---

## 3. Authentication, Ownership, and Role-Based Access Controls

- **Authentication**: A valid JWT bearer token in the `Authorization: Bearer <token>` header is strictly required. Unauthenticated requests return `401 Unauthorized`.
- **Role Enforcement**: Only users with the `customer` role are permitted to select offers via the `require_customer` FastAPI dependency. Requests by users with `caller` or `admin` roles return `403 Forbidden`.
- **Ownership Verification**: The `customer_id` is extracted strictly from `current_user.id` in the verified JWT claims. Selection queries join `LoanApplication` with `MatchRun`, `LenderDecision`, and `Offer`, requiring `LoanApplication.customer_id == current_user.id`.
- **404 Scoping**: If the application does not exist or does not belong to the calling customer, or if the offer does not belong to the application, the endpoint returns `404 Not Found`.

---

## 4. Why Only the Latest Completed Match Run Is Selectable

A customer may update their income, age, or requested loan amount, prompting re-evaluation of lender policies. Each matching execution generates a new sequential `MatchRun` with new `LenderDecision` records and corresponding `Offer` records.
- Older match runs reflect historical state and obsolete eligibility terms.
- Allowing selection of an offer from an older match run would create inconsistencies with current customer criteria and latest policy configurations.
- Therefore, the selection engine verifies that `Offer.lender_decision.match_run_id == latest_completed_match_run.id`. Attempts to select an offer from an earlier run return `409 Conflict`.
- If the latest match run is incomplete (e.g. `started` or `failed`), selection is rejected with `409 Conflict`.

---

## 5. The `available -> selected` Status Transition

The database constraint on `offers.status` allows:
- `available`
- `selected`
- `expired`
- `withdrawn`

To be eligible for selection:
- The offer must currently have `status == "available"`.
- The linked lender decision must have `decision_status == "eligible"`.
- Offers in `expired`, `withdrawn`, or `ineligible` states cannot be selected (`409 Conflict`).
- Upon selection, the chosen offer transitions to `status = "selected"`.

---

## 6. Why Alternative Available Offers Become Withdrawn

When the customer selects one offer, all alternative available offers for that application across all match runs transition from `available` to `withdrawn`:
- Prevents race conditions or accidental dual selection across competing lenders.
- Explicitly archives alternatives while preserving their full audit trail.
- Historical offers, decisions, and match runs are permanently retained in PostgreSQL.
- Offers that are already `expired` or `withdrawn` remain unchanged.

---

## 7. The Application Status Transition from `matched` to `offer_selected`

- Loan applications transition from `matched` to `offer_selected`.
- This lifecycle transition records the user's intent to proceed with a specific lender product.
- Attempting to select an offer when the application is in an invalid lifecycle status (e.g. `draft`, `submitted`) returns `409 Conflict`.

---

## 8. `SELECT FOR UPDATE` and Concurrent Request Protection

To protect against concurrent duplicate selection requests:
1. The transaction begins by acquiring an exclusive row lock on the `LoanApplication` record using `SELECT FOR UPDATE`:
   ```python
   app = (
       db.query(LoanApplication)
       .filter(
           LoanApplication.id == application_id,
           LoanApplication.customer_id == customer_id,
       )
       .with_for_update()
       .first()
   )
   ```
2. Any concurrent selection request on the same application waits on this row lock until the active transaction completes.
3. If an offer has already been selected by the time the second request obtains the lock:
   - If the request targets the same offer, it resolves idempotently as `"already_selected"`.
   - If the request targets a different offer, it fails fast with `409 Conflict`.

---

## 9. How Idempotent Retries Work

Network retries and accidental double-clicks are standard in web applications. Step 10 provides deterministic idempotency:
- If `application.status == "offer_selected"` and the requested `offer_id` matches the existing selected offer:
  - Returns `200 OK`.
  - Sets `selection_result = "already_selected"`.
  - Sets `withdrawn_offer_count = 0`.
  - Does not re-check consents or re-modify database rows.
- If a different offer ID is requested on an already `offer_selected` application:
  - Rejects with `409 Conflict` (`"Application already has a selected offer"`).

---

## 10. Key Facts Statement (KFS) Access After Selection

KFS disclosure documents remain fully accessible after selection:
- The endpoint `GET /api/v1/applications/{application_id}/offers/{offer_id}/kfs` queries the database by `Offer.id` and `LoanApplication.id`.
- It does **not** filter out selected or withdrawn offers.
- For selected offers, KFS returns `offer_status: "selected"`.
- For withdrawn offers, KFS returns `offer_status: "withdrawn"`.
- Calculation disclosure and financial rounding (flooring estimated repayment at principal for low positive APRs) are preserved.

---

## 11. Why Selection Does Not Create an `OfferSubmission`

In consumer lending workflows, selecting an offer is an internal marketplace milestone:
- The customer chooses their preferred offer and reviews final disclosures.
- Creating an `OfferSubmission` record represents dispatching or committing the application to an external lender endpoint.
- In Step 10, the database table `offer_submissions` and `lender_events` remain completely empty (`count == 0`).

---

## 12. Why Actual Lender Submission Belongs to Step 11

Step 11 introduces:
- Creation of `OfferSubmission` records with unique idempotency keys.
- Mock lender submission adapters simulating asynchronous dispatch.
- Webhook simulation and status transitions (`pending -> submitted -> accepted / declined`).
Keeping offer selection (Step 10) decoupled from dispatch (Step 11) ensures a clean separation between customer product selection and lender integration lifecycles.

---

## 13. Fictional Training-Only Boundaries

- **No Real Financial Institutions**: All lenders (Apex Financial, Horizon Credit, Sterling Loans) are simulated entities.
- **No External Connectivity**: No real banks, credit bureaus, payment gateways, or external APIs are contacted.
- **Simulation Disclosures**: All mock KFS documents and offer details explicitly carry simulation notices.
