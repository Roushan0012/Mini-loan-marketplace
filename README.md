# Mini Loan Marketplace

A full-stack training project simulating a consumer credit marketplace where borrowers can request loan terms, receive competitive pre-qualified offers from multiple simulated lending partners, and compare loan options in alignment with Module 16 capstone requirements.

---

## 📖 Project Purpose

The primary goal of the **Mini Loan Marketplace** is to provide a clean, modern, and extensible reference architecture for a multi-lender credit platform.

Key goals:
- Demonstrate modern API design using **FastAPI** with structured validation, service layers, and dependency injection.
- Showcase a modular **React + TypeScript** frontend architecture supporting role-based access for customers, callers, and administrators.
- Implement robust relational persistence using **PostgreSQL**, **SQLAlchemy (2.0)**, and **Alembic**.
- Emulate external financial partner integrations using deterministic mock lender adapters and HMAC-signed webhooks without reliance on live financial networks or third-party credentials.

> [!IMPORTANT]
> **Fictional Training Project & Safety Guardrails**:
> - All borrowers, credit profiles, underwriting calculations, and lending institutions in this project are strictly fictional.
> - The project does **not** connect to real lenders, credit bureaus, banking rails, payment processors, or SMS/OTP gateways.
> - The application does **not** grant or claim actual loan approval; all outcomes are educational simulations.
> - Key Facts Statements (KFS) are synthetic simulations and do not constitute actual legal or regulatory disclosures.

---

## 🛠️ Technology Stack

| Layer | Technologies |
|---|---|
| **Frontend** | React 18, TypeScript, Vite, React Router 6 |
| **Backend** | Python 3.11+, FastAPI, Pydantic v2 |
| **Database & ORM** | PostgreSQL 16, SQLAlchemy 2.0 (with Psycopg 3) |
| **Database Migrations** | Alembic |
| **Testing** | Pytest, HTTPX / TestClient, Vitest, React Testing Library, Playwright |
| **Infrastructure & Tooling** | Docker, Docker Compose |

---

## 👥 Application User Roles

The application strictly defines **three** application user roles:

1. **Customer**:
   - Creates a fictional loan application.
   - Gives or revokes purpose-specific demo consent.
   - Views eligible and nonmatching lender results.
   - Compares offers (APR, amount, term, instalment, and mock KFS link).
   - Selects an offer.
   - Submits application with an idempotency key.
   - Tracks application lifecycle and simulated lender outcomes.

2. **Caller**:
   - Can view only mock leads assigned to them.
   - Cannot access other callers' leads (strict caller isolation).
   - Filters and searches assigned leads.
   - Cannot access admin functionality, system configuration, or customer application workflows.

3. **Admin**:
   - Views aggregate application funnel metrics.
   - Monitors application status distribution and mock lender webhook event processing statuses.
   - Preserves customer privacy: must **not** receive sensitive customer records (PII) in dashboard responses.
   - Cannot access customer application creation or caller lead workspaces.

> [!NOTE]
> **External Simulated Integrations**:
> Mock lenders (*Apex Financial*, *Horizon Credit*, *Sterling Loans*) are **external simulated integrations**, not application user roles. They communicate with the backend exclusively via isolated adapters and signed webhook callbacks.

---

## 🔄 Customer Workflow Sequence

The customer application journey follows an explicit 13-step progression:

1. **Create a draft application**: Initialize a new loan session.
2. **Enter profile details**: Provide age, monthly income, work type, and requested loan amount.
3. **Display demo consent**: Present purpose-specific demo consent notice.
4. **Record consent metadata**: Persist notice version, timestamp, and consent status (`GRANTED`, `REVOKED`, `PENDING`).
5. **Allow consent revocation**: Allow customer to revoke demo consent at any point prior to submission.
6. **Check active consent**: Verify active, non-revoked consent before triggering matching logic.
7. **Run three mock lender policies**: Evaluate applicant profile against *Apex Financial*, *Horizon Credit*, and *Sterling Loans* underwriting rules.
8. **Record policy audit records**: Store policy versions along with eligibility decisions and structured exclusion reasons.
9. **Display matching results**: Show eligible offers alongside transparent names of nonmatching lenders.
10. **Display terms**: Render APR, loan amount, tenure/term, monthly instalment, and mock KFS (Key Fact Statement) link.
11. **Select an offer**: Customer selects their preferred loan product.
12. **Prevent duplicate submissions**: Require a unique submission key (idempotency key) for final submission.
13. **Track lifecycle**: Monitor mock lender responses, webhook receipts, and final application status.

