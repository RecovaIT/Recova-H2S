"""Participant-scoped portal. Identity always comes from the authenticated session."""

from __future__ import annotations

from datetime import datetime, timedelta
import math
import statistics
import uuid

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.deps import AuthContext, requires
from app.core.errors import Forbidden, NotFound, ValidationFailed
from app.core.permissions import P
from app.agents.gate1_consent import evaluate_consents
from app.agents.orchestrator import create_pipeline_run, execute_pipeline_run
from app.engine.metrics import METRIC_CATALOG, normalize_unit
from app.models.base import utcnow
from app.models.care import (
    CareFacility,
    ClinicalReview,
    Intervention,
    OutcomeVerification,
    Referral,
)
from app.models.clinical import (
    CheckIn,
    CognitiveAssessment,
    Consent,
    Observation,
    Patient,
    TrackEnrollment,
    WearableIngestionBatch,
)
from app.models.engine import ClinicalSynthesis
from app.models.enums import ConsentScope, NoticeRecipientState, ObservationSource
from app.models.identity import Organization, ParticipantAccountLink, User, Membership
from app.models.ops import NoticeAcknowledgement, NoticeRecipient, PublicHealthNotice
from app.schemas.clinical import CognitiveTrialInput

router = APIRouter(prefix="/portal", tags=["Participant portal"])


def _all_participant_enrolments(
    ctx: AuthContext,
) -> list[tuple[Patient, TrackEnrollment, Organization]]:
    links = ctx.db.scalars(
        select(ParticipantAccountLink).where(
            ParticipantAccountLink.user_id == ctx.user_id,
            ParticipantAccountLink.revoked_at.is_(None),
        )
    ).all()
    patient_ids = [lnk.patient_id for lnk in links]
    fallback_patients = ctx.db.scalars(
        select(Patient).where(
            Patient.portal_user_id == ctx.user_id, Patient.is_active.is_(True)
        )
    ).all()
    for p in fallback_patients:
        if p.id not in patient_ids:
            patient_ids.append(p.id)
    if not patient_ids:
        return []
    patients = {
        p.id: p
        for p in ctx.db.scalars(
            select(Patient).where(
                Patient.id.in_(patient_ids), Patient.is_active.is_(True)
            )
        ).all()
    }
    if not patients:
        return []
    enrollments = ctx.db.scalars(
        select(TrackEnrollment)
        .where(
            TrackEnrollment.patient_id.in_(list(patients.keys())),
            TrackEnrollment.status == "active",
        )
        .order_by(TrackEnrollment.enrolled_at.asc())
    ).all()
    org_ids = list({e.organization_id for e in enrollments})
    permitted_orgs = set(
        ctx.db.scalars(
            select(Membership.organization_id).where(
                Membership.user_id == ctx.user_id, Membership.is_active.is_(True)
            )
        )
    )
    orgs = (
        {
            o.id: o
            for o in ctx.db.scalars(
                select(Organization).where(
                    Organization.id.in_(org_ids), Organization.is_active.is_(True)
                )
            ).all()
        }
        if org_ids
        else {}
    )
    out: list[tuple[Patient, TrackEnrollment, Organization]] = []
    for enr in enrollments:
        p = patients.get(enr.patient_id)
        org = orgs.get(enr.organization_id)
        if p is not None and org is not None and org.id in permitted_orgs:
            out.append((p, enr, org))
    return out


