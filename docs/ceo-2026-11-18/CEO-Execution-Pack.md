# CEO execution pack
Future Health Digital Innovation Challenge | 18 November 2026

Decision today: prepare for submission from main; final submission approval remains open until the deployed build and video are verified. This pack does not certify clinical safety or provide CEO sign-off on your behalf.

| Task | Completed work / remaining condition |
| --- | --- |
| 1.1 Registration | Hack2skill confirmation received 26 October; CEO confirms the required competition members are already registered. Save the confirmation screenshot in the private team folder and share it with the registered team. No re-registration is needed. |
| 1.11 Pitch | One-page pitch prepared, mapped to all six pillars. Team acknowledgement and demo-order agreement remain to be recorded. |
| 2.x Pilot path | Half-page prospective pilot plan prepared. No pilot, clinic partner or commercial commitment is claimed. |
| 4.5 Governance review | Claim review and replacement wording prepared. Engineering and clinical owners must close or disclose the listed findings. |
| 4.8 Demo presentation | Timed narration and operator plan prepared. Final recording requires a verified deployed build, rehearsal and CEO narration. |
| 4.9 Final sign-off | Release checklist prepared. Approval and actual submission are not yet recorded. |

Release instruction from CEO: submit main, integrating work from the other branches. Doctware (5f16ec2) is already an ancestor of abdul-h2s (4acc152). The separate feat/brain history (da21bab) is preserved under legacy/brain so its older standalone scaffold does not replace the current frontend/backend application. Record the final main SHA in the submission.

Timing: the organiser's 17 November reminder states a 20 November prototype deadline. It requests a working prototype link or repository/build, a concise demo video, and technical documentation describing architecture, datasets, assumptions and limitations. The exact cutoff hour/timezone was not established from the inspected messages; verify it in the submission portal. Aim for the evening of 19 November internally, leaving 20 November as a buffer.

No team email, competition submission or externally binding approval has been sent by preparing this pack. The companion email text is ready for you to send after adding the verified release URL and attachments.


---

# Recova | One engine, four care programmes
CEO pitch | Future Health Digital Innovation Challenge | 18 November 2026

One shared Recova Engine runs six gated stages: consent, emergency screening, aggregation, deterministic scoring, optional AI explanation and referral orchestration.
Four programme experiences support relapse prevention (Core), population-health follow-up (Loop / IFHAS), cognitive wellness (Neuro) and workforce wellbeing (WorkSafe), with enrolment-led access on one platform.

| Judging pillar | What Recova does and where to show it |
| --- | --- |
| Health Impact | Recova connects concerning changes to clinician review and tracked follow-up; show Core patient detail, Clinical Review and Referrals, without claiming proven improvements in patient outcomes. |
| Technical Depth | Six gated stages keep emergency checks and deterministic risk calculations separate from optional generative explanation; show Agents, the Agent 4 signal matrix and the separate Agent 5 provider status or draft. |
| Working Solution | Programme-specific staff experiences and a mobile patient portal use a shared API and database; show onboarding, a selected programme workspace, and a patient check-in saved through /portal. |
| Responsible AI | Consent gates, visible data limitations and clinician review constrain routine processing and AI drafts; show patient consent, blocked processing and the review decision record. |
| Scalability | Organisation-scoped access and shared services support multiple care programmes, with an integration path through FHIR-oriented exports; show tenant roles and the FHIR structural validator, without claiming certified interoperability. |
| Commercial Viability | A clinic-led future feasibility pilot will test whether flags lead to completed follow-up before commercial expansion; show the proposed pilot plan and distinguish intended buyers from contracted customers. |

Proposed demo order: Case D crisis bypass (BM-CORE-04), Case B drift (BM-CORE-02), Neuro presbycusis (BM-NEURO-02), then Benchmarks. Asiyah and the team must confirm this order during rehearsal.

Release basis: main integrates Doctware and abdul-h2s; the earlier brain prototype is retained as historical reference. Show only features verified in the submitted deployment. Device-provider connections, government integration and clinical effectiveness are not demonstrated by local tests. Synthetic benchmark results are engineering checks, not clinical validation.


---

# Proposed future pilot | Recovery follow-up
Submission-ready commercial outline | Planning assumptions, not an active pilot

Recova has no active pilot. After the competition, seek one outpatient or rehabilitation clinic with an existing Recovery cohort. Clinics are intended B2B purchasers; B2G expansion could later involve a health authority such as ADPHC. No partner, endorsement or sale is confirmed.

Start only after securing a clinical lead, follow-up coordinator, appropriate approvals, privacy review, data agreement and budget. Plan two to four weeks for readiness after a partner agrees; approvals may take longer. Then consider an eight-week feasibility window for up to 20 consenting adults: one week of setup, five of enrolment/monitoring, two of follow-up reconciliation. These are adjustable planning assumptions.

Primary measure: participants completing documented clinician-approved follow-up within 14 calendar days of their first qualifying routine flag, divided by participants whose first flag has a complete 14-day observation window. Count each once; show missed, unknown, withdrawn and immature-window cases separately. Emergencies follow the clinic's immediate safety protocol and are reviewed separately.

