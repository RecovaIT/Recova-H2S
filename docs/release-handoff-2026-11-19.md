# Recova release handoff — 19 November 2026

**Start here:** pull `main`. This release builds on the team's unified programme work (`163f68e`) and VPS deployment work (`6fbd384`). It does not alter the separate production Recova applications or copy their credentials.

## What changed

- **Account access:** staff receive private, expiring password setup links. New patients can create their own password from their facility invitation; existing users retain their password and add the facility. Resend, expiry and wrong-recipient handling are connected. Password recovery gives a private generic response, invalidates older links and revokes sessions after reset. Profile pages support password change and email verification.
- **Email operations:** encrypted PostgreSQL email queue, background sending, retries, expiry checks and an Admin delivery panel. Welcome, verification, setup, password security, care updates and appointment reminders use the queue. `sent` means SMTP accepted the message; it does not prove inbox delivery. No shared default password is emailed.
- **Access and safety:** facility suspension stays within that facility; platform accounts are protected. Patient access to staff event streams is blocked. Supervisors remain aggregate-only even with permission overrides. Clinical sign-off records an actual licence number and decision signature; mismatched patient/referral links and invalid referral transitions are rejected. Urgent check-ins can use the configured emergency exception without resuming routine processing.
- **Patient care:** booking, completion, missed appointments and cancellation update the patient care view. Cancellation preserves history. Reminder generation is idempotent. Signup requires deliberate policy acknowledgement and a separate final confirmation. Synthetic accounts are explicitly excluded from the clinical directory count.
- **Care assignment:** registration no longer labels the person entering a record as its primary clinician. An explicitly assigned practitioner must have an active membership and recorded licence in the facility. Department, insurance and follow-up run references are checked for the correct tenant and patient.
- **Consent at registration:** care, wearable, AI and HIE choices start off. Recording prior participant permission requires a consent record reference; otherwise the participant chooses in their portal.
- **Team work retained:** programme dashboard separation, scoped Authority notices, patient notice acknowledgements, programme approval controls, multi-facility links and PostgreSQL event notifications.

Supervisor login now opens WorkSafe directly. Supervisors use protected department aggregates; individual interventions and clinical actions belong to clinical/occupational-health roles. Legacy permission overrides cannot lift this privacy ceiling.

## CTO / deployment owner — do these next

1. **Secure initial setup first.** The public host responded successfully, but `/api/v1/auth/status` reported `needs_bootstrap: true` during this review. Deploy this release before initializing it. Set a private random `BOOTSTRAP_SETUP_TOKEN` (at least 32 characters), enter it on `/bootstrap`, create the intended operator, then clear the token and restart the backend. Production signup is blocked until initialization finishes. Do not circulate the setup token or put it in frontend build variables.
2. **Deploy and migrate.** Back up the production database. Pull `main`, rebuild backend/frontend/worker using `docs/vps-deployment.md`, and run `alembic upgrade head` against the intended deployment database. Required head: `d4e5f6a7b8c9`. The local preview has been backed up and migrated; that does not migrate the VPS.
3. **Configure the sender on backend and worker.** Set `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM`, `SMTP_USE_TLS`. Port 465 uses implicit TLS; 587 supports STARTTLS. Use `FRONTEND_BASE_URL=https://h2s.recovahq.com`, secure cookies, stable encryption/session keys and the correct database. Keep the worker running: `python -m app.cli worker --concurrency 2`. Unconfigured messages remain visible and require retry or a fresh link after expiry.
4. **Verify the actual release.** With a controlled real inbox, test staff setup, new patient invitation, existing-account acceptance, password reset, a booked appointment and its reminder. Confirm HTTPS, correct dashboard routing, persisted care data, worker health and mail acceptance. Check provider delivery/bounce evidence separately. Do not publish shared administrator credentials.

## Still needs external work

**CTO / integrations owner:** finish channel-wide durable retries and delivery-receipt handling for SMS/WhatsApp/HIE; implement and validate required device OAuth connections; configure and test LLM/provider access. The durable queue in this release covers email. CSV/manual ingestion and adapters must not be presented as live device synchronization. SMTP acceptance does not implement inbox delivery receipts/webhooks.

**Frontend / clinical/product owners:** finish Arabic UI translations and RTL testing across patient journeys; verify clinician credentials, approve consent/emergency policies and arrange the planned pilot. No clinical validation, government approval, partner connectivity or regulatory certification is established by these code tests.

**Evidence:** the accompanying validation folder records exact test/build/browser results. Public health checks prove reachability and database readiness only; production authenticated journeys, backups, restore, provider delivery and load behaviour still need deployment-owner verification.
