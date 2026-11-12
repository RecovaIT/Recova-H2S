# REST, SSE & WebSocket API Reference

All application endpoints live under FastAPI with version prefix `/api/v1` (plus `/healthz` and `/readyz` root health/readiness probes). In standard browser deployments, Next.js proxies `/api/v1/:path*` same-origin to FastAPI (`next.config.ts`).

## 1. Conventions

- **Authentication:** Stateful opaque token stored in HttpOnly cookie `recova_session` (or `Authorization: Bearer <token>` for programmatic API clients).
- **CSRF Protection:** Cookie-authenticated mutating requests (`POST`, `PUT`, `PATCH`, `DELETE`) require header `X-CSRF-Token` matching the session's `csrf_token` (`recova_csrf` cookie). Requests to `/auth/bootstrap`, `/auth/login`, `/auth/password-reset/request`, `/auth/password-reset/confirm`, and Bearer-header requests are exempt.
- **Tenant Isolation:** Organization context resolves from the active session (switchable via `POST /api/v1/auth/switch-organization` or `X-Organization-ID` header where the user holds active membership).
- **Error Envelope:**
  ```json
  {
    "error": {
      "code": "validation_failed",
      "message": "Human-readable explanation",
      "details": {}
    },
    "request_id": "uuid"
  }
  ```

## 2. System Probes (Root)

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/healthz` | Liveness check (`{"status": "ok"}`) |
| `GET` | `/readyz` | Readiness check verifying PostgreSQL connectivity |

## 3. Authentication (`/api/v1/auth`)

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/v1/auth/status` | Reports `{"needs_bootstrap": boolean}` |
| `POST` | `/api/v1/auth/bootstrap` | First-run org + `org_admin` creation (rate-limited; fails once initialized) |
| `POST` | `/api/v1/auth/login` | Email/password login -> sets `recova_session` + `recova_csrf` cookies |
| `POST` | `/api/v1/auth/logout` | Revokes active session & clears cookies |
| `GET` | `/api/v1/auth/me` | Returns current user, active org, role, effective permissions, enabled tracks, CSRF token |
| `POST` | `/api/v1/auth/csrf` | Rotates/returns session CSRF token |
| `POST` | `/api/v1/auth/switch-organization` | Switches active tenant org for multi-org users |
| `POST` | `/api/v1/auth/password-reset/request` | Issues password reset token |
| `POST` | `/api/v1/auth/password-reset/confirm` | Consumes reset token and sets new password |
| `POST` | `/api/v1/auth/change-password` | Authenticated password update |