Use synthetic rehearsal first. Proceed only when consent/security checks pass and staff can manage alerts. Review safety, workload and completion before extending. This assesses workflow feasibility, not clinical efficacy. No price, market size, savings or outcome target is asserted; funding and pricing require partner discovery.


---

# Governance review | Claims and release actions
Reviewed: docs/clinical-governance.md and relevant source on the integrated release

| Priority / finding | Evidence and required wording or action |
| --- | --- |
| High: HIE consent | Review found a historical-revocation check that did not require an active grant. Integration now uses the shared effective-consent evaluator. Regression checks cover absent, future, expired, revoked and re-granted consent for export/push. Still verify external integration and cross-tenant deployment behaviour before making wider claims. |
| High: live graph | Frontend event subscriptions did not match backend agent.step_started, agent.step_finished, pipeline.finished and pipeline.emergency_bypass. Integration corrects these names. The bus remains in-process; a separate worker/API topology needs shared transport or a verified persisted-state refresh. Do not claim live cross-process streaming until tested. |
| High: review credentials | Clinical review records a reviewer identity, optional licence field and SHA-256 hash. Say audit-linked review record. A payload hash does not establish verified professional licensing, a certified digital signature or tamper-proof storage. |
| High: compliance | Engineering rules express UAE compliance and sovereignty requirements. They are requirements, not certification evidence. Say designed with consent and role controls; deployment location, encryption coverage, logs, backups and applicable approvals require independent review before patient use. |
| Medium: FHIR | Say FHIR R4-oriented bundle builder with local structural/reference checks. Do not say standards-compliant or Malaffi-ready without official profile validation, terminology validation and destination acceptance. Identifiers supplied by an operator do not prove regional-system connectivity. |
| Medium: delivery | Say provider accepted when an external API accepts a request. Acceptance is not delivery, patient read or a clinical outcome; retain separate provider callbacks, read acknowledgements and human outcome records. |
| Medium: model claims | Six gated workflow stages include deterministic processing plus optional LLM synthesis. Do not imply six independent LLMs. If the provider is absent, show not configured. Bilingual schema fields alone do not demonstrate Arabic clinical quality. |
| Medium: effectiveness | Synthetic benchmark pass rates are fixture agreement only. Do not claim relapse prediction lead time, reduced relapse rates, validated diagnostic accuracy or measured time savings without an appropriate study. |
| Medium: devices and programmes | File-based wearable imports are implemented; direct provider integrations require configuration and verification. Patient memory sessions are practice. Authority-notice code is not evidence of government adoption or production operation. |

Suggested replacement introduction: Recova implements a prototype of consent-gated processing, deterministic risk analysis, optional AI drafting, role-scoped access and clinician review. These controls support evaluation; they do not establish regulatory compliance, validated clinical effectiveness or certified interoperability.

Preserve accurate details: Agent 5 must not change deterministic risk or approve care. A referral notification is not a completed consultation. A completed consultation is not a verified improvement. Keep missing-data explanations visible and require responsible clinical staff to confirm emergency workflows.

Proposed owners: Asiyah coordinates claim wording and evidence; CTO/backend owner validates consent, tenant isolation, credentials, integrations and deployment; frontend owners validate live state, mobile access and Arabic presentation; CEO approves only the supported final narrative. These are requested handoffs, not confirmations that owners have accepted them.


---

# Demo runbook | Proposed 4-minute presentation
CEO narration draft. Rehearse against the deployed main build before recording.

## 0:00-0:20 | Open on the selected programme dashboard
Narration: Recova is one shared engine with four programme experiences: relapse prevention, population-health follow-up, cognitive wellness and workforce wellbeing. A facility selects its programme during onboarding; patients use a mobile portal shaped by their enrolment. Today we will demonstrate synthetic cases and explain exactly where our prototype ends.

Operator: show the release URL and selected organisation/programme. Use clearly labelled synthetic demonstration records; never imply that they are real patients.

## 0:20-1:00 | Case D: safety before routine scoring
Narration: First, this synthetic crisis case tests the emergency gate. The engine is designed to identify configured acute warning signals before continuing routine analysis. Here we inspect the recorded gate result and the urgent event presented to the clinical team. This is decision support: the clinical service must own and verify its emergency response. Recova does not replace emergency care or guarantee response time.

Operator: BM-CORE-04 or its prepared persistent synthetic equivalent. Show Gate 2, resulting run state and emergency record. Do not promise a live animated sequence unless the actual deployment passes that check.

## 1:00-1:45 | Case B: change from the patient's baseline
Narration: This second case shows a change against an individual baseline. The deterministic signal matrix exposes the observations and scoring trace so a clinician can inspect what contributed to the result. Missing streams and confounders matter. The separate AI explanation is an optional draft, subject to consent and provider configuration; it cannot change the deterministic score or approve a referral. If the provider is unavailable, we show that honestly.

Operator: BM-CORE-02 or prepared equivalent. Show baseline, score, completeness, limitations, then the separate Agent 5 status and review action.

