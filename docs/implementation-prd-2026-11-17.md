# Recova Unified Platform Product Requirements and Implementation Plan

Version 1.0

Prepared 17 November 2026

Implementation day 17 November 2026

Audience Product lead, engineering team, QA and clinical reviewers

Product owner Team lead to assign at kickoff

Submission target 20 November 2026, as stated in the team roadmap

## 1 Purpose and product decision

We will deliver one Recova platform with one public domain, one account system and one shared backend engine. Each organisation selects one primary programme during onboarding. Its staff receive the dashboard, navigation, participant profiles and workflows for that programme. Participants use a common portal whose content follows their verified facility enrolment.

Population-health coordination will be available across every programme. It supports public-health notices, emergency communication and appropriately scoped population summaries. Recova Loop remains the dedicated screening and care-navigation programme.

Reuse the existing engine and four workspaces. Today's release must prove a complete staff and participant journey, enforce programme boundaries on the server, and explain shared public-health participation during onboarding. Acceptance criteria in this document define completion. Report unresolved criteria at the release checkpoint.

## 2 Sources and decision precedence

S1 is the team's Google Doc, Recova Future Health Digital Innovation Challenge 2026 PRD and Modular Execution Roadmap. It specifies the six-agent engine, four use cases, synthetic scenarios, clinical review, bilingual summaries, FHIR readiness, benchmarks and a 3 to 5 minute demo video.

Source URL

https://docs.google.com/document/d/1LGIhOgmrJj-z3lVWQpB2r5FHokiu8z1ufEUhNAbBAiY/edit?usp=sharing

S2 is the accompanying PDF supplied by the product owner, bearing the same roadmap title. S3 is the reviewed Doctware implementation in Recova-H2S-challenge. S4 is the product owner's clarification on 17 November 2026 establishing single-programme signup, tailored staff and participant experiences, and shared population-health coordination.

S4 updates the interface and onboarding examples in S1 and S2. S3 establishes the implementation starting point. Treat source-document snippets and numerical examples as proposed designs until verified through execution.

| Source topic | Requirement carried forward |
| --- | --- |
| Shared engine | Retain consent, emergency bypass, aggregation, deterministic scoring, clinical synthesis and referral orchestration |
| Four applications | Deliver distinct programme experiences inside one platform |
| Track switcher | Select the programme during onboarding and through authorised enrolment administration |
| Earlier stack proposal | Continue the existing Next.js, FastAPI and PostgreSQL architecture |
| Benchmark examples | Publish executed measurements with case counts and algorithm versions |
| Clinical governance | Preserve human approval, explainability, confidence degradation and consent-aware export |
| Population-health vision | Add shared coordination independently of the Loop programme |

The roadmap's submission date and judging statements are team planning references. The submission owner must verify the current portal requirements and cutoff before submission.

## 3 Vocabulary and product rules

| Term | Meaning |
| --- | --- |
| Recova Engine | The common backend pipeline powering all programmes |
| Primary programme | The single service selected by an organisation at signup |
| Recovery | Relapse prevention and rehabilitation monitoring, retaining the technical key core |
| Loop | Screening and care navigation, using loop |
| Neuro | Cognitive health monitoring, using neuro |
| WorkSafe | Workforce readiness and occupational health, using worksafe |
| Participant | A patient or worker receiving services |
| Enrolment | A participant's relationship with an organisation and authorised programme |
| Active organisation | The organisation under which a staff member is working |
| Active enrolment | The service context under which a participant is viewing their portal |

Required rules

- Each new organisation selects exactly one primary programme.
- Staff accounts receive access through their organisation membership and role.
- A person can hold several organisation memberships under one login.
- Staff navigation follows the active organisation and effective permissions.
- A newly registered participant inherits the facility's primary programme.
- Participant access derives from a verified account link and enrolment.
- Every relevant backend request validates organisation, programme and role scope.
- Shared population-health capability is provisioned for every organisation.
- Programme enrolment, clinical consent and communication preferences have separate records.
- Additional enrolments require an authorised action and audit record.
- Historical records retain the programme context in which they were created.

