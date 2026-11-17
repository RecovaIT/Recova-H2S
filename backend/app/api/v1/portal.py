"""Participant-scoped portal. Identity always comes from the authenticated session."""

from datetime import datetime, timedelta
import math
import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from app.api.deps import AuthContext, requires
from app.core.permissions import P
from app.core.errors import Forbidden, NotFound, ValidationFailed
from app.models.clinical import (
    Patient,
    TrackEnrollment,
    Observation,
    CheckIn,
    Consent,
    WearableIngestionBatch,
)
from app.models.care import Referral
from app.models.clinical import CognitiveAssessment
from app.models.base import utcnow
from app.agents.gate1_consent import evaluate_consents
from app.agents.orchestrator import create_pipeline_run, execute_pipeline_run
from app.engine.metrics import METRIC_CATALOG, normalize_unit

router = APIRouter(prefix="/portal", tags=["Participant portal"])


def own_records(ctx):
    patient = ctx.db.scalar(
        select(Patient).where(
            Patient.portal_user_id == ctx.user_id,
            Patient.organization_id == ctx.org_id,
            Patient.is_active.is_(True),
        )
    )
    if patient is None:
        raise NotFound(
            "Your facility has not linked a participant record to this account"
        )
    enrollment = ctx.db.scalar(
        select(TrackEnrollment).where(
            TrackEnrollment.patient_id == patient.id,
            TrackEnrollment.organization_id == ctx.org_id,
            TrackEnrollment.status == "active",
        )
    )
    if enrollment is None:
        raise NotFound(
            "Your facility has no active programme enrolment for this account"
        )
    return patient, enrollment


@router.get("/me")
def overview(ctx: AuthContext = Depends(requires(P.PORTAL_SELF))):
    patient, enrollment = own_records(ctx)
    observations = list(
        ctx.db.scalars(
            select(Observation)
            .where(
                Observation.patient_id == patient.id,
                Observation.organization_id == ctx.org_id,
                Observation.track == enrollment.track,
                Observation.status != "entered_in_error",
            )
            .order_by(Observation.effective_at.desc())
            .limit(100)
        )
    )
    checkins = list(
        ctx.db.scalars(
            select(CheckIn)
            .where(CheckIn.patient_id == patient.id, CheckIn.track == enrollment.track)
            .order_by(CheckIn.effective_at.desc())
            .limit(14)
        )
    )
    referrals = list(
        ctx.db.scalars(
            select(Referral)
            .where(
                Referral.patient_id == patient.id,
                Referral.organization_id == ctx.org_id,
                Referral.track == enrollment.track,
                Referral.status.in_(
                    [
                        "approved",
                        "patient_notified",
                        "booked",
                        "consultation_completed",
                        "outcome_verified",
                    ]
                ),
            )
            .order_by(Referral.created_at.desc())
            .limit(10)
        )
    )
    scopes, _ = evaluate_consents(ctx.db, patient, utcnow())
    return {
        "name": patient.given_name,
        "track": enrollment.track,
        "facility": ctx.organization.name,
        "synthetic": patient.is_synthetic,
        "scenario": enrollment.context.get("scenario"),
        "care": enrollment.context.get("portal_care", []),
        "notices": enrollment.context.get("portal_notices", []),
        "acknowledged": enrollment.context.get("portal_acknowledged", []),
        "consents": sorted(scopes),
        "observations": [
            {
                "id": str(o.id),
                "metric": o.metric_code,
                "value": o.value_num,
                "unit": o.unit,
                "at": o.effective_at,
                "source": o.source,
            }
            for o in observations
        ],
        "checkins": [
            {
                "id": str(c.id),
                "at": c.effective_at,
                "mood": c.mood_score,
                "stress": c.stress_score,
                "text": c.text,
                "crisis": c.self_reported_crisis,
            }
            for c in checkins
        ],
        "referrals": [
            {"id": str(r.id), "pathway": r.pathway, "status": r.status}
            for r in referrals
        ],
        "providers": [
            {"id": p, "status": "not_configured"}
            for p in ["apple_health", "fitbit", "garmin"]
        ],
    }


class CheckInInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mood: int = Field(ge=0, le=10)
    stress: int = Field(ge=0, le=10)
    craving: int | None = Field(default=None, ge=0, le=10)
    text: str = Field(default="", max_length=4000)
    crisis: bool = False
    request_id: uuid.UUID


