"""Ingestion services: observations, wearables, check-ins, IFHAS screenings, Neuro assessments."""

from __future__ import annotations

import statistics
import uuid
from datetime import datetime

from sqlalchemy import select

from app.agents.orchestrator import create_pipeline_run, execute_pipeline_run
from app.api.deps import AuthContext
from app.core.errors import Conflict, NotFound, ValidationFailed
from app.core.permissions import P
from app.engine.metrics import METRIC_CATALOG, normalize_unit
from app.models.base import utcnow
from app.models.clinical import (
    CheckIn,
    CognitiveAssessment,
    Observation,
    Patient,
    ScreeningRecord,
    TrackEnrollment,
    WearableIngestionBatch,
)
from app.models.enums import ObservationSource
from app.schemas.clinical import (
    CheckInCreate,
    CognitiveAssessmentCreate,
    ObservationCreate,
    ScreeningCreate,
    WearableBatchCreate,
)
from app.schemas.common import PageParams, paginate


def _require_patient(ctx: AuthContext, patient_id: uuid.UUID) -> Patient:
    p = ctx.db.scalar(
        select(Patient).where(Patient.id == patient_id, Patient.organization_id == ctx.org_id, Patient.is_synthetic.is_(False))
    )
    if p is None:
        raise NotFound("Patient not found")
    return p


def _ensure_enrollment(ctx: AuthContext, patient: Patient, track: str) -> None:
    enr = ctx.db.scalar(
        select(TrackEnrollment).where(TrackEnrollment.patient_id == patient.id, TrackEnrollment.track == track)
    )
    if enr is None:
        ctx.db.add(
            TrackEnrollment(
                organization_id=ctx.org_id,
                patient_id=patient.id,
                track=track,
                status="active",
                enrolled_at=utcnow(),
                context={},
            )
        )
        ctx.db.flush()


def record_observation(ctx: AuthContext, req: ObservationCreate) -> Observation:
    ctx.require(P.OBSERVATIONS_WRITE)
    if req.track:
        ctx.require_track(req.track.value)
    p = _require_patient(ctx, req.patient_id)
    if req.value_num is None and req.value_text is None:
        raise ValidationFailed("Either value_num or value_text must be provided")

    val = req.value_num
    unit = req.unit
    flags: list[str] = []
    if val is not None:
        val, unit, flags = normalize_unit(req.metric_code, val, unit)
        if "out_of_physiological_bounds" in flags:
            spec = METRIC_CATALOG.get(req.metric_code)
            raise ValidationFailed(
                f"Value {val} {unit} for {req.metric_code} is outside valid bounds"
                + (f" [{spec.valid_min}, {spec.valid_max}]" if spec else "")
            )

    obs = Observation(
        organization_id=ctx.org_id,
        patient_id=p.id,
        track=req.track.value if req.track else None,
        metric_code=req.metric_code,
        value_num=val,
        value_text=req.value_text,
        unit=unit,
        effective_at=req.effective_at,
        source=req.source.value,
        provenance=req.provenance,
        quality_flags=flags,
        device_id=req.device_id,
        entered_by_id=ctx.user.id,
    )
    ctx.db.add(obs)
    ctx.db.flush()
    ctx.audit("observation.create", "observation", obs.id, patient_id=p.id, details={"metric": obs.metric_code, "source": obs.source})
    ctx.db.commit()
    return obs


def list_observations(
    ctx: AuthContext,
    patient_id: uuid.UUID,
    params: PageParams,
    *,
    metric_code: str | None = None,
    track: str | None = None,
) -> dict:
    ctx.require(P.OBSERVATIONS_READ)
    _require_patient(ctx, patient_id)
    stmt = select(Observation).where(Observation.organization_id == ctx.org_id, Observation.patient_id == patient_id)
    if metric_code:
        stmt = stmt.where(Observation.metric_code == metric_code)
    if track:
        stmt = stmt.where(Observation.track == track)
    return paginate(
        ctx.db,
        stmt,
        params,
        sortable={"effective_at": Observation.effective_at, "metric_code": Observation.metric_code},
        default_sort=Observation.effective_at.desc(),
    )