Use Recova Engine for the technology. Recovery is the proposed relapse-programme display label, subject to product approval. Preserve core internally for compatibility.

## 4 Users and successful outcomes

| User | Main task | Successful outcome |
| --- | --- | --- |
| Facility administrator | Configure the service and team | Understands the programme, invites staff and registers participants |
| Clinician or coordinator | Review signals and follow up | Sees relevant data, signs a care plan and records an outcome |
| Screening coordinator | Own screening follow-up | Tracks a result through referral and verified attendance |
| Occupational health director | Assess worker health | Uses identifiable records within authorised scope |
| Supervisor | Manage workplace readiness | Uses permitted aggregates with small-group suppression |
| Participant | Complete activities and receive care actions | Checks in, sees next steps and acknowledges relevant notices |
| Authority user | Coordinate a population response | Publishes scoped notices and sees permitted aggregate responses |
| Platform administrator | Manage configuration and investigate failures | Works through an explicit, audited administration context |

Participant and authority roles require completed identity and scope controls. Role names alone do not grant record access.

## 5 Scope and priorities

### P0 for implementation today

- Single-programme organisation onboarding with explicit explanations.
- Backend enforcement of organisation, programme and role boundaries.
- Routing to the appropriate staff dashboard or participant home after login.
- Programme-specific navigation and metrics using existing workspaces.
- Participant registration, default enrolment and secure portal invitation.
- A common participant portal with programme-specific activities and care actions.
- A complete Recovery journey through check-in, engine execution, clinical review and verified follow-up.
- A usable input and result path for Loop, Neuro and WorkSafe using existing features.
- A minimum population-health notice flow with scoped publishing, in-app delivery and acknowledgement.
- Consent gates, emergency handling, audit evidence and synthetic demonstrations.
- Migration handling for existing organisations and regression verification.

### P1 before the submission target

- Complete end-to-end demonstrations for all four programmes.
- Arabic clinical-summary and participant-copy review, including right-to-left layout.
- Verified external notification delivery where sandbox credentials are available.
- Shared event transport between API and separate worker processes.
- Authority reporting, delivery summaries and audited additional-enrolment administration.
- Judge walkthrough, README, governance evidence, benchmark report and demo video.

Live Malaffi, Sahatna, insurer and production wearable integrations depend on provisioned access and verified adapter contracts. Expose configuration and delivery states. Use synthetic records and clearly labelled integration statuses in demonstrations.

## 6 Explicit organisation onboarding

Use five steps. Preserve input when moving backwards and prevent duplicate submission.

| Step | Information and behaviour |
| --- | --- |
| Organisation | Name, type, location and administrator details |
| Programme | Four mutually exclusive cards explaining audience, inputs, daily tasks and outputs |
| Service setup | Relevant configuration and a preview of the staff and participant experience |
| Participation and permissions | Explain shared public-health coordination, channels, data use and choices |
| Review and create | Show the selected programme and choices before final submission |

Programme descriptions must explain the service clearly.

- Recovery supports recovery check-ins, wearable observations, early-warning review and rehabilitation follow-up.
- Loop supports screening records, referral ownership, insurance-aware navigation and consultation follow-up.
- Neuro supports repeated cognitive activities, sensory and practice context, and reviewed longitudinal changes.
- WorkSafe supports short readiness checks, workplace context, heat/fatigue monitoring and occupational-health response.

The participation step explains who can send public-health notices, how audiences are selected, what acknowledgement records, and which external channels or sharing choices apply. Store the version of the information notice and consent wording shown.

Acceptance criteria

