"""Patients/participants, consent and longitudinal clinical/workplace data."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, Timestamped, UUIDPk


def _org_fk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)


class Workplace(UUIDPk, Timestamped, Base):
    """WorkSafe: a physical site (e.g. construction site, plant)."""

    __tablename__ = "workplaces"
    __table_args__ = (UniqueConstraint("organization_id", "name", name="uq_workplace_org_name"),)

    organization_id: Mapped[uuid.UUID] = _org_fk()
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    location: Mapped[str | None] = mapped_column(String(300))
    environment_type: Mapped[str | None] = mapped_column(String(60))  # outdoor|indoor|mixed
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Department(UUIDPk, Timestamped, Base):
    __tablename__ = "departments"
    __table_args__ = (UniqueConstraint("organization_id", "name", name="uq_department_org_name"),)

    organization_id: Mapped[uuid.UUID] = _org_fk()
    workplace_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("workplaces.id", ondelete="SET NULL"))
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    min_group_size_for_reporting: Mapped[int] = mapped_column(Integer, nullable=False, default=5)  # k-anonymity threshold
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Patient(UUIDPk, Timestamped, Base):
    """A patient or employee participant. Synthetic demo records MUST set is_synthetic."""

    __tablename__ = "patients"
    __table_args__ = (UniqueConstraint("organization_id", "mrn", name="uq_patient_org_mrn"),)

    organization_id: Mapped[uuid.UUID] = _org_fk()
    participant_type: Mapped[str] = mapped_column(String(20), nullable=False, default="patient")
    mrn: Mapped[str] = mapped_column(String(64), nullable=False)  # org-local record number / employee number
    given_name: Mapped[str] = mapped_column(String(120), nullable=False)
    family_name: Mapped[str] = mapped_column(String(120), nullable=False)
    date_of_birth: Mapped[date | None] = mapped_column(Date)
    sex: Mapped[str | None] = mapped_column(String(20))  # male|female|other|unknown (FHIR AdministrativeGender)
    preferred_language: Mapped[str] = mapped_column(String(5), nullable=False, default="en")
    # Encrypted-at-rest identifiers & contact details (Fernet)
    national_id_encrypted: Mapped[str | None] = mapped_column(Text)
    phone_encrypted: Mapped[str | None] = mapped_column(Text)
    email_encrypted: Mapped[str | None] = mapped_column(Text)
    emergency_contact_encrypted: Mapped[str | None] = mapped_column(Text)  # JSON string
    # Confounder profile (Neuro adjustments etc.)
    education_level: Mapped[str | None] = mapped_column(String(40))  # none|primary|secondary|tertiary|postgraduate
    primary_language_matches_assessment: Mapped[bool | None] = mapped_column(Boolean)
    hearing_status: Mapped[str | None] = mapped_column(String(40))  # normal|mild_loss|moderate_loss|severe_loss|aided
    vision_status: Mapped[str | None] = mapped_column(String(40))   # normal|corrected|mild_impairment|severe_impairment
    clinical_history: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)  # conditions, medications, discharge info
    # Insurance (Loop / referral routing)
    insurance_plan_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("insurance_plans.id", ondelete="SET NULL"))
    insurance_member_id_encrypted: Mapped[str | None] = mapped_column(Text)
    # WorkSafe
    department_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("departments.id", ondelete="SET NULL"), index=True)
    job_role: Mapped[str | None] = mapped_column(String(120))
    # Ownership / portal
    primary_clinician_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    portal_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))

    enrollments: Mapped[list["TrackEnrollment"]] = relationship(back_populates="patient", cascade="all, delete-orphan")


Index("ix_patients_org_name", Patient.organization_id, Patient.family_name, Patient.given_name)


class TrackEnrollment(UUIDPk, Timestamped, Base):
    __tablename__ = "track_enrollments"
    __table_args__ = (UniqueConstraint("patient_id", "track", name="uq_enrollment_patient_track"),)

    organization_id: Mapped[uuid.UUID] = _org_fk()
    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True)
    track: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")  # active|paused|discharged
    enrolled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    context: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)  # e.g. discharge date, programme
    latest_risk_tier: Mapped[str | None] = mapped_column(String(20))
    latest_run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    latest_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    authority_actor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    authority_reason: Mapped[str | None] = mapped_column(Text)
    history: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    patient: Mapped[Patient] = relationship(back_populates="enrollments")


class Consent(UUIDPk, Timestamped, Base):
    __tablename__ = "consents"

    organization_id: Mapped[uuid.UUID] = _org_fk()
    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True)
    scope: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    method: Mapped[str] = mapped_column(String(40), nullable=False, default="written")  # written|verbal_witnessed|electronic|guardian
    policy_version: Mapped[str] = mapped_column(String(40), nullable=False, default="v1.0")
    authority_to_act: Mapped[str] = mapped_column(String(80), nullable=False, default="self")  # self|legal_guardian|facility_admin
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    granted_by_name: Mapped[str | None] = mapped_column(String(200))  # patient or legal guardian
    recorded_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    evidence_reference: Mapped[str | None] = mapped_column(String(300))
    notes: Mapped[str | None] = mapped_column(Text)


Index("ix_consents_patient_scope", Consent.patient_id, Consent.scope, Consent.effective_at)


class WearableIngestionBatch(UUIDPk, Timestamped, Base):
    __tablename__ = "wearable_ingestion_batches"

    organization_id: Mapped[uuid.UUID] = _org_fk()
    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True)
    source_system: Mapped[str] = mapped_column(String(60), nullable=False)  # apple_health|garmin|fitbit|sahatna|csv|manual_device
    device_id: Mapped[str | None] = mapped_column(String(120))
    idempotency_key: Mapped[str | None] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="received")  # received|processed|partially_processed|failed
    received_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    accepted_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rejected: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    submitted_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    job_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))

    __table_args__ = (UniqueConstraint("organization_id", "idempotency_key", name="uq_wearable_batch_idem"),)


class CheckIn(UUIDPk, Timestamped, Base):
    """Daily voice/text check-in (Core) or readiness check (WorkSafe)."""

    __tablename__ = "check_ins"
    __table_args__ = (UniqueConstraint("patient_id", "idempotency_key", name="uq_checkin_patient_idem"),)

    organization_id: Mapped[uuid.UUID] = _org_fk()
    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True)
    track: Mapped[str] = mapped_column(String(20), nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False, default="text")  # text|voice|readiness
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    mood_score: Mapped[int | None] = mapped_column(Integer)        # 0-10 (10 best)
    craving_score: Mapped[int | None] = mapped_column(Integer)     # 0-10 (10 worst)
    stress_score: Mapped[int | None] = mapped_column(Integer)      # 0-10 (10 worst)
    sleep_quality: Mapped[int | None] = mapped_column(Integer)     # 0-10 (10 best)
    text: Mapped[str | None] = mapped_column(Text)                 # free text or voice transcript
    transcript_source: Mapped[str | None] = mapped_column(String(40))  # browser_speech|typed|imported
    symptoms: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)  # structured symptom codes
    self_reported_crisis: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    submitted_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    idempotency_key: Mapped[str | None] = mapped_column(String(160))
    extra: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)  # readiness answers etc.


class ScreeningRecord(UUIDPk, Timestamped, Base):
    """IFHAS screening encounter (Loop). Biomarker values stored as Observations."""

    __tablename__ = "screening_records"

    organization_id: Mapped[uuid.UUID] = _org_fk()
    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True)
    programme: Mapped[str] = mapped_column(String(60), nullable=False, default="IFHAS")
    screened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    screening_site: Mapped[str | None] = mapped_column(String(200))
    phq9_item_responses: Mapped[list | None] = mapped_column(JSONB)  # 9 integers 0-3
    notes: Mapped[str | None] = mapped_column(Text)
    recorded_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))


class CognitiveAssessment(UUIDPk, Timestamped, Base):
    """Neuro: one Multi-Cognitive Studio session with raw trial-level data."""

    __tablename__ = "cognitive_assessments"
    __table_args__ = (UniqueConstraint("patient_id", "idempotency_key", name="uq_cognitive_patient_idem"),)

    organization_id: Mapped[uuid.UUID] = _org_fk()
    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True)
    enrollment_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("track_enrollments.id", ondelete="SET NULL"), index=True)
    session_index: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-based count for practice-effect modelling
    task_version: Mapped[str | None] = mapped_column(String(60))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    assessment_language: Mapped[str] = mapped_column(String(5), nullable=False, default="en")
    administered_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    idempotency_key: Mapped[str | None] = mapped_column(String(160))
    environment: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)  # device, audio enabled, supervised
    raw_trials: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)  # per-task trial events
    derived_metrics: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="completed")  # in_progress|completed|abandoned|practice


class WorkplaceAssessment(UUIDPk, Timestamped, Base):
    """WorkSafe: environmental & ergonomic readings for a department/site at a time."""

    __tablename__ = "workplace_assessments"

    organization_id: Mapped[uuid.UUID] = _org_fk()
    department_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("departments.id", ondelete="CASCADE"), index=True)
    workplace_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("workplaces.id", ondelete="CASCADE"))
    measured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ambient_temp_c: Mapped[float | None] = mapped_column(Float)
    relative_humidity_pct: Mapped[float | None] = mapped_column(Float)
    heat_index_c: Mapped[float | None] = mapped_column(Float)  # computed (Rothfusz/NWS)
    wbgt_c: Mapped[float | None] = mapped_column(Float)        # if measured by instrument
    noise_db: Mapped[float | None] = mapped_column(Float)
    lighting_lux: Mapped[float | None] = mapped_column(Float)
    ergonomics_checklist: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    source: Mapped[str] = mapped_column(String(40), nullable=False, default="manual")  # manual|sensor|weather_api
    recorded_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))


class Observation(UUIDPk, Timestamped, Base):
    """Normalised longitudinal observation (FHIR Observation-compatible)."""

    __tablename__ = "observations"

    organization_id: Mapped[uuid.UUID] = _org_fk()
    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False)
    track: Mapped[str | None] = mapped_column(String(20))
    metric_code: Mapped[str] = mapped_column(String(60), nullable=False)  # see app.engine.metrics catalogue
    value_num: Mapped[float | None] = mapped_column(Float)
    value_text: Mapped[str | None] = mapped_column(Text)
    unit: Mapped[str | None] = mapped_column(String(30))
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="final")  # final|preliminary|entered_in_error
    provenance: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    quality_flags: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    device_id: Mapped[str | None] = mapped_column(String(120))
    wearable_batch_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("wearable_ingestion_batches.id", ondelete="SET NULL"))
    check_in_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("check_ins.id", ondelete="CASCADE"))
    screening_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("screening_records.id", ondelete="CASCADE"))
    cognitive_assessment_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("cognitive_assessments.id", ondelete="CASCADE"))
    workplace_assessment_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("workplace_assessments.id", ondelete="SET NULL"))
    entered_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))


Index("ix_observations_patient_metric_time", Observation.patient_id, Observation.metric_code, Observation.effective_at)
Index("ix_observations_org_time", Observation.organization_id, Observation.effective_at)
