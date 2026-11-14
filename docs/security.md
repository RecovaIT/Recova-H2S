# Security, Authentication, RBAC & Data Protection

Recova enforces layered defense-in-depth across password storage, stateful sessions, CSRF protection, field-level PII encryption, tenant isolation, RBAC customization, rate limiting, and sanitized audit logging.

## 1. Password & Token Cryptography (`app/core/security.py`)

- **Passwords:** Hashed using **Argon2id** (`argon2-cffi` `PasswordHasher`). Policy requires minimum length `PASSWORD_MIN_LENGTH = 10`, at least one letter, and at least one digit (`validate_password_strength`).
- **Session & Reset Tokens:** Generated via `secrets.token_urlsafe(32)` and stored in PostgreSQL strictly as **keyed HMAC-SHA-256 digests** (`hash_token()` keyed with `SECRET_KEY`). Raw session or password-reset tokens never persist to the database.
- **Constant-Time Verification:** Comparisons use `hmac.compare_digest()`.

## 2. Stateful Sessions, Cookies & CSRF (`app/api/deps.py`, `app/api/v1/auth.py`)

- **HttpOnly Session Cookie (`recova_session`):** Carries the opaque session token; inaccessible to client JavaScript. Enforces both absolute TTL (`SESSION_TTL_MINUTES`, default `480`) and sliding idle expiry (`SESSION_IDLE_TIMEOUT_MINUTES`, default `60`).
- **CSRF Double-Submit Protection (`recova_csrf` / `X-CSRF-Token`):** Login, bootstrap, public organisation registration, and CSRF refresh issue `recova_csrf`. All cookie-authenticated mutating requests (`POST`, `PUT`, `PATCH`, `DELETE`) require header `X-CSRF-Token` matching the server-stored session token (verified in constant time); requests without a valid header are rejected with `403`.
- **Cookie Security Flags:** Controlled via `COOKIE_SECURE` (`false` for HTTP `localhost` development, `true` in HTTPS production) and `COOKIE_SAMESITE` (`lax` default).

## 3. Field-Level Encryption & Log Redaction (`app/core/security.py`, `app/core/audit.py`)

- **Fernet PII Encryption:** Patient sensitive fields (`national_id_enc`, `phone_enc`, `email_enc`, `emergency_contact_enc`, `insurance_member_id_enc`) and organization integration secrets (`IntegrationConfig.secrets_encrypted`) are encrypted via `cryptography.fernet.Fernet`. Production environments should configure an explicit `FIELD_ENCRYPTION_KEY`; in local development if omitted, a deterministic Fernet key is derived from `SECRET_KEY`.
- **Audit Redaction (`app/core/audit.py`):** Before inserting rows into `audit_events`, `_scrub()` recursively masks keys containing `password`, `password_hash`, `token`, `token_hash`, `csrf`, `secret`, `api_key`, `national_id`, `phone`, `email_address`, `emergency_contact`, `insurance_member_id`, `authorization`, or `cookie` with `"[redacted]"`.
- **LLM De-Identification (`app/agents/agent5_synthesis.py`):** Agent 5 strips all direct patient identifiers before dispatching JSON payloads to any external LLM API.

## 4. Multi-Tenant Isolation & RBAC (`app/core/permissions.py`)

Every query filters explicitly by `organization_id` resolved from `AuthContext` (`org_id`). Cross-organization access is denied unless a `platform_admin` is explicitly operating in permitted admin contexts or an authenticated user holds an active `Membership` for that organization and switches via `/api/v1/auth/switch-organization`. Self-service tenant registration (`/api/v1/auth/register-organization`) provisions `is_platform_admin = false` with an `org_admin` membership scoped exclusively to the newly created organization, rejecting duplicate slugs or existing emails with `409 Conflict` under IP rate limiting.

### Built-In Roles

| Role | Intended Persona | Access Boundaries |
| --- | --- | --- |
| `platform_admin` | Platform infrastructure operator | Multi-org creation, global governance, admin operations |
| `org_admin` | Hospital / clinic / employer administrator | User provisioning, track toggles, role overrides, integrations, settings |
| `clinician` | Licensed physician / clinical reviewer | Patient chart, clinical review sign-off, referrals, outcomes, benchmarks |
| `psychiatrist` | Behavioral health / relapse specialist | Same clinical sign-off and high-sensitivity behavioral review access |
| `care_coordinator` | IFHAS / rehabilitation care navigator | Patient intake, referral booking/tracking, notifications, SLA evaluation |
| `screening_coordinator` | Community screening coordinator | IFHAS screening intake and referral coordination |
| `occ_health_director` | Occupational health lead (WorkSafe) | Workplace management & authorized identifiable worker risks (`workforce:identifiable`) |
| `supervisor` | Site / shift manager (WorkSafe) | Aggregate heatmap only; **denied** `workforce:identifiable` unless worker grants explicit consent and RBAC permits |
| `patient` | Enrolled participant / worker | Personal dashboard / self check-ins / own health passport scope |

Per-organization RBAC customization is supported via `RolePermissionOverride` (`grant` or `revoke` entries audited in `audit_events`).

## 5. Rate Limiting & HTTP Security Middleware (`app/core/rate_limit.py`, `app/main.py`)

- **Sliding-Window Rate Limiter:** In-process thread-safe `RateLimiter` protects sensitive endpoints (`rate_limit_login_per_minute = 10` on auth attempts, `rate_limit_default_per_minute = 300` default) and raises HTTP `429` (`RateLimited`) with `retry_after_seconds` when exceeded. For multi-replica horizontal scaling, place a reverse-proxy or Redis-backed rate limiter in front of FastAPI.
- **CORS & Security Headers:** Configured via `CORS_ORIGINS` (`CORSMiddleware` with `allow_credentials=True`) alongside `security_and_context_middleware` in `app/main.py`.
- **Vital-Interest Emergency Screening Exception:** Controlled via `EMERGENCY_SCREEN_WITHOUT_CONSENT` (`True` by default), allowing Gate 2 to screen/escalate acute emergencies even while Gate 1 blocks routine scoring/synthesis.
