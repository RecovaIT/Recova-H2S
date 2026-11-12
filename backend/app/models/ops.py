"""Audit trail, background jobs, benchmarks and integration configuration."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Timestamped, UUIDPk


class AuditEvent(UUIDPk, Base):
    """Append-only audit log. Never store passwords, tokens or raw PHI payloads here."""

    __tablename__ = "audit_events"

    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    organization_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="SET NULL"), index=True)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), index=True)
    actor_label: Mapped[str] = mapped_column(String(80), nullable=False)  # email or system:<component>
    action: Mapped[str] = mapped_column(String(80), nullable=False)       # e.g. patient.create, review.sign
    resource_type: Mapped[str] = mapped_column(String(60), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(64))
    patient_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    outcome: Mapped[str] = mapped_column(String(20), nullable=False, default="success")  # success|denied|failure
    changes: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)  # {field: {before, after}} (non-sensitive)
    details: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    ip_address: Mapped[str | None] = mapped_column(String(64))
    request_id: Mapped[str | None] = mapped_column(String(64))


Index("ix_audit_org_time", AuditEvent.organization_id, AuditEvent.occurred_at)


class Job(UUIDPk, Timestamped, Base):
    """Persistent background job (DB-backed queue, SKIP LOCKED)."""

    __tablename__ = "jobs"
    __table_args__ = (UniqueConstraint("idempotency_key", name="uq_jobs_idempotency_key"),)

    organization_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    job_type: Mapped[str] = mapped_column(String(60), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="queued", index=True)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    result: Mapped[dict | None] = mapped_column(JSONB)
    idempotency_key: Mapped[str | None] = mapped_column(String(160))
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=120)
    run_after: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    locked_by: Mapped[str | None] = mapped_column(String(80))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    history: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)  # [{attempt, started, finished, status, error}]
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))


class BenchmarkRun(UUIDPk, Timestamped, Base):
    """Execution of the benchmark suite against the real engine (isolated synthetic fixtures)."""

    __tablename__ = "benchmark_runs"

    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    suite_name: Mapped[str] = mapped_column(String(80), nullable=False)
    suite_version: Mapped[str] = mapped_column(String(20), nullable=False)
    algorithm_version: Mapped[str] = mapped_column(String(20), nullable=False)
    tracks: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="queued")
    started_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    metrics: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)  # computed from case results only
    total_cases: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    passed_cases: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error: Mapped[str | None] = mapped_column(Text)
    job_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))


class BenchmarkCaseResult(UUIDPk, Timestamped, Base):
    __tablename__ = "benchmark_case_results"
    __table_args__ = (UniqueConstraint("benchmark_run_id", "case_id", name="uq_benchmark_case"),)

    benchmark_run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("benchmark_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    case_id: Mapped[str] = mapped_column(String(40), nullable=False)
    track: Mapped[str] = mapped_column(String(20), nullable=False)
    scenario: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(String(40), nullable=False)  # normal|gradual_decline|missing_data|acute_emergency|confounder|consent
    expected: Mapped[dict] = mapped_column(JSONB, nullable=False)
    actual: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    failure_details: Mapped[str | None] = mapped_column(Text)
    pipeline_run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("pipeline_runs.id", ondelete="SET NULL"))
    duration_ms: Mapped[float | None] = mapped_column(Float)
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class IntegrationConfig(UUIDPk, Timestamped, Base):
    __tablename__ = "integration_configs"
    __table_args__ = (UniqueConstraint("organization_id", "integration", name="uq_integration_org"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    integration: Mapped[str] = mapped_column(String(40), nullable=False)  # malaffi|sahatna|smtp|twilio|llm
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="not_configured")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    settings: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)  # non-secret settings
    secrets_encrypted: Mapped[str | None] = mapped_column(Text)  # Fernet-encrypted JSON
    last_tested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_test_result: Mapped[dict | None] = mapped_column(JSONB)