- ONB01 Selecting another programme replaces the earlier selection.
- ONB02 The signup API rejects missing, unknown or multiple primary programmes.
- ONB03 Programme-specific service setup follows the current selection.
- ONB04 Common fields persist when navigating backwards.
- ONB05 Organisation, primary programme, initial membership and shared capability are created atomically.
- ONB06 Repeated submission cannot create duplicate organisations or invitations.
- ONB07 Failure preserves input and shows a recoverable error.
- ONB08 Record actor, timestamp, policy version and choices.
- ONB09 The completion screen identifies the service and first setup action.

## 7 Login routing and navigation

Retain a single login screen. Resolve the destination from authenticated context.

| State | Destination |
| --- | --- |
| Participant with one active enrolment | Participant home for that enrolment |
| Participant with several authorised enrolments | Enrolment chooser with facility and programme labels |
| Staff with one organisation | That organisation's programme dashboard |
| Staff with several organisations | Last valid organisation or organisation chooser |
| Authority user | Authority workspace within assigned scope |
| Legacy organisation awaiting configuration | Programme-selection task for its administrator |
| Account without active access | Clear membership/invitation state and next action |

Accounts with several capacities, such as staff and participant access, use an explicit context chooser. Remember the last valid context and keep each context scoped to its assigned records.

The staff dashboard can remain /dashboard. Server-authorised configuration determines its contents. Proposed participant routes live under /portal and authority routes under /authority. Organisation switching clears stale records and subscriptions before loading the new scope.

Use Recova's Montserrat typography, navy and recovery mint, quiet borders and responsive spacing. Preserve desktop hover and keyboard-focus sidebar expansion. The participant portal uses simple mobile navigation for home, activities, care and notices.

Acceptance criteria

- NAV01 A Recovery facility sees Recovery actions and relevant metrics.
- NAV02 Modified URLs or track parameters cannot grant unauthorised access.
- NAV03 Participants land in their service portal.
- NAV04 Organisation switching updates scope while preserving the person's account.
- NAV05 Backend and session failures show a retry action and meaningful state.
- NAV06 At a 390 pixel viewport, tasks remain usable without page-wide horizontal scrolling.
- NAV07 Focus, selection, loading, error and empty states remain visible.

## 8 Staff dashboards and participant profiles

Shared pages include participants, reviews, follow-up, notices and settings where permitted. Engine inspection and benchmarking are available to authorised staff and the judge demonstration context.

| Programme | Staff dashboard | Participant profile |
| --- | --- | --- |
| Recovery | Check-in completion, early warnings, clinical review, rehabilitation referrals and verified follow-up | Recovery context, sleep/HRV/heart rate, mood or craving inputs, reflections, consent and care plan |
| Loop | Screening status, abnormal results, referral owner, consultation deadline and missed follow-up | Dated results with units, insurance/network context, assigned clinic, bookings and outcomes |
| Neuro | Activity completion, cognitive results, baseline readiness and review queue | Sequence, reaction-time, rule-switch and recall results, session history and sensory/language/education context |
| WorkSafe | Readiness completion, heat/fatigue indicators, interventions and department summaries | Shift/worksite context, readiness, environmental and authorised physiological observations, intervention history |

Counts must reflect the active organisation and programme. Missing observations remain visibly missing. Supervisors receive aggregate WorkSafe views with the configured suppression rule. Occupational-health staff use their authorised individual workflow.

## 9 Participant registration and secure account linking

Collect common identity, contact and service fields, followed by programme-specific fields. Preselect and explain the primary programme. Identify the facility and service in the invitation.

1. Authorised staff create the participant and enrolment.
2. Issue a single-use, expiring invitation.
3. The recipient establishes or signs into an account.
4. The server verifies and links the intended participant record.
5. The participant reviews information and consent choices.
6. The portal displays the active service and assigned actions.

Email matching alone cannot establish record access. Store invitation tokens as hashes, bind them to purpose and recipient, and invalidate them after acceptance or replacement. Repeated acceptance is idempotent. Account recovery preserves the verified link.

Acceptance criteria

