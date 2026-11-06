# Mini Loan Marketplace

A full-stack training project simulating a consumer credit marketplace where borrowers can request loan terms, receive competitive pre-qualified offers from multiple simulated lending partners, and compare loan options.

---

## 📖 Project Purpose

The primary goal of the **Mini Loan Marketplace** is to provide a clean, modern, and extensible reference architecture for a multi-tenant or multi-lender credit platform.

Key goals:
- Demonstrate modern API design using **FastAPI** with structured validation and dependency injection.
- Showcase a modular **React + TypeScript** frontend architecture for multi-step applications and financial comparison views.
- Implement robust relational persistence using **PostgreSQL**, **SQLAlchemy (2.0)**, and **Alembic**.
- Emulate external financial partner integrations using deterministic mock lender adapters without reliance on live financial networks or third-party credentials.

> [!IMPORTANT]
> **Fictional Training Project**:
> All borrowers, credit profiles, underwriting calculations, and lending institutions in this project are strictly fictional. The project does not connect to real credit bureaus, banking rails, payment processors, or SMS/OTP gateways.

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

## 👥 User Roles & Personas

- **Borrower (Applicant)**: Explores loan products, completes credit inquiries, and compares personalized offers.
- **Marketplace Administrator**: Monitors application queues, inspects conversion metrics, and configures mock lender simulation parameters.
- **Mock Lending Partners**: Fictional financial institutions (*Apex Financial*, *Horizon Credit*, *Sterling Loans*) with differing risk profiles and APR tiers.

For detailed workflow steps and state lifecycle diagrams, see [docs/workflow.md](file:///Users/roushan_iiitbgp/Desktop/Mini_Loan_Marketplace/docs/workflow.md).

---

## 🏛️ System Architecture

The application is structured into decoupled frontend, backend, database, and mock integration layers:

- **Client Layer**: Single-page application built with React and TypeScript.
- **API Layer**: FastAPI application providing structured REST endpoints at `/api/v1`.
- **Domain & Service Layer**: Encapsulates business logic, underwriting rule checks, and mock lender orchestration.
- **Data Layer**: Relational models in PostgreSQL managed with SQLAlchemy declarative models and Alembic migrations.
- **Mock Integrations Layer**: Isolated provider adapters simulating lender quoting behavior.

For the full architectural specification and Mermaid architecture diagrams, see [docs/architecture.md](file:///Users/roushan_iiitbgp/Desktop/Mini_Loan_Marketplace/docs/architecture.md).

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
│   │   ├── services/                   # Core business logic and orchestration services
│   │   └── integrations/
│   │       └── mock_lenders/           # Simulated third-party lender adapters
│   └── tests/                          # Backend test suite (Pytest & HTTPX)
├── frontend/
│   └── src/
│       ├── components/                 # Reusable UI components
│       ├── pages/                      # Top-level view pages
│       ├── features/                   # Domain/feature-specific components and logic
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

### Folder Purpose Summary

- `backend/app/api/v1`: Exposes versioned REST API routes for applications, offers, and mock lender interactions.
- `backend/app/core`: Houses application settings (via Pydantic Settings) and shared utilities.
- `backend/app/db`: Manages SQLAlchemy engine, session factories, and database lifecycle.
- `backend/app/models`: Defines relational database tables and relationships.
- `backend/app/schemas`: Defines request and response validation models with Pydantic.
- `backend/app/services`: Contains the application business logic, isolated from HTTP transport details.
- `backend/app/integrations/mock_lenders`: Provides pluggable, isolated mock lenders for loan quote generation.
- `backend/tests`: Automated test suites using Pytest and HTTPX.
- `frontend/src/components`: Generic, reusable UI elements (e.g., buttons, cards, layout).
- `frontend/src/pages`: Page-level components corresponding to router endpoints.
- `frontend/src/features`: Domain-focused components (e.g., loan inquiry form, offer comparison grid).
- `frontend/src/services`: Client-side HTTP requests and API consumption logic.
- `frontend/src/hooks`: Encapsulates reusable UI and asynchronous state logic.
- `frontend/src/types`: TypeScript contracts mirroring backend API schemas.
- `docs`: Technical documentation including architecture diagrams and user workflows.
- `infra`: Containerization specifications and environment orchestration.

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