## 4. Organizations, Staff Users & Audit (`/api/v1/organizations`, `/api/v1/users`, `/api/v1/audit-logs`)

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/v1/organizations` | List user's active organizations |
| `POST` | `/api/v1/organizations` | Create organization (`platform_admin` / authorized admins) |
| `PATCH` | `/api/v1/organizations/{organization_id}` | Update enabled tracks, retention days, or org settings |
| `GET` | `/api/v1/organizations/permissions/catalog` | List canonical permission keys |
| `GET` | `/api/v1/organizations/permissions/roles` | Inspect default & effective permissions per role |
| `POST` | `/api/v1/organizations/permissions/overrides` | Grant or revoke a role permission override for the org |
| `DELETE` | `/api/v1/organizations/permissions/overrides` | Remove a role permission override |
| `GET` | `/api/v1/users` | List organization staff & memberships |
| `POST` | `/api/v1/users` | Invite or provision user with role + track scoping |
| `PATCH` | `/api/v1/users/{user_id}` | Update user profile / active status |
| `PATCH` | `/api/v1/users/memberships/{membership_id}` | Update role, active flag, or WorkSafe `department_ids` |
| `GET` | `/api/v1/audit-logs` | Paginated immutable audit event query (`action`, `resource_type`, `outcome`) |
| `GET` | `/api/v1/audit-logs/jobs` | Paginated background job queue history (`Page[JobOut]`) |

## 5. Patients, Consents & Clinical Signal Ingestion

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/v1/patients` | Paginated patient/worker directory (`q`, `track`, `risk_tier`, `department_id`, `active_only`) |
| `POST` | `/api/v1/patients` | Register patient/employee + initial track enrollments (PII Fernet-encrypted) |
| `GET` | `/api/v1/patients/{patient_id}` | Full patient chart & enrollments |
| `PATCH` | `/api/v1/patients/{patient_id}` | Update clinical confounders, insurance plan, or status |
| `POST` | `/api/v1/patients/{patient_id}/enrollments` | Enroll existing patient in an additional Recova track |
| `GET` | `/api/v1/patients/{patient_id}/passport` | Unified longitudinal patient/family passport view |
| `GET` | `/api/v1/consents/patient/{patient_id}` | List consent history across all scopes |
| `POST` | `/api/v1/consents` | Grant consent (`data_processing`, `wearable_ingestion`, `llm_synthesis`, `family_notification`, `hie_sharing`, `supervisor_identifiable`) |
| `POST` | `/api/v1/consents/{consent_id}/revoke` | Revoke existing consent with optional reason |
| `GET` | `/api/v1/observations/catalog` | Return canonical LOINC metric catalog & units |
| `GET` | `/api/v1/observations/patient/{patient_id}` | Paginated observations (`metric_code`, `track`) |
| `POST` | `/api/v1/observations` | Record single LOINC-validated observation with unit normalization |
| `POST` | `/api/v1/wearables/ingest` | Batch wearable ingestion (`apple_health`, `garmin`, `fitbit`, `sahatna`, `csv`, `manual_device`) + optional pipeline trigger |
| `GET` | `/api/v1/check-ins/patient/{patient_id}` | List voice/text/readiness check-ins |
| `POST` | `/api/v1/check-ins` | Submit daily check-in (`mood`, `craving`, `stress`, voice transcript, symptoms) + optional pipeline trigger |
| `GET` | `/api/v1/screenings/patient/{patient_id}` | List IFHAS screening records |
| `POST` | `/api/v1/screenings` | Record Loop IFHAS screening (HbA1c, BP, lipids, PHQ-9 items) + optional pipeline trigger |
| `GET` | `/api/v1/cognitive-assessments/patient/{patient_id}` | List Neuro cognitive assessment sessions |
| `POST` | `/api/v1/cognitive-assessments` | Persist multi-trial cognitive battery (`raw_trials`) -> compute accuracy/latency -> trigger pipeline |
| `GET` | `/api/v1/workforce/workplaces` | List WorkSafe workplaces |
| `POST` | `/api/v1/workforce/workplaces` | Create workplace site |
| `GET` | `/api/v1/workforce/departments` | List WorkSafe departments (`min_group_size_for_reporting`) |
| `POST` | `/api/v1/workforce/departments` | Create department with k-anonymity threshold |
| `GET` | `/api/v1/workforce/assessments` | List environmental measurements |
| `POST` | `/api/v1/workforce/assessments` | Record ambient temp, humidity (auto Heat Index C), WBGT, noise, lighting |
| `POST` | `/api/v1/workforce/readiness` | Submit worker readiness + thermal/HR recovery telemetry + trigger pipeline |
| `GET` | `/api/v1/workforce/heatmap` | Department risk heatmap (suppresses `risk_counts` if `< k` workers and caller lacks `workforce:identifiable`) |
| `GET` | `/api/v1/workforce/identifiable-risks` | Individual worker risk roster (requires `workforce:identifiable`; also checks `supervisor_identifiable` consent) |

