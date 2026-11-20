# Recova System Test Cases & Local Dev/Demo Credentials

> **ENVIRONMENT WARNING:** All accounts and credentials below are **SYNTHETIC LOCAL DEVELOPMENT / JUDGE DEMO FIXTURES ONLY**. The seeder (`backend/scripts/seed_all_test_cases.py`) refuses to run when `ENVIRONMENT=production`. Never use these in production.

---

## 1. Where the Local Database Is Referenced in the Codebase

| File | Purpose | Connection / Reference |
| --- | --- | --- |
| `backend/.env` (line 7) | Active local runtime DB URL | `DATABASE_URL=postgresql+psycopg://recova:recova@localhost:5432/recova` |
| `backend/app/core/config.py` (line 28) | Default Pydantic `Settings.database_url` | `"postgresql+psycopg://recova:recova@localhost:5432/recova"` |
| `backend/app/core/db.py` (line 15) | SQLAlchemy 2.0 engine & `SessionLocal` | `create_engine(_settings.database_url, ...)` |
| `backend/migrations/env.py` | Alembic migration target | Reads `get_settings().database_url` (overrides `alembic.ini`) |
| `backend/tests/conftest.py` (lines 13–16) | Pytest isolated test DB | `postgresql+psycopg://recova:recova@127.0.0.1:5432/recova_test` |
| `scripts/start_postgres.bat` | Local PostgreSQL 16 launcher | `"C:\Users\USER\pgsql\bin\postgres.exe" -D "C:\Users\USER\pgsql\data"` |
| `scripts/connect_db.bat` | Local `psql` CLI helper | `"C:\Users\USER\pgsql\bin\psql.exe" -U recova -d recova` |

---

## 2. How to Seed All Test Cases Locally

```powershell
cd c:\Users\USER\Recova\Recova-H2S\backend
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m scripts.seed_all_test_cases --reset```

**Shared Password for All Local Demo/Test Accounts:** `JudgeDemo123!`

---

## 3. Complete Credential Matrix (37 Accounts — All Roles & Sub-Engines)

### A. Platform Command, Authority & Legacy Edge Cases (1–4)

| # | Email | Password | Role / Scope | Target Route | Test Focus |
| :---: | --- | --- | --- | --- | --- |
| **1** | `platform.admin@demo.recova.ae` | `JudgeDemo123!` | `is_platform_admin=True` (`org_admin` in all 4 centers) | `/dashboard` | Overall Engine Command, 4 Sub-Dashboards, 6-Agent Telemetry, Multi-Org Switcher, Programme Request Approvals (`/settings`), `/agents`, `/benchmarks` |
| **2** | `authority.abu-dhabi@demo.recova.ae` | `JudgeDemo123!` | Authority / Platform scope | `/authority` | Draft, preview audience, publish, and withdraw scoped public-health notices |
| **3** | `legacy.admin@demo.recova.ae` | `JudgeDemo123!` | `org_admin` (`legacy-multi-org`) | `/dashboard` | Legacy multi-track org (`programme_configuration_status="pending_selection"`) |
| **4** | `unlinked.user@demo.recova.ae` | `JudgeDemo123!` | No active membership | `/login` | Clear "no active access" / invitation state |

### B. Health Center Staff Accounts (5–16, Scoped to Single Primary Programme)

