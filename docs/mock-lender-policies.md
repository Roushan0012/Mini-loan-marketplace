# Mock Lender Underwriting Policies & Consent Hardening

## 1. Overview & Training Purpose

The Mini Loan Marketplace integrates versioned underwriting policies to simulate automated eligibility evaluation across multiple fictional lending partners.

> [!IMPORTANT]
> **TRAINING DEMO DISCLOSURE**: All lender identities, lender codes (`APEX_FINANCIAL`, `HORIZON_CREDIT`, `STERLING_LOANS`), policy parameters, income thresholds, and eligibility rules described in this document and implemented in the codebase are **purely fictional training examples**. No real financial institution, bank, non-banking financial company (NBFC), or credit bureau is contacted or modeled.

Versioned mock policies provide deterministic, auditable rules against which applicant profiles (`age`, `monthly_income`, `work_type`) can be evaluated during the loan matching lifecycle.

---

## 2. Fictional Training Lender Policies

Three initial version `v1.0` policies are defined and seeded into the system:

| Lender Code | Lender Name | Version | Min Age | Min Monthly Income | Permitted Work Types | Active |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `APEX_FINANCIAL` | Apex Financial | `v1.0` | 21 | ₹25,000.00 | `salaried`, `self_employed` | `true` |
| `HORIZON_CREDIT` | Horizon Credit | `v1.0` | 23 | ₹30,000.00 | `salaried` | `true` |
| `STERLING_LOANS` | Sterling Loans | `v1.0` | 25 | ₹40,000.00 | `salaried`, `self_employed` | `true` |

### Profile Criteria Summary

- **Apex Financial (`APEX_FINANCIAL`)**: Accessible entry tier requiring minimum age 21, minimum monthly income of 25,000.00, and accepting both salaried and self-employed applicants.
- **Horizon Credit (`HORIZON_CREDIT`)**: Mid-tier lender focusing strictly on salaried professionals with minimum age 23 and minimum monthly income of 30,000.00.
- **Sterling Loans (`STERLING_LOANS`)**: Prime tier requiring minimum age 25, minimum monthly income of 40,000.00, open to both salaried and self-employed individuals.

---

## 3. JSONB Rule Structure & Pydantic Schema