- PAT01 Registration creates the organisation-scoped primary enrolment.
- PAT02 A portal account accesses only linked records and authorised services.
- PAT03 Expired, used, altered and wrong-recipient invitations fail safely.
- PAT04 Matching names or emails across facilities never silently merge records.
- PAT05 Participants see the active facility, programme and care contact.
- PAT06 Service selection appears only for granted enrolments.
- PAT07 Historical records remain distinguishable by programme.

## 10 Shared participant portal

The home screen presents the service, next task, recent submissions, care actions and notices. Use everyday language. Release clinical results under the organisation's review policy.

| Programme | Participant action | Visible result |
| --- | --- | --- |
| Recovery | Daily reflection, relevant symptoms and optional voice dictation | Submission receipt, approved care instructions and follow-up status |
| Loop | View screening progress and complete assigned follow-up information | Referral owner, appointment details and outstanding actions |
| Neuro | Complete an assigned accessible cognitive activity | Completion receipt and clinician-released results |
| WorkSafe | Complete the short readiness interaction before a shift | Receipt and authorised instructions or follow-up |

Reuse current cognitive and check-in logic through participant-scoped APIs. The roadmap's WorkSafe target is an approximately ten-second interaction. Measure completion time in usability checks.

Derive participant identity from the authenticated account. Validate the active enrolment and consent on the server. A client-supplied patient identifier cannot establish authority.

Acceptance criteria

- POR01 Recovery submissions appear in the intended clinician workspace.
- POR02 Neuro results include participant, enrolment, task version and observations.
- POR03 WorkSafe responses retain the intended shift and worksite context.
- POR04 Participant activity cannot grant clinical, administrative or supervisor access.
- POR05 Retries produce one activity and the intended single pipeline request.
- POR06 Acknowledgement, provider delivery and clinical outcome remain separate states.
- POR07 Emergency responses show approved escalation instructions immediately.

## 11 Shared engine and clinical workflow

| Stage | Required behaviour |
| --- | --- |
| Consent and guardrails | Validate scope, input schema and missing streams before routine processing |
| Emergency bypass | Detect approved red flags deterministically, bypass routine analysis and create a traceable escalation |
| Signal aggregation | Gather available longitudinal observations with source and time context |
| Deterministic scoring | Apply the versioned baseline, drift, confounder and programme configuration |
| Clinical synthesis | Use validated structured output, authorised inputs and bilingual review where enabled |
| Care orchestration | Propose the appropriate pathway and retain referral ownership through verified outcome |

Retain the roadmap's separation between deterministic risk calculation and LLM explanation. An LLM cannot change the calculated risk tier. Missing data reduces confidence and insufficient baseline data produces the appropriate indeterminate state. External synthesis must report its actual provider/configuration state.

The roadmap describes personal baselines from initial stable observation windows, drift thresholds around 1.0 and 1.96, practice adjustments and sensory confounders. A clinical reviewer must approve the algorithm definition and direction-specific rules. The Python and TypeScript branches currently use different standard-error formulas. Adopt one versioned specification and reconcile numerical fixtures before claiming equivalent results. Never hardcode an example Z-score or confidence percentage to satisfy a demo.

Routine referrals follow proposed, clinician approved, notified, booked, consultation completed and outcome verified states, with missed/escalated paths. Record actor, time and evidence for transitions. A delivered message cannot establish attendance or a verified clinical outcome. Emergency actions follow the separately approved emergency protocol.

## 12 Shared population-health coordination

Provision this capability for every organisation. Include its purpose in onboarding. Facilities configure location, responsible contact and permitted channels.

An authorised authority user creates a draft notice, selects severity and audience, previews the audience count and message, then publishes within assigned scope. Recipients see the notice in the existing platform and acknowledge it where requested. Publishers receive permitted delivery and acknowledgement summaries.

Notice fields include title, message, plain-language action, issuer, category, severity, geographic/facility scope, eligible programmes, start/expiry time, acknowledgement requirement, publication version and audit metadata.

Use draft, published, expired and withdrawn states. Recipient states are available, read and acknowledged. Provider delivery has its own state. Published edits produce a version and audit event.

