# Capstone Requirements Traceability Matrix

> [!NOTE]
> **Source Material Audit & Handbook Availability Notice**:
> The original external course/curriculum handbook or assignment specification (e.g. `Module 16 Capstone Handbook` / PDF) is not included within this repository workspace. Consequently, this audit and traceability matrix are constructed strictly from the repository's source documentation—including [README.md](../README.md), [docs/workflow.md](workflow.md), [docs/architecture.md](architecture.md), [docs/security-and-access-control.md](security-and-access-control.md), and corresponding implementation documentation files in `docs/`.
> 
> Full compliance is verified against the specifications defined in this repository's established documentation. To conduct an exact external academic or organizational assignment compliance check, the original external Module 16 Capstone Handbook / PDF would need to be provided.

---

## 1. Role-Based Requirements Matrix

### 1.1 Customer Role

| Requirement | Workflow Stage | Implementation Location | Verification Method | Status | Evidence |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **User Registration & Authentication**<br>Self-service customer registration, credential verification, and JWT issuance | Identity & Auth | `backend/app/api/v1/auth.py`<br>`backend/app/core/security.py`<br>`frontend/src/features/auth/` | Unit, integration & E2E tests (`test_auth.py`, `test_role_isolation.py`) | Complete | Registration endpoint restricted to `customer` role only; password hashed with PBKDF2; JWT returned. |
| **Loan Application Creation & Editing**<br>Create draft application with age, monthly income, work type, requested amount; edit draft before submission | Application Lifecycle (Steps 1–2) | `backend/app/api/v1/applications.py`<br>`frontend/src/features/applications/` | Schema validation, lifecycle tests (`test_applications.py`, `test_full_customer_lifecycle.py`) | Complete | CRUD endpoints enforce `customer` role ownership; draft state updates allowed only while in draft. |
| **Purpose-Specific Consent Management**<br>Explicit consent notices for `eligibility_matching` and `sharing_with_mock_lenders` with notice versioning and audit timestamp | Consent Management (Steps 3–4) | `backend/app/api/v1/consents.py`<br>`backend/app/models/consent.py`<br>`frontend/src/features/consents/` | API tests (`test_consents.py`), E2E lifecycle tests | Complete | Versioned notices (`v1.0`), granular per-purpose grant/history, UTC audit timestamps recorded. |
| **Consent Revocation & Gating**<br>Allow customer to revoke consent; block lender matching if required consent is revoked or missing | Consent Revocation & Guard (Steps 5–6) | `backend/app/services/consent_service.py`<br>`backend/app/api/v1/matching.py`<br>`frontend/src/features/consents/` | Negative and positive consent tests (`test_consent_service.py`, `test_matching.py`) | Complete | `POST /applications/{id}/match` returns HTTP 400 with `MISSING_CONSENT` if either active consent is revoked or absent. |
| **Multi-Lender Matching Engine**<br>Evaluate profile across 3 versioned fictional policies (Apex Financial, Horizon Credit, Sterling Loans) | Matching Engine (Steps 7–8) | `backend/app/services/matching_service.py`<br>`backend/app/models/lender_policy.py`<br>`frontend/src/features/matching/` | Rule evaluation tests (`test_matching_engine.py`, `test_lender_policies.py`) | Complete | Persists immutable `MatchRun` with explicit eligibility status and structured exclusion reasons per lender. |
| **Offer Generation & Transparent Comparison**<br>Generate deterministic mock offers for eligible lenders; compare APR, term, amount, monthly instalment | Offer Exploration (Steps 9–10) | `backend/app/services/offer_service.py`<br>`backend/app/api/v1/offers.py`<br>`frontend/src/features/offers/` | Offer calculation tests (`test_offer_service.py`, `test_offers_api.py`) | Complete | Strict decimal financial calculations (monthly instalment / EMI); displays eligible offers and nonmatching lender cards. |
| **Mock Key Facts Statement (KFS)**<br>Generate standardized mock KFS transparency sheet with APR, fees, schedule, recovery terms, and fictional disclaimer | Disclosure & Review (Step 10) | `backend/app/services/kfs_service.py`<br>`backend/app/api/v1/offers.py`<br>`frontend/src/features/offers/components/MockKfsModal.tsx` | KFS service and endpoint tests (`test_mock_kfs.py`) | Complete | `GET /offers/{id}/kfs` returns standardized disclosure with total repayment, interest breakdown, and regulatory disclaimer. |
| **Single Offer Selection**<br>Customer selects exactly one offer; remaining offers for the application are withdrawn | Offer Selection (Step 11) | `backend/app/services/offer_selection_service.py`<br>`backend/app/api/v1/offers.py`<br>`frontend/src/features/offers/` | State transition tests (`test_offer_selection.py`) | Complete | Selection transitions chosen offer to `selected` and atomically withdraws unselected peer offers. |
| **Idempotent Mock Offer Submission**<br>Submit selected offer with mandatory `Idempotency-Key` header; safely handle replays and network retries | Offer Submission (Step 12) | `backend/app/services/offer_submission_service.py`<br>`backend/app/api/v1/submissions.py`<br>`frontend/src/features/submissions/` | Idempotency and replay tests (`test_offer_submission.py`, `test_full_customer_lifecycle.py`) | Complete | Enforces unique `idempotency_key`; returns original submission payload on replay without duplicate dispatch. |
| **Simulated Event Tracking & Audit Trail**<br>Track asynchronous lender events, event timeline, and terminal outcomes (`accepted`, `declined`, `timed_out`, `failed`) | Event Tracking (Step 13) | `backend/app/services/lender_event_service.py`<br>`backend/app/api/v1/submissions.py`<br>`frontend/src/features/submissions/` | Event sequencing and duplicate webhook tests (`test_lender_events.py`) | Complete | Customer can query `GET /submissions/{id}/events` to observe event history, transition timestamps, and final status. |