@router.post("/check-ins")
def check_in(body: CheckInInput, ctx: AuthContext = Depends(requires(P.PORTAL_SELF))):
    patient, enrollment = own_records(ctx)
    ctx.db.execute(select(Patient).where(Patient.id == patient.id).with_for_update())
    existing = ctx.db.scalar(
        select(CheckIn).where(
            CheckIn.patient_id == patient.id,
            CheckIn.extra["request_id"].astext == str(body.request_id),
        )
    )
    if existing:
        return {
            "id": str(existing.id),
            "status": "already_received",
            "emergency": existing.self_reported_crisis,
        }
    scopes, _ = evaluate_consents(ctx.db, patient, utcnow())
    if "data_processing" not in scopes:
        raise Forbidden(
            "Enable care-data processing in your privacy settings before submitting"
        )
    row = CheckIn(
        organization_id=ctx.org_id,
        patient_id=patient.id,
        track=enrollment.track,
        kind="readiness" if enrollment.track == "worksafe" else "text",
        effective_at=utcnow(),
        mood_score=body.mood,
        stress_score=body.stress,
        craving_score=body.craving,
        text=body.text,
        symptoms=[],
        self_reported_crisis=body.crisis,
        submitted_by_id=ctx.user_id,
        extra={"request_id": str(body.request_id)},
    )
    ctx.db.add(row)
    ctx.db.flush()
    metrics = [
        ("mood_score", body.mood),
        ("stress_score", body.stress),
        ("craving_score", body.craving),
    ]
    if enrollment.track == "worksafe":
        metrics.append(("readiness_score", body.mood))
    for metric, value in metrics:
        if value is not None:
            ctx.db.add(
                Observation(
                    organization_id=ctx.org_id,
                    patient_id=patient.id,
                    track=enrollment.track,
                    metric_code=metric,
                    value_num=value,
                    unit="score",
                    effective_at=row.effective_at,
                    source="checkin",
                    check_in_id=row.id,
                    entered_by_id=ctx.user_id,
                )
            )
    run = create_pipeline_run(
        ctx.db,
        organization_id=ctx.org_id,
        patient_id=patient.id,
        track=enrollment.track,
        trigger="checkin",
        triggered_by_id=ctx.user_id,
        idempotency_key=f"portal:{patient.id}:{body.request_id}",
    )
    ctx.audit("portal.checkin", "check_in", row.id, patient_id=patient.id)
    ctx.db.commit()
    run = execute_pipeline_run(ctx.db, run.id)
    return {
        "id": str(row.id),
        "status": run.status,
        "emergency": run.status == "emergency_bypass",
    }


class PermissionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scope: str
    granted: bool


class ActivityInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: uuid.UUID
    expected: list[int] = Field(min_length=3, max_length=3)
    response: list[int] = Field(min_length=3, max_length=3)
    reaction_time_ms: int = Field(ge=50, le=600000)
    correct: bool


@router.post("/activities")
def activity(body: ActivityInput, ctx: AuthContext = Depends(requires(P.PORTAL_SELF))):
    patient, enrollment = own_records(ctx)
    if enrollment.track != "neuro":
        raise Forbidden("This activity belongs to the Neuro programme")
    scopes, _ = evaluate_consents(ctx.db, patient, utcnow())
    if "data_processing" not in scopes:
        raise Forbidden("Care-data permission is required")
    if any(value not in range(4) for value in body.expected + body.response):
        raise ValidationFailed("Invalid activity tile")
    ctx.db.execute(select(Patient).where(Patient.id == patient.id).with_for_update())
    existing = list(
        ctx.db.scalars(
            select(CognitiveAssessment).where(
                CognitiveAssessment.patient_id == patient.id
            )
        )
    )
    for assessment in existing:
        if assessment.environment.get("request_id") == str(body.request_id):
            return {"saved": True, "id": str(assessment.id)}
    correct = body.response == body.expected
    now = utcnow()
    row = CognitiveAssessment(
        organization_id=ctx.org_id,
        patient_id=patient.id,
        session_index=len(existing) + 1,
        started_at=now - timedelta(milliseconds=body.reaction_time_ms),
        completed_at=now,
        administered_by_id=ctx.user_id,
        environment={
            "request_id": str(body.request_id),
            "activity_version": "portal-visual-sequence-v1",
            "modality": "visual",
        },
        raw_trials=[
            {
                "task_type": "sequence_4key",
                "modality": "visual",
                "expected": body.expected,
                "response": body.response,
                "correct": correct,
                "reaction_time_ms": body.reaction_time_ms,
            }
        ],
        derived_metrics={"sequence_accuracy": 100 if correct else 0},
        status="practice",
    )
    ctx.db.add(row)
    ctx.db.flush()
    ctx.audit("portal.activity", "cognitive_assessment", row.id, patient_id=patient.id)
    ctx.db.commit()
    return {"saved": True, "id": str(row.id)}


@router.post("/consents")
def consent(body: PermissionInput, ctx: AuthContext = Depends(requires(P.PORTAL_SELF))):
    patient, _ = own_records(ctx)
    if body.scope not in {
        "data_processing",
        "wearable_ingestion",
        "llm_synthesis",
        "family_notification",
        "hie_sharing",
    }:
        raise ValidationFailed("Unknown consent scope")
    ctx.db.add(
        Consent(
            organization_id=ctx.org_id,
            patient_id=patient.id,
            scope=body.scope,
            status="granted" if body.granted else "revoked",
            effective_at=utcnow(),
            method="electronic",
            granted_by_name=ctx.user.full_name,
            recorded_by_id=ctx.user_id,
            evidence_reference="portal-consent-v1",
        )
    )
    ctx.audit(
        "portal.consent",
        "patient",
        patient.id,
        patient_id=patient.id,
        details={"scope": body.scope, "granted": body.granted},
    )
    ctx.db.commit()
    return {"saved": True}