def ingest_wearable_batch(ctx: AuthContext, req: WearableBatchCreate) -> dict:
    ctx.require(P.OBSERVATIONS_WRITE)
    ctx.require_track(req.track.value)
    p = _require_patient(ctx, req.patient_id)

    if req.idempotency_key:
        existing = ctx.db.scalar(
            select(WearableIngestionBatch).where(
                WearableIngestionBatch.organization_id == ctx.org_id,
                WearableIngestionBatch.idempotency_key == req.idempotency_key,
            )
        )
        if existing is not None:
            return {"batch": existing, "run_id": None}

    batch = WearableIngestionBatch(
        organization_id=ctx.org_id,
        patient_id=p.id,
        source_system=req.source_system,
        device_id=req.device_id,
        idempotency_key=req.idempotency_key,
        status="received",
        received_count=len(req.observations),
        submitted_by_id=ctx.user.id,
    )
    ctx.db.add(batch)
    ctx.db.flush()

    accepted = 0
    rejected: list[dict] = []
    for idx, item in enumerate(req.observations):
        if item.metric_code not in METRIC_CATALOG:
            rejected.append({"index": idx, "metric_code": item.metric_code, "reason": "unknown_metric_code"})
            continue
        val, unit, flags = normalize_unit(item.metric_code, item.value_num, item.unit)
        if "out_of_physiological_bounds" in flags:
            rejected.append({"index": idx, "metric_code": item.metric_code, "value": item.value_num, "reason": "out_of_physiological_bounds"})
            continue
        ctx.db.add(
            Observation(
                organization_id=ctx.org_id,
                patient_id=p.id,
                track=req.track.value,
                metric_code=item.metric_code,
                value_num=val,
                unit=unit,
                effective_at=item.effective_at,
                source=ObservationSource.WEARABLE.value,
                provenance={"source_system": req.source_system, "batch_id": str(batch.id)},
                quality_flags=flags,
                device_id=req.device_id,
                wearable_batch_id=batch.id,
                entered_by_id=ctx.user.id,
            )
        )
        accepted += 1

    batch.accepted_count = accepted
    batch.rejected = rejected
    batch.status = "processed" if not rejected else ("partially_processed" if accepted > 0 else "failed")
    _ensure_enrollment(ctx, p, req.track.value)

    ctx.audit(
        "wearable.ingest",
        "wearable_ingestion_batch",
        batch.id,
        patient_id=p.id,
        details={"source_system": req.source_system, "received": batch.received_count, "accepted": accepted, "rejected": len(rejected)},
    )
    ctx.db.commit()

    run = None
    if req.trigger_pipeline and accepted > 0:
        run = create_pipeline_run(
            ctx.db,
            organization_id=ctx.org_id,
            patient_id=p.id,
            track=req.track.value,
            trigger="wearable",
            triggered_by_id=ctx.user.id,
        )
        ctx.db.commit()
        run = execute_pipeline_run(ctx.db, run.id)

    return {"batch": batch, "run_id": run.id if run else None}


def create_checkin(ctx: AuthContext, req: CheckInCreate) -> dict:
    ctx.require(P.OBSERVATIONS_WRITE)
    ctx.require_track(req.track.value)
    p = _require_patient(ctx, req.patient_id)
    effective_at = req.effective_at or utcnow()

    chk = CheckIn(
        organization_id=ctx.org_id,
        patient_id=p.id,
        track=req.track.value,
        kind=req.kind,
        effective_at=effective_at,
        mood_score=req.mood_score,
        craving_score=req.craving_score,
        stress_score=req.stress_score,
        sleep_quality=req.sleep_quality,
        text=req.text,
        transcript_source=req.transcript_source,
        symptoms=req.symptoms,
        self_reported_crisis=req.self_reported_crisis,
        submitted_by_id=ctx.user.id,
        extra=req.extra,
    )
    ctx.db.add(chk)
    ctx.db.flush()

    mapped = [
        ("mood_score", req.mood_score, "score"),
        ("craving_score", req.craving_score, "score"),
        ("stress_score", req.stress_score, "score"),
        ("sleep_quality", req.sleep_quality, "score"),
        ("sleep_hours", req.sleep_hours_reported, "h"),
    ]
    for code, val, unit in mapped:
        if val is not None:
            ctx.db.add(
                Observation(
                    organization_id=ctx.org_id,
                    patient_id=p.id,
                    track=req.track.value,
                    metric_code=code,
                    value_num=float(val),
                    unit=unit,
                    effective_at=effective_at,
                    source=ObservationSource.CHECKIN.value,
                    check_in_id=chk.id,
                    entered_by_id=ctx.user.id,
                )
            )
    _ensure_enrollment(ctx, p, req.track.value)
    ctx.audit("checkin.create", "check_in", chk.id, patient_id=p.id, details={"track": req.track.value, "kind": req.kind})
    ctx.db.commit()

    run = None
    if req.trigger_pipeline:
        run = create_pipeline_run(
            ctx.db,
            organization_id=ctx.org_id,
            patient_id=p.id,
            track=req.track.value,
            trigger="checkin",
            triggered_by_id=ctx.user.id,
            as_of=effective_at,
        )
        ctx.db.commit()
        run = execute_pipeline_run(ctx.db, run.id)

    return {"check_in": chk, "run_id": run.id if run else None}


