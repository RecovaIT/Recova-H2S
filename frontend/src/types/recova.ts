export type Track = "core" | "loop" | "neuro" | "worksafe";

export type RiskTier =
  | "GREEN"
  | "AMBER"
  | "RED"
  | "EMERGENCY_BYPASS"
  | "INDETERMINATE";

export type Role =
  | "platform_admin"
  | "org_admin"
  | "clinician"
  | "psychiatrist"
  | "care_coordinator"
  | "screening_coordinator"
  | "occ_health_director"
  | "supervisor"
  | "authority_user"
  | "patient";

export type ConsentScope =
  | "data_processing"
  | "wearable_ingestion"
  | "llm_synthesis"
  | "family_notification"
  | "hie_sharing"
  | "supervisor_identifiable"
  | "optional_channels";

export type StepStatus =
  | "waiting"
  | "running"
  | "completed"
  | "flagged"
  | "failed"
  | "bypassed"
  | "skipped";

export type ReviewDecision =
  | "approve_referral"
  | "modify_plan"
  | "request_lab"
  | "no_action"
  | "reject";

export type ReferralPathway =
  | "async_teleconsult"
  | "outpatient_therapist"
  | "primary_care"
  | "specialist"
  | "family_alert"
  | "emergency_triage"
  | "routine_monitoring"
  | "occupational_health";

export type ReferralStatus =
  | "proposed"
  | "approved"
  | "patient_notified"
  | "booked"
  | "consultation_completed"
  | "outcome_verified"
  | "missed"
  | "escalated"
  | "cancelled"
  | "rejected";

export type NotificationChannel = "in_app" | "email" | "sms" | "whatsapp" | "sahatna";

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface Organization {
  id: string;
  name: string;
  slug: string;
  org_type: string;
  primary_programme?: string | null;
  programme_configuration_status?: string;
  enabled_tracks: string[];
  is_active: boolean;
  country?: string | null;
  emirate?: string | null;
  settings: Record<string, unknown>;
  data_retention_days?: number | null;
  created_at: string;
}

export interface ProgrammeRequest {
  id: string;
  organization_id: string;
  organization_name?: string | null;
  requested_programme: Track;
  justification: string;
  status: "pending" | "approved" | "rejected";
  requested_by_id?: string | null;
  reviewed_by_id?: string | null;
  reviewed_at?: string | null;
  review_note?: string | null;
  created_at: string;
}

export interface PlatformSubEngineCenter {
  id: string;
  name: string;
  slug: string;
  org_type: string;
  emirate?: string | null;
  primary_programme?: string | null;
  active_patients: number;
  staff_members: number;
  total_runs: number;
  open_emergencies: number;
  risk_distribution: Record<string, number>;
}

export interface PlatformSubEngineSummary {
  track: Track;
  total_centers: number;
  total_patients: number;
  total_staff: number;
  total_runs: number;
  open_emergencies: number;
  risk_distribution: Record<string, number>;
  centers: PlatformSubEngineCenter[];
}

export interface PlatformOverviewReport {
  total_centers: number;
  total_active_patients: number;
  total_staff_members: number;
  total_pipeline_runs: number;
  open_emergencies: number;
  sub_engines: Record<Track, PlatformSubEngineSummary>;
  agent_telemetry: Record<string, Record<string, number>>;
}

export interface Membership {
  id: string;
  user_id: string;
  organization_id: string;
  organization_name?: string | null;
  organization_slug?: string | null;
  role: string;
  is_active: boolean;
  department_ids: string[];
}

export interface User {
  id: string;
  email: string;
  full_name: string;
  is_active: boolean;
  is_platform_admin: boolean;
  preferred_language: string;
  license_number?: string | null;
  last_login_at?: string | null;
  created_at: string;
}

export interface UserWithMemberships extends User {
  memberships: Membership[];
}

export interface ParticipantEnrolmentContext {
  enrolment_id: string;
  patient_id: string;
  organization_id: string;
  organization_name?: string | null;
  programme: string;
  track: string;
  status: string;
}