Eligibility rules are stored in the PostgreSQL `rules` JSONB column of the `lender_policies` table. Schema integrity is strictly enforced by the Pydantic model `LenderPolicyRules` located in [`backend/app/schemas/lender_policy.py`](file:///Users/roushan_iiitbgp/Desktop/Mini_Loan_Marketplace/backend/app/schemas/lender_policy.py).

### Schema Specification

```python
class LenderPolicyRules(BaseModel):
    model_config = ConfigDict(extra="forbid")

    min_age: int = Field(..., gt=0, le=100)
    min_monthly_income: Decimal = Field(..., ge=0, max_digits=12, decimal_places=2)
    allowed_work_types: List[str] = Field(..., min_length=1)
```

### Validation Constraints

1. **`min_age`**: Integer strictly greater than 0 and less than or equal to 100.
2. **`min_monthly_income`**: Non-negative `Decimal` value serialized with up to 12 digits and 2 decimal places.
3. **`allowed_work_types`**: Non-empty list restricted strictly to items from `{"salaried", "self_employed", "other"}`.
4. **Duplicate Rejection**: Entries within `allowed_work_types` are normalized and checked for duplicates (e.g., `["salaried", "salaried"]` or `["Salaried", "salaried"]` are rejected).
5. **Forbidden Extra Keys**: `extra="forbid"` ensures arbitrary or unapproved attributes in policy payloads trigger validation failure.

### Handling Invalid Stored Policy Rules

If an existing database record contains corrupted or non-conforming JSON in its `rules` column, the matching engine does not crash the broader multi-lender evaluation batch. Instead:
- The parser intercepts the `pydantic.ValidationError`.
- A diagnostic configuration error is logged with policy metadata (`id`, `lender_code`, `policy_version`).
- The policy is treated as ineligible or suspended for that run, allowing other valid lender policies to be evaluated uninterrupted.

---

## 4. Policy Versioning & Historical Immutability

Lender policies are versioned using a composite unique constraint:

```sql
CONSTRAINT uq_lender_policies_lender_code_policy_version UNIQUE (lender_code, policy_version)
```

### Why Old Versions Are Retained

In lending platforms, underwriting rules evolve over time (e.g., income thresholds adjust for economic conditions). However:
- Every loan decision (`lender_decisions`) maintains a foreign key reference (`lender_policy_id`) pointing to the exact policy under which the decision was rendered.
- If policy definitions were updated in place, audit trails for past approvals or declinations would become corrupted and legally indefensible.
- When underwriting criteria change, lenders create a new version (e.g., `APEX_FINANCIAL` version `v1.1` or `v2.0`). Existing historical versions (`v1.0`) remain immutable in the database.

---

## 5. Idempotent Seeding & Safety Guards

Seeding is handled via [`backend/app/db/seed_lender_policies.py`](file:///Users/roushan_iiitbgp/Desktop/Mini_Loan_Marketplace/backend/app/db/seed_lender_policies.py).

### Execution Command

```bash
python -m app.db.seed_lender_policies
```

### Seeding Logic & Idempotency

1. Queries for existing records matching `(lender_code, policy_version)`.
2. **New Policy**: Inserts row and returns `inserted`.
3. **Identical Existing Policy**: Verifies that existing metadata and normalized JSON rules match the seed definition. If identical, skips insertion without modification and returns `skipped`.
4. **Mismatched Existing Policy**: If an existing record with the same `(lender_code, policy_version)` has different rules or metadata, the script raises `ValueError("Seed mismatch...")`, executes an immediate transaction rollback, and halts without modifying data.
5. **Atomic Commit**: All new records are committed in a single transaction.

### Safety Guards

The CLI entrypoint enforces strict runtime safety checks:
- Requires `ENVIRONMENT == "development"`.
- Requires `POSTGRES_DB == "mini_loan_marketplace"`.
- Rejects execution against production environments or the automated test database (`mini_loan_marketplace_test`).

---

## 6. Consent Readiness Hardening

During Step 8A, two critical readiness vulnerabilities in [`backend/app/services/consent_service.py`](file:///Users/roushan_iiitbgp/Desktop/Mini_Loan_Marketplace/backend/app/services/consent_service.py) were resolved.

### Fix 1: Multi-Version Consent Resolution

**Previous Defect**:
The original implementation built an in-memory dictionary from all granted consent records:
```python
# Old flawed logic:
active_map = {c.purpose: c.notice_version for c in active_consents}
```
If an applicant had granted an older version (e.g., `v1.0`) and subsequently granted a newer active version (e.g., `v1.1`), the order of iteration in the dictionary comprehension could cause `v1.0` to overwrite `v1.1`, falsely marking consent as missing.

**Resolution**:
`has_required_active_consents()` and `get_missing_required_consents()` now query PostgreSQL directly for the specific current version:
```python
record = (
    db.query(Consent.id)
    .filter(
        Consent.application_id == application_id,
        Consent.purpose == purpose,
        Consent.notice_version == current_ver,
        Consent.status == "granted",
    )
    .first()
)
```
This guarantees that an active current version is recognized immediately, older granted versions never shadow active versions, and revoked current versions properly disqualify readiness.

### Fix 2: Application Lifecycle Status Allowlist

**Previous Defect**:
`is_consent_change_permitted()` previously relied on a blacklist of closed statuses (`CLOSED_APPLICATION_STATUSES`). Any unexpected, intermediate, or unlisted lifecycle state implicitly permitted consent modification.

**Resolution**:
Replaced with an explicit allowlist of documented pre-submission states:
```python
ALLOWED_CONSENT_APPLICATION_STATUSES = {
    "draft",
    "matching",
    "matched",
    "offers_ready",
    "offer_selected",
}

def is_consent_change_permitted(application_status: str) -> bool:
    return application_status in ALLOWED_CONSENT_APPLICATION_STATUSES
```
All post-submission states (`submitted`, `accepted`, `declined`, `finalized`, `timed_out`, `failed`) and any unrecognized custom states strictly reject consent modifications, raising a `ConsentConflictError` mapped to `HTTP 409 Conflict`.
