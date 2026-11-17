# Recova challenge readiness audit · 16 November 2026

## Scope

Reviewed the GitHub branches and the team's November roadmap (Google Doc and PDF). The November 20 date is the team's submission target. The supplied documents describe intended behavior. Their example scores, screenshots-to-be-produced and launch instructions are not validation evidence.

| Branch | Revision | What a judge receives |
| --- | --- | --- |
| main | acf2481 | License only. Following the GitHub landing page gives no application. |
| Doctware | 3c467c0 | FastAPI, PostgreSQL, Next.js, four track workspaces, six-agent pipeline and synthetic benchmark runner. Use as the release candidate. |
| feat/brain | da21bab | TypeScript scoring implementation with eight passing unit tests. Home page and pipeline API are scaffolds. The benchmark command refers to an absent scripts/run-benchmark.ts. |

## Track coverage on Doctware

| Track | Present in the release candidate | Remaining demonstration |
| --- | --- | --- |
| Core | Wearable and check-in ingestion, personal baseline, longitudinal chart, emergency bypass, clinical review and referral tracker | Give a judge stable, decline, missing-data and crisis cases with one-click selection. Demonstrate confidence changes, clinician sign-off and a verified outcome. |
| Loop | Screening records, risk analysis, insurance/SLA routing, referral workflow | Show a synthetic abnormal screening through booking, overdue escalation and confirmed follow-up. Verify actual payer connectivity separately from local routing rules. |
| Neuro | Cognitive tasks, longitudinal scores, sensory/practice adjustments | Demonstrate the same participant before and after a confounder adjustment and obtain clinical review of the scoring model. |
| WorkSafe | Readiness and heat inputs, interventions and supervisor aggregation | Demonstrate privacy suppression for a small cohort and the different occupational-health and supervisor views. |

## Release issues and acceptance criteria

1. **Repository entry point.** Publish the tested application on the default branch or give judges a direct release link. Replace the different repository and root-level npm instructions in the Google Doc. Test the instructions from a clean checkout.
2. **Frontend installation.** On this Windows machine the tracked lockfile failed npm ci with missing @emnapi entries. Regenerate and review the lockfile, pin the Node/npm versions, and run clean install plus production build in CI and in the Docker image.
3. **Judge-ready cases.** backend/app/benchmarks/runner.py removes synthetic fixture patients after each case, while the workspaces select patients from the organization. Provision an isolated, resettable demo organization with the roadmap's 5–10 persistent synthetic cases. Keep benchmark isolation intact.
4. **Live agent graph.** frontend/src/hooks/useRealtimeEvents.ts subscribes to pipeline.step and pipeline.completed. The orchestrator emits agent.step_started, agent.step_finished and pipeline.finished as named SSE events. Align the names. The in-memory EventBus cannot deliver events from the separate Compose worker to the API process. Verify a queued run in the deployed topology with the graph open, including the emergency bypass.
5. **Production settings.** Compose defaults to production with COOKIE_SECURE=false while backend/app/core/config.py rejects that combination. The worker also needs the production cookie setting and currently omits several provider settings carried by the API. Validate API and worker startup together and test one queued notification using sandbox credentials.
6. **Scoring specification.** Python uses baseline SD / sqrt(n) before adjustments. The TypeScript branch uses SD × sqrt(1/n_baseline + 1/n_current). Agree which quantity the model estimates, version it, and use the same signed examples and threshold-boundary cases across implementations. Passing separate test suites cannot establish equivalence.
7. **Consent.** backend/app/agents/agent5_synthesis.py accepts general data-processing permission unless the LLM scope is revoked. Decide whether separate opt-in is required, align behavior and wording, and test absent, granted and revoked states before enabling external synthesis.
8. **Validation and delivery.** Separate benchmark performance on authored cases from clinical validation. Obtain clinical mentor review of thresholds and DECIDE-AI governance. Verify bilingual summaries and human approval. Record the 3–5 minute walkthrough, verify a judge-accessible URL, and package benchmark evidence, architecture and pilot plan. No external provider, regulator, sponsor, or portal action was performed.

## Local setup

Fresh implementation clone: Recova-H2S-challenge. The existing Recova-H2S checkout had local edits. Brain branch testing used a separate local clone. Local testing uses PostgreSQL 15 on loopback port 55432 and separate recova_challenge and recova_test databases. The repository specifies PostgreSQL 16 for deployment. backend/tests/conftest.py hardcodes port 55432 and drops and recreates tables; reserve recova_test for disposable test data.

## Verification results

- Doctware backend: 14 pytest tests passed on real PostgreSQL 15, with one test-client deprecation warning. Tests covered tenant isolation, role checks, consent, emergency bypass, scoring, all four tracks, referral closure, FHIR output, WorkSafe suppression, mocked LLM responses and unconfigured-provider handling.
- The all-track test executed 15/15 synthetic benchmarks and asserted 100% sensitivity, specificity, emergency-case detection and scoring consistency on those fixtures. Independent clinical performance is unverified.
- Doctware frontend: 10/10 tests across six files passed after npm install regenerated the lockfile. ESLint and TypeScript reported no errors. Production build succeeded with 22 static pages. The local lockfile repair has not been pushed.
- feat/brain: 8/8 scoring tests passed after npm ci.
- Fresh database migration to cd2178bcb554 succeeded. GET /readyz reported a connected database, /bootstrap served HTTP 200, and the frontend proxy returned {"needs_bootstrap":true}. Local UI: http://127.0.0.1:3017/bootstrap. API: http://127.0.0.1:8017. Application database deliberately awaits the owner's first-organization setup.
- Scope of runtime verification: local standalone build and API, automated component and integration tests, and HTTP smoke checks. A full interactive browser walkthrough, remote deployment, external service delivery and independent clinical validation remain unverified.

### Restart on this PC

If the isolated database has stopped, run the following PowerShell command:

    & 'C:/Program Files/PostgreSQL/15/bin/pg_ctl.exe' -D "$env:LOCALAPPDATA/recova-challenge-pg-7b6cf11d915f45bf9d85f5ddd86e0522" -l "$env:LOCALAPPDATA/recova-challenge-pg-7b6cf11d915f45bf9d85f5ddd86e0522/server.log" -o '-h 127.0.0.1 -p 55432' -w start

From the clone's backend folder:

    ./.venv/Scripts/python -m uvicorn app.main:app --host 127.0.0.1 --port 8017

From the clone's frontend folder in a second terminal:

    $env:HOSTNAME='127.0.0.1'
    $env:PORT='3017'
    node .next/standalone/server.js
