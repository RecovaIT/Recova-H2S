# Historical brain prototype

Preserved from `origin/feat/brain` (`da21bab`) during main integration on 18 November 2026. This directory retains the original standalone scaffold, synthetic test cases, scoring implementation and tests for provenance and comparison. It is not the deployed application and is not imported by the release frontend or backend. Its stubs, sample data and fallback behavior must not be presented as working product features.

Run the release application from repository `frontend/` and `backend/`. The authoritative production scoring implementation is `backend/app/engine/scoring.py`; this historical TypeScript implementation does not replace it. Any future transfer of scoring changes requires clinical review and parity tests, including missing-data and confounder behavior.
