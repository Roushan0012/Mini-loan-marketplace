# Step 11: Idempotent Mock Offer Submission Documentation

## 1. Difference Between Offer Selection and Offer Submission

In the Mini Loan Marketplace architecture, loan origination separates user preference from provider dispatch:
- **Offer Selection (Step 10)**: The customer chooses exactly one loan offer from available matching results. This transitions the application from `matched` to `offer_selected`, marks the chosen offer as `selected`, and withdraws alternative offers. No external provider dispatch occurs.
- **Offer Submission (Step 11)**: The customer formally commits to the chosen product terms and submits their application to the fictional mock lender. This creates an `OfferSubmission` record, calls the deterministic mock lender adapter, transitions the submission to `submitted`, and updates the application lifecycle status from `offer_selected` to `submitted`.

---

## 2. Submission Endpoint and the `Idempotency-Key` Header

### API Contract
- **Method**: `POST`
- **Route**: `/api/v1/applications/{application_id}/offers/{offer_id}/submit`
- **Authentication**: Bearer JWT (`customer` role required)
- **Required Header**: `Idempotency-Key` (8 to 128 characters, non-empty after trimming)
- **Request Body**: None (IDs are provided in the path; transaction identity is established by the header)
- **Status Code**: `200 OK` on initial submission and replay

### Response Payload (`OfferSubmissionResponse`)
```json
{
  "id": 12,
  "application_id": 101,
  "offer_id": 501,
  "lender_code": "APEX_FINANCIAL",
  "lender_name": "Apex Financial",
  "policy_version": "v1.0",
  "status": "submitted",
  "mock_reference": "MOCK-SUB-APEX_FINANCIAL-12",
  "submitted_at": "2026-11-09T00:25:00Z",
  "created_at": "2026-11-09T00:25:00Z",
  "updated_at": "2026-11-09T00:25:00Z",
  "submission_result": "created"
}
```

On exact replay (same application, same offer, same key):
- `submission_result`: `"replayed"`
- `status`: Preserves stored database status (e.g. `submitted`)
- `status_code`: `200 OK`

---

## 3. Why the Client Must Reuse the Same Key for Retries

Network hiccups, client timeouts, and connection drops can prevent a response from reaching the client even though the server successfully processed the submission.
- The `Idempotency-Key` allows the client to safely retry the identical request without fear of double dispatch or duplicate records.
- If the client changes the `Idempotency-Key` on a subsequent submission for the same application, the server rejects the request with `409 Conflict`, explaining that the original key must be reused.
- This prevents unintentional multiple submissions under different transaction IDs.

---

## 4. How the Application Row Lock Works

Concurrent requests targeting the same application are serialized at the database engine level using PostgreSQL row-level locks:
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
- The first request acquires an exclusive row lock on the `loan_applications` record.
- Any concurrent or interleaved request attempting to select or submit for that application waits until the active transaction commits or rolls back.
- Once released, the second request reads the updated state:
  - If it presents the same key, it returns the replayed response cleanly.
  - If it presents a different key or offer, it fails fast with `409 Conflict`.

---

## 5. How Unique Database Constraints Reinforce Idempotency

Even in distributed systems or multi-threaded environments, database constraints serve as the final integrity safeguard:
1. `UNIQUE (application_id)` on `offer_submissions`: Guarantees at most one submission per application.
2. `UNIQUE (offer_id)` on `offer_submissions`: Ensures an offer cannot be submitted more than once.
3. `UNIQUE (idempotency_key)` on `offer_submissions`: Guarantees no two submissions share the same idempotency key across the platform.

If an unexpected race bypasses application-level locks, PostgreSQL raises an `IntegrityError`, which the service catches, rolls back, and resolves idempotently if the record matches the request.

---

## 6. Application Ownership and Selected-Offer Validation

- **Ownership**: The authenticated user's ID (`current_user.id`) is enforced directly in the `LoanApplication` query. Attempting to access or submit another user's application yields `404 Not Found`.
- **Relationship Scoping**: The target offer must join directly to the application:
  $$\text{Offer} \longrightarrow \text{LenderDecision} \longrightarrow \text{MatchRun} \longrightarrow \text{LoanApplication}$$
