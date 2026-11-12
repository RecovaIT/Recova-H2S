"""Pipeline execution, deterministic scoring, synthesis and emergency records."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, Timestamped, UUIDPk


class PersonalBaseline(UUIDPk, Timestamped, Base):
    """Personal baseline per patient/metric, versioned by algorithm version."""

    __tablename__ = "personal_baselines"
    __table_args__ = (
        UniqueConstraint("patient_id", "metric_code", "algorithm_version", name="uq_baseline_patient_metric_version"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True)
    metric_code: Mapped[str] = mapped_column(String(60), nullable=False)
    algorithm_version: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)  # established|insufficient|reset
    n_windows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    mean: Mapped[float | None] = mapped_column(Float)
    sample_sd: Mapped[float | None] = mapped_column(Float)
    window_values: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)  # [{window:"2026-11-01", value:7.4, n_obs:1}]
    window_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    window_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    established_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reset_reason: Mapped[str | None] = mapped_column(Text)


class PipelineRun(UUIDPk, Timestamped, Base):
    """One execution of the six-agent engine for a patient & track."""

    __tablename__ = "pipeline_runs"
    __table_args__ = (UniqueConstraint("organization_id", "idempotency_key", name="uq_pipeline_run_idem"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    patient_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"), index=True)
    track: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="queued")
    trigger: Mapped[str] = mapped_column(String(40), nullable=False, default="manual")  # manual|checkin|wearable|screening|assessment|scheduled|benchmark
    triggered_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    idempotency_key: Mapped[str | None] = mapped_column(String(120))
    algorithm_version: Mapped[str] = mapped_column(String(20), nullable=False)
    scoring_config_hash: Mapped[str | None] = mapped_column(String(64))
    risk_tier: Mapped[str | None] = mapped_column(String(20))
    confidence_index: Mapped[float | None] = mapped_column(Float)
    is_emergency: Mapped[bool] = mapped_column(default=False, nullable=False)
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)  # observation cut-off
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    error: Mapped[str | None] = mapped_column(Text)
    job_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    benchmark_run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("benchmark_runs.id", ondelete="CASCADE"))

    steps: Mapped[list["AgentStepResult"]] = relationship(back_populates="run", order_by="AgentStepResult.step_order", cascade="all, delete-orphan")


Index("ix_pipeline_runs_patient_created", PipelineRun.patient_id, PipelineRun.created_at)


class AgentStepResult(UUIDPk, Timestamped, Base):
    __tablename__ = "agent_step_results"
    __table_args__ = (UniqueConstraint("run_id", "agent_key", name="uq_step_run_agent"),)

    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("pipeline_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_key: Mapped[str] = mapped_column(String(40), nullable=False)  # gate1_consent|gate2_emergency|agent3_aggregator|agent4_scoring|agent5_synthesis|agent6_referral
    agent_name: Mapped[str] = mapped_column(String(120), nullable=False)
    step_order: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="waiting")
    message: Mapped[str | None] = mapped_column(Text)
    input_payload: Mapped[dict | None] = mapped_column(JSONB)
    output_payload: Mapped[dict | None] = mapped_column(JSONB)
    error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    schema_version: Mapped[str] = mapped_column(String(20), nullable=False, default="1.0")

    run: Mapped[PipelineRun] = relationship(back_populates="steps")


class ScoringResult(UUIDPk, Timestamped, Base):
    """Agent 4 deterministic output, persisted with all mathematical inputs."""

    __tablename__ = "scoring_results"

    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("pipeline_runs.id", ondelete="CASCADE"), nullable=False, unique=True)
    patient_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"), index=True)
    track: Mapped[str] = mapped_column(String(20), nullable=False)
    algorithm_version: Mapped[str] = mapped_column(String(20), nullable=False)
    risk_tier: Mapped[str] = mapped_column(String(20), nullable=False)
    confidence_index: Mapped[float] = mapped_column(Float, nullable=False)
    composite_index: Mapped[float | None] = mapped_column(Float)
    primary_metric_code: Mapped[str | None] = mapped_column(String(60))
    primary_z: Mapped[float | None] = mapped_column(Float)
    metric_results: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    missing_streams: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    confounders_applied: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    config_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ClinicalSynthesis(UUIDPk, Timestamped, Base):
    """Agent 5 output. Always a DRAFT until a clinician review is signed."""

    __tablename__ = "clinical_syntheses"

    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("pipeline_runs.id", ondelete="CASCADE"), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    provider: Mapped[str | None] = mapped_column(String(40))
    model: Mapped[str | None] = mapped_column(String(120))
    prompt_version: Mapped[str] = mapped_column(String(20), nullable=False)
    prompt_hash: Mapped[str | None] = mapped_column(String(64))
    summary_en: Mapped[str | None] = mapped_column(Text)
    summary_ar: Mapped[str | None] = mapped_column(Text)
    structured: Mapped[dict | None] = mapped_column(JSONB)
    error: Mapped[str | None] = mapped_column(Text)
    latency_ms: Mapped[int | None] = mapped_column(Integer)


class EmergencyEvent(UUIDPk, Timestamped, Base):
    __tablename__ = "emergency_events"

    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    patient_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"), index=True)
    run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("pipeline_runs.id", ondelete="CASCADE"))
    track: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")
    rule_codes: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    evidence: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    rules_version: Mapped[str] = mapped_column(String(20), nullable=False)
    acknowledged_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolution_notes: Mapped[str | None] = mapped_column(Text)
