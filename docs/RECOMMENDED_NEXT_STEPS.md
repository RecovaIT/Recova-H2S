# Recova-H2S: Recommended Next Steps & Engineering Roadmap

**Sprint:** Future Health Digital Innovation Challenge 2026 (Nov 8 – 20, 2026)  
**Current Date:** November 18, 2026 (2 days until final submission)  
**Author:** Abdulazeez Abdulganiyu (Frontend Engineer — Clinical Workspace & Track Interfaces)  
**Branch:** `Doctware` (`7a96c62`)  
**Status Reference:** Strict Fact-Check & Zero Mock Policy Adherent  

---

## 🎯 Executive Sprint Countdown & Priorities

```
  Nov 17 (Completed)        Nov 18 (Today / Immediate)       Nov 19 (Freeze)          Nov 20 (Submission)
┌───────────────────────┐  ┌─────────────────────────────┐  ┌────────────────────┐  ┌─────────────────────┐
│ • Postgres & Tools    │  │ • Benchmark Sync (Task 4.2) │  │ • Full E2E Rehearsal│ │ • Final Jury Demo   │
│ • Rules (AGENTS.md)   │  │ • Arabic Sign-Off (Task 2.7)│  │ • Perf & Docker Run│  │ • PDF Brief Handover│
│ • Zero-Mock Audit     │  │ • Edge-Case QA (Task 4.3)   │  │ • Code Freeze      │  │ • Challenge Closes  │
└───────────────────────┘  └─────────────────────────────┘  └────────────────────┘  └─────────────────────┘
```

---

## 1. 🔴 High-Priority Immediate Tasks (Due: Nov 18, 2026)

