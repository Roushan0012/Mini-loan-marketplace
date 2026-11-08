# Security and Access Control Specification

## 1. Authentication versus Authorization

The Mini Loan Marketplace enforces a strict separation between **Authentication** (identity verification) and **Authorization** (permission control):

- **Authentication (AuthN)**: Answers *"Who are you?"*
  - The client presents credentials (email and password on login).
  - The system validates credentials using constant-time Argon2 verification.
  - Upon success, the server issues a digitally signed JWT access token containing the subject identifier (`sub`, the user's positive integer primary key).
  - Missing, expired, malformed, or tampered tokens result in an immediate **HTTP 401 Unauthorized** response with a `WWW-Authenticate: Bearer` challenge header.
- **Authorization (AuthZ)**: Answers *"Are you permitted to perform this action or view this resource?"*
  - Once the user's identity is authenticated, the application verifies whether their assigned account role or resource ownership permits the requested operation.
  - Insufficient privileges result in an immediate **HTTP 403 Forbidden** response with a generic error message, regardless of whether the user holds a valid session token.

---

## 2. Application User Roles

The system defines exactly three non-overlapping user roles stored in the PostgreSQL `users` table:

| Role | Definition & Scope | Restrictions |
| :--- | :--- | :--- |
| `customer` | Prospective borrowers who register publicly to draft loan applications, provide/revoke demo consent, view eligible matches, and select offers. | Cannot access caller leads or admin metrics. Self-registration is strictly restricted to this role. |
| `caller` | Operations agents who review mock lead records assigned directly to them. | Cannot view peer callers' leads, access administrative dashboards, or self-register. |
| `admin` | Internal platform administrators who monitor application funnel metrics, processing delays, and error frequencies. | Receives aggregate metrics only. Never receives individual customer records, borrower PII, or event payloads. Cannot access caller lead lists. |

Simulated lenders (*Apex Financial*, *Horizon Credit*, *Sterling Loans*) are treated as **external simulated integrations**, not as application user roles.

---

## 3. Role-Permission Matrix

| Endpoint | Method | Required Role | Public Access | Purpose |
| :--- | :---: | :---: | :---: | :--- |
| `/api/v1/health` | `GET` | None | Yes | Health check |
| `/api/v1/auth/register` | `POST` | None | Yes | Public customer self-registration |
| `/api/v1/auth/login` | `POST` | None | Yes | Credential verification & JWT issuance |
| `/api/v1/auth/me` | `GET` | Authenticated user (`customer`, `caller`, `admin`) | No | Retrieve personal user profile |
| `/api/v1/caller/leads` | `GET` | `caller` | No | List mock leads assigned exclusively to caller |
| `/api/v1/admin/dashboard/metrics` | `GET` | `admin` | No | Aggregate funnel & integration metrics |

---

## 4. How `require_roles` Works

Role-based access is implemented in `backend/app/core/permissions.py` using a parameterized FastAPI dependency factory:

```python
def require_roles(*allowed_roles: str) -> Callable[[User], User]:
    permitted_roles: Set[str] = set(allowed_roles)

    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in permitted_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access forbidden: insufficient permissions.",
            )
        return current_user

    return role_checker
```

### Execution Flow:
1. `role_checker` depends on `get_current_user`.
2. `get_current_user` extracts the Bearer token, verifies its cryptographic signature (`HS256`), validates expiration, and retrieves the active user record from the PostgreSQL database.
3. The role is evaluated strictly against `current_user.role` from the database. Client-submitted claims or headers are never trusted.
4. If `current_user.role` matches `permitted_roles`, the authenticated `User` object is injected into the endpoint handler.
5. If `current_user.role` does not match, FastAPI halts request processing and returns **HTTP 403 Forbidden**.

Pre-configured dependency singletons are exported for common route guards:
- `require_customer = require_roles("customer")`
- `require_caller = require_roles("caller")`
- `require_admin = require_roles("admin")`

---

## 5. Caller Lead Scoping and Resource Ownership

The `/api/v1/caller/leads` endpoint enforces strict isolation between callers:

1. **Authentication Scoping**: The endpoint derives the caller identity exclusively from `current_user.id`.
2. **Ignored Client Parameters**: Any attempt by a caller to specify or override a `caller_id` via query string, headers, or request body is ignored.
3. **Database-Level Join**:
   ```sql
   SELECT leads.*, lead_assignments.assigned_at
   FROM leads
   JOIN lead_assignments ON leads.id = lead_assignments.lead_id
   WHERE lead_assignments.caller_id = :authenticated_caller_id
   ORDER BY leads.id ASC
   LIMIT :limit OFFSET :offset;
   ```
4. **Peer Isolation**: Caller A cannot view leads assigned to Caller B. If a caller has zero assigned leads, an empty JSON list `[]` is returned without error.

---

## 6. Admin Aggregate Metrics & Privacy Protection

The `/api/v1/admin/dashboard/metrics` endpoint provides high-level system visibility while upholding zero-trust privacy boundaries:

1. **SQL-Level Aggregation**: Metrics are computed exclusively using PostgreSQL aggregate functions (`COUNT`, `GROUP BY`):
   - `func.count(Lead.id)`
   - `func.count(LoanApplication.id)`
   - `func.count(MatchRun.id)`
   - `func.count(Offer.id)`
   - `func.count(OfferSubmission.id)`
   - Applications grouped by status (`LoanApplication.status`)
   - Lender events grouped by processing status (`LenderEvent.processing_status`)
2. **Zero Row Streaming**: Individual customer, application, or event records are never loaded into Python memory or returned to the client.
3. **Data Exclusions**:
   - No borrower names, emails, or phone numbers.
   - No individual requested amounts or financial data.
   - No passwords or password hashes.
   - No webhook/callback payload data (`event_payload` JSONB is never selected).
4. **Resilience**: Operates safely on empty databases, returning zero counts and empty status maps (`{}`) without exceptions.

---

## 7. Difference Between HTTP 401 and HTTP 403

| Attribute | HTTP 401 Unauthorized | HTTP 403 Forbidden |
| :--- | :--- | :--- |
| **Stage** | Authentication | Authorization |
| **Meaning** | Missing, expired, malformed, or unverified identity credentials. | Authenticated identity confirmed, but insufficient permissions to access resource. |
| **Challenge Header** | Includes `WWW-Authenticate: Bearer`. | No challenge header. |
| **Client Remedy** | Re-authenticate, supply credentials, or provide valid Bearer token. | Do not retry with the same credentials; request appropriate role assignment. |

---

## 8. Role-Based Access vs Resource-Level Access

- **Role-Based Access Control (RBAC)**:
  - Determines whether a user's *role* allows access to an entire endpoint family or operational class.
  - *Example*: Only users with role `caller` can invoke `GET /api/v1/caller/leads`; only users with role `admin` can invoke `GET /api/v1/admin/dashboard/metrics`.
- **Resource-Level Access Control (RLAC / Object Ownership)**:
  - Determines whether an authorized user has permission to view or manipulate a *specific record instance*.
  - *Example*: A caller has the `caller` role (RBAC passed), but may only view lead records where `lead_assignments.caller_id == current_user.id` (RLAC passed).
  - *Note*: Customer loan application ownership APIs will enforce customer-specific RLAC in upcoming implementation milestones.
