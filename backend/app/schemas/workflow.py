"""Pipeline execution, clinical review, referral, intervention, FHIR & benchmark schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, EmailStr, Field

from app.core.permissions import Track
from app.models.enums import (
    InterventionStatus,
    InterventionType,
    NotificationChannel,
    ReferralPathway,
    ReferralPriority,
    ReviewDecision,
)
from app.schemas.common import ORMModel


class PipelineRunCreate(BaseModel):
    patient_id: uuid.UUID
    track: Track
    trigger: Literal["manual", "checkin", "wearable", "screening", "assessment"] = "manual"
    as_of: datetime | None = None
    idempotency_key: str | None = Field(default=None, max_length=120)
    run_async: bool = False


class AgentStepOut(ORMModel):
    id: uuid.UUID
    run_id: uuid.UUID
    agent_key: str
    agent_name: str
    step_order: int
    status: str
    message: str | None = None
    input_payload: dict | None = None
    output_payload: dict | None = None
    error: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_ms: int | None = None


class ScoringResultOut(ORMModel):
    id: uuid.UUID
    run_id: uuid.UUID
    patient_id: uuid.UUID | None = None
    track: str
    algorithm_version: str
    risk_tier: str
    confidence_index: float
    composite_index: float | None = None
    primary_metric_code: str | None = None
    primary_z: float | None = None
    metric_results: list = Field(default_factory=list)
    missing_streams: list = Field(default_factory=list)
    confounders_applied: list = Field(default_factory=list)
    config_snapshot: dict = Field(default_factory=dict)
    computed_at: datetime


class ClinicalSynthesisOut(ORMModel):
    id: uuid.UUID
    run_id: uuid.UUID
    status: str
    provider: str | None = None
    model: str | None = None
    prompt_version: str
    summary_en: str | None = None
    summary_ar: str | None = None
    structured: dict | None = None
    error: str | None = None
    latency_ms: int | None = None
    created_at: datetime


class PipelineRunOut(ORMModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    patient_id: uuid.UUID | None = None
    track: str
    status: str
    trigger: str
    algorithm_version: str
    risk_tier: str | None = None
    confidence_index: float | None = None
    is_emergency: bool
    as_of: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_ms: int | None = None
    error: str | None = None
    job_id: uuid.UUID | None = None
    created_at: datetime


class PipelineRunDetailOut(PipelineRunOut):
    steps: list[AgentStepOut] = Field(default_factory=list)
    scoring: ScoringResultOut | None = None
    synthesis: ClinicalSynthesisOut | None = None


class EmergencyEventOut(ORMModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    patient_id: uuid.UUID | None = None
    run_id: uuid.UUID | None = None
    track: str
    status: str
    rule_codes: list = Field(default_factory=list)
    evidence: list = Field(default_factory=list)
    rules_version: str
    acknowledged_by_id: uuid.UUID | None = None
    acknowledged_at: datetime | None = None
    resolved_by_id: uuid.UUID | None = None
    resolved_at: datetime | None = None
    resolution_notes: str | None = None
    created_at: datetime


class EmergencyResolveRequest(BaseModel):
    action: Literal["acknowledge", "resolve"]
    notes: str | None = Field(default=None, max_length=2000)


class ClinicalReviewCreate(BaseModel):
    run_id: uuid.UUID
    decision: ReviewDecision
    agrees_with_tier: bool | None = True
    clinician_notes: str | None = Field(default=None, max_length=4000)
    modified_plan: dict[str, Any] | None = None
    lab_request: dict[str, Any] | None = None
    referral_id: uuid.UUID | None = None
    notify_patient_channel: NotificationChannel | None = None


class ClinicalReviewOut(ORMModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    run_id: uuid.UUID
    patient_id: uuid.UUID
    reviewer_id: uuid.UUID
    reviewer_role: str
    reviewer_license: str | None = None
    decision: str
    agrees_with_tier: bool | None = None
    clinician_notes: str | None = None
    modified_plan: dict | None = None
    lab_request: dict | None = None
    signed_at: datetime
    signature_hash: str


class ReferralCreate(BaseModel):
    patient_id: uuid.UUID
    track: Track
    pathway: ReferralPathway
    priority: ReferralPriority = ReferralPriority.ROUTINE
    reason: str = Field(min_length=5, max_length=2000)
    facility_id: uuid.UUID | None = None
    owner_user_id: uuid.UUID | None = None
    target_date: datetime | None = None


class ReferralBookRequest(BaseModel):
    appointment_at: datetime
    appointment_reference: str | None = Field(default=None, max_length=200)
    facility_id: uuid.UUID | None = None
    notes: str | None = Field(default=None, max_length=1000)


class ReferralCompleteRequest(BaseModel):
    completed_at: datetime | None = None
    notes: str | None = Field(default=None, max_length=2000)


class ReferralNotifyRequest(BaseModel):
    channel: NotificationChannel = NotificationChannel.IN_APP
    message: str | None = Field(default=None, max_length=1000)


class OutcomeVerificationCreate(BaseModel):
    outcome: Literal["improved", "stable", "deteriorated", "relapsed", "lost_to_follow_up", "referred_onward"]
    verification_method: Literal["clinic_visit", "teleconsult", "phone", "record_review", "lab_result"]
    notes: str | None = Field(default=None, max_length=2000)
    follow_up_run_id: uuid.UUID | None = None


class OutcomeVerificationOut(ORMModel):
    id: uuid.UUID
    referral_id: uuid.UUID
    verified_by_id: uuid.UUID
    outcome: str
    verification_method: str
    notes: str | None = None
    follow_up_run_id: uuid.UUID | None = None
    verified_at: datetime


class ReferralEventOut(ORMModel):
    id: uuid.UUID
    referral_id: uuid.UUID
    event_type: str
    from_status: str | None = None
    to_status: str | None = None
    actor_user_id: uuid.UUID | None = None
    actor_label: str
    details: dict = Field(default_factory=dict)
    created_at: datetime


class ReferralOut(ORMModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    patient_id: uuid.UUID
    run_id: uuid.UUID | None = None
    track: str
    pathway: str
    priority: str
    status: str
    reason: str
    rule_trace: dict = Field(default_factory=dict)
    facility_id: uuid.UUID | None = None
    insurance_plan_id: uuid.UUID | None = None
    coverage_status: str
    owner_user_id: uuid.UUID | None = None
    owner_facility_label: str | None = None
    approved_by_id: uuid.UUID | None = None
    approved_at: datetime | None = None
    appointment_at: datetime | None = None
    appointment_reference: str | None = None
    target_date: datetime | None = None
    sla_due_at: datetime | None = None
    sla_status: str
    escalation_level: int
    consultation_completed_at: datetime | None = None
    outcome_verified_at: datetime | None = None
    closed_at: datetime | None = None
    is_emergency: bool
    created_at: datetime


class ReferralDetailOut(ReferralOut):
    events: list[ReferralEventOut] = Field(default_factory=list)
    outcome_verification: OutcomeVerificationOut | None = None


class InterventionCreate(BaseModel):
    track: Track
    patient_id: uuid.UUID | None = None
    department_id: uuid.UUID | None = None
    referral_id: uuid.UUID | None = None
    intervention_type: InterventionType
    title: str = Field(min_length=2, max_length=200)
    details: str | None = None
    assigned_to_id: uuid.UUID | None = None
    due_at: datetime | None = None


class InterventionUpdateRequest(BaseModel):
    status: InterventionStatus
    details: str | None = None


class InterventionOut(ORMModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    track: str
    patient_id: uuid.UUID | None = None
    department_id: uuid.UUID | None = None
    referral_id: uuid.UUID | None = None
    run_id: uuid.UUID | None = None
    intervention_type: str
    status: str
    title: str
    details: str | None = None
    rule_trace: dict = Field(default_factory=dict)
    assigned_to_id: uuid.UUID | None = None
    due_at: datetime | None = None
    completed_at: datetime | None = None
    created_by_label: str
    created_at: datetime


class NotificationOut(ORMModel):
    id: uuid.UUID
    channel: str
    status: str
    category: str
    recipient_user_id: uuid.UUID | None = None
    recipient_patient_id: uuid.UUID | None = None
    recipient_address_masked: str | None = None
    subject: str
    body: str
    referral_id: uuid.UUID | None = None
    emergency_event_id: uuid.UUID | None = None
    provider: str | None = None
    provider_message_id: str | None = None
    last_error: str | None = None
    sent_at: datetime | None = None
    delivered_at: datetime | None = None
    read_at: datetime | None = None
    created_at: datetime


class InsurancePlanCreate(BaseModel):
    code: str = Field(min_length=2, max_length=40)
    name: str = Field(min_length=2, max_length=200)
    payer_name: str | None = Field(default=None, max_length=200)
    network_tier: str | None = Field(default=None, max_length=40)
    covered_pathways: list[ReferralPathway] = Field(default_factory=list)
    requires_preauthorization: bool = False
    verification_source: str | None = Field(default=None, max_length=200)


class InsurancePlanOut(ORMModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    code: str
    name: str
    payer_name: str | None = None
    network_tier: str | None = None
    covered_pathways: list[str]
    requires_preauthorization: bool
    verification_source: str | None = None
    is_active: bool


class CareFacilityCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    facility_type: Literal["primary_care", "specialist", "teleconsult", "rehab", "emergency", "occupational_health", "therapist"]
    pathways: list[ReferralPathway] = Field(default_factory=list)
    specialties: list[str] = Field(default_factory=list)
    accepted_plan_ids: list[uuid.UUID] = Field(default_factory=list)
    address: str | None = Field(default=None, max_length=300)
    contact_phone: str | None = Field(default=None, max_length=40)
    contact_email: EmailStr | None = None
    accepting_referrals: bool = True
    typical_wait_days: int | None = Field(default=None, ge=0, le=365)


class CareFacilityOut(ORMModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    facility_type: str
    pathways: list[str]
    specialties: list[str]
    accepted_plan_ids: list[uuid.UUID]
    address: str | None = None
    contact_phone: str | None = None
    contact_email: str | None = None
    accepting_referrals: bool
    typical_wait_days: int | None = None
    is_active: bool


class IntegrationConfigUpdate(BaseModel):
    enabled: bool = True
    settings: dict[str, Any] = Field(default_factory=dict)
    secrets: dict[str, str] | None = None


class IntegrationConfigOut(BaseModel):
    integration: str
    status: str
    enabled: bool
    settings: dict[str, Any]
    has_secrets: bool
    env_configured: bool
    last_tested_at: datetime | None = None
    last_test_result: dict[str, Any] | None = None


class BenchmarkRunCreate(BaseModel):
    tracks: list[Track] = Field(default_factory=lambda: [Track.CORE, Track.LOOP, Track.NEURO, Track.WORKSAFE])
    run_async: bool = False


class BenchmarkCaseResultOut(ORMModel):
    id: uuid.UUID
    case_id: str
    track: str
    scenario: str
    category: str
    expected: dict
    actual: dict
    passed: bool
    failure_details: str | None = None
    pipeline_run_id: uuid.UUID | None = None
    duration_ms: float | None = None
    executed_at: datetime


class BenchmarkRunOut(ORMModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    suite_name: str
    suite_version: str
    algorithm_version: str
    tracks: list
    status: str
    started_at: datetime | None = None
    finished_at: datetime | None = None
    metrics: dict
    total_cases: int
    passed_cases: int
    error: str | None = None
    created_at: datetime


class BenchmarkRunDetailOut(BenchmarkRunOut):
    cases: list[BenchmarkCaseResultOut] = Field(default_factory=list)
