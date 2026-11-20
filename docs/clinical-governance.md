# Clinical Governance, DECIDE-AI & Interoperability

Recova implements prototype controls for clinical safety, AI human-factors transparency, workforce privacy, and healthcare interoperability in the backend. This document describes implementation, not clinical validation, regulatory certification or approval for patient deployment.

## 1. Human-in-the-Loop & DECIDE-AI Safeguards

Recova adheres to strict boundaries between deterministic analytics, generative LLM explanation, and licensed clinical decision-making:

1. **LLM Non-Autonomy (`app/integrations/llm.py`, `app/agents/agent5_synthesis.py`):**
   - Agent 5 receives only de-identified metrics (`track`, `algorithm_version`, `deterministic_risk_tier`, `confidence_index_pct`, `metric_details`, `missing_streams`, `confounders_applied`). Name, MRN, DOB, national ID, contact info, and narrative notes are never forwarded.
   - Output is validated strictly against `SynthesisDraftSchema` containing bilingual English (`summary_en`) and Arabic (`summary_ar`) drafts, `contributing_signals`, `missing_data_limitations`, `confounder_notes`, `recommended_follow_up_actions`, and `clinical_disclaimer`.
   - The LLM cannot compute risk scores, overwrite `risk_tier`, diagnose conditions, approve referrals, or suppress Gate 1 / Gate 2 controls.
   - If `LLM_PROVIDER=none` or credentials are absent, Agent 5 stores `status="provider_not_configured"` cleanly—**no fabricated AI summary is ever generated or displayed**.

2. **Clinician Review Sign-Off (`ClinicalReview` & `DecideAiReviewWorkspace.tsx`):**
   - Clinicians review the deterministic Agent 4 trace, data completeness/confidence, confounders, and Agent 5 bilingual draft before signing a decision (`approve_referral`, `modify_plan`, `request_lab`, `no_action`, or `reject`).
   - A review record is not external licence verification or a certified digital signature. Every submitted review generates a server-side SHA-256 `signature_hash` stamped with reviewer ID, role, optional practitioner license number, and timestamp.

3. **Closed-Loop Outcome Accountability (`app/models/care.py`):**
   - Agent 6 proposes/initiates referral pathways (`proposed`) matching configured `InsurancePlan` rules and `CareFacility` networks.
   - Referrals **cannot** auto-close. Progress follows auditable human/system milestones: `proposed` -> `approved` -> `patient_notified` -> `booked` -> `consultation_completed` -> `outcome_verified` (or `missed` -> `escalated`), ending with explicit `OutcomeVerification` (`improved`, `stable`, `deteriorated`, `relapsed`, `lost_to_follow_up`, `referred_onward`).

4. **Track-Specific Non-Diagnostic Framing:**
   - **Recova Neuro** explicitly surfaces non-diagnostic wellness screening notices in both UI (`NeuroActivityGame.tsx`) and synthesis prompts, clarifying that longitudinal cognitive drift does not constitute a standalone dementia diagnosis.

## 2. Consent Scopes & Enforcement (`app/models/enums.py`)

Consents are stored as an append-only ledger (`consents` table):

| Scope | Enforcement Point |
| --- | --- |
| `data_processing` | **Mandatory in Gate 1.** Absence or revocation stops routine scoring (`status="blocked"`). |
| `wearable_ingestion` | Governs passive device stream ingestion. |
| `llm_synthesis` | An explicit grant is required. If absent or revoked, Agent 5 stops with `status="consent_not_granted"` while deterministic Agent 4 remains operational. |
| `family_notification` | Governs family/emergency alert outreach pathways. |
| `hie_sharing` | Controls Malaffi / HIE Bundle transmission authorization. |
| `supervisor_identifiable` | Explicit worker consent required before any supervisor role can inspect identifiable worker risks. |

## 3. WorkSafe Privacy & k-Anonymity (`app/services/workforce.py`)

To prevent employer discrimination or retaliatory visibility in **Recova WorkSafe**:
- Each department defines `min_group_size_for_reporting` (k-anonymity threshold, e.g., >= 5).
- In `GET /api/v1/workforce/heatmap`, when a department's active worker count `0 < n < min_group_size_for_reporting` and the caller lacks `workforce:identifiable` (`supervisor` role), `risk_counts` is replaced with `null` and `suppressed_k_anonymity: true` is returned alongside aggregate environmental telemetry.
- `GET /api/v1/workforce/identifiable-risks` rejects callers without `workforce:identifiable` (`403 Forbidden`) and additionally checks per-worker `supervisor_identifiable` consent if caller role is `supervisor`.

## 4. HL7 FHIR R4.0.1 & Regional Health Integration (`app/integrations/fhir.py`)

- **FHIR R4 Bundle Builder (`GET /api/v1/fhir/patients/{patient_id}/bundle`):**
  Generates `collection` or `transaction` Bundles containing FHIR R4-oriented resources: `Organization`, `Patient` (tagged with Malaffi MRN & Sahatna participant identifiers), `Practitioner` (DOH license identifier), `Consent`, `Coverage`, `Observation` (LOINC-coded telemetry + Agent 4 interpretation codes `N` / `A` / `AA` / `HH` / `IND`), `QuestionnaireResponse` (IFHAS / PHQ-9), `ServiceRequest`, `CarePlan`, `Communication`, and `Encounter`.
- **Structural & Reference Integrity Validator (`POST /api/v1/fhir/validate`):**
  Provides local checks, not full HL7 profile or terminology conformance certification. Validates resource types, `fullUrl` uniqueness, and `urn:uuid:` internal reference integrity across Bundle entries.
- **Truthful HIE & Notification Delivery (`malaffi.py`, `sahatna.py`, `notifications.py`):**
  - `POST /api/v1/fhir/patients/{patient_id}/push-malaffi` reports `not_configured` until valid Malaffi OAuth2 credentials (`base_url`, `token_url`, `client_id`, `client_secret`) are provided and reachable.
  - External notifications (SMTP, Twilio SMS/WhatsApp, Sahatna) record provider acceptance when confirmed; acceptance alone does not establish delivery, reading or outcome; otherwise the `notifications` table persists `not_configured` or `failed` transparently.

## Release review boundaries (18 November 2026)

- HIE export and push now require an effective, unexpired `hie_sharing` grant using the shared consent evaluator. Regression tests cover absent, future, expired, revoked and re-granted consent. This does not certify all external integrations.
- Live agent event names were corrected during integration. The event broker is process-local; separate API/worker processes require shared transport or explicit persisted-state refresh. Verify the deployed topology before claiming live streaming.
- Regional identifiers are supplied values. Neither identifiers nor a bundle builder prove Malaffi/Sahatna connectivity; test official destination requirements independently.
- Synthetic benchmark results are scenario agreement, not clinical accuracy or demonstrated relapse prevention. The six stages are deterministic workflow stages plus optional AI synthesis, not six independent language models.
- Arabic output quality, actual licence checks, deployment sovereignty, backups and encryption coverage need specific verification. Engineering requirements are not evidence that compliance has been achieved.
- An external delivery receipt, patient acknowledgement and clinical outcome are distinct records. Clinical review remains necessary; no autonomous diagnosis or treatment claim is made.