---

### 1.2 Caller Role

| Requirement | Workflow Stage | Implementation Location | Verification Method | Status | Evidence |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Strict Assigned-Lead Isolation**<br>Caller can view only leads explicitly assigned to their caller ID in `lead_assignments` | Lead Workspace | `backend/app/api/v1/caller.py`<br>`backend/app/services/caller_service.py`<br>`frontend/src/features/caller/` | Role isolation tests (`test_caller_api.py`, `test_role_isolation.py`) | Complete | Queries join `lead_assignments` filtering by authenticated `caller_id`. Callers cannot view unassigned leads or leads assigned to other callers. |
| **Lead Filtering, Search & Pagination**<br>Search leads by synthetic reference or applicant name; filter by status and work type; server-side pagination | Lead Workspace | `backend/app/api/v1/caller.py`<br>`frontend/src/features/caller/components/CallerLeadList.tsx` | Search and filter tests (`test_caller_api.py`, `CallerWorkspace.test.tsx`) | Complete | Case-insensitive search on `applicant_name` and `synthetic_reference`, enum filtering on `work_type` and `status`, limit/offset pagination. |
| **Read-Only Access Boundary**<br>Caller cannot mutate lead assignments, modify lead statuses, or access customer/admin routes | Role Boundary | `backend/app/api/v1/caller.py`<br>`frontend/src/routes/RoleProtectedRoute.tsx` | RBAC test suite (`test_role_isolation.py`) | Complete | Endpoints are read-only (`GET`); customer application mutation and admin analytics return HTTP 403 Forbidden. |

---

### 1.3 Admin Role

| Requirement | Workflow Stage | Implementation Location | Verification Method | Status | Evidence |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Aggregate Funnel Telemetry**<br>View total applications, drafts, submitted, matched, accepted, declined, and timed out counts | Executive Monitoring | `backend/app/services/admin_metrics_service.py`<br>`backend/app/api/v1/admin.py`<br>`frontend/src/features/admin/` | Metric accuracy tests (`test_admin_metrics.py`, `AdminDashboard.test.tsx`) | Complete | Direct SQL aggregate counts (`COUNT`, `GROUP BY`) across application and submission statuses. |
| **Zero-PII Privacy Protection**<br>Admin telemetry must never return customer names, contact info, income, or individual financial terms | Privacy & Compliance | `backend/app/schemas/admin_metrics.py`<br>`backend/app/api/v1/admin.py` | Data leak audit tests (`test_role_isolation.py`, `test_admin_metrics.py`) | Complete | Pydantic response models contain only numeric counts, durations, and category ratios; no customer entity records returned. |
| **Processing Delay & Error Monitoring**<br>Monitor median submission turnaround time and lender failure/timeout counts | Operational Telemetry | `backend/app/services/admin_metrics_service.py`<br>`frontend/src/features/admin/components/ProcessingDelayCard.tsx` | Timing calculation tests (`test_admin_metrics.py`) | Complete | Median duration computed from submission creation to terminal event; failure rates tabulated by simulated lender. |
| **Role Boundary Protection**<br>Admin role cannot access customer application workflows or mutate caller assignments | Access Control | `backend/app/api/v1/applications.py`<br>`backend/app/api/v1/caller.py` | RBAC isolation tests (`test_role_isolation.py`) | Complete | Attempting customer or caller endpoints with Admin token returns HTTP 403 Forbidden. |