| # | Sub-Engine | Email | Password | Role | Test Focus |
| :---: | --- | --- | --- | --- | --- |
| **5** | **Core (Recovery)** | `admin.core@demo.recova.ae` | `JudgeDemo123!` | `org_admin` | Center admin, staff/patient creation, pending Loop expansion request in `/settings` |
| **6** | **Core (Recovery)** | `judge.core.clinician@demo.recova.ae` | `JudgeDemo123!` | `clinician` | Recovery dashboard, Z-bands, DECIDE-AI Box 1/2, SHA-256 sign-off |
| **7** | **Core (Recovery)** | `care.core@demo.recova.ae` | `JudgeDemo123!` | `care_coordinator` | Closed-loop referral tracking & verified follow-up |
| **8** | **Core (Recovery)** | `psych.core@demo.recova.ae` | `JudgeDemo123!` | `psychiatrist` | Clinical review & Gate 2 crisis resolution |
| **9** | **Loop** | `admin.loop@demo.recova.ae` | `JudgeDemo123!` | `org_admin` | Loop center setup, `InsurancePlan` & `CareFacility` network |
| **10** | **Loop** | `judge.loop.clinician@demo.recova.ae` | `JudgeDemo123!` | `clinician` | IFHAS screening review & clinical sign-off |
| **11** | **Loop** | `coordinator.loop@demo.recova.ae` | `JudgeDemo123!` | `screening_coordinator` | Screening follow-up, consultation booking & SLA deadlines |
| **12** | **Neuro** | `admin.neuro@demo.recova.ae` | `JudgeDemo123!` | `org_admin` | Neuro center management |
| **13** | **Neuro** | `judge.neuro.clinician@demo.recova.ae` | `JudgeDemo123!` | `clinician` | Cognitive Studio game, practice-effect & sensory confounders |
| **14** | **WorkSafe** | `admin.worksafe@demo.recova.ae` | `JudgeDemo123!` | `org_admin` | Workplace & department (`k >= 5`) setup |
| **15** | **WorkSafe** | `judge.worksafe.clinician@demo.recova.ae` | `JudgeDemo123!` | `occ_health_director` | Identifiable worker risks, Rothfusz Heat Index & interventions |
| **16** | **WorkSafe** | `supervisor.worksafe@demo.recova.ae` | `JudgeDemo123!` | `supervisor` | Lands directly on `/worksafe`; sees $k$-anonymous department heatmap only (identifiable records blocked) |

### C. Patient / Participant Portal Accounts (17–37, `/portal`)

| # | Programme | Scenario | Email | Password | Expected Behaviour |
| :---: | --- | --- | --- | --- | --- |
| **17** | **Multi-Enrolled** | Core + Loop | `multi.patient@demo.recova.ae` | `JudgeDemo123!` | Enrolment Chooser switching between Recovery and Loop |
| **18** | **Core** | Stable | `judge.core.stable@demo.recova.ae` | `JudgeDemo123!` | Recovery home, `GREEN` baseline, reflection & CSV wearable import |
| **19** | **Core** | Gradual Decline | `judge.core.gradual_decline@demo.recova.ae` | `JudgeDemo123!` | `AMBER`/`RED` sleep/HRV drift visible in clinician chart |
| **20** | **Core** | Missing Data | `judge.core.missing_data@demo.recova.ae` | `JudgeDemo123!` | `INDETERMINATE` state & degraded confidence index |
| **21** | **Core** | Emergency | `judge.core.emergency@demo.recova.ae` | `JudgeDemo123!` | Gate 2 crisis bypass + immediate red escalation banner |
| **22** | **Core** | Absent Consent | `judge.core.absent_consent@demo.recova.ae` | `JudgeDemo123!` | Routine submission blocked until `data_processing` consent granted |
| **23** | **Loop** | Stable | `judge.loop.stable@demo.recova.ae` | `JudgeDemo123!` | Loop screening progress, dated results & `GREEN` tier |
| **24** | **Loop** | Gradual Decline | `judge.loop.gradual_decline@demo.recova.ae` | `JudgeDemo123!` | Abnormal IFHAS result with active referral navigation |
| **25** | **Loop** | Missing Data | `judge.loop.missing_data@demo.recova.ae` | `JudgeDemo123!` | Partial screening streams & degraded confidence |
| **26** | **Loop** | Emergency | `judge.loop.emergency@demo.recova.ae` | `JudgeDemo123!` | PHQ-9 Item 9 / critical vital Gate 2 crisis bypass |
| **27** | **Loop** | Absent Consent | `judge.loop.absent_consent@demo.recova.ae` | `JudgeDemo123!` | Routine processing blocked until `data_processing` consent granted |
| **28** | **Neuro** | Stable | `judge.neuro.stable@demo.recova.ae` | `JudgeDemo123!` | Brain Health accessible cognitive activity & `GREEN` baseline |
| **29** | **Neuro** | Gradual Decline | `judge.neuro.gradual_decline@demo.recova.ae` | `JudgeDemo123!` | Practice-adjusted longitudinal cognitive drift (`AMBER`/`RED`) |
| **30** | **Neuro** | Missing Data | `judge.neuro.missing_data@demo.recova.ae` | `JudgeDemo123!` | Missing sleep stream & `INDETERMINATE` baseline |
| **31** | **Neuro** | Emergency | `judge.neuro.emergency@demo.recova.ae` | `JudgeDemo123!` | Acute neurological red-flag Gate 2 bypass |
| **32** | **Neuro** | Absent Consent | `judge.neuro.absent_consent@demo.recova.ae` | `JudgeDemo123!` | Routine processing blocked until `data_processing` consent granted |
| **33** | **WorkSafe** | Stable | `judge.worksafe.stable@demo.recova.ae` | `JudgeDemo123!` | ~10s pre-shift readiness check & standard shift clearance |
| **34** | **WorkSafe** | Gradual Decline | `judge.worksafe.gradual_decline@demo.recova.ae` | `JudgeDemo123!` | Elevated heat/fatigue readiness warning & hydration guidance |
| **35** | **WorkSafe** | Missing Data | `judge.worksafe.missing_data@demo.recova.ae` | `JudgeDemo123!` | Missing thermal wearable stream & degraded confidence |
| **36** | **WorkSafe** | Emergency | `judge.worksafe.emergency@demo.recova.ae` | `JudgeDemo123!` | Heatstroke (`core_temp >= 40.0 C` / dizziness) Gate 2 bypass |
| **37** | **WorkSafe** | Absent Consent | `judge.worksafe.absent_consent@demo.recova.ae` | `JudgeDemo123!` | Routine processing blocked until `data_processing` consent granted |

