# Recova Anticipatory Health Platform

Recova is a multi-track anticipatory digital health platform built around **one shared, gated six-agent clinical intelligence engine**. It serves four clinical and occupational pathways on top of a single FastAPI + PostgreSQL core and Next.js App Router frontend:

1. **Recova Core** — Relapse prevention and behavioral rehabilitation monitoring (wearables + voice/text daily check-ins).
2. **Recova Loop** — IFHAS cardiometabolic & mental-health screening-to-care closed-loop navigation (HbA1c, blood pressure, lipids, PHQ-9).
3. **Recova Neuro** — Longitudinal cognitive wellness and early brain-health monitoring (interactive audio-visual sequence, executive rule-switching, and delayed recall battery adjusted for sensory, language, education, and practice effects).
4. **Recova WorkSafe** — Workforce fatigue, heat-stress (NOAA Rothfusz Heat Index), and physiological readiness monitoring with **k-anonymity supervisor suppression** and **Occupational Health Director** separation.

## Key Architectural Invariants

- **FastAPI Single Source of Truth:** All authentication, authorization, clinical business rules, baseline math, LLM calls, FHIR serialization, referral orchestration, and database persistence live in [`backend/`](backend/). Next.js App Router proxies `/api/v1/*` to FastAPI and contains no alternative server-side business backend.
- **Deterministic Risk Classification:** Agent 4 computes personal baselines (mean of initial 3–5 stable windows), sample SD, zero-variance SD floors, confounder multipliers, logarithmic practice adjustments, and longitudinal drift $Z$-scores strictly in Python ([`backend/app/engine/scoring.py`](backend/app/engine/scoring.py)). **No LLM computes or overrides risk tiers.**
- **Independent Emergency Gate:** Gate 2 evaluates physiological red flags and multilingual (English + Arabic) acute crisis indicators deterministically before routine scoring or LLM synthesis, immediately creating an `EmergencyEvent` and STAT `emergency_triage` referral.
- **DECIDE-AI Clinical Safety & Non-Fabrication:** Agent 5 requires patient consent (`data_processing` without `llm_synthesis` revocation), strips PII before calling a configured LLM provider, validates JSON output against `SynthesisDraftSchema`, and honestly records `provider_not_configured` when no LLM key is present. Unconfigured notifications, Malaffi HIE, and Sahatna integrations likewise report `not_configured` rather than simulating success.

## Technology Stack

| Layer | Technology |
| --- | --- |
| Frontend | Next.js 16.4.6 (App Router, Turbopack, standalone output), React 19.3.0, TypeScript, Tailwind CSS 4, Lucide Icons, Recharts 3 |
| Backend API & Worker | Python 3.13, FastAPI, Pydantic v2, SQLAlchemy 2.0, Alembic 1.14+, `uvicorn` |
| Database | PostgreSQL 16 (`psycopg` v3 binary driver) |
| Security | Argon2id (`argon2-cffi`), HttpOnly `recova_session` + HMAC-SHA256 token hashing, `recova_csrf` / `X-CSRF-Token`, Fernet field encryption |
| Interoperability | HL7 FHIR R4.0.1 Bundle builder & structural validator (`urn:uuid:` integrity), Malaffi / Sahatna / SMTP / Twilio / Multi-LLM HTTPS adapters |
| Verification | `pytest` against PostgreSQL (`recova_test`), `tsc --noEmit`, Vitest + Testing Library, ESLint 9, 15-case synthetic benchmark suite |

## Quickstart (Local Development)

### 1. Prerequisites
- Python 3.13+
- Node.js 20+ / 22+
- PostgreSQL 16 (running locally with databases `recova` and `recova_test`, or Docker Desktop with `docker-compose.yml`)

### 2. Configure Environment
```bash
cp .env.example backend/.env
# Ensure DATABASE_URL points to your running PostgreSQL instance
```

Create `frontend/.env.local`:
```env
NEXT_PUBLIC_API_BASE_URL=/api/v1
BACKEND_INTERNAL_URL=http://127.0.0.1:8000
NEXT_PUBLIC_WS_BASE_URL=ws://localhost:8000/api/v1
```