export interface SessionResponse {
  user: User;
  active_organization: Organization | null;
  role: string | null;
  primary_programme?: string | null;
  programme_configuration_status?: string | null;
  permissions: string[];
  tracks: string[];
  capability_flags?: Record<string, boolean>;
  active_enrolment?: ParticipantEnrolmentContext | null;
  participant_enrolments?: ParticipantEnrolmentContext[];
  memberships: Membership[];
  csrf_token?: string | null;
}

export interface AuthorityScope {
  id: string;
  user_id: string;
  organization_id?: string | null;
  assigned_emirates: string[];
  assigned_facility_ids: string[];
  can_publish: boolean;
  can_view_reports: boolean;
  min_suppression_k: number;
  is_active: boolean;
}

export interface AuthorityNotice {
  id: string;
  title: string;
  message: string;
  plain_language_action?: string | null;
  issuer: string;
  category: string;
  severity: "info" | "advisory" | "urgent";
  scope_emirate?: string | null;
  facility_ids?: string[];
  eligible_programmes: string[];
  acknowledgement_required: boolean;
  status: "draft" | "published" | "expired" | "withdrawn";
  version: number;
  starts_at?: string | null;
  published_at?: string | null;
  expires_at?: string | null;
  withdrawn_at?: string | null;
  acknowledgement_count: number;
  read_count?: number;
  acknowledged?: boolean;
  recipient_state?: "available" | "read" | "acknowledged" | string | null;
  read_at?: string | null;
  acknowledged_at?: string | null;
}

export interface AuthorityReport {
  k_threshold: number;
  scoped_organization_count: number;
  programme_summary: Record<
    string,
    { participant_count: number | null; suppressed_k_anonymity: boolean; k_threshold: number }
  >;
  notice_summaries: Array<{
    notice_id: string;
    title: string;
    status: string;
    version: number;
    scope_emirate?: string | null;
    suppressed_k_anonymity: boolean;
    recipient_count: number | null;
    read_count: number | null;
    acknowledgement_count: number | null;
  }>;
}

export interface Enrollment {
  id: string;
  patient_id: string;
  track: Track | string;
  status: string;
  enrolled_at: string;
  context: Record<string, unknown>;
  latest_risk_tier?: string | null;
  latest_run_id?: string | null;
  latest_run_at?: string | null;
  authority_reason?: string | null;
  history?: Array<Record<string, unknown>>;
}

export interface PatientSummary {
  id: string;
  organization_id: string;
  participant_type: "patient" | "employee" | string;
  mrn: string;
  given_name: string;
  family_name: string;
  date_of_birth?: string | null;
  sex?: string | null;
  preferred_language: "en" | "ar" | string;
  insurance_plan_id?: string | null;
  department_id?: string | null;
  job_role?: string | null;
  primary_clinician_id?: string | null;
  is_active: boolean;
  created_at: string;
  enrollments: Enrollment[];
}

export interface PatientDetail extends PatientSummary {
  phone_masked?: string | null;
  email_masked?: string | null;
  national_id_masked?: string | null;
  insurance_member_id_masked?: string | null;
  education_level?: string | null;
  primary_language_matches_assessment?: boolean | null;
  hearing_status?: string | null;
  vision_status?: string | null;
  clinical_history: Record<string, unknown>;
}

export interface Consent {
  id: string;
  organization_id: string;
  patient_id: string;
  scope: ConsentScope | string;
  status: "granted" | "revoked" | string;
  method: string;
  policy_version?: string;
  authority_to_act?: string;
  granted_by_name?: string | null;
  effective_at: string;
  expires_at?: string | null;
  revoked_at?: string | null;
  evidence_reference?: string | null;
  notes?: string | null;
  created_at: string;
}

export interface MetricCatalogEntry {
  code: string;
  label: string;
  unit: string;
  stream_name: string;
  direction: string;
  valid_min: number;
  valid_max: number;
  loinc_code?: string | null;
}

export interface Observation {
  id: string;
  organization_id: string;
  patient_id: string;
  track?: string | null;
  metric_code: string;
  value_num?: number | null;
  value_text?: string | null;
  unit?: string | null;
  effective_at: string;
  source: string;
  status: string;
  provenance: Record<string, unknown>;
  quality_flags: string[];
  device_id?: string | null;
  created_at: string;
}