---

## 4. End-to-End System Test Cases Checklist

1. **TC-01 Onboarding (`ONB01`–`ONB09`):** Visit `/register-organization`, complete 5 steps selecting 1 programme -> verify `POST /api/v1/auth/register-organization` creates org and rejects multi-track payloads with `422`.
2. **TC-02 Programme Expansion:** Sign in as `admin.core@demo.recova.ae` -> `/settings` -> Programmes & Expansion -> view/submit request -> sign in as `platform.admin@demo.recova.ae` -> approve -> verify `core` org gains `loop`.
3. **TC-03 Overall Engine Command:** Sign in as `platform.admin@demo.recova.ae` -> `/dashboard` -> switch across `Core`, `Loop`, `Neuro`, `WorkSafe` sub-dashboard tabs -> inspect customer centers & 6-agent telemetry.
4. **TC-04 Portal Invitations (`PAT01`–`PAT07`):** Sign in as `judge.core.clinician@demo.recova.ae` -> `/patients/[id]` -> click **Issue Portal Invite** -> verify 72h hashed token -> accept via `/accept-invitation`.
5. **TC-05 Dynamic Participant Portal (`POR01`–`POR07`):** Sign in as `multi.patient@demo.recova.ae` -> switch between Recovery & Loop -> submit check-in -> verify idempotency & immediate appearance in clinician workspace.
6. **TC-06 DECIDE-AI & Closed-Loop Care:** Sign in as `judge.core.clinician@demo.recova.ae` -> `/core` -> inspect Box 1 (Agent 4) vs Box 2 (Agent 5 EN/AR `dir="rtl"`) -> sign off with SHA-256 -> track referral through `outcome_verified`.
7. **TC-07 WorkSafe $k$-Anonymity:** Sign in as `supervisor.worksafe@demo.recova.ae` -> verify direct routing to `/worksafe` & aggregate-only heatmap (`k >= 5`), and `403` on identifiable worker endpoints.
8. **TC-08 Shared Population-Health Notices (`POP01`–`POP09`):** Sign in as `authority.abu-dhabi@demo.recova.ae` -> `/authority` -> draft & publish notice -> sign in as any participant -> `/portal` Notices tab -> acknowledge idempotently.
9. **TC-09 Live Benchmarks:** Sign in as `platform.admin@demo.recova.ae` -> `/benchmarks` -> run suite -> verify `15/15` passed (`100%` sensitivity, specificity, emergency detection).
