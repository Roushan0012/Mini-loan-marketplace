# Step 12: Mock Lender Responses, Signed Webhooks, Event Sequencing, and Timeout Processing

> [!IMPORTANT]
> **Fictional Training Project Disclaimer**:
> This project is a simulated educational prototype. It does not connect to real banks, financial institutions, payment gateways, credit bureaus, or external networks. All webhook signatures, event identifiers, and lender interactions operate purely in a deterministic, simulated local testbed.

---

## 1. Overview and Purpose

In an asynchronous loan origination architecture, submitting a loan application does not immediately yield a final loan disbursement or denial. Instead, lenders process applications asynchronously through internal credit decisioning and underwriting systems, eventually reporting their decisions back via signed webhooks.

Step 12 implements:
1. **Signed Webhook Ingestion**: Receives mock lender outcome events at `POST /api/v1/webhooks/mock-lenders/events`.
2. **Cryptographic Authentication**: Validates an HMAC-SHA256 signature generated over the exact raw request bytes.
3. **Deterministic State Transitions**: Synchronously transitions both `OfferSubmission.status` and `LoanApplication.status` to `accepted`, `declined`, `timed_out`, or `failed`.
4. **Authoritative Event Sequencing**: Rejects out-of-order or stale events (`sequence_number <= max_processed`) as `ignored` without altering submission or application state.
5. **Idempotent Duplicate Event Handling**: Detects duplicate `event_id` deliveries; returns `duplicate: true` for identical replays, and `409 Conflict` for mismatched payloads.
6. **Customer Event History API**: Exposes an ordered audit trail of received webhook events at `GET /api/v1/applications/{application_id}/submission/events`.
7. **Timeout Processing**: Models lender timeouts via explicit signed `lender.timed_out` events without background queue daemons or schedulers.

---

## 2. Database Model: `LenderEvent`

The `LenderEvent` table was created in Step 4B and is reused in Step 12 without requiring any schema changes or migrations:

| Column | Type | Constraints / Nullability | Description |
|---|---|---|---|
| `id` | `BIGINT` | Primary Key, Auto-increment | Unique internal database ID |
| `submission_id` | `BIGINT` | `NOT NULL`, FK to `offer_submissions.id` (`ON DELETE CASCADE`) | The associated offer submission |
| `event_id` | `VARCHAR(100)` | `NOT NULL`, `UNIQUE` | Unique external event identifier |
| `event_type` | `VARCHAR(50)` | `NOT NULL` | Event discriminator (`lender.accepted`, `lender.declined`, `lender.timed_out`, `lender.failed`) |
| `sequence_number` | `INTEGER` | `NULLABLE`, Check: `sequence_number > 0` | Authoritative monotonic event sequence |
| `event_payload` | `JSONB` / `JSON` | `NOT NULL` | Sanitized metadata (e.g. `{"simulation": true, ...}`) |
| `processing_status` | `VARCHAR(20)` | `NOT NULL`, Check: `IN ('received', 'processed', 'ignored', 'failed')` | Internal status of event processing |
| `occurred_at` | `TIMESTAMP WITH TIME ZONE` | `NOT NULL` | Timestamp when the event occurred at the mock lender |
| `created_at` | `TIMESTAMP WITH TIME ZONE` | `NOT NULL`, Server default `now()` | Timestamp when the event record was persisted |

### Database Constraints
- `uq_lender_events_event_id`: Ensures global uniqueness of `event_id`.
- `ck_lender_events_processing_status`: Enforces `processing_status IN ('received', 'processed', 'ignored', 'failed')`.
- `ck_lender_events_sequence_number_positive`: Enforces `sequence_number IS NULL OR sequence_number > 0`.
- Foreign key `fk_lender_events_submission_id_offer_submissions`: Maintains relational integrity to the parent `OfferSubmission`.

---

## 3. Webhook Security and HMAC-SHA256 Authentication

### Signature Header Format
Webhooks arrive with the header:
```http
X-Mock-Lender-Signature: sha256=<hex_digest>
```