export interface CheckIn {
  id: string;
  patient_id: string;
  track: string;
  kind: string;
  effective_at: string;
  mood_score?: number | null;
  craving_score?: number | null;
  stress_score?: number | null;
  sleep_quality?: number | null;
  text?: string | null;
  transcript_source?: string | null;
  symptoms: string[];
  self_reported_crisis: boolean;
  extra: Record<string, unknown>;
  created_at: string;
}

export interface ScreeningRecord {
  id: string;
  patient_id: string;
  programme: string;
  screened_at: string;
  screening_site?: string | null;
  phq9_item_responses?: number[] | null;
  notes?: string | null;
  created_at: string;
}

export interface CognitiveTrialInput {
  task_type:
    | "sequence_4key"
    | "sequence_6key"
    | "audio_memory"
    | "visual_memory"
    | "rule_switch"
    | "delayed_recall";
  modality: "visual" | "auditory" | "audiovisual" | "executive" | "recall";
  expected: unknown[];
  response: unknown[];
  reaction_time_ms: number;
  correct: boolean;
}

export interface CognitiveAssessment {
  id: string;
  patient_id: string;
  session_index: number;
  started_at: string;
  completed_at?: string | null;
  assessment_language: string;
  environment: Record<string, unknown>;
  raw_trials: CognitiveTrialInput[];
  derived_metrics: Record<string, number>;
  status: string;
  created_at: string;
}

export interface PersonalBaseline {
  id: string;
  metric_code: string;
  algorithm_version: string;
  status: string;
  n_windows: number;
  mean: number;
  sample_sd: number;
  window_values: number[];
  established_at?: string | null;
}

export interface AgentStep {
  id: string;
  run_id: string;
  agent_key: string;
  agent_name: string;
  step_order: number;
  status: StepStatus | string;
  message?: string | null;
  input_payload?: Record<string, unknown> | null;
  output_payload?: Record<string, unknown> | null;
  error?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
  duration_ms?: number | null;
}

export interface MetricScoreItem {
  metric_code: string;
  label?: string;
  unit?: string;
  current_value?: number | null;
  baseline_mean?: number | null;
  baseline_sd?: number | null;
  raw_se?: number | null;
  adjusted_se?: number | null;
  practice_adjustment?: number | null;
  z_score?: number | null;
  signed_z?: number | null;
  risk_tier: string;
  status: string;
  weight?: number;
  notes?: string | null;
}

export interface ScoringResult {
  id: string;
  run_id: string;
  patient_id?: string | null;
  track: string;
  algorithm_version: string;
  risk_tier: RiskTier | string;
  confidence_index: number;
  composite_index?: number | null;
  primary_metric_code?: string | null;
  primary_z?: number | null;
  metric_results: MetricScoreItem[];
  missing_streams: string[];
  confounders_applied: Array<Record<string, unknown>>;
  config_snapshot: Record<string, unknown>;
  computed_at: string;
}

export interface ClinicalSynthesis {
  id: string;
  run_id: string;
  status:
    | "completed"
    | "provider_not_configured"
    | "consent_not_granted"
    | "provider_error"
    | "validation_failed"
    | string;
  provider?: string | null;
  model?: string | null;
  prompt_version: string;
  summary_en?: string | null;
  summary_ar?: string | null;
  structured?: Record<string, unknown> | null;
  error?: string | null;
  latency_ms?: number | null;
  created_at: string;
}

export interface PipelineRun {
  id: string;
  organization_id: string;
  patient_id?: string | null;
  track: string;
  status: string;
  trigger: string;
  algorithm_version: string;
  risk_tier?: string | null;
  confidence_index?: number | null;
  is_emergency: boolean;
  as_of: string;
  started_at?: string | null;
  finished_at?: string | null;
  duration_ms?: number | null;
  error?: string | null;
  job_id?: string | null;
  created_at: string;
}

export interface PipelineRunDetail extends PipelineRun {
  steps: AgentStep[];
  scoring?: ScoringResult | null;
  synthesis?: ClinicalSynthesis | null;
}