## 1:45-2:20 | Neuro: context changes interpretation
Narration: In this synthetic presbycusis case, hearing context must be considered when interpreting cognitive performance. Show the configured confounder in the trace and the resulting limitation. This is cognitive wellness support, not a dementia diagnosis. The patient memory exercise is practice and should not be presented as a validated clinical assessment.

Operator: BM-NEURO-02 or prepared equivalent. Confirm the current fixture's expected result before recording; do not invent results or claim untested modality safeguards.

## 2:20-2:55 | Patient check-in and follow-up
Narration: The patient experience is designed for mobile use. A patient sees their programme, records a check-in, manages permissions and can review follow-up information. In this demonstration we save an action to the backend and show that it survives refresh. Wearable data can be imported from supported files; direct device-provider connections remain dependent on real integrations.

Operator: patient-scoped account in a separate session, narrow viewport, submit check-in, refresh. Return to staff view and show its stored record. Never expose shared demo passwords in the video.

## 2:55-3:35 | Benchmarks and honest boundaries
Narration: Our benchmark screen makes authored engineering scenarios visible. We show the suite version, actual run results and any failures. Passing these synthetic checks tells us the implementation matches those expected scenarios; it does not establish clinical accuracy, prevention effectiveness or real-world safety. Our documentation records data assumptions, provider dependencies and deployment limitations.

Operator: run the actual available suite and show timestamp and counts. Benchmark fixtures may be ephemeral; prepare separate persistent demo records rather than expecting benchmark patients to remain in the patient list.

## 3:35-4:00 | Commercial path and close
Narration: After the competition, our next step is a clinic-led feasibility pilot once a partner, approvals and clinical capacity are in place. We propose measuring whether routine flags lead to documented follow-up within fourteen days. There is no active pilot or confirmed commercial agreement. The opportunity is one inspectable engine, multiple care settings, and a measurable route from signal to human follow-up.

Preflight: team agrees order; screen recording and audio work; no personal patient data; staff and patient sessions are separate; test accounts have the required permissions; provider states are truthful; prepared cases reproduce expected results; links work from a fresh browser. Do not record a claim that has not been demonstrated.


---

# Release checklist and CEO decision record
Status: NOT YET APPROVED FOR SUBMISSION

## Engineering evidence
- Record final main commit, migration head, build command and deployed revision.
- Apply migrations to the deployment database after backup/recovery preparation; do not run destructive test fixtures there.
- Verify fresh login, explicit single-programme onboarding, organisation switching and programme routing.
- Verify patient login, mobile layout, saved check-in after refresh, consent withdrawal and tenant isolation.
- Reproduce Case D, Case B and Neuro presbycusis; inspect actual run trace and benchmark results.
- Verify live agent events in the actual API/worker topology, or describe persisted run history truthfully.
- Close or explicitly disclose the governance findings; unconfigured external integrations stay visibly unconfigured.

## Submission evidence
- Yusuf supplies a judge-accessible HTTPS URL and deployment details. Localhost is not a judge-accessible URL.
- Test judge access in a fresh session, including credentials and permissions supplied privately where needed.
- Asiyah and the team acknowledge the pitch and agree the demo order.
- CEO records or approves the narration; export and watch the entire final video, including sound.
- Attach architecture, dataset description, assumptions, limitations, installation instructions and test evidence.
- Confirm the actual submission form's file/link limits and cutoff timezone. Submit by the proposed internal target: evening of 19 November, leaving 20 November as contingency.
- Save the final submission receipt privately. Do not infer submission from a successful upload alone.

## Final approval fields
CEO decision: pending. Approver and time: not recorded. Deployed URL and release SHA: to be recorded after deployment verification. Video location: not yet supplied. Remaining exceptions: to be accepted or fixed before approval. These are open evidence fields, not completed sign-offs.

## Source register
- CEO task brief supplied by the user: Task Brief Abdulbasit Fazazi (CEO).pdf, pages 1-3.
- User clarification, 18 November: required members registered; no current pilot; submit main after branch integration.
- Hack2skill registration email, 26 October 2026: individual registration confirmation. Private evidence reference in registration-evidence.txt; do not publish email or account details.
- Hack2skill reminder, 17 November: prototype deadline 20 November; working prototype, concise demo video and technical documentation requested.
- Official challenge page: https://hack2skill.com/event/futurehealthchallenge/ (checked 18 November).
- Original shared planning document: https://docs.google.com/document/d/1LGIhOgmrJj-z3lVWQpB2r5FHokiu8z1ufEUhNAbBAiY/edit ; earlier PRD and repository documentation provide product context, not deployment evidence.
- Technical meeting notes, 17 November: https://docs.google.com/document/d/1KJ-dz36MMUCyCKJfvcBzHMUA5deZGWW-4Kt8gEB64-8/edit ; machine-generated notes are contextual, not verification evidence.
- Repository sources reviewed: docs/clinical-governance.md, backend/app/api/v1/ops.py, backend/app/agents/gate1_consent.py, backend/app/core/events.py, backend/app/agents/orchestrator.py, frontend/src/hooks/useRealtimeEvents.ts and related application code.