---

## 2. 13-Step Customer Journey Lifecycle Matrix

| Step # | Journey Step Description | Backend API Endpoint | Database Entities Involved | Frontend UI Component | Verification Status |
| :---: | :--- | :--- | :--- | :--- | :---: |
| **1** | Create Draft Application | `POST /api/v1/applications/` | `LoanApplication` | `ApplicationCreateModal.tsx` | Complete |
| **2** | Enter Application Profile Details | `PUT /api/v1/applications/{id}` | `LoanApplication` | `ApplicationForm.tsx` | Complete |
| **3** | Display Purpose-Specific Consent Notices | `GET /api/v1/consents/notices` | Static Notice Config | `ConsentModal.tsx` | Complete |
| **4** | Record Consent Audit Trail | `POST /api/v1/applications/{id}/consents` | `Consent` | `ConsentManagementPanel.tsx` | Complete |
| **5** | Allow Consent Revocation | `POST /api/v1/applications/{id}/consents/revoke` | `Consent` | `ConsentRevokeDialog.tsx` | Complete |
| **6** | Verify Active Consent Before Matching | `POST /api/v1/applications/{id}/match` | `Consent`, `LoanApplication` | `MatchingTriggerCard.tsx` | Complete |
| **7** | Evaluate 3 Versioned Mock Lender Policies | `POST /api/v1/applications/{id}/match` | `LenderPolicy`, `MatchRun` | `MatchingStatusCard.tsx` | Complete |
| **8** | Record Policy Versions & Audit Reasons | `POST /api/v1/applications/{id}/match` | `MatchRun`, `LenderDecision` | `DecisionAuditView.tsx` | Complete |
| **9** | Present Eligible & Nonmatching Lenders | `GET /api/v1/applications/{id}/match-runs` | `MatchRun`, `LenderDecision` | `EligibilityResultsList.tsx` | Complete |
| **10** | Display Key Financial Terms & Mock KFS | `GET /api/v1/offers/{id}/kfs` | `Offer`, `LenderPolicy` | `OfferCard.tsx`, `MockKfsModal.tsx` | Complete |
| **11** | Customer Selects Exactly One Offer | `POST /api/v1/offers/{id}/select` | `Offer`, `LoanApplication` | `OfferSelectionButton.tsx` | Complete |
| **12** | Submit Offer with Idempotency Key | `POST /api/v1/applications/{id}/submissions` | `OfferSubmission` | `SubmitOfferModal.tsx` | Complete |
| **13** | Track Mock Responses & Event History | `GET /api/v1/submissions/{id}/events` | `LenderEvent`, `OfferSubmission` | `SubmissionStatusPanel.tsx` | Complete |

---

## 3. Failure & Resilience Matrix

| Failure Scenario | Threat / Failure Vector | Mitigation Mechanism | Implementation Location | Test Verification | Status |
| :--- | :--- | :--- | :--- | :--- | :---: |
| **Missing Consent** | Customer attempts matching without granting required consents | Strict validation in `match_application`; returns HTTP 400 | `backend/app/services/matching_service.py` | `test_matching.py` | Complete |
| **Consent Revocation** | Customer revokes consent after drafting | Active consent check halts downstream matching immediately | `backend/app/services/consent_service.py` | `test_consents.py` | Complete |
| **All Lenders Reject** | Profile fails all 3 lender underwriting criteria | Returns 0 eligible offers, structured decline reasons, application status updated cleanly | `backend/app/services/matching_service.py` | `test_matching_engine.py` | Complete |
| **Duplicate Submission** | Network retry resends submission request with same key | Returns existing submission record without duplicate side-effects | `backend/app/services/offer_submission_service.py` | `test_offer_submission.py` | Complete |
| **Duplicate Webhook** | Simulated lender re-transmits identical webhook | Idempotency guard on `event_id`; returns HTTP 200 with `duplicate=true` | `backend/app/services/lender_event_service.py` | `test_lender_events.py` | Complete |
| **Out-of-Order Webhook** | Webhook arrives with lower sequence than current status | Monotonic state guard; event recorded as `ignored` without state regression | `backend/app/services/lender_event_service.py` | `test_lender_events.py` | Complete |
| **Late Webhook on Terminal** | Webhook arrives after application reached terminal status | Terminal check rejects mutation; preserves terminal integrity | `backend/app/services/lender_event_service.py` | `test_lender_events.py` | Complete |
| **Simulated Partner Timeout** | Adapter simulation times out | Transitions submission to `timed_out`; increments admin timeout telemetry | `backend/app/services/lender_event_service.py` | `test_full_customer_lifecycle.py` | Complete |