### Signature Verification Requirements
1. **Raw Body Verification**: Verification is performed over the unmodified raw UTF-8 bytes (`request.body()`), strictly before any JSON parsing or deserialization.
2. **Dedicated Secret**: Configured via `MOCK_LENDER_WEBHOOK_SECRET` in `backend/app/core/config.py`. It is completely separate from `JWT_SECRET_KEY`.
3. **Fail-Closed Design**: If `MOCK_LENDER_WEBHOOK_SECRET` is unset, empty, or still set to an insecure default placeholder, the webhook receiver aborts immediately with `503 Service Unavailable`.
4. **Constant-Time Comparison**: The digest comparison uses `hmac.compare_digest()` to eliminate timing attack vulnerabilities.
5. **Tamper Detection**: If any character or whitespace in the payload is altered between transmission and receipt, verification fails with `401 Unauthorized`.

### Python Helper Snippet: Generating Signatures
```python
import hmac
import hashlib
import json

def compute_webhook_signature(payload_dict: dict, secret: str) -> str:
    """Generate the X-Mock-Lender-Signature header value."""
    raw_body = json.dumps(payload_dict).encode("utf-8")
    signature = hmac.new(
        secret.encode("utf-8"),
        msg=raw_body,
        digestmod=hashlib.sha256,
    ).hexdigest()
    return f"sha256={signature}"
```

---

## 4. Webhook Receiver Endpoint

### API Contract
- **Method**: `POST`
- **Route**: `/api/v1/webhooks/mock-lenders/events`
- **Authentication**: `X-Mock-Lender-Signature: sha256=<hex_digest>`
- **Content-Type**: `application/json`
- **Status Codes**:
  - `200 OK`: Event processed or duplicate replay accepted.
  - `401 Unauthorized`: Missing, malformed, or invalid signature.
  - `404 Not Found`: Unknown `submission_id`, mismatched `mock_reference`, or mismatched `lender_code`.
  - `409 Conflict`: Conflicting payload for previously received `event_id`.
  - `422 Unprocessable Content`: Schema validation failure or presence of PII / unexpected fields.
  - `503 Service Unavailable`: Webhook secret is not configured on the server.

### Response Payload (`LenderEventResponse`)
```json
{
  "id": 45,
  "event_id": "evt_apex_98124_acc",
  "submission_id": 12,
  "event_type": "lender.accepted",
  "sequence_number": 1,
  "processing_status": "processed",
  "occurred_at": "2026-11-09T02:40:00Z",
  "created_at": "2026-11-09T02:40:01Z",
  "submission_status": "accepted",
  "application_status": "accepted",
  "duplicate": false
}
```

---

## 5. Supported Event Types and State Transitions

| Mock Event Type | Target `OfferSubmission.status` | Target `LoanApplication.status` | Description |
|---|---|---|---|
| `lender.accepted` | `accepted` | `accepted` | Fictional lender approved the submission |
| `lender.declined` | `declined` | `declined` | Fictional lender rejected the submission |
| `lender.timed_out` | `timed_out` | `timed_out` | Fictional lender decision window elapsed |
| `lender.failed` | `failed` | `failed` | Technical or execution failure at the mock lender |

### Offer Status Immutability
- The underlying `Offer.status` remains `"selected"`.
- The financial terms (`loan_amount`, `apr`, `term_months`, `monthly_installment`) remain strictly unchanged and continue to reflect the agreed terms.
- The Key Facts Statement (`GET /api/v1/applications/{application_id}/offers/{offer_id}/kfs`) remains fully accessible and readable.

---

## 6. Example Webhook Payloads

### 1. `lender.accepted`
```json
{
  "event_id": "evt_apex_891234_acc",
  "submission_id": 12,
  "mock_reference": "MOCK-SUB-APEX_FINANCIAL-12",
  "lender_code": "APEX_FINANCIAL",
  "event_type": "lender.accepted",
  "sequence_number": 1,
  "occurred_at": "2026-11-09T02:40:00Z",
  "reason_code": "STANDARD_APPROVAL"
}
```