## 6. Six-Agent Engine, Baselines, Scoring & Streaming (`/api/v1/baselines`, `/scoring`, `/pipeline`, `/agents`)

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/v1/baselines/patient/{patient_id}` | View established personal baselines per metric |
| `POST` | `/api/v1/baselines/patient/{patient_id}/reset` | Recalculate/reset baseline windows for a metric or patient |
| `GET` | `/api/v1/scoring/patient/{patient_id}` | Deterministic Agent 4 `ScoringResult` history |
| `GET` | `/api/v1/scoring/config` | Current algorithm version (`1.2.0`), thresholds, and track metric configurations |
| `GET` | `/api/v1/pipeline/runs` | Paginated pipeline execution runs |
| `POST` | `/api/v1/pipeline/runs` | Trigger 6-agent pipeline synchronously or asynchronously via durable job queue |
| `GET` | `/api/v1/pipeline/runs/{run_id}` | Detailed run including all 6 `AgentStepResult` I/O records, `ScoringResult`, and `ClinicalSynthesis` |
| `GET` | `/api/v1/pipeline/events/stream` | Server-Sent Events (SSE) stream of live org-scoped pipeline & care events |
| `WS` | `/api/v1/pipeline/ws` | WebSocket real-time event stream (token/cookie auth checked on handshake) |
| `GET` | `/api/v1/agents/catalog` | Canonical agent step order and descriptions |
| `GET` | `/api/v1/agents/emergencies` | List Gate 2 emergency escalation events |
| `POST` | `/api/v1/agents/emergencies/{event_id}/resolve` | Acknowledge or resolve an emergency escalation with clinical notes |

## 7. Clinical Care, Referrals, Interventions & Outcomes

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/v1/clinical-reviews` | List clinician DECIDE-AI sign-offs |
| `POST` | `/api/v1/clinical-reviews` | Record signed clinician review decision (`approve_referral`, `modify_plan`, `request_lab`, `no_action`, `reject`) |
| `GET` | `/api/v1/referrals` | Paginated closed-loop referrals (`track`, `status`, `sla_status`, `patient_id`) |
| `POST` | `/api/v1/referrals` | Manually initiate a referral |
| `POST` | `/api/v1/referrals/evaluate-slas` | Scan active referrals and escalate overdue SLAs |
| `GET` | `/api/v1/referrals/{referral_id}` | Detailed referral timeline, events, notifications, and verified outcomes |
| `POST` | `/api/v1/referrals/{referral_id}/notify` | Dispatch patient notification across configured channel |
| `POST` | `/api/v1/referrals/{referral_id}/book` | Book appointment date/facility for referral |
| `POST` | `/api/v1/referrals/{referral_id}/complete-consultation` | Mark specialist/primary consultation completed |
| `POST` | `/api/v1/referrals/{referral_id}/missed` | Mark appointment missed and trigger SLA escalation path |
| `POST` | `/api/v1/outcomes/referral/{referral_id}/verify` | Human-verified outcome closure (`improved`, `stable`, `deteriorated`, `relapsed`, `lost_to_follow_up`, `referred_onward`) |
| `GET` | `/api/v1/interventions` | List preventive/occupational interventions |
| `POST` | `/api/v1/interventions` | Create intervention (`rest_break`, `hydration`, `shift_rotation`, `coaching`, `lab_request`, `follow_up_call`, `other`) |
| `PATCH` | `/api/v1/interventions/{intervention_id}` | Transition intervention status (`planned` / `in_progress` / `completed` / `cancelled`) |
| `GET` | `/api/v1/notifications` | Paginated notification history |
| `POST` | `/api/v1/notifications/{notification_id}/read` | Mark notification read |

## 8. Benchmarks, FHIR R4, Integrations & Population Analytics

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/v1/benchmarks/suite` | Inspect the 15-case synthetic validation suite specifications |
| `GET` | `/api/v1/benchmarks/runs` | List historical benchmark runs |
| `POST` | `/api/v1/benchmarks/runs` | Execute benchmark cases across selected tracks (`run_async` optional) |
| `GET` | `/api/v1/benchmarks/runs/{benchmark_run_id}` | Full benchmark run report with per-case expected vs actual metrics |
| `GET` | `/api/v1/fhir/patients/{patient_id}/bundle` | Generate & validate HL7 FHIR R4.0.1 Bundle (`collection` or `transaction`) |
| `POST` | `/api/v1/fhir/validate` | Validate an arbitrary FHIR R4 Bundle JSON structure |
| `POST` | `/api/v1/fhir/patients/{patient_id}/push-malaffi` | Transmit validated FHIR R4 Bundle to configured Malaffi endpoint (returns `not_configured` if credentials unset) |
| `GET` | `/api/v1/settings/insurance-plans` | List organization payer plans |
| `POST` | `/api/v1/settings/insurance-plans` | Create payer coverage rules |
| `GET` | `/api/v1/settings/care-facilities` | List configured provider facilities |
| `POST` | `/api/v1/settings/care-facilities` | Add provider facility & accepted plans |
| `GET` | `/api/v1/settings/integrations` | List integration statuses (`llm`, `malaffi`, `sahatna`, `smtp`, `twilio`) without exposing secrets |
| `PUT` | `/api/v1/settings/integrations/{name}` | Save integration config & Fernet-encrypted secrets |
| `POST` | `/api/v1/settings/integrations/{name}/test` | Run live connectivity probe for integration `name` |
| `GET` | `/api/v1/reports/overview` | Executive KPI summary (`active_patients`, `open_emergencies`, pending reviews, referral funnel, risk distributions) |
