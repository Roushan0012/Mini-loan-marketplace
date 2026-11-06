# Mini Loan Marketplace

A full-stack training project simulating a consumer credit marketplace where borrowers can request loan terms, receive competitive pre-qualified offers from multiple simulated lending partners, and compare loan options in alignment with Module 16 capstone requirements.

---

## 📖 Project Purpose

The primary goal of the **Mini Loan Marketplace** is to provide a clean, modern, and extensible reference architecture for a multi-lender credit platform.

Key goals:
- Demonstrate modern API design using **FastAPI** with structured validation, service layers, and dependency injection.
- Showcase a modular **React + TypeScript** frontend architecture supporting role-based access for customers, callers, and administrators.
- Implement robust relational persistence using **PostgreSQL**, **SQLAlchemy (2.0)**, and **Alembic**.
- Emulate external financial partner integrations using deterministic mock lender adapters without reliance on live financial networks or third-party credentials.

> [!IMPORTANT]
> **Fictional Training Project & Safety Guardrails**:
> - All borrowers, credit profiles, underwriting calculations, and lending institutions in this project are strictly fictional.
> - The project does **not** connect to real lenders, credit bureaus, banking rails, payment processors, or SMS/OTP gateways.
> - The application does **not** grant or claim actual loan approval; all outcomes are educational simulations.
> - Follows Module 16 capstone specifications directly without extraneous production architecture inventions.

---

## 🛠️ Technology Stack

| Layer | Technologies |
|---|---|
| **Frontend** | React, TypeScript, Vite, React Router |
| **Backend** | Python 3.11+, FastAPI, Pydantic v2 |
| **Database & ORM** | PostgreSQL, SQLAlchemy 2.0 |
| **Database Migrations** | Alembic |
| **Testing** | Pytest, HTTPX (Backend), Vitest (Frontend) |
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
   - Tracks application status.

2. **Caller**:
   - Can view only mock leads assigned to them.
   - Cannot access other callers' leads (strict caller isolation).
   - Cannot access admin functionality or system configuration.

3. **Admin**:
   - Views aggregate application funnel metrics.
   - Views application processing delays.
   - Views system error events.
   - Must **not** receive sensitive customer records in dashboard responses (privacy-preserving analytics).

> [!NOTE]
> **External Simulated Integrations**:
> Mock lenders (*Apex Financial*, *Horizon Credit*, *Sterling Loans*) are **external simulated integrations**, not application user roles. They communicate with the backend exclusively via isolated adapters and simulated callbacks.

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

For full sequence flowcharts, state transitions, and detailed descriptions, refer to [docs/workflow.md](file:///Users/roushan_iiitbgp/Desktop/Mini_Loan_Marketplace/docs/workflow.md).

---

## ⚠️ Failure Scenarios & Safe Backend Handling

The backend architecture is engineered to handle failure states safely and deterministically:

- **Success**: Lender processes and returns approval terms; application status cleanly moves to completed.
- **Decline**: Policy or underwriting rejection logged with explicit exclusion reasons without breaking application flow.
- **Timeout**: Gracefully handles simulated partner latency breaches, records timeout error events, and aggregates available partner offers.
- **Duplicate Webhook**: Enforces idempotency via submission keys and event IDs to avoid duplicate mutations.
- **Late Webhook**: Webhooks received after terminal states are safely audited without mutating application state.
- **Out-of-Order Status Event**: Monotonic state transition validations prevent out-of-sequence updates (e.g., disbursal events before review).

---

## 🏛️ System Architecture

The application is structured around a decoupled multi-layer architecture:

- **Client Interfaces**: Role-specific SPAs for Customer, Caller (assigned leads), and Admin (aggregate metrics).
- **FastAPI Application**: High-performance API layer with route controllers and authorization guards.
- **Core Services**:
  - `Application Service`: Manages drafts, profile data, and state transitions.
  - `Consent Service`: Tracks notice versions, timestamps, active consent checks, and revocations.
  - `Matching Service`: Runs policy evaluations across three mock lenders and tracks exclusion reasons.
  - `Offer Service`: Computes APR, instalments, links mock KFS documents, and manages offer selection.
  - `Submission Service`: Manages unique submission keys, dispatches lender requests, and enforces idempotency.
- **Mock Lender Adapters**: Isolated simulators (*Apex Financial*, *Horizon Credit*, *Sterling Loans*).
- **Data Layer**: Relational models in PostgreSQL managed with SQLAlchemy declarative models and Alembic migrations.

For the architectural diagram and component details, refer to [docs/architecture.md](file:///Users/roushan_iiitbgp/Desktop/Mini_Loan_Marketplace/docs/architecture.md).

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
│   │   ├── services/                   # Application, Consent, Matching, Offer, and Submission services
│   │   └── integrations/
│   │       └── mock_lenders/           # Simulated third-party lender adapters
│   └── tests/                          # Backend test suite (Pytest & HTTPX)
├── frontend/
│   └── src/
│       ├── components/                 # Reusable UI components
│       ├── pages/                      # Customer, Caller, and Admin views
│       ├── features/                   # Application flow, offer comparison, lead management
│       ├── services/                   # API clients and HTTP integrations
│       ├── hooks/                      # Custom reusable React hooks
│       └── types/                      # TypeScript type definitions and API contracts
├── docs/                               # System and workflow documentation
│   ├── architecture.md                 # System architecture & Mermaid diagrams
│   └── workflow.md                     # Customer journey & application lifecycle
├── infra/                              # Docker and infrastructure manifests
├── .env.example                        # Template for environment variables
├── .gitignore                          # Git ignore rules for Python, Node, OS, and secrets
└── README.md                           # Project documentation
```

---

## 🚀 Getting Started

### Prerequisites
- Python 3.11+
- Node.js 18+ & npm
- PostgreSQL 15+ (or Docker)
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

*(Implementation of API endpoints, frontend components, and database migrations will follow in subsequent steps.)*
