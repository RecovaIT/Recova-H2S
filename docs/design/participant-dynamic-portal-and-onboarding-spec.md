# Dynamic Participant Portal, Onboarding & Population-Health Specification

> **Scope:** Cross-cutting user/patient dynamic flow, 5-step health center onboarding, secure invitation/account linking, additional-programme requests, and shared population-health coordination.
> **Aligned With:** [implementation-prd-2026-11-17.md](file:///c:/Users/USER/Recova/Recova-H2S/docs/implementation-prd-2026-11-17.md), [patient-portal-handoff.md](file:///c:/Users/USER/Recova/Recova-H2S/docs/patient-portal-handoff.md), and [AGENTS.md](file:///c:/Users/USER/Recova/Recova-H2S/AGENTS.md).

---

## 1. Health Center Onboarding & Programme Request Flow

### 1.1 Five-Step Onboarding (`/register-organization` -> `OrganizationOnboardingCard.tsx`)
1. **Step 1 — Organisation:** Name, facility type, location/emirate, and initial administrator details.
2. **Step 2 — Programme (Mutually Exclusive):** Four cards (`Recovery` [`core`], `Loop` [`loop`], `Neuro` [`neuro`], `WorkSafe` [`worksafe`]) explaining target audience, inputs, daily staff tasks, and outputs. Selecting one replaces any earlier selection (`ONB01`). API rejects missing, unknown, or multiple programmes (`ONB02`).
3. **Step 3 — Service Setup:** Programme-specific configuration and live preview of the staff dashboard and participant portal experience (`ONB03`).
4. **Step 4 — Participation & Permissions:** Explains shared population-health coordination (who can publish notices, audience selection, acknowledgement tracking, external channels) and records the policy version + consent wording (`ONB08`).
5. **Step 5 — Review & Create:** Summarizes all choices. Submits atomically to `POST /api/v1/auth/register-organization` with idempotency key to prevent duplicate organisations/invitations (`ONB05`, `ONB06`). Backwards navigation preserves all common fields (`ONB04`); errors preserve input (`ONB07`).

### 1.2 Requesting Additional Programmes Post-Onboarding
- A center starts with **exactly one** `primary_programme`.
- If a center needs a second programme later, an authorised Facility Administrator submits a **Programme Expansion Request** from `/settings` (recording justification, target programme, actor, and timestamp).
- Approval by a Platform Administrator creates an audited `TrackEnrolment` / `enabled_tracks` update without mutating historical records' original programme context.

---

## 2. Dynamic Login Routing (`GET /api/v1/auth/me`)

Single `/login` screen resolves destination strictly from authenticated server context:

| Authenticated State | Destination |
| --- | --- |
| Participant with 1 active enrolment | `/portal` (that enrolment's programme home) |
| Participant with $> 1$ authorised enrolments | Enrolment Chooser (facility + programme labels) -> `/portal` |
| Staff with 1 organisation | `/dashboard` (scoped to that org's `primary_programme`) |
| Staff with $> 1$ organisations | Last valid org or Organisation Chooser -> `/dashboard` (clears stale state on switch) |
| Authority user | `/authority` (within assigned geography/facility scope) |
| Legacy multi-track org awaiting resolution | Dedicated Programme-Selection task for its administrator |
| Account without active access | Clear membership/invitation state and next action |

---

## 3. Participant Registration, Invitations & Secure Linking

1. **Staff Registration (`PatientQuickCreateModal.tsx`):** Collects common identity/contact fields (encrypted at rest via Fernet AES-128-CBC) + programme-specific context. Preselects and explains the facility's `primary_programme` (`PAT01`).
2. **Single-Use Expiring Invitation (`POST /api/v1/patients/{id}/portal-invitations`):**
   - Token stored as a cryptographic **hash**, bound to `purpose` and `recipient`, and invalidated upon acceptance or replacement (`PAT03`).
   - Matching names or emails across facilities **never** silently merge records (`PAT04`).
3. **Account Linking & Consent Review:**
   - Server verifies token -> links `Patient.portal_user_id` -> participant reviews information & separate consent records (`data_processing`, `wearable_ingestion`, `llm_synthesis`, `family_notifications`, `external_hie`).
   - Client-supplied `patient_id` overrides are rejected on all `/api/v1/portal/*` routes (`PAT02`).

---

## 4. Dynamic Participant Portal (`/portal`)

- **Mobile-First Navigation (`390px` min width, no horizontal scroll):** Bottom bar with `Home`, `Activities`, `Care`, `Notices` + safe-area padding.
- **Programme-Driven Home:**
  - **`core` (Recovery):** Daily reflection, craving/mood, wearable CSV import, approved care instructions.
  - **`loop` (Loop):** Screening progress, dated results with units, assigned clinic/insurance context, bookings.
  - **`neuro` (Brain Health):** Accessible cognitive practice/assessment activities, clinician-released results.
  - **`worksafe` (WorkSafe):** ~10-second pre-shift readiness check, shift/worksite context, hydration/safety instructions.
- **Idempotency & Separation (`POR05`, `POR06`):** Retries use idempotency keys so duplicate submissions create only one activity and one pipeline run. Acknowledgement, provider delivery, and clinical outcome remain separate states.

---

## 5. Shared Population-Health Coordination (`/authority` & `/api/v1/notices`)

Provisioned for **every** organisation regardless of `primary_programme` (`POP01`):
- **States:** Notice (`draft`, `published`, `expired`, `withdrawn`); Recipient (`available`, `read`, `acknowledged`); Provider delivery (separate state).
- **Authority Workflow:**
  1. `POST /api/v1/authority/notices` — Create draft within assigned geographic/facility scope (`POP02`).
  2. Draft preview shows exact target audience and count before publication (`POP03`).
  3. `POST /api/v1/authority/notices/{id}/publish` — Publishes versioned notice; edits create new version + audit event (`POP09`).
- **Recipient Workflow:**
  - `GET /api/v1/notices` returns only in-scope notices (`POP04`).
  - `POST /api/v1/notices/{id}/acknowledgements` records authenticated acknowledgement idempotently (`POP05`).
## 6. Backend Endpoint Mapping (`portal.py`, `auth.py`, `clinical.py`, `orgs_users.py`)

### 6.1 Existing Endpoints
- **Portal (`portal.py`):**
  - `GET /api/v1/portal/me` — Returns authenticated participant's active enrolment, facility context, signals, care actions, and notices.
  - `POST /api/v1/portal/check-ins` — Persists Recovery check-ins and WorkSafe pre-shift readiness, triggering the shared engine.
  - `POST /api/v1/portal/activities` — Persists Neuro cognitive activity observations & server-derived correctness.
  - `POST /api/v1/portal/consents` — Updates participant consent grants/revocations.
  - `POST /api/v1/portal/wearable-import` — Validates and ingests wearable CSV (`sleep_hours`, `hrv_rmssd`, `resting_hr`, `steps`) with SHA-256 idempotency.
  - `POST /api/v1/portal/notices/acknowledge` — Records idempotent notice acknowledgement.
- **Auth & Staff Participant Provisioning (`auth.py`, `clinical.py`, `orgs_users.py`):**
  - `POST /api/v1/auth/register-organization`, `GET /api/v1/auth/me`, `POST /api/v1/auth/switch-organization`
  - `GET/POST /api/v1/patients`, `GET/PATCH /api/v1/patients/{patient_id}`, `POST /api/v1/patients/{patient_id}/enrollments`
  - `GET /api/v1/patients/{patient_id}/passport`
  - `GET/POST /api/v1/users`, `PATCH /api/v1/users/{user_id}`, `PATCH /api/v1/users/memberships/{membership_id}`

### 6.2 Proposed / Gap Endpoints to Add
- `POST /api/v1/patients/{id}/portal-invitations` (and acceptance endpoint) for hashed, expiring, recipient-bound onboarding links.
- `GET /api/v1/notices`, `POST /api/v1/authority/notices`, `POST /api/v1/authority/notices/{id}/publish`, `POST /api/v1/notices/{id}/acknowledgements` (to replace fixture-backed demo notices in `portal.py`).
- `POST /api/v1/organizations/programme-requests` for centers requesting additional programmes post-onboarding.

---

## 7. Pages & Features to Create / Adjust

1. **`/login` & Context Chooser (`frontend/src/app/login/page.tsx`):** Single login routing by `GET /api/v1/auth/me` with Enrolment Chooser (multiple participant enrolments) and Organisation Chooser (multiple staff orgs).
2. **`/register-organization` (`OrganizationOnboardingCard.tsx`):** 5-step onboarding wizard with mutually exclusive programme cards, live staff/patient preview, and shared public-health disclosure.
3. **`/portal` (`frontend/src/app/portal/page.tsx`):** Dynamic mobile-first (`390px` safe) participant portal rendering `Recovery`, `Loop`, `Brain Health`, or `WorkSafe` home + `Home / Activities / Care / Notices` bottom nav + Privacy/Consent controls.
4. **`/patients` & `/patients/[id]` (`PatientQuickCreateModal.tsx`):** Staff participant creation inheriting `primary_programme`, portal invitation issuance, and Family Health Passport (`GET /api/v1/patients/{patient_id}/passport`).
5. **`/authority` (New Page):** Scoped public-health notice drafting, audience count preview, publication, and aggregate acknowledgement reporting.