### 2. `lender.declined`
```json
{
  "event_id": "evt_apex_891235_dec",
  "submission_id": 12,
  "mock_reference": "MOCK-SUB-APEX_FINANCIAL-12",
  "lender_code": "APEX_FINANCIAL",
  "event_type": "lender.declined",
  "sequence_number": 1,
  "occurred_at": "2026-11-09T02:40:00Z",
  "reason_code": "RISK_SCORE_THRESHOLD"
}
```

### 3. `lender.timed_out`
```json
{
  "event_id": "evt_apex_891236_to",
  "submission_id": 12,
  "mock_reference": "MOCK-SUB-APEX_FINANCIAL-12",
  "lender_code": "APEX_FINANCIAL",
  "event_type": "lender.timed_out",
  "sequence_number": 1,
  "occurred_at": "2026-11-09T02:40:00Z",
  "reason_code": "DECISION_WINDOW_EXPIRED"
}
```

### 4. `lender.failed`
```json
{
  "event_id": "evt_apex_891237_fail",
  "submission_id": 12,
  "mock_reference": "MOCK-SUB-APEX_FINANCIAL-12",
  "lender_code": "APEX_FINANCIAL",
  "event_type": "lender.failed",
  "sequence_number": 1,
  "occurred_at": "2026-11-09T02:40:00Z",
  "reason_code": "DOWNSTREAM_DISPATCH_FAILURE"
}
```

---

## 7. Duplicate Event Handling and Conflict Detection

When a webhook arrives with an `event_id` that already exists in the `LenderEvent` table:
1. **Identical Replay**: If the incoming `event_type`, `submission_id`, `sequence_number`, and `occurred_at` match the stored event record:
   - Returns `200 OK`.
   - Returns the existing record with `"duplicate": true`.
   - Does not re-mutate application or submission status.
   - Prevents duplicate database inserts.
2. **Conflicting Replay**: If the incoming payload differs in `event_type`, `submission_id`, `sequence_number`, or `occurred_at`:
   - Returns `409 Conflict`.
   - Explains that the `event_id` is already bound to a conflicting event payload.
   - Rejects payload manipulation or forgery.

---

## 8. Event Sequencing and Out-of-Order Delivery

In distributed webhook delivery, network retries and routing anomalies can cause events to arrive out of order (e.g. sequence 2 arrives before sequence 1).

### Authoritative Sequence Ordering
1. Every event includes a positive monotonic integer `sequence_number`.
2. When an event arrives, the engine queries the maximum `sequence_number` of previously processed events for that submission:
   $$\text{max\_processed} = \max(\text{sequence\_number}) \quad \text{where} \quad \text{processing\_status} = \text{'processed'}$$
3. **Stale or Out-of-Order Event** ($\text{sequence\_number} \le \text{max\_processed}$):
   - The event is recorded in `LenderEvent` with `processing_status = "ignored"`.
   - Neither `OfferSubmission.status` nor `LoanApplication.status` is modified.
   - The response returns `processing_status: "ignored"`.
4. **Authoritative Newer Event** ($\text{sequence\_number} > \text{max\_processed}$):
   - The event is recorded with `processing_status = "processed"`.
   - Both `OfferSubmission.status` and `LoanApplication.status` advance to the new outcome.

---

## 9. Concurrency and Row Locking

To prevent race conditions between simultaneous webhooks or between webhooks and customer retry submissions:
1. **Canonical Lock Ordering**:
   ```python
   # 1. Lock LoanApplication first
   app = (
       db.query(LoanApplication)
       .filter(LoanApplication.id == submission.application_id)
       .with_for_update()
       .first()
   )
   # 2. Lock OfferSubmission second
   sub = (
       db.query(OfferSubmission)
       .filter(OfferSubmission.id == event.submission_id)
       .with_for_update()
       .first()
   )
   ```
2. **Deadlock Prevention**: All services (offer submission and webhook processing) acquire locks in the exact same order: `LoanApplication` $\rightarrow$ `OfferSubmission`.
3. **Integrity Safeguards**: If two concurrent workers receive the same `event_id` simultaneously, PostgreSQL's `UNIQUE (event_id)` constraint forces one to abort. The service catches `IntegrityError`, rolls back the sub-transaction, and re-queries to handle it as an idempotent replay.

