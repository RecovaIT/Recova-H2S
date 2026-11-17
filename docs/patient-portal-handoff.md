# Patient portal implementation handoff

## Running the portal

The patient application is at /portal on the existing frontend, using the existing login. Both the login submission and the root redirect send patient memberships to /portal. Staff routing remains role based. Keep the frontend at http://127.0.0.1:3017 and the backend at http://127.0.0.1:8017 for the supplied local account sheet.

## Delivered patient experience

- Four enrolment-driven homes for Recovery, Loop, Brain Health and WorkSafe.
- Mobile bottom navigation with safe-area padding and large touch controls.
- Daily reflections and worker readiness inputs, persisted to patient-scoped check-ins and observations and passed to the shared engine.
- Health signal cards, timestamps and seven-observation charts.
- Wearable CSV ingestion with explicit permissions, metric/unit validation and idempotency. Imported readings enter the shared engine.
- Loop screening values from the facility record.
- A visual memory practice activity with persisted raw responses and server-derived correctness.
- Approved referral status, synthetic demo care steps and facility context.
- Demo public-health notices with authenticated, idempotent acknowledgement.
- Privacy controls and sign-out.

## Scope for the CTO

The additive backend module is app/api/v1/portal.py, registered by api/v1/router.py. It uses the existing Patient.portal_user_id unique foreign key. Every request requires portal:self, resolves the active organisation, and looks up the linked patient and active enrolment on the server. Inputs reject extra identity fields. The module does not grant staff permissions to participant accounts.

Routes are GET /portal/me and POST /portal/check-ins, /portal/activities, /portal/consents, /portal/wearable-import and /portal/notices/acknowledge under /api/v1. Cookie-authenticated mutations use the existing CSRF dependency.

The patient needs a staff-provisioned portal_user_id and an active patient membership/enrolment. Existing fixture seeding supplies this linkage for demonstration. Invitation and identity-verification provisioning for live patients remains with the backend/onboarding workstream.

Agent 5 now requires both data_processing and llm_synthesis grants. Its existing check for revocation remains. The clinical pipeline regression expectation has been updated accordingly. Preserve this explicit opt-in when merging the backend work.

## Demonstration data

Run from backend with ./.venv/Scripts/python -m scripts.seed_portal_demo. The script refuses production mode, retains existing account passwords on normal reruns, and creates four separate synthetic organisations with 30 participant users. It adds labelled scenario fixtures without erasing user submissions.

The credential sheet is output/portal-test-accounts.csv in the parent Recova workspace, outside the repository. It contains a unique generated password for each account. Keep this local demonstration credential sheet separate from source control and production identity data.

| Programme | Accounts | Scenario coverage |
| --- | --- | --- |
| Recovery | 8 | Stable, sleep decline, missed check-ins, disconnected wearable, pending consent, urgent support, booked follow-up, first day |
| Loop | 8 | Routine screening, abnormal result follow-up, booked visit, missed visit, missing results, pending consent, new referral, notice |
| Brain Health | 7 | First activity, established history, hearing/vision context, repeat activity, missing sleep, review pending |
| WorkSafe | 7 | Ready for shift, fatigue, hot worksite, missing wearable, night shift, return to work, notice |

Synthetic patient records remain marked is_synthetic and retain the existing exclusion from routine clinical participant lists. These fixtures exercise the patient application. They are separate from the benchmark runner's temporary cases and from live patient reporting. Scenario labels describe the fixture being demonstrated and do not establish a clinically validated outcome.

## Wearables and remaining integration dependencies

The CSV header is metric,value,unit,at. Supported metrics are sleep_hours, hrv_rmssd, resting_hr and steps. Use timezone-aware ISO timestamps. The server normalises compatible units and rejects unsupported or out-of-range values. The UI accepts up to 500 readings in a file under 1 MB and can download a clearly labelled synthetic example. File-content hashes make repeat uploads use the same request identifier.

Apple Health, Fitbit and Garmin direct connections are visibly unavailable until configured. OAuth callback/token refresh, provider webhooks, Apple native HealthKit or a supported export bridge, device identity, and source-specific verification belong to the provider integration workstream. No direct device authorisation is simulated by the portal.

The Neuro activity is a visual practice session. It is stored with status practice and its own activity version, and does not write observations into the clinical battery's baseline. The full clinical multi-task assessment and validated interpretation remain in the Neuro workstream.

For this demo, enrolment context stores seeded care cards, notices and acknowledgements. Replace those fixture fields with the approved care/authority service contracts when the corresponding backend work lands. Released referrals already read from the clinical referral table. Public-health publishing and live scheduling are separate workstreams.

## Verification

The portal regression tests cover patient identity isolation, rejecting client identity overrides, staff endpoint denial, unit conversion, invalid-unit rejection, duplicate imports, consent revocation, check-in persistence and single execution, explicit synthesis consent, programme-scoped activities and server-derived practice correctness.

All 30 seeded accounts were verified through the application's login and /portal/me endpoints. The existing backend and frontend suites and production build were also exercised during implementation. Browser automation failed to initialise in this session, so a visual desktop/mobile walkthrough remains a manual release check.

## Manual acceptance walkthrough

1. Sign in with one account from each programme and verify the correct title, facility, activities and content.
2. Submit a Recovery reflection and confirm it persists after refresh. Inspect the linked engine run.
3. Open a pending-consent account, grant care-data permission and verify submission becomes available.
4. Import an example wearable file, inspect readings and timestamps, then re-import it and verify duplicate prevention.
5. Revoke wearable permission and confirm further imports are refused.
6. Open a Loop follow-up account and inspect its screening snapshot and care state.
7. Complete a Brain Health practice sequence and inspect the stored raw responses.
8. Submit WorkSafe readiness and inspect its readiness_score observation.
9. Acknowledge a notice, refresh and verify the saved state.
10. Test at 390 pixel and desktop widths, including long care text, error messages, consent choices and keyboard focus.