P0 targeting uses assigned facilities and geography. Targeting by identifiable health characteristics requires an explicit purpose and permission design. Assign authority scope through administration. Population reports enforce permitted aggregation and the configured small-group suppression threshold.

Acceptance criteria

- POP01 Every organisation receives the capability and onboarding explanation.
- POP02 Issuers publish only inside assigned scope.
- POP03 Draft preview shows the audience and count before publication.
- POP04 Out-of-scope recipients cannot retrieve a notice by changing its identifier.
- POP05 Read and acknowledgement records belong to the authenticated recipient.
- POP06 Expired and withdrawn notices expose their current status.
- POP07 Reports apply suppression and exclude unauthorised clinical detail.
- POP08 Optional external channels use valid preferences and configured adapters.
- POP09 Publish, revision, withdrawal and acknowledgement actions are audited.

## 13 Consent and information governance

Maintain separate decisions for routine service processing, wearable ingestion, external synthesis, family notifications, external health-information exchange and optional channels where applicable. Store scope, status, policy version, actor, authority to act, effective time and revocation time.

Apply the latest valid decision at execution time. Queued tasks recheck relevant permission and consent before dispatch. The current synthesis code treats general processing consent as sufficient unless LLM synthesis was revoked. The explicit onboarding model should require a recorded grant of the relevant external-synthesis scope.

Product and clinical leads must approve participation wording and emergency communication scope before live use. Synthetic recipients and in-app notices can demonstrate the flow while external access is being provisioned.

## 14 Data model and migration

The following are proposed schema changes. Match names to existing conventions and use Alembic.

| Entity | Required change |
| --- | --- |
| Organisation | Add primary_programme and programme_configuration_status |
| Membership | Retain organisation role and effective access rules |
| Track enrolment | Retain programme/service state and record authority/history for changes |
| Participant account link | Link verified user, participant and organisation context |
| Portal invitation | Hashed token, expiry, purpose, recipient binding and acceptance state |
| Consent | Add policy version and missing scope metadata |
| Authority scope | Assigned geography/facilities and publishing/reporting permissions |
| Public-health notice | Content, scope, state, version and expiry |
| Notice recipient | Scoped recipient and read/acknowledgement times |
| Audit | Programme configuration, enrolment, invitation and notice events |

Migration rules

- Preserve existing participant, enrolment and engine-run identifiers.
- Backfill single-track organisations to that primary programme.
- Mark multi-track organisations as requiring administrator selection. Preserve their records and controlled legacy care access during resolution.
- Keep primary_programme separate from enabled_tracks during transition.
- New signup enforces one programme. Authorised administrators resolve legacy configuration through a dedicated task.
- Re-run migrations and backfills safely. Record configuration changes.
- Before changing access, create a backup and exercise restore in staging. Use a feature flag for routing rollout so the previous compatible experience can be restored if verification fails.
- Preserve records added after rollout when reverting the feature flag. Schema rollback requires an explicit data-preservation plan.

## 15 API contracts

These routes are proposed contracts. Reuse current service logic and response types where they preserve the required behaviour.

| Contract | Requirement |
| --- | --- |
| POST /api/v1/auth/register-organization | Accept one primary programme and create organisation/membership atomically |
| GET /api/v1/auth/me | Return active organisation, role, primary programme, capability flags and participant service contexts |
| GET /api/v1/portal/me | Return the authenticated participant's authorised enrolments |
| POST /api/v1/portal/check-ins | Derive identity and validate enrolment before saving |
| POST /api/v1/portal/cognitive-sessions | Save assigned activity observations for the authenticated participant |
| GET /api/v1/portal/care | Return released instructions, appointments and follow-up states |
| POST /api/v1/patients/{id}/portal-invitations | Issue an authorised, recipient-bound invitation |
| GET /api/v1/notices | Return notices visible to the authenticated scope |
| POST /api/v1/authority/notices | Create a draft inside assigned authority scope |
| POST /api/v1/authority/notices/{id}/publish | Validate audience and permission, then publish the intended version |
| POST /api/v1/notices/{id}/acknowledgements | Record authenticated acknowledgement idempotently |

