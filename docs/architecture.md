# System Architecture

Recova implements a layered, single-core modular architecture where **FastAPI + PostgreSQL** act as the sole source of truth and **Next.js (App Router)** serves strictly as a typed presentation layer consuming FastAPI over same-origin `/api/v1/*` rewrites.

## 1. High-Level Topology

```text
Browser / Clinician / Worker / Admin
   │
   │  HTTPS / HTTP (HttpOnly session cookie + X-CSRF-Token)
   ▼
Next.js Frontend (`frontend/`, port 3000)
   ├── App Router UI (`src/app/*`, `src/features/*`, `src/components/*`)
   └── `next.config.ts` rewrites `/api/v1/:path*` -> `${BACKEND_INTERNAL_URL}/api/v1/:path*`
   │
   ▼
FastAPI Backend (`backend/app/main.py`, port 8000)
   ├── Middleware: Security & Request Context (`security_and_context_middleware`), CORS (`CORSMiddleware`), Exception Handlers
   ├── API v1 Routers (`app/api/v1/*`): Auth, Clinical, Engine, Care, Orgs/Users, Ops + SSE/WS
   ├── Service Layer (`app/services/*`): Organizations, Patients, Signals, Workforce, Care, Auth
   ├── Shared 6-Agent Engine (`app/agents/*` & `app/engine/*`)
   ├── Integration Adapters (`app/integrations/*`): FHIR R4, LLM, Malaffi, Sahatna, SMTP, Twilio
   └── PostgreSQL Job Queue (`app/tasks/queue.py`): Embedded (dev) or Dedicated CLI Worker (prod)
   │
   ▼
PostgreSQL 16 Database (`cd2178bcb554`)
   └── 26 multi-tenant tables across Identity, Clinical, Engine, Care, and Ops
```

## 2. Shared Intelligence Engine vs. Four Application Tracks

Recova **does not duplicate AI or scoring systems** per clinical use case. Instead, all four tracks enter the same six-step gated pipeline orchestrator (`app/agents/orchestrator.py`):

| Track Key | Product Name | Primary Input Streams | Shared Engine Specializations |
| --- | --- | --- | --- |
| `core` | **Recova Core** | `wearable_sleep`, `wearable_hrv`, `wearable_hr`, `daily_checkin` | Relapse-drift weights, shift-work SE confounder (`1.15x`), craving/mood check-in & crisis NLP |
| `loop` | **Recova Loop** | `ifhas_labs`, `ifhas_vitals`, `ifhas_phq9`, `wearable_activity` | Single-visit clinical reference fallback (HbA1c, BP, PHQ-9, lipids), PHQ-9 Item 9 crisis bypass, IFHAS care navigation |
| `neuro` | **Recova Neuro** | `cognitive_sequence`, `cognitive_executive`, `cognitive_recall`, `wearable_sleep` | Logarithmic practice adjustment (`4% * ln(session_index)`, max `12%`), hearing/vision/language/education SE multipliers |
| `worksafe` | **Recova WorkSafe** | `worker_readiness`, `wearable_thermal`, `wearable_hrv`, `workplace_env` | Rothfusz Heat Index calculation, acute core-temp >= 40.0 C heatstroke Gate 2 bypass, supervisor k-anonymity heatmap suppression |

## 3. Architectural Layer Boundaries

### A. Frontend Layer (`frontend/src/`)
- **Routing (`src/app/`):** App Router pages for `/login`, `/bootstrap`, `/forgot-password`, `/reset-password`, `/dashboard`, `/core`, `/loop`, `/neuro`, `/worksafe`, `/patients`, `/patients/[id]`, `/agents`, `/reviews`, `/referrals`, `/benchmarks`, `/reports`, `/settings`, and `/admin`.
- **Same-Origin Proxy (`next.config.ts`):** Rewrites `/api/v1/:path*` to `BACKEND_INTERNAL_URL` so browser requests share origin with Next.js (`credentials: "include"`), ensuring HttpOnly `recova_session` cookies and `recova_csrf` cookies work seamlessly without cross-site cookie friction.
- **No Alternative Backend:** Next.js Server Actions are not used. Every mutation and query calls `src/lib/api.ts`, which attaches `X-CSRF-Token` for `POST`, `PUT`, `PATCH`, and `DELETE`.
- **Real-Time Telemetry (`src/hooks/useRealtimeEvents.ts`):** Subscribes to `GET /api/v1/pipeline/events/stream` (SSE) using `EventSource` to stream live `pipeline.*`, `review.signed`, `referral.updated`, and `emergency.resolved` notifications.

### B. API & Service Layer (`backend/app/api/v1/` & `backend/app/services/`)
- **Dependencies (`app/api/deps.py`):** Resolves the opaque session token from cookie or `Authorization: Bearer`, verifies session expiry and idle timeout, enforces `X-CSRF-Token` double-submit validation on mutating cookie-authenticated requests, resolves tenant `organization_id` from membership/header, and supplies `AuthContext`.
- **Event Bus (`app/core/events.py`):** Thread-safe in-process pub/sub bridging synchronous/worker pipeline completions to async SSE and WebSocket consumers.

### C. Background Processing Layer (`backend/app/tasks/`)
- Durable job execution is persisted in the PostgreSQL `jobs` table (`SKIP LOCKED` worker claims).
- Supported async handlers (`app/tasks/handlers.py`) cover asynchronous pipeline runs (`run_async=true`), benchmark suite runs, notification retries, and scheduled referral SLA breach evaluations.
- In development (`RUN_EMBEDDED_WORKER=true`), FastAPI starts an in-process worker thread; in Docker/production (`docker-compose.yml`), `RUN_EMBEDDED_WORKER=false` on the web container and a dedicated `worker` container executes `python -m app.cli worker --concurrency 2`.
