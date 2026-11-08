# Deterministic Multi-Lender Matching Engine

## 1. Overview & Architecture

The Matching Engine simulates automated, multi-lender credit eligibility evaluation. It ingests customer loan applications and evaluates them against versioned lender underwriting policies stored as JSONB rules in PostgreSQL.

```
+-----------------------------------------------------------------------------------+
|                           POST /api/v1/applications/{id}/match                    |
+-----------------------------------------------------------------------------------+
                                         |
                                         v
               +---------------------------------------------------+
               | 1. Authentication & Ownership Verification         |
               |    - current_user.role == "customer"              |
               |    - application.customer_id == current_user.id    |
               +---------------------------------------------------+
                                         |
                                         v
               +---------------------------------------------------+
               | 2. Application Status Validation                  |
               |    - Status must be 'draft' or 'matched'          |
               +---------------------------------------------------+
                                         |
                                         v
               +---------------------------------------------------+
               | 3. Mandatory Consent Verification                 |
               |    - eligibility_matching (current active version)|
               |    - sharing_with_mock_lenders (current version)  |
               +---------------------------------------------------+
                                         |
                                         v
               +---------------------------------------------------+
               | 4. Concurrency Lock & MatchRun Creation           |
               |    - SELECT ... FOR UPDATE on LoanApplication     |
               |    - Compute next sequential run_number           |
               |    - Create MatchRun (status: started)            |
               |    - Set application.status = 'matching'          |
               +---------------------------------------------------+
                                         |
                                         v
               +---------------------------------------------------+
               | 5. Deterministic Policy Evaluation (per lender)   |
               |    - APEX_FINANCIAL (v1.0)                        |
               |    - HORIZON_CREDIT (v1.0)                        |
               |    - STERLING_LOANS (v1.0)                        |
               |    - Validate JSONB rules via LenderPolicyRules   |
               |    - Record LenderDecision rows                   |
               +---------------------------------------------------+
                                         |
                                         v
               +---------------------------------------------------+
               | 6. Atomic Transaction Commit                      |
               |    - MatchRun.status = 'completed'                |
               |    - Application.status = 'matched'               |
               |    - Return HTTP 201 + MatchRunResponse           |
               +---------------------------------------------------+
```

> [!IMPORTANT]
> **TRAINING DEMO DISCLOSURE**: All lenders, lender codes (`APEX_FINANCIAL`, `HORIZON_CREDIT`, `STERLING_LOANS`), policy parameters, and eligibility evaluations are **purely fictional training simulations**. No real banks, NBFCs, credit bureaus, or external financial APIs are contacted or integrated.

> [!NOTE]
> **Eligibility vs. Final Approval**: An `eligible` decision indicates that the applicant's self-reported profile satisfies a lender's baseline underwriting filters. It does **not** constitute a formal loan offer, sanction letter, or credit commitment. Formal offers, loan agreements, and lender integration adapters belong to future development steps.

---

## 2. Fictional Training Policies & Underwriting Rules

Policies are retrieved from PostgreSQL filtering on `is_active == True` and sorted deterministically by `lender_code`:

| Lender Code | Policy Version | Min Age | Min Monthly Income | Permitted Work Types |
| :--- | :--- | :--- | :--- | :--- |
| `APEX_FINANCIAL` | `v1.0` | 21 | ₹25,000.00 | `salaried`, `self_employed` |
| `HORIZON_CREDIT` | `v1.0` | 23 | ₹30,000.00 | `salaried` |
| `STERLING_LOANS` | `v1.0` | 25 | ₹40,000.00 | `salaried`, `self_employed` |

---

## 3. Deterministic Evaluation Logic

For each active policy, the applicant's attributes are evaluated against three criteria:

1. **Age**: `application.age >= rules.min_age`
2. **Monthly Income**: `Decimal(application.monthly_income) >= Decimal(rules.min_monthly_income)` (exact Decimal precision without floating-point conversion)
3. **Work Type**: `application.work_type.lower() in rules.allowed_work_types`

### Exclusion Reason Codes

When an application fails one or more criteria, a structured reason code is assigned:

| Condition | Outcome | Exclusion Reason Code | Exclusion Reason Detail |
| :--- | :--- | :--- | :--- |
| All criteria pass | `eligible` | `NULL` | `NULL` |
| Age below minimum | `ineligible` | `AGE_BELOW_MINIMUM` | Explanatory message with applicant age & policy minimum |
| Income below minimum | `ineligible` | `INCOME_BELOW_MINIMUM` | Explanatory message with applicant income & policy minimum |
| Disallowed work type | `ineligible` | `WORK_TYPE_NOT_ALLOWED` | Explanatory message with applicant work type & allowed types |
| Multiple rules fail | `ineligible` | `MULTIPLE_RULES_FAILED` | Semicolon-delimited summary of all failed conditions |
| Stored JSONB invalid | `ineligible` | `POLICY_CONFIGURATION_INVALID` | Schema validation error details |

