"""Strict Pydantic input/output schemas for each of the 6 Recova agents."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class Gate1Input(BaseModel):
    organization_id: uuid.UUID
    patient_id: uuid.UUID
    track: str
    as_of: datetime
    required_scope: str = "data_processing"


class Gate1Output(BaseModel):
    consent_valid: bool
    active_scopes: list[str] = Field(default_factory=list)
    revoked_or_missing_scopes: list[str] = Field(default_factory=list)
    present_streams: list[str] = Field(default_factory=list)
    missing_streams: list[str] = Field(default_factory=list)
    data_completeness_pct: float
    validation_warnings: list[str] = Field(default_factory=list)
    allow_routine_processing: bool
    allow_emergency_screen: bool


class Gate2Input(BaseModel):
    patient_id: uuid.UUID
    track: str
    as_of: datetime
    recent_observations_count: int
    recent_checkins_count: int


class Gate2Evidence(BaseModel):
    rule_code: str
    severity: str
    source: str
    summary: str
    value: Any = None
    observed_at: datetime | None = None


class Gate2Output(BaseModel):
    rules_version: str
    emergency_triggered: bool
    rule_codes: list[str] = Field(default_factory=list)
    evidence: list[Gate2Evidence] = Field(default_factory=list)
    emergency_event_id: uuid.UUID | None = None


class Agent3Input(BaseModel):
    patient_id: uuid.UUID
    track: str
    as_of: datetime
    evaluation_window_days: int


class Agent3Output(BaseModel):
    present_streams: list[str] = Field(default_factory=list)
    metrics_with_data: list[str] = Field(default_factory=list)
    total_observations_considered: int
    baseline_windows_count: dict[str, int] = Field(default_factory=dict)
    current_windows_count: dict[str, int] = Field(default_factory=dict)
    confounders_detected: dict[str, Any] = Field(default_factory=dict)
    fhir_observations_mapped: int


class Agent4Input(BaseModel):
    track: str
    algorithm_version: str
    metrics_Count: int = Field(alias="metrics_count")

    model_config = {"populate_by_name": True}


class Agent4Output(BaseModel):
    scoring_result_id: uuid.UUID
    algorithm_version: str
    risk_tier: str
    confidence_index: float
    composite_index: float | None = None
    primary_metric_code: str | None = None
    primary_z: float | None = None
    missing_streams: list[str] = Field(default_factory=list)
    confounders_applied: list[str] = Field(default_factory=list)
    metric_results: list[dict[str, Any]] = Field(default_factory=list)


class Agent5Input(BaseModel):
    track: str
    risk_tier: str
    confidence_index: float
    primary_metric_code: str | None = None
    primary_z: float | None = None
    llm_consent_granted: bool


class Agent5Output(BaseModel):
    synthesis_id: uuid.UUID
    status: str
    provider: str | None = None
    model: str | None = None
    prompt_version: str
    summary_en: str | None = None
    summary_ar: str | None = None
    error: str | None = None
    is_draft_only: bool = True


class Agent6Input(BaseModel):
    track: str
    risk_tier: str
    is_emergency: bool
    insurance_plan_id: uuid.UUID | None = None


class Agent6Output(BaseModel):
    pathway: str
    priority: str
    referral_id: uuid.UUID | None = None
    referral_status: str | None = None
    coverage_status: str
    facility_id: uuid.UUID | None = None
    facility_name: str | None = None
    sla_due_at: datetime | None = None
    interventions_created: list[uuid.UUID] = Field(default_factory=list)
    notifications_dispatched: list[dict[str, Any]] = Field(default_factory=list)
    rule_trace: dict[str, Any] = Field(default_factory=dict)