class Reading(BaseModel):
    model_config = ConfigDict(extra="forbid")
    metric: str
    value: float
    unit: str
    at: datetime


class ImportInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: uuid.UUID
    readings: list[Reading] = Field(min_length=1, max_length=500)


@router.post("/wearable-import")
def import_wearable(
    body: ImportInput, ctx: AuthContext = Depends(requires(P.PORTAL_SELF))
):
    patient, enrollment = own_records(ctx)
    scopes, _ = evaluate_consents(ctx.db, patient, utcnow())
    if not {"data_processing", "wearable_ingestion"}.issubset(scopes):
        raise Forbidden("Care-data and wearable permissions are required")
    ctx.db.execute(select(Patient).where(Patient.id == patient.id).with_for_update())
    key = f"portal:{patient.id}:{body.request_id}"
    existing = ctx.db.scalar(
        select(WearableIngestionBatch).where(
            WearableIngestionBatch.organization_id == ctx.org_id,
            WearableIngestionBatch.idempotency_key == key,
        )
    )
    if existing:
        return {"accepted": existing.accepted_count, "status": "already_received"}
    values = []
    for item in body.readings:
        if item.metric not in {"sleep_hours", "hrv_rmssd", "resting_hr", "steps"}:
            raise ValidationFailed("Unsupported wearable metric")
        spec = METRIC_CATALOG[item.metric]
        compatible_units = {
            "sleep_hours": {
                "h",
                "hr",
                "hrs",
                "hour",
                "hours",
                "min",
                "mins",
                "minute",
                "minutes",
            },
            "hrv_rmssd": {"ms", "s", "sec", "secs", "second", "seconds"},
            "resting_hr": {"bpm", "/min"},
            "steps": {"count", "steps"},
        }
        if item.unit.strip().lower() not in compatible_units[item.metric]:
            raise ValidationFailed("Incompatible reading unit")
        value, unit, flags = normalize_unit(item.metric, item.value, item.unit)
        if "unit_mismatch" in flags:
            raise ValidationFailed("Incompatible reading unit")
        if not math.isfinite(value) or not spec.valid_min <= value <= spec.valid_max:
            raise ValidationFailed(f"Invalid value for {item.metric}")
        if item.at.tzinfo is None or item.at > utcnow() + timedelta(minutes=5):
            raise ValidationFailed(
                "Readings need a timezone and cannot be in the future"
            )
        values.append((item, value, unit))
    batch = WearableIngestionBatch(
        organization_id=ctx.org_id,
        patient_id=patient.id,
        source_system="csv",
        idempotency_key=key,
        status="processed",
        received_count=len(values),
        accepted_count=len(values),
        rejected=[],
        submitted_by_id=ctx.user_id,
    )
    ctx.db.add(batch)
    ctx.db.flush()
    for item, value, unit in values:
        ctx.db.add(
            Observation(
                organization_id=ctx.org_id,
                patient_id=patient.id,
                track=enrollment.track,
                metric_code=item.metric,
                value_num=value,
                unit=unit,
                effective_at=item.at,
                source="wearable",
                wearable_batch_id=batch.id,
                entered_by_id=ctx.user_id,
                provenance={"method": "participant_file_import"},
            )
        )
    ctx.audit(
        "portal.wearable_import",
        "wearable_ingestion_batch",
        batch.id,
        patient_id=patient.id,
    )
    run = create_pipeline_run(
        ctx.db,
        organization_id=ctx.org_id,
        patient_id=patient.id,
        track=enrollment.track,
        trigger="wearable",
        triggered_by_id=ctx.user_id,
        idempotency_key=f"import:{patient.id}:{body.request_id}",
    )
    ctx.db.commit()
    run = execute_pipeline_run(ctx.db, run.id)
    return {"accepted": len(values), "status": "processed", "run_status": run.status}


class AcknowledgeInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    notice_id: str


@router.post("/notices/acknowledge")
def acknowledge(
    body: AcknowledgeInput, ctx: AuthContext = Depends(requires(P.PORTAL_SELF))
):
    patient, enrollment = own_records(ctx)
    ctx.db.execute(
        select(TrackEnrollment)
        .where(TrackEnrollment.id == enrollment.id)
        .with_for_update()
    )
    ctx.db.refresh(enrollment)
    data = dict(enrollment.context)
    if body.notice_id not in {n["id"] for n in data.get("portal_notices", [])}:
        raise NotFound("Notice not found")
    data["portal_acknowledged"] = sorted(
        set(data.get("portal_acknowledged", [])) | {body.notice_id}
    )
    enrollment.context = data
    ctx.audit(
        "portal.notice_acknowledged",
        "track_enrollment",
        enrollment.id,
        patient_id=patient.id,
        details={"notice_id": body.notice_id},
    )
    ctx.db.commit()
    return {"saved": True}