def own_records(
    ctx: AuthContext, enrolment_id: uuid.UUID | None = None
) -> tuple[Patient, TrackEnrollment]:
    all_enr = _all_participant_enrolments(ctx)
    if enrolment_id is not None:
        match = next(((p, e, o) for p, e, o in all_enr if e.id == enrolment_id), None)
        if match is None:
            raise Forbidden("Requested enrolment is not linked to your account")
        return match[0], match[1]

    patient = ctx.db.scalar(
        select(Patient).where(
            Patient.portal_user_id == ctx.user_id,
            Patient.organization_id == ctx.org_id,
            Patient.is_active.is_(True),
        )
    )
    if patient is None:
        link = ctx.db.scalar(
            select(ParticipantAccountLink).where(
                ParticipantAccountLink.user_id == ctx.user_id,
                ParticipantAccountLink.organization_id == ctx.org_id,
                ParticipantAccountLink.revoked_at.is_(None),
            )
        )
        if link is not None:
            patient = ctx.db.scalar(
                select(Patient).where(
                    Patient.id == link.patient_id, Patient.is_active.is_(True)
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


def _notice_visible_to_org_and_track(
    notice: PublicHealthNotice, org: Organization | None, track: str, now: datetime
) -> bool:
    if notice.status != "published":
        return False
    if notice.starts_at and notice.starts_at > now:
        return False
    if notice.expires_at and notice.expires_at < now:
        return False
    if (
        notice.scope_emirate
        and org
        and org.emirate
        and notice.scope_emirate.lower() != org.emirate.lower()
    ):
        return False
    if notice.facility_ids and org and str(org.id) not in set(notice.facility_ids):
        return False
    if notice.eligible_programmes and track not in set(notice.eligible_programmes):
        return False
    return True


@router.get("/me")
def overview(
    enrolment_id: uuid.UUID | None = Query(default=None),
    ctx: AuthContext = Depends(requires(P.PORTAL_SELF)),
):
    patient, enrollment = own_records(ctx, enrolment_id=enrolment_id)
    org = ctx.db.get(Organization, enrollment.organization_id) or ctx.organization
    org_id = enrollment.organization_id
    all_enr = _all_participant_enrolments(ctx)

    clinician = (
        ctx.db.scalar(
            select(User)
            .join(Membership, Membership.user_id == User.id)
            .where(
                User.id == patient.primary_clinician_id,
                User.is_active.is_(True),
                User.license_number.is_not(None),
                User.license_number != "",
                Membership.organization_id == org_id,
                Membership.is_active.is_(True),
                Membership.role.in_(
                    [
                        "clinician",
                        "psychiatrist",
                        "occ_health_director",
                        "org_admin",
                        "platform_admin",
                    ]
                ),
            )
        )
        if patient.primary_clinician_id
        else None
    )
    care_contact = {
        "name": (
            clinician.full_name
            if clinician
            else (
                org.settings.get("responsible_contact", {}).get("name")
                if org and org.settings
                else None
            )
            or "Assigned Care Team"
        ),
        "role": "Primary Clinician" if clinician else "Facility Care Desk",
        "facility": org.name if org else None,
    }

    observations = list(
        ctx.db.scalars(
            select(Observation)
            .where(
                Observation.patient_id == patient.id,
                Observation.organization_id == org_id,
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
                Referral.organization_id == org_id,
                Referral.track == enrollment.track,
                Referral.status.in_(
                    [
                        "approved",
                        "patient_notified",
                        "booked",
                        "consultation_completed",
                        "outcome_verified",
                        "cancelled",
                        "missed",
                        "escalated",
                    ]
                ),
            )
            .order_by(Referral.created_at.desc())
            .limit(10)
        )
    )
    scopes, _ = evaluate_consents(ctx.db, patient, utcnow())

    now = utcnow()
    live_notices = list(
        ctx.db.scalars(
            select(PublicHealthNotice)
            .where(PublicHealthNotice.status == "published")
            .order_by(PublicHealthNotice.published_at.desc())
        )
    )
    acked_live = set(
        str(nid)
        for nid in ctx.db.scalars(
            select(NoticeAcknowledgement.notice_id).where(
                NoticeAcknowledgement.user_id == ctx.user.id
            )
        )
    )
    merged_notices = list(enrollment.context.get("portal_notices", []))
    for n in live_notices:
        if not _notice_visible_to_org_and_track(n, org, enrollment.track, now):
            continue
        merged_notices.append(
            {
                "id": str(n.id),
                "title": n.title,
                "body": n.message,
                "plain_language_action": n.plain_language_action,
                "issuer": n.issuer,
                "severity": n.severity,
            }
        )
    merged_ack = list(
        dict.fromkeys(
            list(enrollment.context.get("portal_acknowledged", [])) + list(acked_live)
        )
    )

    enrolments_out = [
        {
            "enrolment_id": str(e.id),
            "patient_id": str(p.id),
            "organization_id": str(o.id),
            "facility": o.name,
            "programme": e.track,
            "track": e.track,
            "status": e.status,
            "active": e.id == enrollment.id,
        }
        for p, e, o in all_enr
    ]

    return {
        "name": patient.given_name,
        "track": enrollment.track,
        "facility": org.name if org else None,
        "care_contact": care_contact,
        "active_enrolment": {
            "enrolment_id": str(enrollment.id),
            "patient_id": str(patient.id),
            "organization_id": str(org_id),
            "facility": org.name if org else None,
            "programme": enrollment.track,
            "track": enrollment.track,
        },
        "enrolments": enrolments_out,
        "synthetic": patient.is_synthetic,
        "scenario": enrollment.context.get("scenario"),
        "care": enrollment.context.get("portal_care", []),
        "notices": merged_notices,
        "acknowledged": merged_ack,
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


@router.get("/care")
def portal_care(
    enrolment_id: uuid.UUID | None = Query(default=None),
    ctx: AuthContext = Depends(requires(P.PORTAL_SELF)),
):
    """Return clinician-released instructions, appointments and follow-up states."""
    patient, enrollment = own_records(ctx, enrolment_id=enrolment_id)
    org_id = enrollment.organization_id
    referrals = list(
        ctx.db.scalars(
            select(Referral)
            .where(
                Referral.patient_id == patient.id,
                Referral.organization_id == org_id,
                Referral.track == enrollment.track,
                Referral.status.in_(
                    [
                        "approved",
                        "patient_notified",
                        "booked",
                        "consultation_completed",
                        "outcome_verified",
                        "cancelled",
                        "missed",
                        "escalated",
                    ]
                ),
            )
            .order_by(Referral.created_at.desc())
            .limit(20)
        )
    )
    fac_ids = [r.facility_id for r in referrals if r.facility_id]
    facilities = (
        {
            f.id: f.name
            for f in ctx.db.scalars(
                select(CareFacility).where(CareFacility.id.in_(fac_ids))
            ).all()
        }
        if fac_ids
        else {}
    )
    ref_ids = [r.id for r in referrals]
    outcomes = (
        {
            ov.referral_id: ov
            for ov in ctx.db.scalars(
                select(OutcomeVerification).where(
                    OutcomeVerification.referral_id.in_(ref_ids)
                )
            ).all()
        }
        if ref_ids
        else {}
    )

    # Release clinical reviews/syntheses only when a clinician has signed off
    signed_reviews = list(
        ctx.db.scalars(
            select(ClinicalReview)
            .where(
                ClinicalReview.patient_id == patient.id,
                ClinicalReview.organization_id == org_id,
                ClinicalReview.decision.in_(
                    ["approve_referral", "modify_plan", "no_action"]
                ),
            )
            .order_by(ClinicalReview.signed_at.desc())
            .limit(10)
        )
    )
    syn_ids = [rev.synthesis_id for rev in signed_reviews if rev.synthesis_id]
    syntheses = (
        {
            s.id: s
            for s in ctx.db.scalars(
                select(ClinicalSynthesis).where(ClinicalSynthesis.id.in_(syn_ids))
            ).all()
        }
        if syn_ids
        else {}
    )

    released_instructions = [
        *[
            {
                "id": f"care-{idx}",
                "source": "facility_care_plan",
                "instruction": item,
            }
            for idx, item in enumerate(enrollment.context.get("portal_care", []))
        ],
        *[
            {
                "id": str(rev.id),
                "source": "clinician_review",
                "signed_at": rev.signed_at,
                "decision": rev.decision,
                "notes": rev.clinician_notes,
                "summary_en": (
                    syntheses[rev.synthesis_id].summary_en
                    if rev.synthesis_id in syntheses
                    else None
                ),
                "summary_ar": (
                    syntheses[rev.synthesis_id].summary_ar
                    if rev.synthesis_id in syntheses
                    else None
                ),
            }
            for rev in signed_reviews
        ],
    ]

    interventions = list(
        ctx.db.scalars(
            select(Intervention)
            .where(
                Intervention.patient_id == patient.id,
                Intervention.organization_id == org_id,
                Intervention.track == enrollment.track,
            )
            .order_by(Intervention.created_at.desc())
            .limit(20)
        )
    )

    return {
        "enrolment_id": str(enrollment.id),
        "track": enrollment.track,
        "released_instructions": released_instructions,
        "appointments": [
            {
                "referral_id": str(r.id),
                "pathway": r.pathway,
                "status": r.status,
                "priority": r.priority,
                "facility_name": (
                    facilities.get(r.facility_id)
                    if r.facility_id
                    else r.owner_facility_label
                ),
                "appointment_at": r.appointment_at,
                "appointment_reference": r.appointment_reference,
                "follow_up_due_at": r.follow_up_due_at,
                "outcome": outcomes[r.id].outcome if r.id in outcomes else None,
                "outcome_verified_at": r.outcome_verified_at,
            }
            for r in referrals
        ],
        "interventions": [
            {
                "id": str(iv.id),
                "type": iv.intervention_type,
                "status": iv.status,
                "title": iv.title,
                "details": iv.details,
                "due_at": iv.due_at,
            }
            for iv in interventions
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
    enrolment_id: uuid.UUID | None = None
    shift: str | None = Field(default=None, max_length=80)
    worksite: str | None = Field(default=None, max_length=160)
    fatigue_feeling: str | None = Field(default=None, max_length=40)
    hydrated: bool | None = None


_EMERGENCY_ESCALATION_INSTRUCTIONS = {
    "en": "Immediate safety escalation triggered. Stop strenuous activity, stay with a trusted person or supervisor, and contact your facility urgent triage line or UAE emergency services (998 / 999) immediately.",
    "ar": "تم تفعيل مسار الطوارئ الفوري. توقف عن أي مجهود، ابقَ مع شخص موثوق أو المشرف، وتواصل فوراً مع فريق الفرز الطبي العاجل أو خدمات الطوارئ في الإمارات (998 / 999).",
    "emergency_numbers": ["998", "999"],
}


@router.post("/check-ins")
def check_in(body: CheckInInput, ctx: AuthContext = Depends(requires(P.PORTAL_SELF))):
    patient, enrollment = own_records(ctx, enrolment_id=body.enrolment_id)
    org_id = enrollment.organization_id
    ctx.db.execute(select(Patient).where(Patient.id == patient.id).with_for_update())
    idem_key = f"portal:{patient.id}:{body.request_id}"
    existing = ctx.db.scalar(
        select(CheckIn).where(
            CheckIn.patient_id == patient.id,
            CheckIn.idempotency_key == idem_key,
        )
    )
    if existing:
        return {
            "id": str(existing.id),
            "status": "already_received",
            "emergency": existing.self_reported_crisis,
            "escalation_instructions": (
                _EMERGENCY_ESCALATION_INSTRUCTIONS
                if existing.self_reported_crisis
                else None
            ),
        }
    scopes, _ = evaluate_consents(ctx.db, patient, utcnow())
    from app.agents.gate2_emergency import has_emergency_text

    urgent = (
        body.crisis
        or body.fatigue_feeling == "dizzy_heat_illness"
        or has_emergency_text(body.text)
    )
    from app.core.config import get_settings

    emergency_only = (
        "data_processing" not in scopes
        and urgent
        and get_settings().emergency_screen_without_consent
    )
    if "data_processing" not in scopes and not emergency_only:
        raise Forbidden(
            "Enable care-data processing in your privacy settings before submitting"
        )
    extra = {
        "request_id": str(body.request_id),
        "enrolment_id": str(enrollment.id),
    }
    if body.shift:
        extra["shift"] = body.shift
    if body.worksite:
        extra["worksite"] = body.worksite
    if body.fatigue_feeling:
        extra["fatigue_feeling"] = body.fatigue_feeling
    if body.hydrated is not None:
        extra["hydrated"] = body.hydrated

    symptoms = (
        ["heatstroke_confusion"] if body.fatigue_feeling == "dizzy_heat_illness" else []
    )
    crisis = urgent

    row = CheckIn(
        organization_id=org_id,
        patient_id=patient.id,
        track=enrollment.track,
        kind="readiness" if enrollment.track == "worksafe" else "text",
        effective_at=utcnow(),
        mood_score=None if emergency_only else body.mood,
        stress_score=None if emergency_only else body.stress,
        craving_score=None if emergency_only else body.craving,
        text=body.text,
        symptoms=symptoms,
        self_reported_crisis=crisis,
        submitted_by_id=ctx.user_id,
        idempotency_key=idem_key,
        extra=extra,
    )
    ctx.db.add(row)
    try:
        ctx.db.flush()
    except IntegrityError:
        ctx.db.rollback()
        return {"id": None, "status": "already_received", "emergency": crisis}

    if enrollment.track == "worksafe" and (body.shift or body.worksite):
        ctx_data = dict(enrollment.context or {})
        if body.shift:
            ctx_data["last_shift"] = body.shift
        if body.worksite:
            ctx_data["last_worksite"] = body.worksite
        enrollment.context = ctx_data

    metrics = (
        []
        if emergency_only
        else [
            ("mood_score", body.mood),
            ("stress_score", body.stress),
            ("craving_score", body.craving),
        ]
    )
    if enrollment.track == "worksafe" and not emergency_only:
        metrics.append(("readiness_score", body.mood))
    for metric, value in metrics:
        if value is not None:
            ctx.db.add(
                Observation(
                    organization_id=org_id,
                    patient_id=patient.id,
                    track=enrollment.track,
                    metric_code=metric,
                    value_num=value,
                    unit="score",
                    effective_at=row.effective_at,
                    source="checkin",
                    check_in_id=row.id,
                    entered_by_id=ctx.user_id,
                    provenance=(
                        {"shift": body.shift, "worksite": body.worksite}
                        if (body.shift or body.worksite)
                        else {}
                    ),
                )
            )
    run = create_pipeline_run(
        ctx.db,
        organization_id=org_id,
        patient_id=patient.id,
        track=enrollment.track,
        trigger="checkin",
        triggered_by_id=ctx.user_id,
        idempotency_key=idem_key,
    )
    ctx.audit(
        "portal.checkin",
        "check_in",
        row.id,
        patient_id=patient.id,
        details={
            "track": enrollment.track,
            "shift": body.shift,
            "worksite": body.worksite,
        },
    )
    ctx.db.commit()
    run = execute_pipeline_run(ctx.db, run.id)
    is_emg = run.status == "emergency_bypass"
    return {
        "id": str(row.id),
        "status": run.status,
        "emergency": is_emg,
        "escalation_instructions": (
            _EMERGENCY_ESCALATION_INSTRUCTIONS if is_emg else None
        ),
        "shift": body.shift,
        "worksite": body.worksite,
    }


class PermissionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scope: str
    granted: bool
    policy_version: str = Field(default="v1.0", max_length=40)
    authority_to_act: str = Field(default="self", max_length=80)
    enrolment_id: uuid.UUID | None = None


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
    idem_key = f"portal-act:{patient.id}:{body.request_id}"
    existing_idem = ctx.db.scalar(
        select(CognitiveAssessment).where(
            CognitiveAssessment.patient_id == patient.id,
            CognitiveAssessment.idempotency_key == idem_key,
        )
    )
    if existing_idem is not None:
        return {"saved": True, "id": str(existing_idem.id)}

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
        organization_id=enrollment.organization_id,
        patient_id=patient.id,
        enrollment_id=enrollment.id,
        session_index=len(existing) + 1,
        task_version="portal-visual-sequence-v1",
        started_at=now - timedelta(milliseconds=body.reaction_time_ms),
        completed_at=now,
        administered_by_id=ctx.user_id,
        idempotency_key=idem_key,
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


class CognitiveSessionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: uuid.UUID
    enrolment_id: uuid.UUID | None = None
    task_version: str = Field(default="neuro-battery-v1", min_length=2, max_length=60)
    assessment_language: str = Field(default="en", pattern=r"^(en|ar)$")
    environment: dict = Field(default_factory=dict)
    raw_trials: list[CognitiveTrialInput] = Field(min_length=1, max_length=200)
    is_practice: bool = False
    trigger_pipeline: bool = True


@router.post("/cognitive-sessions")
def cognitive_session(
    body: CognitiveSessionInput, ctx: AuthContext = Depends(requires(P.PORTAL_SELF))
):
    """Save assigned cognitive activity observations for the authenticated Neuro participant."""
    patient, enrollment = own_records(ctx, enrolment_id=body.enrolment_id)
    if enrollment.track != "neuro":
        raise Forbidden("Cognitive sessions belong to the Neuro programme")
    scopes, _ = evaluate_consents(ctx.db, patient, utcnow())
    if "data_processing" not in scopes:
        raise Forbidden("Care-data permission is required")

    ctx.db.execute(select(Patient).where(Patient.id == patient.id).with_for_update())
    idem_key = f"portal-cog:{patient.id}:{body.request_id}"
    existing = ctx.db.scalar(
        select(CognitiveAssessment).where(
            CognitiveAssessment.patient_id == patient.id,
            CognitiveAssessment.idempotency_key == idem_key,
        )
    )
    if existing is not None:
        return {
            "saved": True,
            "status": "already_received",
            "id": str(existing.id),
            "enrollment_id": str(existing.enrollment_id or enrollment.id),
            "task_version": existing.task_version,
            "observations_saved": 0,
            "run_id": None,
        }

    prev_count = len(
        ctx.db.scalars(
            select(CognitiveAssessment.id).where(
                CognitiveAssessment.organization_id == enrollment.organization_id,
                CognitiveAssessment.patient_id == patient.id,
                CognitiveAssessment.status == "completed",
            )
        ).all()
    )
    session_index = prev_count + 1
    now = utcnow()

    # Server derives correctness from expected == response
    trials = []
    for t in body.raw_trials:
        d = t.model_dump()
        d["correct"] = d["response"] == d["expected"]
        trials.append(d)

    seq_trials = [
        t
        for t in trials
        if t["task_type"]
        in {"sequence_4key", "sequence_6key", "audio_memory", "visual_memory"}
    ]
    vis_trials = [t for t in trials if t["modality"] in {"visual", "audiovisual"}]
    aud_trials = [t for t in trials if t["modality"] == "auditory"]
    switch_trials = [t for t in trials if t["task_type"] == "rule_switch"]
    recall_trials = [t for t in trials if t["task_type"] == "delayed_recall"]

    def acc(lst: list[dict]) -> float | None:
        return (
            round(100.0 * sum(1 for t in lst if t["correct"]) / len(lst), 2)
            if lst
            else None
        )

    overall_acc = acc(seq_trials or trials)
    median_rt = round(statistics.median([t["reaction_time_ms"] for t in trials]), 1)
    vis_acc = acc(vis_trials)
    aud_acc = acc(aud_trials)
    switch_acc = acc(switch_trials)
    recall_acc = acc(recall_trials)

    derived = {
        "session_index": session_index,
        "task_version": body.task_version,
        "total_trials": len(trials),
        "cog_sequence_accuracy": overall_acc,
        "cog_reaction_time_ms": median_rt,
        "cog_visual_accuracy": vis_acc,
        "cog_auditory_accuracy": aud_acc,
        "cog_rule_switch_accuracy": switch_acc,
        "cog_recall_accuracy": recall_acc,
    }

    ca = CognitiveAssessment(
        organization_id=enrollment.organization_id,
        patient_id=patient.id,
        enrollment_id=enrollment.id,
        session_index=session_index,
        task_version=body.task_version,
        started_at=now
        - timedelta(milliseconds=int(sum(t["reaction_time_ms"] for t in trials))),
        completed_at=now,
        assessment_language=body.assessment_language,
        administered_by_id=ctx.user_id,
        idempotency_key=idem_key,
        environment={
            **body.environment,
            "request_id": str(body.request_id),
            "task_version": body.task_version,
        },
        raw_trials=trials,
        derived_metrics=derived,
        status="practice" if body.is_practice else "completed",
    )
    ctx.db.add(ca)
    ctx.db.flush()

    observations_saved = 0
    if not body.is_practice:
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
                        organization_id=enrollment.organization_id,
                        patient_id=patient.id,
                        track="neuro",
                        metric_code=code,
                        value_num=float(val),
                        unit=unit,
                        effective_at=now,
                        source=ObservationSource.ASSESSMENT.value,
                        cognitive_assessment_id=ca.id,
                        entered_by_id=ctx.user_id,
                        provenance={
                            "task_version": body.task_version,
                            "enrolment_id": str(enrollment.id),
                        },
                    )
                )
                observations_saved += 1

    run = None
    if body.trigger_pipeline and not body.is_practice:
        run = create_pipeline_run(
            ctx.db,
            organization_id=enrollment.organization_id,
            patient_id=patient.id,
            track="neuro",
            trigger="assessment",
            triggered_by_id=ctx.user_id,
            as_of=now,
            idempotency_key=idem_key,
        )

    ctx.audit(
        "portal.cognitive_session",
        "cognitive_assessment",
        ca.id,
        patient_id=patient.id,
        details={
            "task_version": body.task_version,
            "enrolment_id": str(enrollment.id),
            "observations_saved": observations_saved,
        },
    )
    ctx.db.commit()
    if run is not None:
        run = execute_pipeline_run(ctx.db, run.id)

    return {
        "saved": True,
        "status": "completed",
        "id": str(ca.id),
        "patient_id": str(patient.id),
        "enrollment_id": str(enrollment.id),
        "task_version": ca.task_version,
        "observations_saved": observations_saved,
        "derived_metrics": derived,
        "run_id": str(run.id) if run else None,
        "run_status": run.status if run else None,
    }


@router.post("/consents")
def consent(body: PermissionInput, ctx: AuthContext = Depends(requires(P.PORTAL_SELF))):
    patient, enrollment = own_records(ctx, enrolment_id=body.enrolment_id)
    valid_scopes = {
        ConsentScope.DATA_PROCESSING.value,
        ConsentScope.WEARABLE_INGESTION.value,
        ConsentScope.LLM_SYNTHESIS.value,
        ConsentScope.FAMILY_NOTIFICATION.value,
        ConsentScope.HIE_SHARING.value,
        ConsentScope.OPTIONAL_CHANNELS.value,
    }
    if body.scope not in valid_scopes:
        raise ValidationFailed("Unknown consent scope")
    ctx.db.add(
        Consent(
            organization_id=enrollment.organization_id,
            patient_id=patient.id,
            scope=body.scope,
            status="granted" if body.granted else "revoked",
            effective_at=utcnow(),
            method="electronic",
            policy_version=body.policy_version,
            authority_to_act=body.authority_to_act,
            actor_user_id=ctx.user_id,
            granted_by_name=ctx.user.full_name,
            recorded_by_id=ctx.user_id,
            evidence_reference=f"portal-consent-{body.policy_version}",
        )
    )
    ctx.audit(
        "portal.consent",
        "patient",
        patient.id,
        patient_id=patient.id,
        details={
            "scope": body.scope,
            "granted": body.granted,
            "policy_version": body.policy_version,
        },
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
            WearableIngestionBatch.organization_id == enrollment.organization_id,
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
        organization_id=enrollment.organization_id,
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
                organization_id=enrollment.organization_id,
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
        organization_id=enrollment.organization_id,
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
    org = ctx.db.get(Organization, enrollment.organization_id) or ctx.organization

    # Support live PublicHealthNotice UUIDs as well as enrollment.context["portal_notices"]
    try:
        notice_uuid = uuid.UUID(body.notice_id)
    except ValueError:
        notice_uuid = None

    if notice_uuid is not None:
        notice = ctx.db.get(PublicHealthNotice, notice_uuid)
        if notice is not None:
            now = utcnow()
            if not _notice_visible_to_org_and_track(notice, org, enrollment.track, now):
                raise NotFound("Notice not found")
            existing = ctx.db.scalar(
                select(NoticeAcknowledgement).where(
                    NoticeAcknowledgement.notice_id == notice_uuid,
                    NoticeAcknowledgement.user_id == ctx.user.id,
                )
            )
            if existing is None:
                ctx.db.add(
                    NoticeAcknowledgement(
                        notice_id=notice_uuid,
                        user_id=ctx.user.id,
                        organization_id=enrollment.organization_id,
                        acknowledged_at=now,
                    )
                )
            rec = ctx.db.scalar(
                select(NoticeRecipient).where(
                    NoticeRecipient.notice_id == notice_uuid,
                    NoticeRecipient.user_id == ctx.user.id,
                )
            )
            if rec is None:
                ctx.db.add(
                    NoticeRecipient(
                        notice_id=notice_uuid,
                        user_id=ctx.user.id,
                        organization_id=enrollment.organization_id,
                        state=NoticeRecipientState.ACKNOWLEDGED.value,
                        read_at=now,
                        acknowledged_at=now,
                    )
                )
            else:
                rec.state = NoticeRecipientState.ACKNOWLEDGED.value
                rec.read_at = rec.read_at or now
                rec.acknowledged_at = rec.acknowledged_at or now
            ctx.audit(
                "portal.notice_acknowledged",
                "public_health_notice",
                notice_uuid,
                patient_id=patient.id,
                details={"notice_id": str(notice_uuid)},
            )
            ctx.db.commit()
            return {"saved": True}

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