export interface EmergencyEvent {
  id: string;
  organization_id: string;
  patient_id?: string | null;
  run_id?: string | null;
  track: string;
  status: "open" | "acknowledged" | "resolved" | string;
  rule_codes: string[];
  evidence: Array<Record<string, unknown>>;
  rules_version: string;
  acknowledged_by_id?: string | null;
  acknowledged_at?: string | null;
  resolved_by_id?: string | null;
  resolved_at?: string | null;
  resolution_notes?: string | null;
  created_at: string;
}

export interface ClinicalReview {
  id: string;
  organization_id: string;
  run_id: string;
  patient_id: string;
  reviewer_id: string;
  reviewer_role: string;
  reviewer_license?: string | null;
  decision: string;
  agrees_with_tier?: boolean | null;
  clinician_notes?: string | null;
  modified_plan?: Record<string, unknown> | null;
  lab_request?: Record<string, unknown> | null;
  signed_at: string;
  signature_hash: string;
}

export interface ReferralEvent {
  id: string;
  referral_id: string;
  event_type: string;
  from_status?: string | null;
  to_status?: string | null;
  actor_user_id?: string | null;
  actor_label: string;
  details: Record<string, unknown>;
  created_at: string;
}

export interface OutcomeVerification {
  id: string;
  referral_id: string;
  verified_by_id: string;
  outcome: string;
  verification_method: string;
  notes?: string | null;
  follow_up_run_id?: string | null;
  verified_at: string;
}

export interface Referral {
  id: string;
  organization_id: string;
  patient_id: string;
  run_id?: string | null;
  track: string;
  pathway: string;
  priority: string;
  status: ReferralStatus | string;
  reason: string;
  rule_trace: Record<string, unknown>;
  facility_id?: string | null;
  insurance_plan_id?: string | null;
  coverage_status: string;
  owner_user_id?: string | null;
  owner_facility_label?: string | null;
  approved_by_id?: string | null;
  approved_at?: string | null;
  appointment_at?: string | null;
  appointment_reference?: string | null;
  target_date?: string | null;
  sla_due_at?: string | null;
  sla_status: string;
  escalation_level: number;
  consultation_completed_at?: string | null;
  outcome_verified_at?: string | null;
  closed_at?: string | null;
  is_emergency: boolean;
  created_at: string;
}

export interface ReferralDetail extends Referral {
  events: ReferralEvent[];
  outcome_verification?: OutcomeVerification | null;
}

export interface Intervention {
  id: string;
  organization_id: string;
  track: string;
  patient_id?: string | null;
  department_id?: string | null;
  referral_id?: string | null;
  run_id?: string | null;
  intervention_type: string;
  status: string;
  title: string;
  details?: string | null;
  rule_trace: Record<string, unknown>;
  assigned_to_id?: string | null;
  due_at?: string | null;
  completed_at?: string | null;
  created_by_label: string;
  created_at: string;
}

export interface NotificationItem {
  id: string;
  channel: string;
  status: string;
  category: string;
  recipient_user_id?: string | null;
  recipient_patient_id?: string | null;
  recipient_address_masked?: string | null;
  subject: string;
  body: string;
  referral_id?: string | null;
  emergency_event_id?: string | null;
  provider?: string | null;
  provider_message_id?: string | null;
  last_error?: string | null;
  sent_at?: string | null;
  delivered_at?: string | null;
  read_at?: string | null;
  created_at: string;
}

export interface InsurancePlan {
  id: string;
  organization_id: string;
  code: string;
  name: string;
  payer_name?: string | null;
  network_tier?: string | null;
  covered_pathways: string[];
  requires_preauthorization: boolean;
  verification_source?: string | null;
  is_active: boolean;
}

export interface CareFacility {
  id: string;
  organization_id: string;
  name: string;
  facility_type: string;
  pathways: string[];
  specialties: string[];
  accepted_plan_ids: string[];
  address?: string | null;
  contact_phone?: string | null;
  contact_email?: string | null;
  accepting_referrals: boolean;
  typical_wait_days?: number | null;
  is_active: boolean;
}

export interface IntegrationConfig {
  integration: string;
  status: string;
  enabled: boolean;
  settings: Record<string, unknown>;
  has_secrets: boolean;
  env_configured: boolean;
  last_tested_at?: string | null;
  last_test_result?: Record<string, unknown> | null;
}