- **State Validation**:
  - `LoanApplication.status == "offer_selected"`
  - `Offer.status == "selected"`
  - `LenderDecision.decision_status == "eligible"`
  - Exactly 1 offer is selected for the application.
  - Submitting `available`, `withdrawn`, or `expired` offers is strictly forbidden (`409 Conflict`).

---

## 7. Active Consent Verification

Before creating a new submission, the service verifies that active, current-version consent records exist for all mandatory purposes:
- `eligibility_matching`
- `sharing_with_mock_lenders`

If either consent is missing, revoked, or outdated, the new submission is blocked with `409 Conflict` (listing the missing purposes).

**Replay Exception**: An exact idempotent replay of an already-submitted offer returns the stored submission without re-checking consent, because no new data sharing or processing occurs during replay.

---

## 8. How the Local Mock Lender Adapter Works

The mock lender adapter is located at `backend/app/integrations/mock_lenders/`:
- **Local & Deterministic**: Runs entirely in Python memory without external HTTP calls or network I/O.
- **Allowed Lenders**: Only supports recognized training lender codes:
  - `APEX_FINANCIAL`
  - `HORIZON_CREDIT`
  - `STERLING_LOANS`
- **Rejection**: Unknown lender codes immediately raise `UnsupportedLenderCodeError`.

---

## 9. Mock Reference Format

The mock reference generated by the adapter is deterministic:
$$\text{MOCK-SUB-}\{\text{lender\_code}\}\text{-}\{\text{submission\_id}\}$$
- Example: `MOCK-SUB-APEX_FINANCIAL-12`
- Fits within `OfferSubmission.mock_reference String(150)`.
- Explicitly flags itself as fictional (`MOCK-SUB-`).
- Guaranteed unique and reproducible for each submission ID.

---

## 10. Privacy: No Customer PII Sent to Adapter

The adapter interface requires only:
- `lender_code: str`
- `submission_id: int`

Customer PII (applicant name, email, phone number, age, monthly income, employment status) is never passed into the adapter function or transmitted.

---

## 11. Meaning of Submission Status `"submitted"`

The lifecycle status of `OfferSubmission` is set to `"submitted"`:
- Reflects that the customer has executed the dispatch action.
- The corresponding `LoanApplication.status` transitions from `offer_selected` to `submitted`.
- The offer remains in `status = "selected"`.

---

## 12. Why Acceptance, Decline, and Timeout Are Deferred

In real lending systems, credit underwriting is asynchronous. The lender evaluates the application in a secondary decisioning stage before delivering an approval, decline, or timing out.
- In Step 11, the submission action establishes the dispatched state.
- In Step 12, asynchronous webhook simulation, provider callbacks, and subsequent transitions (`accepted`, `declined`, `timed_out`) will be introduced.

---

## 13. Why No `LenderEvent` Is Created in Step 11

The `lender_events` table models incoming asynchronous webhook callbacks and provider event logs. Because Step 11 focuses strictly on outbound customer submission dispatch, no inbound lender events occur. `LenderEvent` remains completely untouched (`count == 0`).

---

## 14. No Real Lender Network Integration

- Antigravity and the Mini Loan Marketplace do not integrate with live financial networks, NPCI, RBI-regulated entities, credit bureaus (CIBIL/Experian), or banking APIs.
- All lender policies and submissions are software training simulations.

---

## 15. How Replay Returns the Existing Submission

When a client replays a request with the original `Idempotency-Key`:
1. The service queries `OfferSubmission` by `idempotency_key`.
2. It verifies that `application_id` and `offer_id` match.
3. It reconstructs the `OfferSubmissionResponse` using the stored record and relationship snapshots.
4. It sets `submission_result = "replayed"`.
5. It preserves the current stored `status` without resetting it to `submitted`.

---

## 16. Error Handling and Atomic Rollback

If any step fails during submission (e.g. adapter exception, database error):
1. `db.rollback()` is invoked immediately.
2. The `OfferSubmission` insert is discarded.
3. `LoanApplication.status` remains `offer_selected`.
4. No dirty or orphaned records remain in PostgreSQL.
5. The customer can retry using the same `Idempotency-Key` once the underlying issue is resolved.

---

## 17. Fictional Training-Only Disclosure

> [!NOTE]
> This module is an educational and training simulation. No credit evaluation, legal lending contract, or regulatory transmission occurs.
