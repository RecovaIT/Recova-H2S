# Main integration and CEO handoff

The CEO selected `main` for submission on 18 November 2026.

- `abdul-h2s` (`4acc152`) includes `Doctware` (`5f16ec2`), the patient portal, dashboard redesign, subsequent chart work, single-programme onboarding, authority notices and migrations.
- The divergent `feat/brain` (`da21bab`) is preserved under `legacy/brain`, with its history joined. This is an earlier standalone prototype; deploy `frontend` with `backend`.
- Integration corrects authority-page lint, subscribes to the actual backend step/completion/emergency events, and requires effective HIE consent for export and push.
- Governance wording distinguishes prototype controls, local FHIR checks and provider acceptance from certification, delivered messages and clinical outcomes.

## Local validation

19 backend tests; 18 frontend tests; TypeScript; ESLint; production build. Local development migrations reach `b2c3d4e5f6a7`. Tests use a separate `recova_test` database; never use the destructive test fixtures against a deployment.

Local HTTP smoke evidence is separate from visual browser or hosted deployment evidence. The available browser-control runtime failed to initialise; no fresh browser inspection is claimed. The public release URL is still needed. The SSE broker remains process-local; verify events in the actual worker topology.

## Team documents

See `docs/ceo-2026-11-18/` for the pitch, prospective pilot, governance review, narration, release checklist and PDF. No pilot is active. Confirm the demo order and validate the deployed build before recording. CEO approval and competition submission are pending; preparing these documents does not supply either.

Team checkout: fetch origin, then update main in a clean checkout. Preserve or commit local work before switching. Do not force-reset another engineer's changes. Use the installation instructions in README and apply migrations before starting the API.
