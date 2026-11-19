"""Clinical, wearable, check-in, IFHAS screening, Neuro cognitive, and WorkSafe schemas."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, EmailStr, Field

from app.core.permissions import Track
from app.models.enums import ConsentScope, ObservationSource, ParticipantType
from app.schemas.common import ORMModel


class EnrollmentOut(ORMModel):
    id: uuid.UUID
    patient_id: uuid.UUID
    track: str
    status: str
    enrolled_at: datetime
    context: dict = Field(default_factory=dict)
    latest_risk_tier: str | None = None
    latest_run_id: uuid.UUID | None = None
    latest_run_at: datetime | None = None
    authority_reason: str | None = None
    history: list = Field(default_factory=list)


class PatientCreate(BaseModel):
    participant_type: ParticipantType = ParticipantType.PATIENT
    mrn: str = Field(min_length=2, max_length=64)
    given_name: str = Field(min_length=1, max_length=120)
    family_name: str = Field(min_length=1, max_length=120)
    date_of_birth: date | None = None
    sex: Literal["male", "female", "other", "unknown"] | None = "unknown"
    preferred_language: Literal["en", "ar"] = "en"
    national_id: str | None = Field(default=None, max_length=80)
    phone: str | None = Field(default=None, max_length=40)
    email: EmailStr | None = None
    emergency_contact: dict[str, Any] | None = None
    education_level: Literal["none", "primary", "secondary", "tertiary", "postgraduate"] | None = None
    primary_language_matches_assessment: bool | None = True
    hearing_status: Literal["normal", "mild_loss", "moderate_loss", "severe_loss", "aided"] | None = "normal"
    vision_status: Literal["normal", "corrected", "mild_impairment", "severe_impairment"] | None = "normal"
    clinical_history: dict[str, Any] = Field(default_factory=dict)
    insurance_plan_id: uuid.UUID | None = None
    insurance_member_id: str | None = Field(default=None, max_length=80)
    department_id: uuid.UUID | None = None
    job_role: str | None = Field(default=None, max_length=120)
    primary_clinician_id: uuid.UUID | None = None
    tracks: list[Track] | None = None


class PatientUpdate(BaseModel):
    given_name: str | None = Field(default=None, min_length=1, max_length=120)
    family_name: str | None = Field(default=None, min_length=1, max_length=120)
    date_of_birth: date | None = None
    sex: Literal["male", "female", "other", "unknown"] | None = None
    preferred_language: Literal["en", "ar"] | None = None
    phone: str | None = Field(default=None, max_length=40)
    email: EmailStr | None = None
    emergency_contact: dict[str, Any] | None = None
    education_level: Literal["none", "primary", "secondary", "tertiary", "postgraduate"] | None = None
    primary_language_matches_assessment: bool | None = None
    hearing_status: Literal["normal", "mild_loss", "moderate_loss", "severe_loss", "aided"] | None = None
    vision_status: Literal["normal", "corrected", "mild_impairment", "severe_impairment"] | None = None
    clinical_history: dict[str, Any] | None = None
    insurance_plan_id: uuid.UUID | None = None
    insurance_member_id: str | None = Field(default=None, max_length=80)
    department_id: uuid.UUID | None = None
    job_role: str | None = Field(default=None, max_length=120)
    primary_clinician_id: uuid.UUID | None = None
    is_active: bool | None = None


class PatientSummaryOut(ORMModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    participant_type: str
    mrn: str
    given_name: str
    family_name: str
    date_of_birth: date | None = None
    sex: str | None = None
    preferred_language: str
    insurance_plan_id: uuid.UUID | None = None
    department_id: uuid.UUID | None = None
    job_role: str | None = None
    primary_clinician_id: uuid.UUID | None = None
    is_active: bool
    created_at: datetime
    enrollments: list[EnrollmentOut] = Field(default_factory=list)


class PatientDetailOut(PatientSummaryOut):
    phone_masked: str | None = None
    email_masked: str | None = None
    national_id_masked: str | None = None
    insurance_member_id_masked: str | None = None
    education_level: str | None = None
    primary_language_matches_assessment: bool | None = None
    hearing_status: str | None = None
    vision_status: str | None = None
    clinical_history: dict = Field(default_factory=dict)


class EnrollmentCreate(BaseModel):
    track: Track
    context: dict[str, Any] = Field(default_factory=dict)
    reason: str | None = Field(default=None, max_length=500)


class ConsentCreate(BaseModel):
    patient_id: uuid.UUID
    scope: ConsentScope
    method: Literal["written", "verbal_witnessed", "electronic", "guardian"] = "electronic"
    policy_version: str = Field(default="v1.0", max_length=40)
    authority_to_act: str = Field(default="self", max_length=80)
    granted_by_name: str | None = Field(default=None, max_length=200)
    effective_at: datetime | None = None
    expires_at: datetime | None = None
    evidence_reference: str | None = Field(default=None, max_length=300)
    notes: str | None = None


class ConsentOut(ORMModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    patient_id: uuid.UUID
    scope: str
    status: str
    method: str
    policy_version: str = "v1.0"
    authority_to_act: str = "self"
    granted_by_name: str | None = None
    effective_at: datetime
    expires_at: datetime | None = None
    revoked_at: datetime | None = None
    evidence_reference: str | None = None
    notes: str | None = None
    created_at: datetime


class ObservationCreate(BaseModel):
    patient_id: uuid.UUID
    track: Track | None = None
    metric_code: str = Field(min_length=2, max_length=60)
    value_num: float | None = None
    value_text: str | None = None
    unit: str | None = Field(default=None, max_length=30)
    effective_at: datetime
    source: ObservationSource = ObservationSource.MANUAL
    device_id: str | None = Field(default=None, max_length=120)
    provenance: dict[str, Any] = Field(default_factory=dict)


class ObservationOut(ORMModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    patient_id: uuid.UUID
    track: str | None = None
    metric_code: str
    value_num: float | None = None
    value_text: str | None = None
    unit: str | None = None
    effective_at: datetime
    source: str
    status: str
    provenance: dict = Field(default_factory=dict)
    quality_flags: list = Field(default_factory=list)
    device_id: str | None = None
    created_at: datetime


class WearableObservationItem(BaseModel):
    metric_code: str = Field(min_length=2, max_length=60)
    value_num: float
    unit: str | None = Field(default=None, max_length=30)
    effective_at: datetime


class WearableBatchCreate(BaseModel):
    patient_id: uuid.UUID
    track: Track = Track.CORE
    source_system: Literal["apple_health", "garmin", "fitbit", "sahatna", "csv", "manual_device"] = "sahatna"
    device_id: str | None = Field(default=None, max_length=120)
    idempotency_key: str | None = Field(default=None, max_length=120)
    observations: list[WearableObservationItem] = Field(min_length=1, max_length=1000)
    trigger_pipeline: bool = False


class WearableBatchOut(ORMModel):
    id: uuid.UUID
    patient_id: uuid.UUID
    source_system: str
    device_id: str | None = None
    status: str
    received_count: int
    accepted_count: int
    rejected: list = Field(default_factory=list)
    job_id: uuid.UUID | None = None
    created_at: datetime


class CheckInCreate(BaseModel):
    patient_id: uuid.UUID
    track: Track = Track.CORE
    kind: Literal["text", "voice", "readiness"] = "text"
    effective_at: datetime | None = None
    mood_score: int | None = Field(default=None, ge=0, le=10)
    craving_score: int | None = Field(default=None, ge=0, le=10)
    stress_score: int | None = Field(default=None, ge=0, le=10)
    sleep_quality: int | None = Field(default=None, ge=0, le=10)
    sleep_hours_reported: float | None = Field(default=None, ge=0, le=20)
    text: str | None = Field(default=None, max_length=4000)
    transcript_source: Literal["browser_speech", "typed", "imported"] | None = None
    symptoms: list[str] = Field(default_factory=list)
    self_reported_crisis: bool = False
    extra: dict[str, Any] = Field(default_factory=dict)
    trigger_pipeline: bool = True


class CheckInOut(ORMModel):
    id: uuid.UUID
    patient_id: uuid.UUID
    track: str
    kind: str
    effective_at: datetime
    mood_score: int | None = None
    craving_score: int | None = None
    stress_score: int | None = None
    sleep_quality: int | None = None
    text: str | None = None
    transcript_source: str | None = None
    symptoms: list = Field(default_factory=list)
    self_reported_crisis: bool
    extra: dict = Field(default_factory=dict)
    created_at: datetime


class ScreeningCreate(BaseModel):
    patient_id: uuid.UUID
    programme: str = Field(default="IFHAS", max_length=60)
    screened_at: datetime | None = None
    screening_site: str | None = Field(default=None, max_length=200)
    hba1c: float | None = Field(default=None, ge=3.0, le=20.0)
    bp_systolic: float | None = Field(default=None, ge=50.0, le=280.0)
    bp_diastolic: float | None = Field(default=None, ge=30.0, le=180.0)
    phq9_item_responses: list[int] | None = Field(default=None, min_length=9, max_length=9)
    phq9_score: int | None = Field(default=None, ge=0, le=27)
    total_cholesterol: float | None = Field(default=None, ge=50.0, le=700.0)
    ldl_cholesterol: float | None = Field(default=None, ge=15.0, le=500.0)
    hdl_cholesterol: float | None = Field(default=None, ge=10.0, le=180.0)
    triglycerides: float | None = Field(default=None, ge=20.0, le=2000.0)
    steps: float | None = Field(default=None, ge=0.0, le=100000.0)
    notes: str | None = None
    trigger_pipeline: bool = True


class ScreeningOut(ORMModel):
    id: uuid.UUID
    patient_id: uuid.UUID
    programme: str
    screened_at: datetime
    screening_site: str | None = None
    phq9_item_responses: list | None = None
    notes: str | None = None
    created_at: datetime


class CognitiveTrialInput(BaseModel):
    task_type: Literal["sequence_4key", "sequence_6key", "audio_memory", "visual_memory", "rule_switch", "delayed_recall"]
    modality: Literal["visual", "auditory", "audiovisual", "executive", "recall"]
    expected: list[Any]
    response: list[Any]
    reaction_time_ms: float = Field(ge=50.0, le=60000.0)
    correct: bool


class CognitiveAssessmentCreate(BaseModel):
    patient_id: uuid.UUID
    started_at: datetime | None = None
    completed_at: datetime | None = None
    assessment_language: Literal["en", "ar"] = "en"
    environment: dict[str, Any] = Field(default_factory=dict)
    raw_trials: list[CognitiveTrialInput] = Field(min_length=1, max_length=200)
    trigger_pipeline: bool = True


class CognitiveAssessmentOut(ORMModel):
    id: uuid.UUID
    patient_id: uuid.UUID
    session_index: int
    started_at: datetime
    completed_at: datetime | None = None
    assessment_language: str
    environment: dict = Field(default_factory=dict)
    raw_trials: list = Field(default_factory=list)
    derived_metrics: dict = Field(default_factory=dict)
    status: str
    created_at: datetime


class WorkplaceCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    location: str | None = Field(default=None, max_length=300)
    environment_type: Literal["outdoor", "indoor", "mixed"] = "outdoor"


class WorkplaceOut(ORMModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    location: str | None = None
    environment_type: str | None = None
    is_active: bool


class DepartmentCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    workplace_id: uuid.UUID | None = None
    min_group_size_for_reporting: int = Field(default=5, ge=3, le=50)


class DepartmentOut(ORMModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    workplace_id: uuid.UUID | None = None
    name: str
    min_group_size_for_reporting: int
    is_active: bool


class WorkplaceAssessmentCreate(BaseModel):
    department_id: uuid.UUID | None = None
    workplace_id: uuid.UUID | None = None
    measured_at: datetime | None = None
    ambient_temp_c: float | None = Field(default=None, ge=-20.0, le=65.0)
    relative_humidity_pct: float | None = Field(default=None, ge=0.0, le=100.0)
    wbgt_c: float | None = Field(default=None, ge=-10.0, le=60.0)
    noise_db: float | None = Field(default=None, ge=20.0, le=150.0)
    lighting_lux: float | None = Field(default=None, ge=0.0, le=200000.0)
    ergonomics_checklist: dict[str, Any] = Field(default_factory=dict)
    source: Literal["manual", "sensor", "weather_api"] = "manual"


class WorkplaceAssessmentOut(ORMModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    department_id: uuid.UUID | None = None
    workplace_id: uuid.UUID | None = None
    measured_at: datetime
    ambient_temp_c: float | None = None
    relative_humidity_pct: float | None = None
    heat_index_c: float | None = None
    wbgt_c: float | None = None
    noise_db: float | None = None
    lighting_lux: float | None = None
    ergonomics_checklist: dict = Field(default_factory=dict)
    source: str
    created_at: datetime


class WorkerReadinessCreate(BaseModel):
    patient_id: uuid.UUID
    readiness_score: int = Field(ge=0, le=10)
    fatigue_feeling: Literal["fresh", "mild_fatigue", "exhausted", "dizzy_heat_illness"] = "fresh"
    hydrated: bool = True
    shift_duration_hours: float | None = Field(default=None, ge=0.0, le=24.0)
    core_temp_est_c: float | None = Field(default=None, ge=33.0, le=44.0)
    hr_recovery_minutes: float | None = Field(default=None, ge=1.0, le=180.0)
    sleep_debt_hours: float | None = Field(default=None, ge=0.0, le=40.0)
    hrv_rmssd: float | None = Field(default=None, ge=3.0, le=250.0)
    voice_note: str | None = Field(default=None, max_length=2000)
    trigger_pipeline: bool = True
