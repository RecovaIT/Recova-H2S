# Deployment Runbook

Recova supports containerized multi-service deployment via Docker Compose ([`docker-compose.yml`](../docker-compose.yml)) as well as bare-metal Python/Node.js execution backed by PostgreSQL 16.

## 1. Containerized Deployment (`docker-compose.yml`)

The provided compose topology runs four coordinated services:
1. **`postgres` (`postgres:16-alpine`):** Persistent volume `recova_pgdata` on port `5432` with `pg_isready` healthcheck.
2. **`backend` ([`backend/Dockerfile`](../backend/Dockerfile)):** Python 3.13 slim image; automatically runs `alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000`, exposes port `8000`, `RUN_EMBEDDED_WORKER="false"`, healthchecked at `/readyz`.
3. **`worker`:** Reuses backend image, executing `python -m app.cli worker --concurrency 2` against the shared PostgreSQL queue.
4. **`frontend` ([`frontend/Dockerfile`](../frontend/Dockerfile)):** Multi-stage `node:22-alpine` build setting `BACKEND_INTERNAL_URL=http://backend:8000` and `NEXT_PUBLIC_API_BASE_URL=/api/v1`, running Next.js standalone server (`node server.js`) on port `3000`.

### Production Launch Steps
```bash
# 1. Supply mandatory secrets in shell or `.env` next to docker-compose.yml
export SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
export FIELD_ENCRYPTION_KEY="$(python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')"
export ENVIRONMENT=production
export COOKIE_SECURE=true   # when fronted by TLS termination (HTTPS)
export CORS_ORIGINS='["https://your-domain.example"]'
export FRONTEND_BASE_URL='https://your-domain.example'

# 2. Build and launch stack
docker compose up -d --build

# 3. Verify readiness & logs
docker compose ps
docker compose logs -f backend worker frontend
```

Reverse proxy (Nginx / Caddy / ALB) requirements in production:
- Terminate TLS externally and forward `X-Forwarded-Proto` / `Host`.
- Keep buffering **disabled** (`proxy_buffering off` in Nginx) on `/api/v1/pipeline/events/stream` so Server-Sent Events stream immediately without proxy batching.

## 2. Bare-Metal / Local Workstation Deployment

### PostgreSQL Setup
Create databases `recova` and `recova_test` owned by role `recova`, then run migrations:
```bash
cd backend
alembic upgrade head
```

### Backend API & Optional Standalone Worker
Development (embedded worker):
```bash
cd backend
.\.venv\Scripts\uvicorn.exe app.main:app --host 127.0.0.1 --port 8000
```
Separated worker topology (recommended outside single-process dev):
```bash
# Terminal 1 (with RUN_EMBEDDED_WORKER=false)
uvicorn app.main:app --host 0.0.0.0 --port 8000

# Terminal 2
python -m app.cli worker --concurrency 2
```

### Frontend Production Build (`output: "standalone"`)
`frontend/next.config.ts` enables `output: "standalone"`. For production Node execution outside Docker, either:
- Run `npm run build` and copy `.next/static` and `public` into `.next/standalone/`, then launch `node .next/standalone/server.js`, or
- Run `npm run dev` during interactive development.

> **Windows Port Note:** On Windows machines with Hyper-V / WinNAT dynamic port exclusions, TCP port `3000` (or other low dev ports) may occasionally raise `EACCES`. In that situation, start Next.js on an alternate port (e.g., `-p 3100`) and include that origin in backend `CORS_ORIGINS`.

## 3. First-Run Onboarding
1. Navigate to `/bootstrap` (automatically redirected from `/` and `/login` when `/api/v1/auth/status` returns `needs_bootstrap: true`).
2. Create the initial organization (`core`, `loop`, `neuro`, `worksafe` track toggles) and first `org_admin` account.
3. Configure optional **Settings** (`/settings`) for LLM synthesis credentials, insurance plans, network care facilities, SMTP/Twilio notifications, and Malaffi/Sahatna endpoints.
