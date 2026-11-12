# Database Schema & Migrations

Recova persists all state in **PostgreSQL 16** managed via **SQLAlchemy 2.0** ORM models (`backend/app/models/`) and **Alembic** migrations (`backend/migrations/versions/cd2178bcb554_initial_recova_schema.py`). Every table uses UUID primary keys (`UUIDPk`) and UTC timestamps (`Timestamped`), with multi-tenant organization scoping (`organization_id`) across clinical, operational, and workflow records.

## 1. Migration Revision History

| Revision | Down Revision | Description |
| --- | --- | --- |
| `cd2178bcb554` | `None` (initial) | Creates all 26 core Recova tables, unique constraints, foreign keys, and query indexes |

Apply migrations with:
```bash
cd backend
alembic upgrade head
```

## 2. Table Catalog (26 Tables Across 5 Modules)

### Identity & Access Control (`app/models/identity.py`)
| Table | Purpose | Key Columns & Security Invariants |
| --- | --- | --- |
| `organizations` | Tenant organizations (`hospital`, `clinic`, `rehab_center`, `public_health`, `employer`) | `slug` (unique), `enabled_tracks` (JSONB), `data_retention_days`, `settings` |
| `users` | Staff, clinician, supervisor, and patient accounts | `email` (unique), `password_hash` (Argon2id), `license_number`, `is_platform_admin` |
| `memberships` | User-to-organization role binding | `(user_id, organization_id)` unique, `role`, `department_ids` (JSONB list for WorkSafe scoping) |
| `role_permission_overrides` | Per-organization RBAC customization | `(organization_id, role, permission)`, `effect` (`grant` / `revoke`) |
| `user_sessions` | Server-side stateful sessions | `token_hash` (HMAC-SHA-256), `csrf_token`, `expires_at`, `last_seen_at`, `revoked_at` |
| `password_reset_tokens` | Single-use password reset & user invite tokens | `token_hash` (HMAC-SHA-256), `expires_at`, `used_at` |

### Clinical & Signal Ingestion (`app/models/clinical.py`)
| Table | Purpose | Key Columns & Governance Invariants |
| --- | --- | --- |
| `workplaces` | Physical employer sites (WorkSafe) | `organization_id`, `name`, `location`, `environment_type` |
| `departments` | Workplace organizational units (WorkSafe) | `min_group_size_for_reporting` (k-anonymity threshold, default >= 5) |
| `patients` | Patients and occupational participants | `mrn` (unique per org), `national_id_enc` / `phone_enc` / `email_enc` / `emergency_contact_enc` / `insurance_member_id_enc` (Fernet-encrypted), `is_synthetic` (isolates benchmark fixtures), `department_id`, `education_level`, `hearing_status`, `vision_status` |
| `track_enrollments` | Per-track enrollment state | `(patient_id, track)`, `latest_risk_tier`, `latest_run_id`, `latest_confidence_index`, `context` |
| `consents` | Append-only consent grant/revocation history | `scope` (`data_processing`, `wearable_ingestion`, `llm_synthesis`, `family_notification`, `hie_sharing`, `supervisor_identifiable`), `status`, `effective_at`, `revoked_at`, `expires_at` |
| `wearable_ingestion_batches` | Batch metadata for wearable syncs | `source_system`, `device_id`, `observation_count`, `quality_summary` |
| `check_ins` | Daily voice, text, or WorkSafe readiness submissions | `kind` (`text`, `voice`, `readiness`), `mood_score`, `craving_score`, `stress_score`, `transcript_source`, `symptoms`, `self_reported_crisis` |
| `screening_records` | Loop IFHAS cardiometabolic & PHQ-9 screenings | `programme`, `hba1c`, `bp_systolic`, `bp_diastolic`, lipids, `phq9_score`, `phq9_item_responses` |
| `cognitive_assessments` | Neuro session trials & derived summary metrics | `session_index`, `assessment_language`, `raw_trials` (JSONB), `derived_metrics` |
| `workplace_assessments` | Environmental measurements (WorkSafe) | `ambient_temp_c`, `relative_humidity_pct`, `heat_index_c` (Rothfusz), `wbgt_c`, `noise_db`, `lighting_lux` |
| `observations` | Unified LOINC-coded longitudinal observation stream | `metric_code`, `value_num`, `unit`, `effective_at`, `source`, `quality_flags`, `provenance` |