export interface Workplace {
  id: string;
  organization_id: string;
  name: string;
  location?: string | null;
  environment_type?: string | null;
  is_active: boolean;
}

export interface Department {
  id: string;
  organization_id: string;
  workplace_id?: string | null;
  name: string;
  min_group_size_for_reporting: number;
  is_active: boolean;
}

export interface WorkplaceAssessment {
  id: string;
  organization_id: string;
  department_id?: string | null;
  workplace_id?: string | null;
  measured_at: string;
  ambient_temp_c?: number | null;
  relative_humidity_pct?: number | null;
  heat_index_c?: number | null;
  wbgt_c?: number | null;
  noise_db?: number | null;
  lighting_lux?: number | null;
  ergonomics_checklist: Record<string, unknown>;
  source: string;
  created_at: string;
}

export interface HeatmapRow {
  department_id: string;
  department_name: string;
  worker_count: number;
  k_anonymity_threshold: number;
  suppressed_k_anonymity: boolean;
  risk_counts: Record<string, number> | null;
  latest_heat_index_c?: number | null;
  latest_ambient_temp_c?: number | null;
  open_interventions: number;
}

export interface BenchmarkCaseResult {
  id: string;
  case_id: string;
  track: string;
  scenario: string;
  category: string;
  expected: Record<string, unknown>;
  actual: Record<string, unknown>;
  passed: boolean;
  failure_details?: string | null;
  pipeline_run_id?: string | null;
  duration_ms?: number | null;
  executed_at: string;
}

export interface BenchmarkRun {
  id: string;
  organization_id: string;
  suite_name: string;
  suite_version: string;
  algorithm_version: string;
  tracks: string[];
  status: string;
  started_at?: string | null;
  finished_at?: string | null;
  metrics: Record<string, unknown>;
  total_cases: number;
  passed_cases: number;
  error?: string | null;
  created_at: string;
}

export interface BenchmarkRunDetail extends BenchmarkRun {
  cases: BenchmarkCaseResult[];
}

export interface OverviewReport {
  organization_id: string;
  active_patients: number;
  open_emergencies: number;
  pending_clinician_reviews: number;
  open_referrals: number;
  verified_outcomes: number;
  sla_breaches: number;
  total_pipeline_runs: number;
  track_risk_distribution: Record<string, Record<string, number>>;
  referral_funnel: Record<string, number>;
}

export interface AuditEvent {
  id: string;
  occurred_at: string;
  organization_id?: string | null;
  actor_user_id?: string | null;
  actor_label: string;
  action: string;
  resource_type: string;
  resource_id?: string | null;
  patient_id?: string | null;
  run_id?: string | null;
  outcome: string;
  changes: Record<string, unknown>;
  details: Record<string, unknown>;
  ip_address?: string | null;
  request_id?: string | null;
}

export interface JobRecord {
  id: string;
  organization_id?: string | null;
  job_type: string;
  status: string;
  payload: Record<string, unknown>;
  result?: Record<string, unknown> | null;
  attempts: number;
  max_attempts: number;
  timeout_seconds: number;
  run_after: string;
  started_at?: string | null;
  finished_at?: string | null;
  last_error?: string | null;
  created_at: string;
}

export interface RolePermissionView {
  role: string;
  default_permissions: string[];
  effective_permissions: string[];
  overrides: Array<{ id?: string; role?: string; permission: string; effect: string }>;
}

export interface FamilyHealthPassport {
  patient: PatientDetail;
  insurance_plan: {
    id: string;
    code: string;
    name: string;
    network_tier?: string | null;
    covered_pathways: string[];
  } | null;
  latest_risk_tier?: string | null;
  latest_confidence_index?: number | null;
  recent_observations: Observation[];
  referrals: Array<{
    id: string;
    track: string;
    pathway: string;
    status: string;
    priority: string;
    coverage_status: string;
    facility_name?: string | null;
    sla_due_at?: string | null;
    sla_status: string;
    appointment_at?: string | null;
    outcome_verified_at?: string | null;
  }>;
  consents: Consent[];
}
