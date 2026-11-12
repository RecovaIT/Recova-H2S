# Environment Configuration Reference

Recova configures backend behavior via Pydantic Settings (`backend/app/core/config.py`) reading `.env` / OS environment variables, and configures Next.js server rewrites and client URLs via `frontend/.env.local` / container environment variables. See [`.env.example`](../.env.example).

## 1. Core Application & Database

| Variable | Component | Default / Example | Purpose |
| --- | --- | --- | --- |
| `ENVIRONMENT` | Backend | `development` | `development`, `test`, or `production` |
| `APP_NAME` | Backend | `"Recova Anticipatory Health Platform"` | FastAPI OpenAPI title |
| `API_PREFIX` | Backend | `/api/v1` | REST/SSE/WS route prefix |
| `DATABASE_URL` | Backend | `postgresql+psycopg://recova:recova@localhost:5432/recova` | SQLAlchemy PostgreSQL connection URI |
| `FRONTEND_BASE_URL` | Backend | `http://localhost:3000` | Base URL used for links in password reset / notification flows |
| `CORS_ORIGINS` | Backend | `["http://localhost:3000"]` | JSON list of allowed CORS origins |
| `EMERGENCY_SCREEN_WITHOUT_CONSENT` | Backend | `true` | Allows Gate 2 vital-interest acute crisis screening when routine `data_processing` consent is missing |

## 2. Security, Sessions & Encryption

| Variable | Component | Default / Example | Purpose |
| --- | --- | --- | --- |
| `SECRET_KEY` | Backend | *(required in prod)* | HMAC-SHA-256 token hashing key and session signing secret |
| `FIELD_ENCRYPTION_KEY` | Backend | *(Fernet base64 key)* | Dedicated Fernet encryption key for patient PII and `integration_configs.secrets_encrypted` |
| `COOKIE_SECURE` | Backend | `false` (`true` in HTTPS prod) | Marks `recova_session` and `recova_csrf` cookies as HTTPS-only |
| `COOKIE_SAMESITE` | Backend | `lax` | SameSite cookie policy (`lax`, `strict`, `none`) |
| `SESSION_TTL_MINUTES` | Backend | `480` | Absolute lifetime of authenticated session |
| `SESSION_IDLE_TIMEOUT_MINUTES` | Backend | `60` | Idle session expiration window |
| `PASSWORD_RESET_TTL_MINUTES` | Backend | `30` | Expiration window for password reset tokens |
| `RATE_LIMIT_LOGIN_PER_MINUTE` | Backend | `10` | Per-minute login rate-limit threshold |
| `RATE_LIMIT_DEFAULT_PER_MINUTE` | Backend | `300` | Default per-minute request limit |

Generate strong production secrets:
```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

## 3. Background Worker

| Variable | Component | Default | Purpose |
| --- | --- | --- | --- |
| `RUN_EMBEDDED_WORKER` | Backend | `true` (`false` when dedicated `worker` runs) | Starts/disables in-process job worker thread inside FastAPI |
| `WORKER_POLL_INTERVAL_SECONDS` | Backend | `1.0` | Job table poll interval |
| `SCHEDULER_INTERVAL_SECONDS` | Backend | `60` | Periodic scheduler interval (SLA escalation scan, housekeeping) |

## 4. LLM Provider Abstraction (Agent 5)

| Variable | Component | Default | Purpose |
| --- | --- | --- | --- |
| `LLM_PROVIDER` | Backend | `none` | One of: `none`, `openai`, `azure_openai`, `gemini`, `anthropic` |
| `LLM_API_KEY` | Backend | empty | Provider API key (can also be stored per-org encrypted via `/settings`) |
| `LLM_MODEL` | Backend | empty | Model ID (e.g., `gpt-4o-mini`, `gemini-2.5-flash`, `claude-3-5-sonnet-latest`) |
| `LLM_BASE_URL` | Backend | empty | Custom/OpenAI-compatible endpoint or Azure OpenAI resource URL |
| `LLM_AZURE_DEPLOYMENT` | Backend | empty | Azure OpenAI deployment name |
| `LLM_AZURE_API_VERSION` | Backend | `2024-06-01` | Azure OpenAI REST API version |
| `LLM_TIMEOUT_SECONDS` | Backend | `45.0` | HTTPS request timeout for synthesis calls |

## 5. Notification & HIE Integrations

| Variable | Purpose |
| --- | --- |
| `SMTP_HOST`, `SMTP_PORT` (`587`), `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM`, `SMTP_USE_TLS` (`true`) | Real SMTP email dispatch (`sent` only on relay acceptance) |
| `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM_NUMBER`, `TWILIO_WHATSAPP_FROM` | Real Twilio SMS / WhatsApp dispatch |
| `MALAFFI_BASE_URL`, `MALAFFI_TOKEN_URL`, `MALAFFI_CLIENT_ID`, `MALAFFI_CLIENT_SECRET` | Abu Dhabi Malaffi HIE OAuth2 client credentials & FHIR endpoint |
| `SAHATNA_BASE_URL`, `SAHATNA_API_KEY` | Abu Dhabi Sahatna super-app API endpoint and bearer key |

Note: Organizations may also override integration settings/secrets securely in the UI at `/settings` (`PUT /api/v1/settings/integrations/{name}`).

## 6. Frontend (`frontend/.env.local` & `next.config.ts`)

| Variable | Default / Example | Purpose |
| --- | --- | --- |
| `NEXT_PUBLIC_API_BASE_URL` | `/api/v1` | Base URL used by browser fetch & `EventSource` requests |
| `BACKEND_INTERNAL_URL` | `http://127.0.0.1:8000` (local) / `http://backend:8000` (Docker) | Server-side rewrite destination for `/api/v1/:path*` in `next.config.ts` |
| `NEXT_PUBLIC_WS_BASE_URL` | `ws://localhost:8000/api/v1` | WebSocket origin if WS streaming is used directly |