def list_checkins(ctx: AuthContext, patient_id: uuid.UUID) -> list[CheckIn]:
    ctx.require(P.OBSERVATIONS_READ)
    _require_patient(ctx, patient_id)
    return list(
        ctx.db.scalars(
            select(CheckIn).where(CheckIn.organization_id == ctx.org_id, CheckIn.patient_id == patient_id).order_by(CheckIn.effective_at.desc())
        ).all()
    )


def create_screening(ctx: AuthContext, req: ScreeningCreate) -> dict:
    ctx.require(P.OBSERVATIONS_WRITE)
    ctx.require_track("loop")
    p = _require_patient(ctx, req.patient_id)
    screened_at = req.screened_at or utcnow()

    phq9_total = req.phq9_score
    if req.phq9_item_responses is not None:
        if any(x < 0 or x > 3 for x in req.phq9_item_responses):
            raise ValidationFailed("PHQ-9 item responses must each be between 0 and 3")
        phq9_total = sum(req.phq9_item_responses)

    scr = ScreeningRecord(
        organization_id=ctx.org_id,
        patient_id=p.id,
        programme=req.programme,
        screened_at=screened_at,
        screening_site=req.screening_site,
        phq9_item_responses=req.phq9_item_responses,
        notes=req.notes,
        recorded_by_id=ctx.user.id,
    )
    ctx.db.add(scr)
    ctx.db.flush()

    obs_pairs = [
        ("hba1c", req.hba1c, "%"),
        ("bp_systolic", req.bp_systolic, "mmHg"),
        ("bp_diastolic", req.bp_diastolic, "mmHg"),
        ("phq9_score", float(phq9_total) if phq9_total is not None else None, "score"),
        ("total_cholesterol", req.total_cholesterol, "mg/dL"),
        ("ldl_cholesterol", req.ldl_cholesterol, "mg/dL"),
        ("hdl_cholesterol", req.hdl_cholesterol, "mg/dL"),
        ("triglycerides", req.triglycerides, "mg/dL"),
        ("steps", req.steps, "steps/d"),
    ]
    for code, val, unit in obs_pairs:
        if val is not None:
            ctx.db.add(
                Observation(
                    organization_id=ctx.org_id,
                    patient_id=p.id,
                    track="loop",
                    metric_code=code,
                    value_num=float(val),
                    unit=unit,
                    effective_at=screened_at,
                    source=ObservationSource.SCREENING.value,
                    screening_id=scr.id,
                    entered_by_id=ctx.user.id,
                )
            )
    _ensure_enrollment(ctx, p, "loop")
    ctx.audit("screening.create", "screening_record", scr.id, patient_id=p.id, details={"programme": req.programme})
    ctx.db.commit()

    run = None
    if req.trigger_pipeline:
        run = create_pipeline_run(
            ctx.db,
            organization_id=ctx.org_id,
            patient_id=p.id,
            track="loop",
            trigger="screening",
            triggered_by_id=ctx.user.id,
            as_of=screened_at,
        )
        ctx.db.commit()
        run = execute_pipeline_run(ctx.db, run.id)

    return {"screening": scr, "run_id": run.id if run else None}


def list_screenings(ctx: AuthContext, patient_id: uuid.UUID) -> list[ScreeningRecord]:
    ctx.require(P.OBSERVATIONS_READ)
    ctx.require_track("loop")
    _require_patient(ctx, patient_id)
    return list(
        ctx.db.scalars(
            select(ScreeningRecord)
            .where(ScreeningRecord.organization_id == ctx.org_id, ScreeningRecord.patient_id == patient_id)
            .order_by(ScreeningRecord.screened_at.desc())
        ).all()
    )


