"""Gate 1: Consent, Governance & Guardrail Agent."""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.schemas import Gate1Input, Gate1Output
from app.core.config import get_settings
from app.engine.metrics import METRIC_CATALOG, TRACK_CONFIGS
from app.models.clinical import CheckIn, CognitiveAssessment, Consent, Observation, Patient, ScreeningRecord, WorkplaceAssessment
from app.models.enums import ConsentScope, ConsentStatus


def evaluate_consents(db: Session, patient: Patient, as_of: datetime) -> tuple[set[str], set[str]]:
    """Determine effective active consent scopes for `patient` at `as_of`."""
    rows = db.scalars(
        select(Consent)
        .where(
            Consent.organization_id == patient.organization_id,
            Consent.patient_id == patient.id,
            Consent.effective_at <= as_of,
        )
        .order_by(Consent.effective_at.asc(), Consent.created_at.asc())
    ).all()

    latest_by_scope: dict[str, Consent] = {}
    for row in rows:
        latest_by_scope[row.scope] = row

    active: set[str] = set()
    revoked_or_expired: set[str] = set()
    for scope, row in latest_by_scope.items():
        if row.status != ConsentStatus.GRANTED.value or row.revoked_at is not None:
            revoked_or_expired.add(scope)
            continue
        if row.expires_at is not None and row.expires_at <= as_of:
            revoked_or_expired.add(scope)
            continue
        active.add(scope)
    return active, revoked_or_expired


def run_gate1(db: Session, patient: Patient, track: str, as_of: datetime) -> tuple[Gate1Input, Gate1Output]:
    s = get_settings()
    inp = Gate1Input(
        organization_id=patient.organization_id,
        patient_id=patient.id,
        track=track,
        as_of=as_of,
    )
    if not patient.is_active:
        return inp, Gate1Output(
            consent_valid=False,
            data_completeness_pct=0.0,
            validation_warnings=["Patient record is inactive"],
            allow_routine_processing=False,
            allow_emergency_screen=False,
        )

    active_scopes, revoked_scopes = evaluate_consents(db, patient, as_of)
    consent_valid = ConsentScope.DATA_PROCESSING.value in active_scopes

    # Determine present data streams across observations & domain tables within lookback window.
    track_cfg = TRACK_CONFIGS[track]
    lookback_start = as_of - timedelta(days=30)
    obs_rows = db.scalars(
        select(Observation).where(
            Observation.organization_id == patient.organization_id,
            Observation.patient_id == patient.id,
            Observation.effective_at <= as_of,
            Observation.effective_at >= lookback_start,
            Observation.status != "entered_in_error",
        )
    ).all()

    present_streams: set[str] = set()
    warnings: list[str] = []
    for o in obs_rows:
        spec = METRIC_CATALOG.get(o.metric_code)
        if spec:
            present_streams.add(spec.stream_name)
        if o.quality_flags:
            for fl in o.quality_flags:
                if fl not in warnings:
                    warnings.append(f"{o.metric_code}:{fl}")

    has_checkin = db.scalar(
        select(CheckIn.id)
        .where(
            CheckIn.organization_id == patient.organization_id,
            CheckIn.patient_id == patient.id,
            CheckIn.effective_at <= as_of,
            CheckIn.effective_at >= lookback_start,
        )
        .limit(1)
    )
    if has_checkin:
        present_streams.add("worker_readiness" if track == "worksafe" else "daily_checkin")

    if track == "loop":
        has_scr = db.scalar(
            select(ScreeningRecord.id)
            .where(
                ScreeningRecord.organization_id == patient.organization_id,
                ScreeningRecord.patient_id == patient.id,
                ScreeningRecord.screened_at <= as_of,
            )
            .limit(1)
        )
        if has_scr:
            present_streams.add("ifhas_phq9")

    if track == "neuro":
        has_cog = db.scalar(
            select(CognitiveAssessment.id)
            .where(
                CognitiveAssessment.organization_id == patient.organization_id,
                CognitiveAssessment.patient_id == patient.id,
                CognitiveAssessment.started_at <= as_of,
                CognitiveAssessment.status == "completed",
            )
            .limit(1)
        )
        if has_cog:
            present_streams.add("cognitive_sequence")

    if track == "worksafe" and patient.department_id:
        has_env = db.scalar(
            select(WorkplaceAssessment.id)
            .where(
                WorkplaceAssessment.organization_id == patient.organization_id,
                WorkplaceAssessment.department_id == patient.department_id,
                WorkplaceAssessment.measured_at <= as_of,
                WorkplaceAssessment.measured_at >= lookback_start,
            )
            .limit(1)
        )
        if has_env:
            present_streams.add("workplace_env")

    expected = list(track_cfg.expected_streams)
    missing = [st for st in expected if st not in present_streams]
    completeness = round(100.0 * (len(expected) - len(missing)) / max(len(expected), 1), 1)

    if not consent_valid:
        warnings.append("Mandatory consent 'data_processing' is missing, expired, or revoked.")

    out = Gate1Output(
        consent_valid=consent_valid,
        active_scopes=sorted(active_scopes),
        revoked_or_missing_scopes=sorted(revoked_scopes),
        present_streams=sorted(present_streams),
        missing_streams=missing,
        data_completeness_pct=completeness,
        validation_warnings=warnings,
        allow_routine_processing=consent_valid,
        allow_emergency_screen=consent_valid or s.emergency_screen_without_consent,
    )
    return inp, out