Database check constraints on `lender_decisions` enforce that:
- `eligible` decisions have both `exclusion_reason_code` and `exclusion_reason` set to `NULL`.
- `ineligible` decisions have a non-null `exclusion_reason_code`.

### Malformed Policy Resilience

If an individual lender policy contains malformed JSONB rules that fail `LenderPolicyRules.model_validate`, the engine logs a safe diagnostic warning (without exposing customer PII) and records an `ineligible` decision with `POLICY_CONFIGURATION_INVALID`. The engine does **not** crash the entire batch run, ensuring other valid lenders continue to be evaluated.

---

## 4. Consent Requirements & Primary Reference

Before running eligibility evaluation, the system executes:

```python
has_required_active_consents(db, application.id)
```

Both required purposes must have active, granted consents matching their current published notice versions:
1. `eligibility_matching` (`v1.0`)
2. `sharing_with_mock_lenders` (`v1.0`)

If either consent is missing, revoked, or outdated, matching is blocked with `HTTP 409 Conflict`, returning a payload identifying the missing purpose(s).

### Primary Consent Reference

The `match_runs` table has a mandatory foreign key `consent_id` referencing `consents.id`. This column stores the ID of the applicant's active `eligibility_matching` consent record—the primary legal authorization allowing automated matching algorithms to evaluate profile data. Both consents are strictly verified prior to run execution.

---

## 5. MatchRun Lifecycle & Concurrency Protection

### Sequential Run Numbering

Applications can be re-evaluated as applicant details update or lenders change policies. Repeated matching calls increment the sequential `run_number` per application:
- Initial match: `run_number = 1`
- Subsequent match: `run_number = 2`

Previous `MatchRun` records and associated `LenderDecision` rows remain permanently immutable in PostgreSQL for full historical auditing.

### Concurrency & Locking

To prevent race conditions during concurrent matching requests:
1. The engine locks the parent `LoanApplication` row using PostgreSQL `SELECT ... FOR UPDATE`.
2. The next `run_number` is computed while holding the lock: `MAX(run_number) + 1`.
3. If an unexpected concurrent race occurs, the composite unique constraint `(application_id, run_number)` triggers an `IntegrityError`, caught and converted into a controlled `HTTP 409 Conflict` with transaction rollback.

---

## 6. API Reference

### 1. Execute Matching

**`POST /api/v1/applications/{application_id}/match`**

- **Authorization**: Bearer JWT (`customer` role only)
- **Status Codes**:
  - `201 Created`: Matching executed successfully. Returns `MatchRunResponse`.
  - `401 Unauthorized`: Missing or invalid token.
  - `403 Forbidden`: Caller or Admin role attempted matching.
  - `404 Not Found`: Application does not exist or belongs to another customer.
  - `409 Conflict`: Missing required consent or application not in `draft`/`matched` status.
  - `503 Service Unavailable`: No active policies or ambiguous policy configuration.

#### Response Example (`201 Created`)

```json
{
  "id": 1,
  "application_id": 10,
  "run_number": 1,
  "status": "completed",
  "started_at": "2026-11-08T04:20:00Z",
  "completed_at": "2026-11-08T04:20:01Z",
  "decisions": [
    {
      "id": 1,
      "lender_code": "APEX_FINANCIAL",
      "lender_name": "Apex Financial",
      "policy_version_snapshot": "v1.0",
      "decision_status": "eligible",
      "exclusion_reason_code": null,
      "exclusion_reason": null,
      "evaluated_at": "2026-11-08T04:20:00Z"
    },
    {
      "id": 2,
      "lender_code": "HORIZON_CREDIT",
      "lender_name": "Horizon Credit",
      "policy_version_snapshot": "v1.0",
      "decision_status": "ineligible",
      "exclusion_reason_code": "WORK_TYPE_NOT_ALLOWED",
      "exclusion_reason": "Applicant work type 'self_employed' is not allowed by policy. Permitted work types: ['salaried'].",
      "evaluated_at": "2026-11-08T04:20:00Z"
    },
    {
      "id": 3,
      "lender_code": "STERLING_LOANS",
      "lender_name": "Sterling Loans",
      "policy_version_snapshot": "v1.0",
      "decision_status": "eligible",
      "exclusion_reason_code": null,
      "exclusion_reason": null,
      "evaluated_at": "2026-11-08T04:20:00Z"
    }
  ]
}
```

### 2. Retrieve Match History

**`GET /api/v1/applications/{application_id}/matches`**

- **Authorization**: Bearer JWT (`customer` role only)
- **Status Codes**:
  - `200 OK`: Returns `MatchRunSummaryResponse` with full history ordered by `run_number ASC`.
  - `404 Not Found`: Application does not exist or belongs to another customer.

#### Response Example (`200 OK`)

```json
{
  "total_runs": 1,
  "runs": [
    {
      "id": 1,
      "application_id": 10,
      "run_number": 1,
      "status": "completed",
      "started_at": "2026-11-08T04:20:00Z",
      "completed_at": "2026-11-08T04:20:01Z",
      "decisions": [...]
    }
  ]
}
```