Mutations retain CSRF protection for cookie sessions, organisation checks and audit metadata. Return consistent errors for invalid programme, missing enrolment, expired invitation and unavailable integration. Idempotency keys cover retriable creation, activity submission and notice publication. Enforce uniqueness in the database as well as the service layer.

## 16 Verification and judge demonstration

Use a resettable synthetic demo organisation per programme and linked synthetic participants. A judge must be able to open stable, gradual-decline, missing-data, emergency and absent-consent cases, inspect the trace and follow an approved referral.

The benchmark runner deletes its temporary fixture patients. Create persistent judge fixtures through a separate seed/reset process. Preserve benchmark isolation and exclude demo records from live reporting.

| Test | Evidence required |
| --- | --- |
| Signup and routing | All four selections, invalid/multiple API values and correct landing pages |
| Staff scope | Direct route/API attempts across programmes and organisations |
| Participant isolation | Two accounts tested against each other's records |
| Invitation lifecycle | Correct, expired, replaced, used and altered tokens |
| Recovery vertical | Portal check-in through review and verified follow-up |
| Loop vertical | Screening through referral ownership and follow-up evidence |
| Neuro vertical | Saved activity, sensory/practice context and versioned result |
| WorkSafe vertical | Short check-in, appropriate response and suppressed supervisor view |
| Consent | Absent, granted, revoked and revocation during queued execution |
| Emergency | Approved fixture bypass and persisted escalation |
| Public-health notice | Scope, preview, publish, visibility, expiry and acknowledgement |
| Legacy migration | Single-track and ambiguous organisations retain records |
| Live graph | API plus separate worker with traceable persisted steps |
| Failure recovery | API outage, missing provider, duplicate submit and expired session |
| Responsive and language | Staff/portal tasks at mobile and desktop sizes, Arabic review where enabled |

Historical audit results were 14 passing backend tests, 15 passing synthetic benchmark cases and 10 passing frontend tests. Re-run verification after these changes. Display sensitivity, specificity, emergency detection, missing-data handling and scoring consistency from executed cases with denominators, suite version and algorithm version. A perfect score on authored fixtures describes that fixture set.

The demo video should introduce the engine, show programme-specific onboarding, complete one participant-to-clinician care loop, demonstrate an emergency bypass, show the other programme inputs, and finish with measured benchmarks and a scoped public-health notice. Target the roadmap's 3 to 5 minute duration.

## 17 Implementation plan for today

Use elapsed hours from kickoff on 17 November in Africa Lagos time. Assign named owners at kickoff. Roles below describe accountability, allowing one person to cover more than one area if staffing requires it. Adjust timing to actual capacity and record unfinished work.

| Window | Work and dependencies | Owner role | Exit evidence |
| --- | --- | --- | --- |
| Hour 0 to 1 | Confirm rules, labels, consent wording, role matrix and API contracts | Product lead and clinical reviewer | Decision log and assigned tickets |
| Hour 1 to 3 | Organisation schema, legacy migration and backend scope checks | Backend lead | Signup validation and migration fixtures passing |
| Hour 1 to 4 | Five-step onboarding and programme-driven staff UI | Frontend lead | Four signup paths exercised against the contract |
| Hour 2 to 5 | Account links, invitations and participant APIs | Backend owner | Invitation and cross-account access checks |
| Hour 3 to 6 | Portal home, Recovery check-in and tailored programme views | Frontend owner | Participant submission visible to intended staff |
| Hour 3 to 6 | In-app authority notice and acknowledgement | Assigned backend/frontend owners | Scoped synthetic notice journey |
| Hour 5 to 7 | Recovery care loop and existing Loop/Neuro/WorkSafe inputs | Programme owners and reviewer | Recorded vertical demonstrations |
| Hour 6 to 8 | Integrate, verify, seed staging and exercise deployment | QA and release owner | Acceptance matrix and unresolved issues |
| Final checkpoint | Freeze the verified build and assign remaining work | Product and release leads | Release decision and demo plan |