---

## 10. Customer Event History API

Customers can inspect the complete audit trail of webhook events for their submission.

### API Contract
- **Method**: `GET`
- **Route**: `/api/v1/applications/{application_id}/submission/events`
- **Authentication**: Bearer JWT (`customer` role required)
- **Authorization**: The customer must own the application (`customer_id == current_user.id`). Other customers receive `404 Not Found`. Callers and admins receive `403 Forbidden`.
- **Status Codes**:
  - `200 OK`: Returns the list of events. (Returns an empty list `[]` if the application has not yet been submitted).
  - `401 Unauthorized`: Missing or invalid Bearer token.
  - `403 Forbidden`: Authenticated user is a `caller` or `admin`.
  - `404 Not Found`: Unknown application or unowned application.

### Ordering
Results are strictly ordered by:
1. `sequence_number ASC NULLS LAST`
2. `occurred_at ASC`
3. `id ASC`

### Response Payload
```json
[
  {
    "id": 45,
    "event_id": "evt_apex_98124_acc",
    "submission_id": 12,
    "event_type": "lender.accepted",
    "sequence_number": 1,
    "processing_status": "processed",
    "occurred_at": "2026-11-09T02:40:00Z",
    "created_at": "2026-11-09T02:40:01Z"
  }
]
```

---

## 11. Security and Privacy Hardening

1. **No PII in Event Payloads**:
   The `details` dictionary is strictly validated and sanitized. PII fields (e.g. `customer_name`, `email`, `pan_number`, `phone_number`, `aadhaar`, `password`, `income`) are rejected with `422 Unprocessable Content`.
2. **Schema Whitelisting**:
   The event schema uses `extra = "forbid"` to reject any unvetted fields.
3. **Strict Integer Validation**:
   Boolean values (`True`/`False`) are explicitly rejected for integer fields (`submission_id`, `sequence_number`) to prevent Python type coercion vulnerabilities.
4. **Timezone Enforcement**:
   The `occurred_at` timestamp must be a valid ISO 8601 string with explicit timezone offset.

---

## 12. Verification and Testing Summary

The test suite in `backend/tests/test_lender_events.py` covers 57 verification scenarios across 17 test functions:

1. **HMAC Security**:
   - Valid signatures accepted.
   - Missing, malformed, or tampered signatures return `401 Unauthorized`.
   - Unset webhook secret returns `503 Service Unavailable`.
   - Modifying raw request body invalidates the signature.
2. **Outcome State Transitions**:
   - `lender.accepted` $\rightarrow$ `accepted`.
   - `lender.declined` $\rightarrow$ `declined`.
   - `lender.timed_out` $\rightarrow$ `timed_out`.
   - `lender.failed` $\rightarrow$ `failed`.
   - Offer terms and status remain `"selected"` and uncorrupted.
   - KFS remains readable after terminal outcome.
3. **Reference Validation**:
   - Unknown submission ID returns `404 Not Found`.
   - Mismatched `mock_reference` returns `404 Not Found`.
   - Mismatched `lender_code` returns `404 Not Found`.
   - PII fields and unexpected properties are rejected with `422`.
4. **Duplicate Replay and Conflicts**:
   - Exact replays return `200 OK` with `duplicate: true`.
   - Conflicting replays with different event details return `409 Conflict`.
5. **Sequencing and Ordering**:
   - Normal progression updates state.
   - Out-of-order or stale sequence numbers are marked `processing_status = "ignored"` without mutating submission or application state.
6. **Transaction Atomicity and Concurrency**:
   - Database errors roll back both event persistence and status mutations.
   - Concurrent webhook deliveries across separate threads/sessions are serialized and prevent duplicate database records.
   - Submissions replayed after webhook outcomes preserve the current outcome status.
7. **Customer Event History API**:
   - Ownership verification, sorting order, empty state handling, and customer isolation.
8. **Test Cleanup Safety**:
   - Cleanup functions isolate test data by prefix and never delete unrelated records.