### Six-Agent Engine (`app/models/engine.py`)
| Table | Purpose | Key Columns & Reproducibility Invariants |
| --- | --- | --- |
| `personal_baselines` | Established 3–5 window individual baselines | `(patient_id, track, metric_code)`, `algorithm_version`, `n_windows`, `mean`, `sample_sd`, `window_values`, `status` |
| `pipeline_runs` | Parent record per 6-agent pipeline execution | `status`, `trigger`, `idempotency_key`, `algorithm_version`, `risk_tier`, `confidence_index`, `is_emergency`, `benchmark_run_id` |
| `agent_step_results` | Individual audit trace for Gate 1, Gate 2, Agents 3–6 | `run_id`, `agent_key`, `step_order`, `status`, `input_payload`, `output_payload`, `duration_ms` |
| `scoring_results` | Immutable mathematical output of Agent 4 | `algorithm_version`, `config_hash`, `risk_tier`, `primary_z`, `metric_results` (JSONB), `missing_streams`, `confounders_applied` |
| `clinical_syntheses` | Agent 5 LLM explanation draft | `status` (`completed`, `provider_not_configured`, `consent_not_granted`, `provider_error`, `validation_failed`), `provider`, `model`, `prompt_version`, `summary_en`, `summary_ar`, `structured` |
| `emergency_events` | Gate 2 acute escalation records | `status` (`open`, `acknowledged`, `resolved`), `rule_codes`, `evidence`, `rules_version`, `acknowledged_by_id`, `resolved_by_id` |

### Clinical Care & Closed-Loop Orchestration (`app/models/care.py`)
| Table | Purpose | Key Columns & Closed-Loop Invariants |
| --- | --- | --- |
| `insurance_plans` | Payer network coverage & pre-auth policies | `code`, `network_tier`, `covered_pathways`, `requires_preauthorization` |
| `care_facilities` | Configured clinical facilities & pathways | `facility_type`, `pathways`, `specialties`, `accepted_plan_ids`, `typical_wait_days` |
| `clinical_reviews` | Signed clinician/DECIDE-AI human decision | `decision`, `agrees_with_tier`, `clinician_notes`, `modified_plan`, `signature_hash` (SHA-256) |
| `referrals` | Closed-loop referral records & SLAs | `pathway`, `status`, `priority`, `coverage_status`, `facility_id`, `sla_due_at`, `sla_status`, `appointment_at`, `outcome_verified_at` |
| `referral_events` | Append-only referral state timeline | `event_type`, `from_status`, `to_status`, `actor_label`, `details` |
| `outcome_verifications` | Clinician/coordinator outcome verification | `outcome` (`improved`, `stable`, `deteriorated`, `relapsed`, `lost_to_follow_up`, `referred_onward`), `verification_method`, `follow_up_run_id` |
| `interventions` | WorkSafe & clinical preventive interventions | `intervention_type`, `status`, `department_id`, `patient_id`, `due_at` |
| `notifications` | Multi-channel notification log | `channel` (`in_app`, `email`, `sms`, `whatsapp`, `sahatna`), `status` (`pending`, `sent`, `delivered`, `failed`, `not_configured`), `provider_message_id` |

### Operations, Governance & Benchmarking (`app/models/ops.py`)
| Table | Purpose | Key Columns & Governance Invariants |
| --- | --- | --- |
| `audit_events` | Immutable security & clinical audit log | `actor_label`, `action`, `resource_type`, `outcome`, `changes`, `details` (scrubbed of PII/secrets) |
| `jobs` | PostgreSQL-backed durable async job queue | `job_type`, `status`, `payload`, `attempts`, `max_attempts`, `timeout_seconds`, `run_after` |
| `benchmark_runs` | Synthetic benchmark suite summary execution | `suite_name`, `suite_version`, `algorithm_version`, `tracks`, `metrics`, `total_cases`, `passed_cases` |
| `benchmark_case_results` | Individual synthetic case expected vs actual verification | `case_id`, `track`, `category`, `expected`, `actual`, `passed`, `pipeline_run_id` |
| `integration_configs` | Per-org external integration settings & encrypted secrets | `(organization_id, integration)` (`llm`, `malaffi`, `sahatna`, `smtp`, `twilio`), `enabled`, `settings`, `secrets_encrypted` |