def create_cognitive_assessment(ctx: AuthContext, req: CognitiveAssessmentCreate) -> dict:
    ctx.require(P.COGNITIVE_ADMINISTER)
    ctx.require_track("neuro")
    p = _require_patient(ctx, req.patient_id)
    started_at = req.started_at or utcnow()
    completed_at = req.completed_at or utcnow()

    prev_count = len(
        ctx.db.scalars(
            select(CognitiveAssessment.id).where(
                CognitiveAssessment.organization_id == ctx.org_id,
                CognitiveAssessment.patient_id == p.id,
                CognitiveAssessment.status == "completed",
            )
        ).all()
    )
    session_index = prev_count + 1

    trials = [t.model_dump() for t in req.raw_trials]
    seq_trials = [t for t in trials if t["task_type"] in {"sequence_4key", "sequence_6key", "audio_memory", "visual_memory"}]
    vis_trials = [t for t in trials if t["modality"] in {"visual", "audiovisual"}]
    aud_trials = [t for t in trials if t["modality"] == "auditory"]
    switch_trials = [t for t in trials if t["task_type"] == "rule_switch"]
    recall_trials = [t for t in trials if t["task_type"] == "delayed_recall"]

    def acc(lst: list[dict]) -> float | None:
        return round(100.0 * sum(1 for t in lst if t["correct"]) / len(lst), 2) if lst else None

    overall_acc = acc(seq_trials or trials)
    median_rt = round(statistics.median([t["reaction_time_ms"] for t in trials]), 1)
    vis_acc = acc(vis_trials)
    aud_acc = acc(aud_trials)
    switch_acc = acc(switch_trials)
    recall_acc = acc(recall_trials)

    derived = {
        "session_index": session_index,
        "total_trials": len(trials),
        "cog_sequence_accuracy": overall_acc,
        "cog_reaction_time_ms": median_rt,
        "cog_visual_accuracy": vis_acc,
        "cog_auditory_accuracy": aud_acc,
        "cog_rule_switch_accuracy": switch_acc,
        "cog_recall_accuracy": recall_acc,
        "non_diagnostic_notice": "Cognitive activity metrics are longitudinal tracking signals, not an independent medical diagnosis.",
    }

    ca = CognitiveAssessment(
        organization_id=ctx.org_id,
        patient_id=p.id,
        session_index=session_index,
        started_at=started_at,
        completed_at=completed_at,
        assessment_language=req.assessment_language,
        administered_by_id=ctx.user.id,
        environment=req.environment,
        raw_trials=trials,
        derived_metrics=derived,
        status="completed",
    )
    ctx.db.add(ca)
    ctx.db.flush()

    obs_map = [
        ("cog_sequence_accuracy", overall_acc, "%"),
        ("cog_reaction_time_ms", median_rt, "ms"),
        ("cog_visual_accuracy", vis_acc, "%"),
        ("cog_auditory_accuracy", aud_acc, "%"),
        ("cog_rule_switch_accuracy", switch_acc, "%"),
        ("cog_recall_accuracy", recall_acc, "%"),
    ]
    for code, val, unit in obs_map:
        if val is not None:
            ctx.db.add(
                Observation(
                    organization_id=ctx.org_id,
                    patient_id=p.id,
                    track="neuro",
                    metric_code=code,
                    value_num=float(val),
                    unit=unit,
                    effective_at=completed_at,
                    source=ObservationSource.ASSESSMENT.value,
                    cognitive_assessment_id=ca.id,
                    entered_by_id=ctx.user.id,
                )
            )
    _ensure_enrollment(ctx, p, "neuro")
    ctx.audit("cognitive_assessment.create", "cognitive_assessment", ca.id, patient_id=p.id, details={"session_index": session_index})
    ctx.db.commit()

    run = None
    if req.trigger_pipeline:
        run = create_pipeline_run(
            ctx.db,
            organization_id=ctx.org_id,
            patient_id=p.id,
            track="neuro",
            trigger="assessment",
            triggered_by_id=ctx.user.id,
            as_of=completed_at,
        )
        ctx.db.commit()
        run = execute_pipeline_run(ctx.db, run.id)

    return {"assessment": ca, "run_id": run.id if run else None}


def list_cognitive_assessments(ctx: AuthContext, patient_id: uuid.UUID) -> list[CognitiveAssessment]:
    ctx.require(P.OBSERVATIONS_READ)
    ctx.require_track("neuro")
    _require_patient(ctx, patient_id)
    return list(
        ctx.db.scalars(
            select(CognitiveAssessment)
            .where(CognitiveAssessment.organization_id == ctx.org_id, CognitiveAssessment.patient_id == patient_id)
            .order_by(CognitiveAssessment.started_at.desc())
        ).all()
    )