Critical dependency chain is organisation context, server scope, verified account linking, participant submission, engine execution, clinical review and follow-up. Staff UI, notice UI and demo preparation can progress against agreed contracts while backend work proceeds.

If capacity is constrained, establish programme scope and participant isolation first, then complete Recovery and the in-app notice journey. Record the other verticals as incomplete until their acceptance evidence exists. Use 18 and 19 November for remaining work and submission preparation, subject to the verified portal cutoff.

## 18 Decision log and definition of done

| Decision | Proposed default | Decision owner |
| --- | --- | --- |
| Programme ownership | One primary programme per organisation | Product lead |
| Relapse display label | Recovery with core retained internally | Product lead |
| Additional enrolments | Authorised administration with audited history | Product/backend leads |
| Legacy multi-track state | Administrator selection with preserved care access | Product/release leads |
| External synthesis | Explicit recorded consent grant | Product/clinical reviewers |
| Emergency consent exception | Approved versioned rule before live use | Clinical/governance reviewers |
| Authority scope | Assigned geography and facilities | Product/backend leads |
| Suppression threshold | Existing validated WorkSafe setting reviewed for authority reports | Clinical/backend leads |
| Initial communication channels | In-app delivery and available sandbox adapters | Release owner |
| Scoring specification | Current Python runtime pending approved reconciliation | Clinical/engineering leads |

Release completion checklist

- Each P0 requirement has an owner, status and evidence link.
- Signup selects one programme and explains shared participation.
- Staff and participant logins resolve to their authorised experience.
- Profiles and activities match the service provided.
- Recovery has a demonstrated complete care loop.
- Each other programme has its actual completion status recorded.
- The scoped notice flow has evidence or is recorded as unfinished.
- Consent, tenant isolation, participant isolation and role checks pass.
- Migration preserves historical records and handles ambiguity explicitly.
- Benchmarks reflect executed cases.
- The frontend, API and separate worker configuration are exercised together.
- The judge walkthrough explains the shared engine and distinct services.
- Outstanding work and external dependencies have named owners.

## 19 Repository implementation map

| Area | Existing location or proposed addition |
| --- | --- |
| Organisation onboarding | frontend/src/components/OrganizationOnboardingCard.tsx |
| Authentication context | frontend/src/hooks/useAuth.tsx |
| Staff shell/navigation | frontend/src/components/AppShell.tsx and AppSidebar.tsx |
| Dashboard | frontend/src/app/dashboard/page.tsx |
| Participant creation | frontend/src/components/PatientQuickCreateModal.tsx |
| Recovery workspace | frontend/src/features/core/CoreWorkspace.tsx |
| Loop workspace | frontend/src/features/loop/LoopWorkspace.tsx |
| Neuro activity | frontend/src/features/neuro/NeuroActivityGame.tsx |
| WorkSafe workspace | frontend/src/features/worksafe/WorkSafeWorkspace.tsx |
| Participant routes | Proposed frontend/src/app/portal |
| Authority routes | Proposed frontend/src/app/authority |
| Permissions/context | backend/app/core/permissions.py and backend/app/api/deps.py |
| Identity/organisation services | backend/app/services/auth.py and organizations.py |
| Patient/signal services | backend/app/services/patients.py and signals.py |
| Shared engine | backend/app/agents/orchestrator.py and backend/app/engine |
| Clinical follow-up | backend/app/services/care.py |
| Queue/events | backend/app/tasks and backend/app/core/events.py |
| Schema migrations | backend/migrations/versions |
| Benchmarks | backend/app/benchmarks |
| Integrations | backend/app/integrations |

Keep changes within the existing architecture. Record schema and API changes alongside acceptance evidence so another team member can verify the complete workflow.
