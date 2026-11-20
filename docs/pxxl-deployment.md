# PXXL Deployment Guide (Recova Unified Platform)

Recova deploys cleanly to **PXXL** (`pxxl.app`) as two web services (**Backend API** + **Frontend**), backed by **PostgreSQL 16** (plus an optional **Standalone Worker** service).

## Why this works seamlessly on PXXL
1. **Dynamic `$PORT` & Proxy Headers:** `backend/Dockerfile` and `backend/Procfile` bind Uvicorn to `0.0.0.0:${PORT:-8000}` with `--proxy-headers --forwarded-allow-ips='*'` so PXXL's TLS reverse proxy is honored.
2. **Automatic `DATABASE_URL` Normalization:** `backend/app/core/config.py` automatically normalizes `postgres://` and `postgresql://` URLs to `postgresql+psycopg://` for SQLAlchemy 2.0 + `psycopg` v3 and Alembic.
3. **Runtime API + SSE Proxy:** `frontend/src/app/api/v1/[...path]/route.ts` proxies `/api/v1/*` (including `Set-Cookie`, `X-CSRF-Token`, and SSE streams) to `BACKEND_INTERNAL_URL` at **runtime**, keeping `recova_session` and `recova_csrf` first-party same-origin cookies without needing build-time URLs.
4. **Cross-Process Event Bus:** PostgreSQL `LISTEN`/`NOTIFY` (`backend/app/core/events.py`) bridges real-time pipeline events across separate API and worker processes with zero Redis dependency.

---

## Step 1: Provision PostgreSQL 16
Provision a PostgreSQL 16 database on PXXL (or managed Postgres) and copy its connection string (`DATABASE_URL`).

Generate required cryptographic keys locally:
```bash
python -c "import secrets; print('SECRET_KEY=' + secrets.token_urlsafe(48))"
python -c "from cryptography.fernet import Fernet; print('FIELD_ENCRYPTION_KEY=' + Fernet.generate_key().decode())"
```

---

## Step 2: Deploy Backend Service (`backend/`)
Create a PXXL service pointing to the **`backend`** root directory (via Dockerfile `backend/Dockerfile` or native Python runtime).

- **Build command (if native Python):** `pip install -r requirements.txt`
- **Start command (if native Python):** `alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT --proxy-headers --forwarded-allow-ips='*'`
- **Healthcheck path:** `/readyz`

### Backend Environment Variables
| Variable | Value |
| --- | --- |
| `ENVIRONMENT` | `production` |
| `DATABASE_URL` | `<your-postgres-connection-url>` |
| `SECRET_KEY` | `<generated-48-byte-url-safe-secret>` |
| `FIELD_ENCRYPTION_KEY` | `<generated-fernet-key>` |
| `COOKIE_SECURE` | `true` |
| `COOKIE_SAMESITE` | `lax` |
| `RUN_EMBEDDED_WORKER` | `true` (set `false` if running a separate Worker service below) |
| `FRONTEND_BASE_URL` | `https://<your-frontend-domain>` |
| `CORS_ORIGINS` | `["https://<your-frontend-domain>"]` |
| `LLM_PROVIDER` | `none` (or `openai` / `gemini` / `anthropic` with `LLM_API_KEY` + `LLM_MODEL`) |

### Optional: Separate Worker Service (`backend/`)
If you prefer a dedicated background worker process:
- Set `RUN_EMBEDDED_WORKER=false` on the Backend API service.
- Create a second PXXL worker service from `backend/` with start command:
  `python -m app.cli worker --concurrency 2`
- Pass the same `ENVIRONMENT`, `DATABASE_URL`, `SECRET_KEY`, and `FIELD_ENCRYPTION_KEY`.

---

## Step 3: Deploy Frontend Service (`frontend/`)
Create a PXXL service pointing to the **`frontend`** root directory (via Dockerfile `frontend/Dockerfile` or native Node 22 runtime).

- **Build command (if native Node):** `npm ci && npm run build`
- **Start command (if native Node):** `npm run start`
- **Healthcheck path:** `/login`

### Frontend Environment Variables
| Variable | Value |
| --- | --- |
| `NEXT_PUBLIC_API_BASE_URL` | `/api/v1` |
| `BACKEND_INTERNAL_URL` | `https://<your-backend-service-url>` |

---

## Step 4: Post-Deploy Verification
1. Visit `https://<your-backend-domain>/readyz` → `{"status":"ready","database":"connected"}`.
2. Visit `https://<your-frontend-domain>` → automatically routes to `/bootstrap` on an empty database, or `/login` once initialized.
3. On `/bootstrap`, create your initial platform organisation and `org_admin` account; verify `/dashboard`, `/authority`, `/patients`, `/portal`, and `/admin` operate end-to-end.
