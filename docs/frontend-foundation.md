# Frontend Foundation Architecture and Integration Guide

> [!IMPORTANT]
> **Fictional Training Project Disclaimer**:
> This frontend is part of an educational training simulation designed to demonstrate full-stack credit workflow orchestration with FastAPI, PostgreSQL, and React. It does **not** connect to real lenders, banks, credit bureaus, or payment gateways. All borrower records, credit criteria, and loan terms are purely fictional simulations.

---

## 1. Overview and Architecture

The Mini Loan Marketplace frontend is a single-page application (SPA) built with modern **React 18**, **TypeScript (Strict Mode)**, **Vite**, and **React Router 6**. It interfaces directly with the asynchronous FastAPI backend via standard RESTful endpoints.

### Key Architectural Pillars
1. **Lightweight & Modular**: Built without heavy UI component libraries or CSS runtime overhead, using semantic HTML5, accessible form attributes, and modular responsive CSS.
2. **Authoritative Backend Security**: The backend remains the single authoritative source of truth for authorization and permissions; frontend route guards provide user guidance and role-segregated navigation.
3. **Strict Role-Based Workspaces**: Separate interfaces for `customer`, `caller`, and `admin` roles driven dynamically by the server-verified role from `/auth/me`.
4. **Resilient Network Client**: Native fetch-based API client with automatic token injection, standardized error transformation (`ApiError`), request cancellation (`AbortSignal`), and fail-closed handling.

---

## 2. Directory Structure

```
frontend/
├── public/
│   └── vite.svg                      # Static assets
├── src/
│   ├── app/
│   │   ├── App.tsx                   # Top-level application with providers
│   │   ├── router.tsx                # Central React Router configuration
│   │   ├── providers/
│   │   │   ├── AuthContext.ts        # Authentication context & useAuth hook
│   │   │   └── AuthProvider.tsx      # Authentication state lifecycle provider
│   │   └── routes/
│   │       ├── RouteGuards.tsx       # GuestOnlyRoute, ProtectedRoute, RoleRoute
│   │       └── routeUtils.ts         # Role navigation helpers
│   ├── components/
│   │   ├── feedback/
│   │   │   ├── EmptyState.tsx        # Empty record presentations
│   │   │   ├── ErrorMessage.tsx      # Accessible alert banners
│   │   │   └── LoadingSpinner.tsx    # Accessible loading indicators
│   │   ├── layout/
│   │   │   ├── DashboardLayout.tsx   # Page framing with Navbar and Footer
│   │   │   ├── Footer.tsx            # Persistent educational disclaimer
│   │   │   └── Navbar.tsx            # Role-aware responsive navigation
│   │   └── ui/
│   │       ├── Button.tsx            # Styled reusable button
│   │       ├── Card.tsx              # Content containment card
│   │       └── Input.tsx             # Accessible inputs with error binding
│   ├── features/
│   │   └── auth/
│   │       ├── components/
│   │       │   ├── LoginForm.tsx     # Client-validated sign-in form
│   │       │   └── RegisterForm.tsx  # Customer self-registration form
│   │       ├── hooks/
│   │       │   └── useAuth.ts        # Re-exported authentication hook
│   │       ├── services/
│   │       │   └── authService.ts    # Authentication API calls
│   │       └── types.ts              # Authentication TypeScript definitions
│   ├── hooks/
│   │   └── useAuth.ts                # General hook export
│   ├── pages/
│   │   ├── AdminDashboardPage.tsx    # Telemetry and funnel metrics
│   │   ├── CallerDashboardPage.tsx   # Assigned lead queue
│   │   ├── CustomerDashboardPage.tsx # Application history and overview
│   │   ├── LoginPage.tsx             # Sign in view
│   │   ├── NotFoundPage.tsx          # 404 handler
│   │   ├── RegisterPage.tsx          # Customer registration view
│   │   └── UnauthorizedPage.tsx      # 403 forbidden view
│   ├── services/
│   │   ├── apiClient.ts              # Fetch wrapper with interceptors
│   │   ├── apiErrors.ts              # Structured ApiError class
│   │   └── tokenStorage.ts           # Centralized sessionStorage manager
│   ├── styles/
│   │   └── global.css                # CSS custom properties and layout rules
│   ├── test/
│   │   └── setup.ts                  # Vitest DOM cleanup and mock setup
│   └── types/
│       ├── api.ts                    # Backend response schemas
│       └── auth.ts                   # User profiles and token models
├── eslint.config.js                  # ESLint 9 configuration
├── index.html                        # SPA HTML root entry point
├── package.json                      # Package manifest and test scripts
├── tsconfig.json                     # TypeScript project references
├── tsconfig.app.json                 # Strict compiler options for application
├── tsconfig.node.json                # Node environment compiler options
├── vite.config.ts                    # Vite server and bundler settings
└── vitest.config.ts                  # Vitest runner configuration
```

---

## 3. Configuration and API Client

### Environment Variables
The frontend reads the backend API root from `import.meta.env.VITE_API_BASE_URL`:
- **Default Fallback**: `http://localhost:8000/api/v1`
- **Override in Production**: Define `VITE_API_BASE_URL=https://api.yourdomain.com/api/v1` in `.env.local` or hosting environment variables.
- **Security Rule**: Never store secrets, passwords, or private signing keys in `VITE_` variables; any variable prefixed with `VITE_` is baked into clientside JavaScript bundles.