For full sequence flowcharts, state transitions, and detailed descriptions, refer to [docs/workflow.md](docs/workflow.md).

---

## ⚠️ Failure Scenarios & Safe Backend Handling

The backend architecture is engineered to handle failure states safely and deterministically:

- **Success**: Lender processes and returns approval terms; application status cleanly moves to `accepted`.
- **Decline**: Policy or underwriting rejection logged with explicit exclusion reasons without breaking application flow (`declined`).
- **Timeout**: Gracefully handles simulated partner latency breaches, records timeout error events, and transitions application to `timed_out`.
- **Duplicate Webhook**: Enforces idempotency via submission keys and event IDs to avoid duplicate mutations.
- **Late Webhook**: Webhooks received after terminal states are safely audited without mutating application state.
- **Out-of-Order Status Event**: Monotonic state transition validations prevent out-of-sequence updates by recording superseded events as `ignored`.

---

## 🏛️ System Architecture

The application is structured around a decoupled multi-layer architecture:

- **Client Interfaces**: Role-specific SPAs for Customer, Caller (assigned leads), and Admin (aggregate metrics).
- **FastAPI Application**: High-performance API layer with route controllers, authorization guards, and CORS configuration.
- **Core Services**:
  - `Application Service`: Manages drafts, profile data, and state transitions.
  - `Consent Service`: Tracks notice versions, timestamps, active consent checks, and revocations.
  - `Matching Service`: Runs policy evaluations across three mock lenders and tracks exclusion reasons.
  - `Offer Service`: Computes APR, instalments, links mock KFS documents, and manages offer selection.
  - `Submission Service`: Manages unique submission keys, dispatches lender requests, and enforces idempotency.
  - `Lender Event Service`: Verifies HMAC-SHA256 signatures, manages event sequencing, and handles duplicate webhooks.
  - `Caller Service`: Enforces strict assigned-lead scoping and filtering.
  - `Admin Metrics Service`: Computes aggregate SQL counts without customer PII.
- **Mock Lender Adapters**: Isolated simulators (*Apex Financial*, *Horizon Credit*, *Sterling Loans*).
- **Data Layer**: Relational models in PostgreSQL managed with SQLAlchemy declarative models and Alembic migrations.

For the architectural diagram and component details, refer to [docs/architecture.md](docs/architecture.md).

---

## 📁 Repository Structure

```text
Mini_Loan_Marketplace/
├── backend/
│   ├── app/
│   │   ├── api/v1/                     # API routers and endpoint handlers
│   │   ├── core/                       # App configuration, security, and global settings
│   │   ├── db/                         # Database connection, session lifecycle, and base models
│   │   ├── models/                     # SQLAlchemy declarative ORM models
│   │   ├── schemas/                    # Pydantic schemas for request validation & responses
│   │   └── services/                   # Application, Consent, Matching, Offer, and Submission services
│   ├── migrations/                     # Alembic database migration scripts
│   ├── scripts/                        # Development-only user bootstrap CLI
│   └── tests/                          # Backend test suites (unit, integration, and e2e)
├── frontend/
│   ├── src/
│   │   ├── components/                 # Reusable UI components
│   │   ├── pages/                      # Customer, Caller, and Admin views
│   │   ├── features/                   # Application flow, offer comparison, lead management, admin
│   │   ├── services/                   # API clients and HTTP integrations
│   │   ├── hooks/                      # Custom reusable React hooks
│   │   └── types/                      # TypeScript type definitions and API contracts
│   └── e2e/                            # Playwright browser end-to-end test specifications
├── docs/                               # System and workflow technical documentation
├── infra/                              # Docker and infrastructure manifests
├── .env.example                        # Template for environment variables
├── .gitignore                          # Git ignore rules for Python, Node, OS, and secrets
└── README.md                           # Project documentation
```

---

## 🚀 Getting Started