### 3. Start PostgreSQL, Migrate, and Run Backend API
```bash
cd backend
python -m venv .venv
# Activate .venv (Windows: .\.venv\Scripts\Activate.ps1, macOS/Linux: source .venv/bin/activate)
pip install -r requirements-dev.txt
alembic upgrade head
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### 4. Build / Run Frontend
```bash
cd frontend
npm ci
npm run dev
```

Visit `http://localhost:3000`. On an uninitialized database, Recova routes to `/bootstrap` to create the first organization, enable tracks, and provision the initial `org_admin` account.

### 5. Run Tests
```bash
# Backend integration tests (requires PostgreSQL `recova_test`)
cd backend
pytest -v

# Frontend checks & production build
cd frontend
npm run typecheck
npm test
npm run lint
npm run build
```

## Repository Structure

```text
Recova-H2S/
├── backend/
│   ├── app/
│   │   ├── agents/        # Gate 1, Gate 2, Agents 3–6, Pydantic schemas, Orchestrator
│   │   ├── api/v1/        # FastAPI route handlers (90 HTTP/WS/SSE routes total)
│   │   ├── benchmarks/    # 15-case isolated synthetic validation suite & runner
│   │   ├── core/          # Config, DB, Argon2/CSRF/Fernet security, RBAC, audit, SSE bus, rate limiter
│   │   ├── engine/        # LOINC metric catalog, unit normalization, NOAA Heat Index, Z-score math
│   │   ├── integrations/  # FHIR R4 Bundle builder, LLM abstraction, Malaffi, Sahatna, SMTP/Twilio
│   │   ├── models/        # 26 SQLAlchemy 2.0 ORM tables + enums
│   │   ├── schemas/       # Pydantic v2 request/response contracts
│   │   ├── services/      # Domain business logic services
│   │   └── tasks/         # PostgreSQL-backed durable background job queue & scheduler
│   ├── migrations/        # Alembic schema migrations (`cd2178bcb554_initial_recova_schema.py`)
│   ├── tests/             # Real PostgreSQL pytest suite
│   ├── Dockerfile
│   └── requirements.txt / requirements-dev.txt
├── frontend/
│   ├── src/
│   │   ├── app/           # Next.js App Router pages (`/dashboard`, `/core`, `/loop`, `/neuro`, `/worksafe`, etc.)
│   │   ├── components/    # Shared UI primitives & clinical components (Agent graph, DECIDE-AI review, FHIR modal)
│   │   ├── features/      # Track-specific interactive workspaces (Core, Loop, Neuro audio-visual game, WorkSafe)
│   │   ├── hooks/         # Session auth context (`useAuth`) & SSE event subscriber (`useRealtimeEvents`)
│   │   ├── lib/           # Same-origin API client with automatic CSRF attachment
│   │   ├── services/      # Typed FastAPI client modules
│   │   ├── types/         # Shared TypeScript interfaces matching Pydantic schemas
│   │   └── __tests__/     # Vitest + Testing Library unit/component specs
│   ├── Dockerfile
│   ├── next.config.ts     # Rewrites `/api/v1/*` -> `BACKEND_INTERNAL_URL` & standalone output
│   └── vitest.config.ts
├── docs/                  # Technical architecture & governance documentation
├── docker-compose.yml     # Multi-container stack: postgres, backend, worker, frontend
└── .env.example           # Documented environment variable template
```

## Documentation Index

- [System Architecture](docs/architecture.md)
- [Database Schema & Migrations](docs/database-schema.md)
- [REST, SSE & WebSocket API Reference](docs/api.md)
- [Shared Six-Agent Workflow & Scoring Engine](docs/agent-workflow.md)
- [Clinical Governance, DECIDE-AI & Interoperability](docs/clinical-governance.md)
- [Security, Authentication, RBAC & Privacy](docs/security.md)
- [Environment Configuration](docs/environment-configuration.md)
- [Deployment Runbook](docs/deployment.md)
- [Testing & Synthetic Validation Suite](docs/testing.md)
