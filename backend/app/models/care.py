"""Care network configuration, clinical reviews, referrals, interventions, notifications, outcomes."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, Timestamped, UUIDPk


class InsurancePlan(UUIDPk, Timestamped, Base):
    """Organisation-configured insurance plan / network tier (e.g. Thiqa, Basic, Enhanced)."""

    __tablename__ = "insurance_plans"
    __table_args__ = (UniqueConstraint("organization_id", "code", name="uq_insurance_plan_org_code"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(40), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    payer_name: Mapped[str | None] = mapped_column(String(200))
    network_tier: Mapped[str | None] = mapped_column(String(40))
    covered_pathways: Mapped[list[str]] = mapped_column(ARRAY(String(40)), nullable=False, default=list)
    requires_preauthorization: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    verification_source: Mapped[str | None] = mapped_column(String(200))  # where coverage info was verified
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class CareFacility(UUIDPk, Timestamped, Base):
    """Organisation-configured referral destination (clinic, specialist, tele-consult service)."""

    __tablename__ = "care_facilities"
    __table_args__ = (UniqueConstraint("organization_id", "name", name="uq_facility_org_name"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    facility_type: Mapped[str] = mapped_column(String(40), nullable=False)  # primary_care|specialist|teleconsult|rehab|emergency|occupational_health|therapist
    pathways: Mapped[list[str]] = mapped_column(ARRAY(String(40)), nullable=False, default=list)
    specialties: Mapped[list[str]] = mapped_column(ARRAY(String(60)), nullable=False, default=list)
    accepted_plan_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)), nullable=False, default=list)
    address: Mapped[str | None] = mapped_column(String(300))
    contact_phone: Mapped[str | None] = mapped_column(String(40))
    contact_email: Mapped[str | None] = mapped_column(String(320))
    accepting_referrals: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    typical_wait_days: Mapped[int | None] = mapped_column(Integer)
    fhir_endpoint: Mapped[str | None] = mapped_column(String(300))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class ClinicalReview(UUIDPk, Timestamped, Base):
    """Human-in-the-loop DECIDE-AI sign-off of a pipeline run."""

    __tablename__ = "clinical_reviews"

    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("pipeline_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True)
    reviewer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    reviewer_role: Mapped[str] = mapped_column(String(40), nullable=False)
    reviewer_license: Mapped[str | None] = mapped_column(String(80))
    decision: Mapped[str] = mapped_column(String(30), nullable=False)
    agrees_with_tier: Mapped[bool | None] = mapped_column(Boolean)
    clinician_notes: Mapped[str | None] = mapped_column(Text)
    modified_plan: Mapped[dict | None] = mapped_column(JSONB)
    lab_request: Mapped[dict | None] = mapped_column(JSONB)
    synthesis_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("clinical_syntheses.id", ondelete="SET NULL"))
    signed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    signature_hash: Mapped[str] = mapped_column(String(128), nullable=False)  # hash over run+decision+reviewer+time


class Referral(UUIDPk, Timestamped, Base):
    __tablename__ = "referrals"

    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True)
    run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("pipeline_runs.id", ondelete="SET NULL"), index=True)
    track: Mapped[str] = mapped_column(String(20), nullable=False)
    pathway: Mapped[str] = mapped_column(String(40), nullable=False)
    priority: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="proposed")
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    rule_trace: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)  # which configured rule produced it
    facility_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("care_facilities.id", ondelete="SET NULL"))
    insurance_plan_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("insurance_plans.id", ondelete="SET NULL"))
    coverage_status: Mapped[str] = mapped_column(String(30), nullable=False, default="unknown")  # covered|not_covered|unknown|no_plan
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), index=True)
    owner_facility_label: Mapped[str | None] = mapped_column(String(200))
    approved_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("clinical_reviews.id", ondelete="SET NULL"))
    appointment_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    appointment_reference: Mapped[str | None] = mapped_column(String(200))
    target_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sla_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    sla_status: Mapped[str] = mapped_column(String(20), nullable=False, default="not_applicable")
    escalation_level: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    consultation_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    follow_up_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    outcome_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_emergency: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    events: Mapped[list["ReferralEvent"]] = relationship(back_populates="referral", order_by="ReferralEvent.created_at", cascade="all, delete-orphan")


Index("ix_referrals_org_status", Referral.organization_id, Referral.status)


class ReferralEvent(UUIDPk, Timestamped, Base):
    __tablename__ = "referral_events"

    referral_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("referrals.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)  # status_change|note|escalation|sla_warning|notification|missed_appointment
    from_status: Mapped[str | None] = mapped_column(String(30))
    to_status: Mapped[str | None] = mapped_column(String(30))
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    actor_label: Mapped[str] = mapped_column(String(80), nullable=False, default="user")  # user|system:agent6|system:sla_monitor
    details: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    referral: Mapped[Referral] = relationship(back_populates="events")


class OutcomeVerification(UUIDPk, Timestamped, Base):
    __tablename__ = "outcome_verifications"

    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    referral_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("referrals.id", ondelete="CASCADE"), nullable=False, unique=True)
    verified_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    outcome: Mapped[str] = mapped_column(String(40), nullable=False)  # improved|stable|deteriorated|relapsed|lost_to_follow_up|referred_onward
    verification_method: Mapped[str] = mapped_column(String(40), nullable=False)  # clinic_visit|teleconsult|phone|record_review|lab_result
    notes: Mapped[str | None] = mapped_column(Text)
    follow_up_run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("pipeline_runs.id", ondelete="SET NULL"))
    verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Intervention(UUIDPk, Timestamped, Base):
    __tablename__ = "interventions"

    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    track: Mapped[str] = mapped_column(String(20), nullable=False)
    patient_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"), index=True)
    department_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("departments.id", ondelete="CASCADE"), index=True)
    referral_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("referrals.id", ondelete="SET NULL"))
    run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("pipeline_runs.id", ondelete="SET NULL"))
    intervention_type: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="planned")
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    details: Mapped[str | None] = mapped_column(Text)
    rule_trace: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    assigned_to_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    created_by_label: Mapped[str] = mapped_column(String(80), nullable=False, default="user")


class Notification(UUIDPk, Timestamped, Base):
    __tablename__ = "notifications"

    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="queued")
    category: Mapped[str] = mapped_column(String(40), nullable=False)  # emergency|referral|sla|reminder|account|intervention
    recipient_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    recipient_patient_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"), index=True)
    recipient_address_masked: Mapped[str | None] = mapped_column(String(120))
    subject: Mapped[str] = mapped_column(String(300), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    referral_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("referrals.id", ondelete="SET NULL"), index=True)
    emergency_event_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("emergency_events.id", ondelete="SET NULL"))
    provider: Mapped[str | None] = mapped_column(String(40))
    provider_message_id: Mapped[str | None] = mapped_column(String(200))
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(Text)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    idempotency_key: Mapped[str | None] = mapped_column(String(160), unique=True)