### Prerequisites
- Python 3.11+
- Node.js 20+ & npm
- PostgreSQL 16+ (or Docker)
- Git

### Initial Configuration
1. Clone the repository and navigate into the project root:
   ```bash
   git clone https://github.com/Roushan0012/Mini-loan-marketplace.git
   cd Mini-loan-marketplace
   ```

2. Set up environment variables:
   ```bash
   cp .env.example .env
   ```
   Generate random keys and update `.env`:
   ```bash
   python3 -c "import secrets; print('JWT_SECRET_KEY=' + secrets.token_hex(32))"
   python3 -c "import secrets; print('MOCK_LENDER_WEBHOOK_SECRET=' + secrets.token_hex(32))"
   ```

3. Start PostgreSQL using Docker Compose:
   ```bash
   docker compose -f infra/compose.yaml up -d db
   ```

### Running the Backend Service
1. Navigate to the backend directory and set up the virtual environment:
   ```bash
   cd backend
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. Run Alembic migrations and seed mock lender policies:
   ```bash
   alembic upgrade head
   python -m app.db.seed_lender_policies
   ```

3. Bootstrap development caller and admin accounts (interactive prompt for password >= 12 chars, or via `BOOTSTRAP_DEV_USER_PASSWORD`):
   ```bash
   python scripts/bootstrap_dev_users.py --role caller --email dev_caller@example.com --full-name "Dev Caller"
   python scripts/bootstrap_dev_users.py --role admin --email dev_admin@example.com --full-name "Dev Admin"
   # To update an existing dev account, add --update-existing:
   # python scripts/bootstrap_dev_users.py --role admin --email dev_admin@example.com --update-existing
   ```

4. Start the FastAPI development server:
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```
   The backend API will be available at `http://localhost:8000`.

### Running the Frontend Service
1. Navigate to the frontend directory:
   ```bash
   cd frontend
   npm install
   ```

2. Start the Vite development server:
   ```bash
   npm run dev
   ```
   The frontend application will be accessible at `http://localhost:5173`.

---

## 🧪 Running Tests

- **Backend Full Suite (368 tests)**:
  ```bash
  cd backend
  .venv/bin/python -m pytest -v
  ```
  Runs all 368 tests: 311 unit and integration tests, 24 strict E2E database safety tests, 21 dev bootstrap tests, and 12 dedicated E2E customer journey and role isolation tests.

- **Dedicated Backend E2E Suite (12 tests)**:
  ```bash
  cd backend
  .venv/bin/python -m pytest tests/e2e -v
  ```
  Runs complete 28-step customer lifecycle, four terminal outcomes, and RBAC isolation against the dedicated isolated PostgreSQL database (`mini_loan_marketplace_e2e`).

- **Frontend Vitest Suite (141 tests)**:
  ```bash
  cd frontend
  npm test -- --run
  ```
  Runs 141 component and workflow tests across 20 test files covering authentication, draft applications, consent auditing, matching, mock offers, KFS dialog, submission tracking, caller leads, and admin dashboard.

- **Browser End-to-End Automation (Playwright)**:
  ```bash
  cd frontend
  npm run test:e2e
  ```
  Runs automated Chromium browser tests covering customer lifecycle, caller workspace, admin metrics, and session logout role switching.

- **Frontend Typecheck, Lint & Production Build**:
  ```bash
  cd frontend
  npm run typecheck
  npm run lint
  npm run build
  ```

---

## 📚 Technical Documentation

- [Final Acceptance & Integration Audit Report](docs/final-acceptance-report.md)
- [Capstone Requirements Traceability Matrix](docs/capstone-requirements-matrix.md)
- [Frontend Foundation & Architecture](docs/frontend-foundation.md)
- [Customer Application & Matching Workflow](docs/customer-application-workflow.md)
- [Customer Offer & Submission Workflow](docs/customer-offer-and-submission-workflow.md)
- [Caller Workspace](docs/caller-workspace.md)
- [Admin Analytics Dashboard](docs/admin-analytics-dashboard.md)
- [Mock Lender Webhooks & Signed Event Lifecycle](docs/mock-lender-webhooks.md)
- [Lending Workflow & State Machine](docs/workflow.md)
- [System Architecture](docs/architecture.md)