### API Client (`src/services/apiClient.ts`)
The client uses native `fetch` and provides:
1. **Automatic Bearer Token Insertion**: Automatically attaches `Authorization: Bearer <token>` from session storage if present (unless `requiresAuth: false`).
2. **Selective Headers**: Adds `Content-Type: application/json` only when a request body is supplied, avoiding unneeded headers on bodyless requests.
3. **Structured Error Handling**: Parses both string error details (`409 Conflict`) and FastAPI validation lists (`422 Unprocessable Content`), converting them into typed `ApiError` instances.
4. **Token Revocation on 401**: If an authenticated call receives a 401 response, stored credentials are cleared immediately to prevent infinite authorization loops.
5. **No Credential Logging**: Access tokens and passwords are never logged to `console`.

---

## 4. Authentication and Session Management

### Session Storage Tradeoff
Access tokens are held in browser `sessionStorage`:
- **Why**: Keeps session tokens isolated to the active tab, clearing them upon tab closure and preventing cross-tab pollution during development.
- **Educational Tradeoff Note**: While `sessionStorage` avoids cross-tab persistence, it remains accessible to any JavaScript running in the same origin. For a production financial service, HTTP-only, secure, same-site cookies are the industry standard for credential containment.

### Authentication Flow
1. **Customer Registration** (`POST /api/v1/auth/register`):
   - Accepts `full_name`, `email`, and `password`.
   - Strictly does **not** send a `role` field.
   - Always creates an account with `role: "customer"`.
2. **Login** (`POST /api/v1/auth/login`):
   - Accepts `email` and `password`.
   - Returns Bearer JWT `access_token`.
   - Client stores token in `sessionStorage`.
3. **Identity Verification** (`GET /api/v1/auth/me`):
   - Immediately called upon login and page load.
   - Authoritatively determines the user's role (`customer`, `caller`, or `admin`).
   - The user is redirected to their authorized dashboard.

---

## 5. Route Protection and Role Separation

Route access is managed by three composable route guards in `src/app/routes/RouteGuards.tsx`:

| Guard | Permitted Users | Behavior if Disallowed |
|---|---|---|
| `GuestOnlyRoute` | Unauthenticated visitors | Authenticated users are redirected to their own role dashboard (`/customer/dashboard`, `/caller/dashboard`, or `/admin/dashboard`) |
| `ProtectedRoute` | Authenticated users of any role | Unauthenticated visitors are redirected to `/login` |
| `RoleRoute` | Authenticated users with an allowed role | Unauthenticated $\rightarrow$ `/login`<br>Wrong role $\rightarrow$ `/unauthorized` |

### Route Matrix
- `/login` $\rightarrow$ `GuestOnlyRoute`
- `/register` $\rightarrow$ `GuestOnlyRoute`
- `/customer/dashboard` $\rightarrow$ `RoleRoute(['customer'])`
- `/caller/dashboard` $\rightarrow$ `RoleRoute(['caller'])`
- `/admin/dashboard` $\rightarrow$ `RoleRoute(['admin'])`
- `/unauthorized` $\rightarrow$ Informational 403 Forbidden screen
- `*` $\rightarrow$ 404 Not Found screen

---

## 6. Role Dashboard Landing Pages

1. **Customer Dashboard (`/customer/dashboard`)**:
   - Calls `GET /api/v1/applications`.
   - Greets user with their verified name.
   - Displays summary metrics (Total, Active, Completed applications).
   - Renders application table with ID, requested loan amount, income, employment type, and lifecycle badge.
   - Features empty state guidance for new applicants.
2. **Caller Workspace (`/caller/dashboard`)**:
   - Calls `GET /api/v1/caller/leads`.
   - Displays only leads assigned strictly to the authenticated caller identity.
   - Demonstrates caller isolation with zero visibility into other callers' leads.
   - Omits admin controls and cross-caller dropdowns.
3. **Administrator Monitoring (`/admin/dashboard`)**:
   - Calls `GET /api/v1/admin/dashboard/metrics`.
   - Displays real-time aggregate pipeline counts (Total leads, applications, match runs, offers, submissions).
   - Renders application status breakdowns and lender webhook processing counts.
   - Strictly protects privacy by displaying zero customer names, email addresses, or PII.

---

## 7. Backend CORS Integration

FastAPI backend CORS middleware is configured in `backend/app/main.py` using `CORS_ORIGINS` from `backend/app/core/config.py`:
- **Allowed Origins**: Configured explicitly (`http://localhost:3000,http://localhost:5173,http://127.0.0.1:3000,http://127.0.0.1:5173`).
- **No Wildcards**: Wildcard `*` origins are avoided.
- **Allowed Headers**: `Authorization`, `Content-Type`, `Idempotency-Key`, `Accept`.
- **Allowed Methods**: `GET`, `POST`, `PUT`, `PATCH`, `DELETE`, `OPTIONS`.
- **Credentials**: `allow_credentials=False` because Bearer authorization headers are utilized rather than cookies.

---

## 8. Development and Testing Commands

### Dependency Installation
```bash
cd frontend
npm install
```

### Development Server
```bash
cd frontend
npm run dev
```
The application will be available at `http://localhost:5173`. Make sure the FastAPI backend is running on `http://localhost:8000`.

### Type Checking
```bash
cd frontend
npm run typecheck
```

### Linting
```bash
cd frontend
npm run lint
```

### Running Frontend Tests
```bash
cd frontend
npm test -- --run
```

### Production Build
```bash
cd frontend
npm run build
```
Build output is generated in `frontend/dist/`.

---

## 9. Current Scope Limitations

This bootstrap foundation intentionally completes Step 13A. The following workflow capabilities will be implemented in subsequent steps:
- Full customer loan application creation form.
- Consent notice presentation and revocation checkboxes.
- Offer comparison table with APR sorting.
- Key Facts Statement (KFS) modal viewer.
- Customer offer selection and final mock lender submission triggers.
- Caller lead status updates.