### 1.1 Task 4.2 — Live Benchmark Synchronization with Hasan
* **Context:** The validation dashboard at [`frontend/src/app/benchmarks/page.tsx`](file:///c:/Users/USER/Recova-H2S/frontend/src/app/benchmarks/page.tsx) is dynamically connected to the backend runner (`/api/v1/ops/benchmarks/run`). All hardcoded placeholder metrics (`100%`, `94.2%`) were removed.
* **Action Required:**
  1. Coordinate with Hasan to verify the benchmark runner executes against his offline gold-standard clinical case files.
  2. Confirm 100% sensitivity on **Gate 2 Emergency Bypass** detection across acute withdrawal, self-harm, and severe heat illness ($T_{\text{core}} > 38.5^\circ\text{C}$).
  3. Validate mathematical consistency of personal baseline drift ($Z$-scores) and missing stream tolerances.
* **Success Criteria:** Benchmark run records populate in PostgreSQL `benchmark_runs` table and render dynamically in the Benchmarks & QA tab without errors.

---

### 1.2 Task 2.7 — Close Out Clinical Sign-Off for Arabic Synthesis with Asiyah
* **Context:** The Arabic clinical synthesis preview in [`frontend/src/components/DecideAiReviewWorkspace.tsx`](file:///c:/Users/USER/Recova-H2S/frontend/src/components/DecideAiReviewWorkspace.tsx) was completely rewritten to use native `<div dir="rtl" className="space-y-3 text-right font-sans ...">` with pure Arabic strings and zero broken inline JSX interpolations. Vitest automated tests pass.
* **Action Required:**
  1. Deliver the final formatted Arabic text bundle to Asiyah's clinical reviewer.
  2. Secure formal sign-off confirmation from the reviewer.
  3. Record the sign-off in the task checklist and update Task 2.7 status to **DONE (Approved)**.
* **Success Criteria:** Reviewer confirms that the medical phrasing, terminology, and RTL punctuation read correctly without typographical errors.

---

### 1.3 Task 4.3 — Formal Edge-Case Testing & QA Handover Report
* **Context:** All automated regression suites pass 100% (17/17 Vitest, 18/18 Pytest). Edge cases have been verified in code: empty states, missing streams, crisis phrases, and $k$-anonymity suppression.
* **Action Required:**
  1. Consolidate the edge-case verification log into a concise QA summary report.
  2. Deliver the report to Yusuf and Hasan for their integration and walkthrough verification.
  3. Verify that no uncaught promise rejections or hydration mismatches occur during rapid navigation across all 4 tracks.
* **Success Criteria:** Zero crashes across edge-case scenarios; written sign-off handed over to Yusuf and Hasan.

---

## 2. 🟡 Medium-Priority Technical Hardening (Nov 18–19, 2026)

### 2.1 Real-Time SSE Stream Auto-Reconnection & Exponential Backoff
* **File:** [`frontend/src/hooks/useRealtimeEvents.ts`](file:///c:/Users/USER/Recova-H2S/frontend/src/hooks/useRealtimeEvents.ts)
* **Goal:** Increase connection resilience during live clinician monitoring.
* **Implementation Recommendation:**
  * Add exponential backoff reconnection logic (e.g., retry after 1s, 2s, 4s, up to 15s max) if the Server-Sent Events (SSE) stream (`/api/v1/engine/events/stream`) disconnects due to server reload or network disruption.
  * Display a subtle connection indicator badge (`Live Connected` / `Reconnecting...`) in the top navigation bar.

---

### 2.2 Database Migration Automation in Docker Entrypoint
* **File:** [`docker-compose.yml`](file:///c:/Users/USER/Recova-H2S/docker-compose.yml)
* **Goal:** Ensure smooth zero-configuration deployment on any target VPS or container platform.
* **Implementation Recommendation:**
  * Update the backend container startup command or entrypoint script to automatically execute:
    ```bash
    alembic upgrade head && python seed_demo.py && uvicorn app.main:app --host 0.0.0.0 --port 8000
    ```
  * This guarantees that when a reviewer or judge boots the Docker stack, the database is migrated and seeded without manual shell commands.

---

### 2.3 Explicit Production Fernet Key & Secrets Management
* **File:** [`backend/app/core/config.py`](file:///c:/Users/USER/Recova-H2S/backend/app/core/config.py)
* **Goal:** Production-grade security compliance under UAE Health Data Law.
* **Implementation Recommendation:**
  * In development, `field_encryption_key` is derived from `SECRET_KEY`.
  * For production VPS deployment, generate a dedicated 32-byte Fernet key via Python:
    ```python
    from cryptography.fernet import Fernet
    print(Fernet.generate_key().decode())
    ```
  * Store this key in production environment variables (`FIELD_ENCRYPTION_KEY`) or cloud secrets manager.

---

## 3. 🛡️ Invariant Rules to Maintain (Do Not Violate)

1. **Zero Mock & Zero Static Data Policy:**  
   Never re-introduce hardcoded arrays, mock JSON files, or simulated numbers into UI components. Always use live backend endpoints and `<EmptyState />` handlers. Reference: [`AGENTS.md`](file:///c:/Users/USER/Recova-H2S/AGENTS.md).
2. **DECIDE-AI Separation:**  
   Box 1 (Agent 4 deterministic math) must remain visually and architecturally separated from Box 2 (Agent 5 LLM synthesis).
3. **Emergency Gate 2 Priority:**  
   Crisis signals must bypass routine triage and immediately surface red emergency alerts.
4. **Bilingual RTL Integrity:**  
   Arabic text must always use `dir="rtl"` with semantic right alignment.
5. **WorkSafe $k$-Anonymity:**  
   Supervisors must never see individual worker biometric scores; departments with fewer than $k$ workers ($k \ge 5$) must remain suppressed.

---

## 4. 🧰 Quick Reference Runbook

### Service Management Batch Scripts (in `scripts/`)
| Script | Path | Purpose |
| :--- | :--- | :--- |
| **Connect Database** | [`scripts/connect_db.bat`](file:///c:/Users/USER/Recova-H2S/scripts/connect_db.bat) | Opens `psql` to `recova` database immediately. |
| **Start PostgreSQL** | [`scripts/start_postgres.bat`](file:///c:/Users/USER/Recova-H2S/scripts/start_postgres.bat) | Starts PostgreSQL 16 on port 5432. |
| **Seed Database** | [`scripts/seed_demo_data.bat`](file:///c:/Users/USER/Recova-H2S/scripts/seed_demo_data.bat) | Re-seeds clinical cohorts (Core, Loop, Neuro, WorkSafe) and 30 portal test accounts. |
| **Start Backend** | [`scripts/start_backend.bat`](file:///c:/Users/USER/Recova-H2S/scripts/start_backend.bat) | Launches FastAPI server on `http://127.0.0.1:8000`. |
| **Start Frontend** | [`scripts/start_frontend.bat`](file:///c:/Users/USER/Recova-H2S/scripts/start_frontend.bat) | Launches Next.js dev server on `http://localhost:3000`. |

### Automated Quality Checks
```powershell
# 1. Frontend TypeScript Compilation Check (Zero Errors Required)
npm --prefix frontend run typecheck

# 2. Frontend Vitest Unit & Integration Test Suite (17 Tests)
npm --prefix frontend test -- --run

# 3. Backend Pytest Integration Test Suite (18 Tests)
backend\.venv\Scripts\pytest backend/tests/
```

### Key Credentials (Seeded Demo Environment)
* **Clinical Admin Email:** `admin@recova.ae`
* **Password:** `Password123!`
* **Organization:** Abu Dhabi Health Hub (`ad-health`)
* **Participant Accounts:** `C:\Users\USER\output\portal-test-accounts.csv`
