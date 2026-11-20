# Sign-in and signup release

This supersedes the 19 November handoff's startup restriction on customer signup. Public registration and protected operator provisioning are now independent.

Verification: 44 backend tests, 47 frontend tests and nine browser checks passed. TypeScript, ESLint and the production build passed. All 37 saved login accounts passed a fresh check. The dev site remains at `http://127.0.0.1:3017`.

## Public addresses

- `/login`: sign in with an existing account. Operator setup status never redirects customers away from this page.
- `/signup`: normal organisation registration. Programme selections from the landing page remain selected.
- `/bootstrap` redirects to `/signup`. The previous `/register-organization` address also redirects to `/signup`, preserving valid programme selections.
- `/operator/setup`: separate, one-time deployment-owner setup. Production still requires the private `BOOTSTRAP_SETUP_TOKEN`. This page is not linked from public navigation.

## Server behaviour

Customers can register a facility before a platform operator exists. Registration always creates an ordinary facility administrator, even if a request supplies extra platform-admin fields. First-operator setup remains protected by its production secret and cannot be repeated after an operator exists.

The internal `needs_bootstrap` status now means that the platform operator has not been provisioned. It does not mean that ordinary users cannot sign in or register. Session loading checks the current session independently, so an unavailable setup-status endpoint does not discard a valid session.

Protected pages send unauthenticated visitors to `/login`. Signed-in patients, supervisors, authority users and other staff retain their respective workspace routes. Private invitation links continue through sign-in before acceptance.

Patient, referral, review and agent workspaces now mount only after the access guard succeeds. This prevents private requests and uncaught authentication errors while redirecting an unauthenticated visitor. Request failures on patient/referral/review lists are handled visibly instead of becoming unhandled promise rejections.

## Deployment

This release changes both backend and frontend. Pull `main`, install dependencies, and rebuild/restart the H2S backend, frontend and worker using the existing VPS deployment procedure. No new database migration is required. Preserve existing database, session and encryption keys. The older frontend-only landing-page deployment instruction is not sufficient for this auth release.

The first operator should be provisioned separately at `/operator/setup`; sign out of any facility account before using it. Keep the setup secret private and clear it after initialization.

## Other checks

`npm install` completed. A compatible `npm audit fix` updated development-tool dependencies without `--force`; the resulting install reported zero vulnerabilities. No runtime dependency advisory was reported before the fix either.

The existing local database instance on port 55432 was stopped and needed PostgreSQL recovery/startup; it was restarted using its original data directory. No account reseeding or database reset was performed. Saved-language restoration was also deferred until after hydration to remove two language-initialization lint errors without suppressing the checks.
