# Testing & Synthetic Benchmark Validation

Recova separates verification across three complementary layers: **real-PostgreSQL backend integration tests**, **frontend static/component tests**, and an **in-application 15-case isolated synthetic benchmark suite**.

## 1. Backend Integration Tests (`pytest`)

Backend tests run directly against a dedicated PostgreSQL test database (`recova_test`, configured in [`backend/tests/conftest.py`](../backend/tests/conftest.py)) so migrations, constraints, transactions, and worker handlers run on real PostgreSQL rather than SQLite stubs.

### Test Suites (`backend/tests/`)
| File | Coverage |
| --- | --- |
| `test_auth_and_tenancy.py` | First-run bootstrap, Argon2 login, HttpOnly cookie + CSRF enforcement, org switching, multi-tenant isolation, RBAC |
| `test_scoring_engine.py` | Unit normalization conversions, Rothfusz heat index, zero-variance SD floor guard, insufficient baseline handling, Neuro confounder & practice effect adjustments |
| `test_pipeline_and_tracks.py` | Core end-to-end closed loop & FHIR R4 validation, Gate 2 emergency bypass & truthful notification status, Loop/Neuro/WorkSafe pipelines & 15-case benchmarks |
| `test_llm_synthesis.py` | Agent 5 `provider_not_configured` non-fabrication behavior & mocked provider strict `SynthesisDraftSchema` validation |
| `test_ops_and_governance.py` | WorkSafe supervisor k-anonymity suppression, SLA escalation & async job queue, RBAC overrides & user deactivation |

Run backend tests:
```bash
cd backend
.\.venv\Scripts\pytest.exe -v --tb=short
```

## 2. Frontend Typecheck, Unit/Component Tests, Lint & Build

| Check | Command | Coverage |
| --- | --- | --- |
| TypeScript | `npm run typecheck` | Full `tsc --noEmit` static verification across `src/` |
| Component & API Tests | `npm test` (`vitest run`) | `api.test.ts` (CSRF header injection & error parsing), `agent-graph.test.tsx` (6-agent inspection gating), `decide-ai.test.tsx` (honest `provider_not_configured` notice + RTL Arabic tab rendering), `neuro-game.test.tsx` (non-diagnostic disclaimer & cognitive session launch), `worksafe.test.tsx` (k-anonymity suppression banner) |
| ESLint 9 + React Compiler | `npm run lint` | Next.js Core Web Vitals & React 19 Compiler effect/purity checks |
| Production Build | `npm run build` | Compiles App Router & builds all 21 routes |

Run full frontend gate suite:
```bash
cd frontend
npm run typecheck && npm test && npm run lint && npm run build
```

## 3. Isolated 15-Case Synthetic Benchmark Suite (`app/benchmarks/`)

Recova includes an API- and UI-executable validation suite (`/benchmarks` -> `POST /api/v1/benchmarks/runs`) defined in [`backend/app/benchmarks/suites.py`](../backend/app/benchmarks/suites.py).
- Synthetic benchmark patients are flagged `is_synthetic=True` so they **never appear** in clinical patient directories or WorkSafe metrics.
- Cases run through the actual six-agent orchestrator and compute real sensitivity, specificity, emergency detection accuracy, missing-data degradation pass rate, scoring consistency, and latency telemetry.

| Case ID | Track | Category | Scenario & Verification Target |
| --- | --- | --- | --- |
| `BM-CORE-01` | `core` | `normal` | Stable recovery control -> `GREEN` |
| `BM-CORE-02` | `core` | `gradual_decline` | 4-day sleep/HRV/mood drop -> `RED` |
| `BM-CORE-03` | `core` | `missing_data` | Missing smartwatch stream graceful degradation (`confidence_index` penalized) |
| `BM-CORE-04` | `core` | `acute_emergency` | Suicidal ideation text -> immediate Gate 2 `EMERGENCY_BYPASS` |
| `BM-CORE-05` | `core` | `acute_emergency` | Severe withdrawal seizure cues -> immediate Gate 2 `EMERGENCY_BYPASS` |
| `BM-CONSENT-01` | `core` | `consent` | Missing mandatory consent blocks routine processing (`blocked`) |
| `BM-LOOP-01` | `loop` | `normal` | Stable IFHAS cardiometabolic baseline -> `GREEN` |
| `BM-LOOP-02` | `loop` | `gradual_decline` | IFHAS HbA1c & BP elevation (`5.4% -> 6.9%`) -> actionable escalation |
| `BM-LOOP-03` | `loop` | `acute_emergency` | PHQ-9 Item 9 self-harm score >= 1 -> Gate 2 `EMERGENCY_BYPASS` |
| `BM-NEURO-01` | `neuro` | `normal` | Stable longitudinal cognitive session baseline -> `GREEN` |
| `BM-NEURO-02` | `neuro` | `confounder` | Mild presbycusis hearing confounder widens SE (`1.25x`) -> avoids false `RED` |
| `BM-NEURO-03` | `neuro` | `gradual_decline` | Multi-stream cognitive accuracy & recall drop -> `RED` |
| `BM-OSH-01` | `worksafe` | `normal` | Normal worker shift readiness & thermal recovery -> `GREEN` |
| `BM-OSH-02` | `worksafe` | `gradual_decline` | Delayed HR recovery & core temp drift -> heat-fatigue escalation |
| `BM-OSH-03` | `worksafe` | `acute_emergency` | Suspected exertional heatstroke (`core_temp_est_c >= 40.0 C`) -> Gate 2 `EMERGENCY_BYPASS` |

## 4. Full-Stack Live E2E Verification

To verify the complete runtime stack end-to-end against a clean PostgreSQL database:
1. Run `alembic upgrade head` against a target Postgres database.
2. Start FastAPI (`uvicorn app.main:app --host 127.0.0.1 --port 8000`) and Next.js (`node .next/standalone/server.js` or `npm run dev` on port `3000`).
3. Verify `/healthz` and `/readyz`, Next.js SSR App Router responses across pages, `/api/v1/auth/bootstrap` + cookie/CSRF enforcement through the Next.js `/api/v1` proxy, Gate 1 consent blocking, Core wearable baseline & Gate 2 emergency bypass, Loop IFHAS screening, Neuro cognitive trial ingestion, WorkSafe supervisor vs `org_admin` k-anonymity separation, FHIR R4 Bundle validation, and execution of all 15 synthetic benchmark cases.
