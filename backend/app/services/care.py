"""Clinical review (DECIDE-AI sign-off), closed-loop referrals, outcomes, interventions, insurance/facilities."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import AuthContext
from app.core import audit
from app.core.errors import Conflict, NotFound, ValidationFailed
from app.core.permissions import P
from app.core.security import encrypt_str
from app.integrations.notifications import dispatch_notification
from app.models.base import utcnow
from app.models.care import (
    CareFacility,
    ClinicalReview,
    InsurancePlan,
    Intervention,
    Notification,
    OutcomeVerification,
    Referral,
    ReferralEvent,
)
from app.models.clinical import Patient
from app.models.engine import ClinicalSynthesis, EmergencyEvent, PipelineRun, ScoringResult
from app.models.enums import (
    IntegrationStatus,
    InterventionStatus,
    NotificationChannel,
    NotificationStatus,
    ReferralStatus,
    ReviewDecision,
    SlaStatus,
)
from app.models.ops import IntegrationConfig
from app.schemas.common import PageParams, paginate
from app.schemas.workflow import (
    CareFacilityCreate,
    ClinicalReviewCreate,
    EmergencyResolveRequest,
    InsurancePlanCreate,
    IntegrationConfigUpdate,
    InterventionCreate,
    InterventionUpdateRequest,
    OutcomeVerificationCreate,
    ReferralBookRequest,
    ReferralCompleteRequest,
    ReferralCreate,
    ReferralNotifyRequest,
)


def create_clinical_review(ctx: AuthContext, req: ClinicalReviewCreate) -> ClinicalReview:
    ctx.require(P.REVIEWS_SIGN)
    run = ctx.db.scalar(
        select(PipelineRun).where(PipelineRun.id == req.run_id, PipelineRun.organization_id == ctx.org_id)
    )
    if run is None or run.patient_id is None:
        raise NotFound("Pipeline run not found")
    ctx.require_track(run.track)

    patient = ctx.db.get(Patient, run.patient_id)
    assert patient is not None

    syn = ctx.db.scalar(select(ClinicalSynthesis).where(ClinicalSynthesis.run_id == run.id))
    now = utcnow()
    sig_input = f"{run.id}:{ctx.user.id}:{req.decision.value}:{now.isoformat()}"
    sig_hash = hashlib.sha256(sig_input.encode()).hexdigest()

    review = ClinicalReview(
        organization_id=ctx.org_id,
        run_id=run.id,
        patient_id=patient.id,
        reviewer_id=ctx.user.id,
        reviewer_role=ctx.role.value if ctx.role else "clinician",
        reviewer_license=ctx.user.license_number,
        decision=req.decision.value,
        agrees_with_tier=req.agrees_with_tier,
        clinician_notes=req.clinician_notes,
        modified_plan=req.modified_plan,
        lab_request=req.lab_request,
        synthesis_id=syn.id if syn else None,
        signed_at=now,
        signature_hash=sig_hash,
    )
    ctx.db.add(review)
    ctx.db.flush()

    # Link to referral (either passed explicitly or associated with this run)
    referral: Referral | None = None
    if req.referral_id:
        referral = ctx.db.scalar(
            select(Referral).where(Referral.id == req.referral_id, Referral.organization_id == ctx.org_id)
        )
    else:
        referral = ctx.db.scalar(
            select(Referral).where(
                Referral.run_id == run.id,
                Referral.organization_id == ctx.org_id,
                Referral.status == ReferralStatus.PROPOSED.value,
            )
        )

    if referral is not None:
        old_status = referral.status
        referral.review_id = review.id
        if req.decision in {ReviewDecision.APPROVE_REFERRAL, ReviewDecision.MODIFY_PLAN}:
            if referral.status == ReferralStatus.PROPOSED.value:
                referral.status = ReferralStatus.APPROVED.value
            referral.approved_by_id = ctx.user.id
            referral.approved_at = now
            ctx.db.add(
                ReferralEvent(
                    referral_id=referral.id,
                    event_type="status_change",
                    from_status=old_status,
                    to_status=referral.status,
                    actor_user_id=ctx.user.id,
                    actor_label=ctx.user.email,
                    details={"review_id": str(review.id), "decision": req.decision.value},
                )
            )
            if req.notify_patient_channel:
                n = dispatch_notification(
                    ctx.db,
                    organization_id=ctx.org_id,
                    channel=req.notify_patient_channel,
                    category="referral",
                    subject=f"Care Follow-Up Scheduled ({referral.pathway.replace('_', ' ').title()})",
                    body=req.clinician_notes or referral.reason,
                    recipient_patient=patient,
                    referral_id=referral.id,
                )
                if n.status in {NotificationStatus.SENT.value, NotificationStatus.DELIVERED.value}:
                    referral.status = ReferralStatus.PATIENT_NOTIFIED.value
                    ctx.db.add(
                        ReferralEvent(
                            referral_id=referral.id,
                            event_type="notification",
                            from_status=ReferralStatus.APPROVED.value,
                            to_status=ReferralStatus.PATIENT_NOTIFIED.value,
                            actor_user_id=ctx.user.id,
                            actor_label=ctx.user.email,
                            details={"channel": req.notify_patient_channel.value, "notification_id": str(n.id)},
                        )
                    )
        elif req.decision == ReviewDecision.REJECT:
            referral.status = ReferralStatus.REJECTED.value
            referral.closed_at = now
            ctx.db.add(
                ReferralEvent(
                    referral_id=referral.id,
                    event_type="status_change",
                    from_status=old_status,
                    to_status=ReferralStatus.REJECTED.value,
                    actor_user_id=ctx.user.id,
                    actor_label=ctx.user.email,
                    details={"review_id": str(review.id), "notes": req.clinician_notes},
                )
            )

    if req.decision == ReviewDecision.REQUEST_LAB:
        ctx.db.add(
            Intervention(
                organization_id=ctx.org_id,
                track=run.track,
                patient_id=patient.id,
                referral_id=referral.id if referral else None,
                run_id=run.id,
                intervention_type="lab_request",
                status=InterventionStatus.PLANNED.value,
                title="Clinician-ordered laboratory / toxicology screen",
                details=json.dumps(req.lab_request or {"notes": req.clinician_notes}),
                assigned_to_id=ctx.user.id,
                due_at=now + timedelta(hours=48),
                created_by_label=ctx.user.email,
            )
        )

    ctx.audit(
        "clinical_review.sign",
        "clinical_review",
        review.id,
        patient_id=patient.id,
        run_id=run.id,
        details={"decision": req.decision.value, "signature_hash": sig_hash},
    )
    ctx.db.commit()
    return review


def list_reviews(ctx: AuthContext, params: PageParams, patient_id: uuid.UUID | None = None, run_id: uuid.UUID | None = None) -> dict:
    ctx.require(P.REVIEWS_READ)
    stmt = select(ClinicalReview).where(ClinicalReview.organization_id == ctx.org_id)
    if patient_id:
        stmt = stmt.where(ClinicalReview.patient_id == patient_id)
    if run_id:
        stmt = stmt.where(ClinicalReview.run_id == run_id)
    return paginate(
        ctx.db,
        stmt,
        params,
        sortable={"signed_at": ClinicalReview.signed_at},
        default_sort=ClinicalReview.signed_at.desc(),
    )


def list_referrals(
    ctx: AuthContext,
    params: PageParams,
    *,
    track: str | None = None,
    status: str | None = None,
    patient_id: uuid.UUID | None = None,
    sla_status: str | None = None,
) -> dict:
    ctx.require(P.REFERRALS_READ)
    stmt = select(Referral).where(Referral.organization_id == ctx.org_id)
    if track:
        stmt = stmt.where(Referral.track == track)
    if status:
        stmt = stmt.where(Referral.status == status)
    if patient_id:
        stmt = stmt.where(Referral.patient_id == patient_id)
    if sla_status:
        stmt = stmt.where(Referral.sla_status == sla_status)
    return paginate(
        ctx.db,
        stmt,
        params,
        sortable={"created_at": Referral.created_at, "sla_due_at": Referral.sla_due_at, "priority": Referral.priority},
        default_sort=Referral.created_at.desc(),
    )


def get_referral(ctx: AuthContext, referral_id: uuid.UUID) -> tuple[Referral, OutcomeVerification | None]:
    ctx.require(P.REFERRALS_READ)
    r = ctx.db.scalar(
        select(Referral)
        .options(selectinload(Referral.events))
        .where(Referral.id == referral_id, Referral.organization_id == ctx.org_id)
    )
    if r is None:
        raise NotFound("Referral not found")
    ov = ctx.db.scalar(select(OutcomeVerification).where(OutcomeVerification.referral_id == r.id))
    return r, ov


def create_referral(ctx: AuthContext, req: ReferralCreate) -> Referral:
    ctx.require(P.REFERRALS_WRITE)
    ctx.require_track(req.track.value)
    p = ctx.db.scalar(select(Patient).where(Patient.id == req.patient_id, Patient.organization_id == ctx.org_id))
    if p is None:
        raise NotFound("Patient not found")
    now = utcnow()
    sla_due = req.target_date or (now + timedelta(hours=48 if req.priority.value == "urgent" else 168))
    facility = ctx.db.get(CareFacility, req.facility_id) if req.facility_id else None
    r = Referral(
        organization_id=ctx.org_id,
        patient_id=p.id,
        track=req.track.value,
        pathway=req.pathway.value,
        priority=req.priority.value,
        status=ReferralStatus.APPROVED.value,
        reason=req.reason,
        facility_id=facility.id if facility else None,
        insurance_plan_id=p.insurance_plan_id,
        coverage_status="unknown",
        owner_user_id=req.owner_user_id or ctx.user.id,
        owner_facility_label=facility.name if facility else None,
        approved_by_id=ctx.user.id,
        approved_at=now,
        target_date=sla_due,
        sla_due_at=sla_due,
        sla_status=SlaStatus.ON_TRACK.value,
    )
    ctx.db.add(r)
    ctx.db.flush()
    ctx.db.add(
        ReferralEvent(
            referral_id=r.id,
            event_type="status_change",
            from_status=None,
            to_status=r.status,
            actor_user_id=ctx.user.id,
            actor_label=ctx.user.email,
            details={"manual": True},
        )
    )
    ctx.audit("referral.create", "referral", r.id, patient_id=p.id, details={"pathway": r.pathway})
    ctx.db.commit()
    return r


def notify_patient_for_referral(ctx: AuthContext, referral_id: uuid.UUID, req: ReferralNotifyRequest) -> tuple[Referral, Notification]:
    ctx.require(P.REFERRALS_WRITE)
    r = ctx.db.scalar(select(Referral).where(Referral.id == referral_id, Referral.organization_id == ctx.org_id))
    if r is None:
        raise NotFound("Referral not found")
    if r.status == ReferralStatus.PROPOSED.value:
        raise ValidationFailed("Referral must be approved by a clinician before notifying the patient")
    p = ctx.db.get(Patient, r.patient_id)
    assert p is not None

    n = dispatch_notification(
        ctx.db,
        organization_id=ctx.org_id,
        channel=req.channel,
        category="referral",
        subject=f"Care Pathway Follow-Up ({r.pathway.replace('_', ' ').title()})",
        body=req.message or r.reason,
        recipient_patient=p,
        referral_id=r.id,
    )
    if n.status in {NotificationStatus.SENT.value, NotificationStatus.DELIVERED.value} and r.status == ReferralStatus.APPROVED.value:
        old = r.status
        r.status = ReferralStatus.PATIENT_NOTIFIED.value
        ctx.db.add(
            ReferralEvent(
                referral_id=r.id,
                event_type="notification",
                from_status=old,
                to_status=r.status,
                actor_user_id=ctx.user.id,
                actor_label=ctx.user.email,
                details={"channel": req.channel.value, "notification_id": str(n.id), "delivery_status": n.status},
            )
        )
    else:
        ctx.db.add(
            ReferralEvent(
                referral_id=r.id,
                event_type="notification",
                from_status=r.status,
                to_status=r.status,
                actor_user_id=ctx.user.id,
                actor_label=ctx.user.email,
                details={"channel": req.channel.value, "notification_id": str(n.id), "delivery_status": n.status, "error": n.last_error},
            )
        )
    ctx.audit("referral.notify", "referral", r.id, patient_id=r.patient_id, details={"channel": req.channel.value, "status": n.status})
    ctx.db.commit()
    return r, n


def book_referral(ctx: AuthContext, referral_id: uuid.UUID, req: ReferralBookRequest) -> Referral:
    ctx.require(P.REFERRALS_WRITE)
    r = ctx.db.scalar(select(Referral).where(Referral.id == referral_id, Referral.organization_id == ctx.org_id))
    if r is None:
        raise NotFound("Referral not found")
    if r.status in {ReferralStatus.PROPOSED.value, ReferralStatus.REJECTED.value, ReferralStatus.CANCELLED.value}:
        raise ValidationFailed(f"Cannot book referral in status '{r.status}'")
    old = r.status
    r.status = ReferralStatus.BOOKED.value
    r.appointment_at = req.appointment_at
    r.appointment_reference = req.appointment_reference
    if req.facility_id:
        fac = ctx.db.scalar(select(CareFacility).where(CareFacility.id == req.facility_id, CareFacility.organization_id == ctx.org_id))
        if fac is None:
            raise NotFound("Care facility not found")
        r.facility_id = fac.id
        r.owner_facility_label = fac.name
    ctx.db.add(
        ReferralEvent(
            referral_id=r.id,
            event_type="status_change",
            from_status=old,
            to_status=r.status,
            actor_user_id=ctx.user.id,
            actor_label=ctx.user.email,
            details={"appointment_at": req.appointment_at.isoformat(), "reference": req.appointment_reference, "notes": req.notes},
        )
    )
    ctx.audit("referral.book", "referral", r.id, patient_id=r.patient_id)
    ctx.db.commit()
    return r


def complete_referral_consultation(ctx: AuthContext, referral_id: uuid.UUID, req: ReferralCompleteRequest) -> Referral:
    ctx.require(P.REFERRALS_WRITE)
    r = ctx.db.scalar(select(Referral).where(Referral.id == referral_id, Referral.organization_id == ctx.org_id))
    if r is None:
        raise NotFound("Referral not found")
    if r.status in {ReferralStatus.PROPOSED.value, ReferralStatus.REJECTED.value, ReferralStatus.CANCELLED.value}:
        raise ValidationFailed(f"Cannot mark consultation completed in status '{r.status}'")
    old = r.status
    r.status = ReferralStatus.CONSULTATION_COMPLETED.value
    r.consultation_completed_at = req.completed_at or utcnow()
    r.follow_up_due_at = r.consultation_completed_at + timedelta(days=14)
    if r.sla_due_at and r.consultation_completed_at <= r.sla_due_at:
        r.sla_status = SlaStatus.MET.value
    ctx.db.add(
        ReferralEvent(
            referral_id=r.id,
            event_type="status_change",
            from_status=old,
            to_status=r.status,
            actor_user_id=ctx.user.id,
            actor_label=ctx.user.email,
            details={"notes": req.notes},
        )
    )
    ctx.audit("referral.complete_consultation", "referral", r.id, patient_id=r.patient_id)
    ctx.db.commit()
    return r


def mark_referral_missed(ctx: AuthContext, referral_id: uuid.UUID, notes: str | None = None) -> Referral:
    ctx.require(P.REFERRALS_WRITE)
    r = ctx.db.scalar(select(Referral).where(Referral.id == referral_id, Referral.organization_id == ctx.org_id))
    if r is None:
        raise NotFound("Referral not found")
    old = r.status
    r.status = ReferralStatus.MISSED.value
    r.escalation_level += 1
    ctx.db.add(
        ReferralEvent(
            referral_id=r.id,
            event_type="missed_appointment",
            from_status=old,
            to_status=r.status,
            actor_user_id=ctx.user.id,
            actor_label=ctx.user.email,
            details={"notes": notes, "escalation_level": r.escalation_level},
        )
    )
    ctx.audit("referral.missed", "referral", r.id, patient_id=r.patient_id)
    ctx.db.commit()
    return r


def verify_referral_outcome(ctx: AuthContext, referral_id: uuid.UUID, req: OutcomeVerificationCreate) -> OutcomeVerification:
    ctx.require(P.OUTCOMES_VERIFY)
    r = ctx.db.scalar(select(Referral).where(Referral.id == referral_id, Referral.organization_id == ctx.org_id))
    if r is None:
        raise NotFound("Referral not found")
    existing = ctx.db.scalar(select(OutcomeVerification).where(OutcomeVerification.referral_id == r.id))
    if existing is not None:
        raise Conflict("Outcome has already been verified for this referral")
    if r.status in {ReferralStatus.PROPOSED.value, ReferralStatus.REJECTED.value, ReferralStatus.CANCELLED.value}:
        raise ValidationFailed(f"Cannot verify outcome while referral is '{r.status}'")

    now = utcnow()
    ov = OutcomeVerification(
        organization_id=ctx.org_id,
        referral_id=r.id,
        verified_by_id=ctx.user.id,
        outcome=req.outcome,
        verification_method=req.verification_method,
        notes=req.notes,
        follow_up_run_id=req.follow_up_run_id,
        verified_at=now,
    )
    ctx.db.add(ov)
    old = r.status
    r.status = ReferralStatus.OUTCOME_VERIFIED.value
    r.outcome_verified_at = now
    r.closed_at = now
    if r.sla_status in {SlaStatus.ON_TRACK.value, SlaStatus.AT_RISK.value}:
        r.sla_status = SlaStatus.MET.value
    ctx.db.add(
        ReferralEvent(
            referral_id=r.id,
            event_type="status_change",
            from_status=old,
            to_status=r.status,
            actor_user_id=ctx.user.id,
            actor_label=ctx.user.email,
            details={"outcome": req.outcome, "method": req.verification_method},
        )
    )
    ctx.audit("outcome.verify", "outcome_verification", ov.id, patient_id=r.patient_id, details={"outcome": req.outcome})
    ctx.db.commit()
    return ov


def evaluate_referral_slas(db, *, organization_id: uuid.UUID | None = None) -> dict:
    """Periodic / on-demand SLA monitor: flags at-risk, breached, and missed appointments, and escalates."""
    now = utcnow()
    open_statuses = [
        ReferralStatus.APPROVED.value,
        ReferralStatus.PATIENT_NOTIFIED.value,
        ReferralStatus.BOOKED.value,
        ReferralStatus.MISSED.value,
    ]
    stmt = select(Referral).where(Referral.status.in_(open_statuses))
    if organization_id:
        stmt = stmt.where(Referral.organization_id == organization_id)

    refs = db.scalars(stmt).all()
    escalated = 0
    at_risk = 0
    missed_detected = 0

    for r in refs:
        # Detect past-due booked appointments
        if r.status == ReferralStatus.BOOKED.value and r.appointment_at and r.appointment_at + timedelta(hours=2) < now:
            old = r.status
            r.status = ReferralStatus.MISSED.value
            r.escalation_level += 1
            missed_detected += 1
            db.add(
                ReferralEvent(
                    referral_id=r.id,
                    event_type="missed_appointment",
                    from_status=old,
                    to_status=r.status,
                    actor_label="system:sla_monitor",
                    details={"appointment_at": r.appointment_at.isoformat()},
                )
            )
            if r.owner_user_id:
                from app.models.identity import User

                owner = db.get(User, r.owner_user_id)
                if owner:
                    dispatch_notification(
                        db,
                        organization_id=r.organization_id,
                        channel=NotificationChannel.IN_APP,
                        category="sla",
                        subject=f"Missed Appointment Detected ({r.pathway})",
                        body=f"Booked appointment for referral {r.id} passed without completion; follow-up required.",
                        recipient_user=owner,
                        referral_id=r.id,
                        idempotency_key=f"sla:missed:{r.id}:{r.escalation_level}",
                    )

        if r.sla_due_at is not None:
            if now > r.sla_due_at and r.sla_status != SlaStatus.BREACHED.value:
                r.sla_status = SlaStatus.BREACHED.value
                r.escalation_level += 1
                old = r.status
                r.status = ReferralStatus.ESCALATED.value
                escalated += 1
                db.add(
                    ReferralEvent(
                        referral_id=r.id,
                        event_type="escalation",
                        from_status=old,
                        to_status=r.status,
                        actor_label="system:sla_monitor",
                        details={"sla_due_at": r.sla_due_at.isoformat(), "reason": "SLA breached"},
                    )
                )
            elif r.sla_due_at - now <= timedelta(hours=12) and r.sla_status == SlaStatus.ON_TRACK.value:
                r.sla_status = SlaStatus.AT_RISK.value
                at_risk += 1

    db.commit()
    return {"checked": len(refs), "escalated": escalated, "at_risk": at_risk, "missed_detected": missed_detected}


def list_emergencies(ctx: AuthContext, status: str | None = None) -> list[EmergencyEvent]:
    ctx.require(P.PIPELINE_READ)
    stmt = select(EmergencyEvent).where(EmergencyEvent.organization_id == ctx.org_id)
    if status:
        stmt = stmt.where(EmergencyEvent.status == status)
    return list(ctx.db.scalars(stmt.order_by(EmergencyEvent.created_at.desc()).limit(100)).all())


def resolve_emergency(ctx: AuthContext, event_id: uuid.UUID, req: EmergencyResolveRequest) -> EmergencyEvent:
    ctx.require(P.REVIEWS_SIGN)
    ev = ctx.db.scalar(select(EmergencyEvent).where(EmergencyEvent.id == event_id, EmergencyEvent.organization_id == ctx.org_id))
    if ev is None:
        raise NotFound("Emergency event not found")
    now = utcnow()
    if req.action == "acknowledge":
        ev.status = "acknowledged"
        ev.acknowledged_by_id = ctx.user.id
        ev.acknowledged_at = now
    else:
        ev.status = "resolved"
        if not ev.acknowledged_at:
            ev.acknowledged_by_id = ctx.user.id
            ev.acknowledged_at = now
        ev.resolved_by_id = ctx.user.id
        ev.resolved_at = now
    if req.notes:
        ev.resolution_notes = req.notes
    ctx.audit(f"emergency.{req.action}", "emergency_event", ev.id, patient_id=ev.patient_id, details={"notes": req.notes})
    ctx.db.commit()
    return ev


def list_interventions(ctx: AuthContext, track: str | None = None, department_id: uuid.UUID | None = None) -> list[Intervention]:
    ctx.require(P.INTERVENTIONS_READ)
    stmt = select(Intervention).where(Intervention.organization_id == ctx.org_id)
    if track:
        stmt = stmt.where(Intervention.track == track)
    if department_id:
        stmt = stmt.where(Intervention.department_id == department_id)
    return list(ctx.db.scalars(stmt.order_by(Intervention.created_at.desc()).limit(100)).all())


def create_intervention(ctx: AuthContext, req: InterventionCreate) -> Intervention:
    ctx.require(P.INTERVENTIONS_WRITE)
    ctx.require_track(req.track.value)
    iv = Intervention(
        organization_id=ctx.org_id,
        track=req.track.value,
        patient_id=req.patient_id,
        department_id=req.department_id,
        referral_id=req.referral_id,
        intervention_type=req.intervention_type.value,
        status=InterventionStatus.PLANNED.value,
        title=req.title,
        details=req.details,
        assigned_to_id=req.assigned_to_id or ctx.user.id,
        due_at=req.due_at,
        created_by_label=ctx.user.email,
    )
    ctx.db.add(iv)
    ctx.db.flush()
    ctx.audit("intervention.create", "intervention", iv.id, patient_id=req.patient_id)
    ctx.db.commit()
    return iv


def update_intervention(ctx: AuthContext, intervention_id: uuid.UUID, req: InterventionUpdateRequest) -> Intervention:
    ctx.require(P.INTERVENTIONS_WRITE)
    iv = ctx.db.scalar(select(Intervention).where(Intervention.id == intervention_id, Intervention.organization_id == ctx.org_id))
    if iv is None:
        raise NotFound("Intervention not found")
    iv.status = req.status.value
    if req.details is not None:
        iv.details = req.details
    if req.status == InterventionStatus.COMPLETED:
        iv.completed_at = utcnow()
        iv.completed_by_id = ctx.user.id
    ctx.audit("intervention.update", "intervention", iv.id, details={"status": iv.status})
    ctx.db.commit()
    return iv


def list_insurance_plans(ctx: AuthContext) -> list[InsurancePlan]:
    ctx.require(P.ORG_READ)
    return list(ctx.db.scalars(select(InsurancePlan).where(InsurancePlan.organization_id == ctx.org_id, InsurancePlan.is_active.is_(True)).order_by(InsurancePlan.name)).all())


def create_insurance_plan(ctx: AuthContext, req: InsurancePlanCreate) -> InsurancePlan:
    ctx.require(P.SETTINGS_MANAGE)
    existing = ctx.db.scalar(select(InsurancePlan.id).where(InsurancePlan.organization_id == ctx.org_id, InsurancePlan.code == req.code.strip()))
    if existing:
        raise Conflict("Insurance plan code already exists")
    plan = InsurancePlan(
        organization_id=ctx.org_id,
        code=req.code.strip(),
        name=req.name.strip(),
        payer_name=req.payer_name,
        network_tier=req.network_tier,
        covered_pathways=[p.value for p in req.covered_pathways],
        requires_preauthorization=req.requires_preauthorization,
        verification_source=req.verification_source,
    )
    ctx.db.add(plan)
    ctx.db.flush()
    ctx.audit("insurance_plan.create", "insurance_plan", plan.id, details={"code": plan.code})
    ctx.db.commit()
    return plan


def list_care_facilities(ctx: AuthContext) -> list[CareFacility]:
    ctx.require(P.ORG_READ)
    return list(ctx.db.scalars(select(CareFacility).where(CareFacility.organization_id == ctx.org_id, CareFacility.is_active.is_(True)).order_by(CareFacility.name)).all())


def create_care_facility(ctx: AuthContext, req: CareFacilityCreate) -> CareFacility:
    ctx.require(P.SETTINGS_MANAGE)
    existing = ctx.db.scalar(select(CareFacility.id).where(CareFacility.organization_id == ctx.org_id, CareFacility.name == req.name.strip()))
    if existing:
        raise Conflict("Care facility with that name already exists")
    fac = CareFacility(
        organization_id=ctx.org_id,
        name=req.name.strip(),
        facility_type=req.facility_type,
        pathways=[p.value for p in req.pathways],
        specialties=req.specialties,
        accepted_plan_ids=req.accepted_plan_ids,
        address=req.address,
        contact_phone=req.contact_phone,
        contact_email=str(req.contact_email) if req.contact_email else None,
        accepting_referrals=req.accepting_referrals,
        typical_wait_days=req.typical_wait_days,
    )
    ctx.db.add(fac)
    ctx.db.flush()
    ctx.audit("care_facility.create", "care_facility", fac.id, details={"name": fac.name})
    ctx.db.commit()
    return fac


def list_notifications(ctx: AuthContext, params: PageParams) -> dict:
    ctx.require(P.NOTIFICATIONS_READ)
    stmt = select(Notification).where(Notification.organization_id == ctx.org_id)
    if not ctx.has(P.ORG_MANAGE):
        stmt = stmt.where(Notification.recipient_user_id == ctx.user.id)
    return paginate(
        ctx.db,
        stmt,
        params,
        sortable={"created_at": Notification.created_at},
        default_sort=Notification.created_at.desc(),
    )


def mark_notification_read(ctx: AuthContext, notif_id: uuid.UUID) -> Notification:
    n = ctx.db.scalar(select(Notification).where(Notification.id == notif_id, Notification.organization_id == ctx.org_id))
    if n is None:
        raise NotFound("Notification not found")
    if n.recipient_user_id and n.recipient_user_id != ctx.user.id and not ctx.has(P.ORG_MANAGE):
        raise NotFound("Notification not found")
    if not n.read_at:
        n.read_at = utcnow()
        ctx.db.commit()
    return n


def list_integrations(ctx: AuthContext) -> list[dict]:
    ctx.require(P.SETTINGS_READ)
    from app.core.config import get_settings

    s = get_settings()
    rows = {
        c.integration: c
        for c in ctx.db.scalars(select(IntegrationConfig).where(IntegrationConfig.organization_id == ctx.org_id)).all()
    }
    env_flags = {
        "llm": s.llm_configured,
        "smtp": s.smtp_configured,
        "twilio": s.twilio_configured,
        "malaffi": bool(s.malaffi_base_url and s.malaffi_client_id and s.malaffi_client_secret),
        "sahatna": bool(s.sahatna_base_url and s.sahatna_api_key),
    }
    out = []
    for name in ("llm", "malaffi", "sahatna", "smtp", "twilio"):
        c = rows.get(name)
        env_ok = env_flags[name]
        status = c.status if c else (IntegrationStatus.CONFIGURED.value if env_ok else IntegrationStatus.NOT_CONFIGURED.value)
        out.append(
            {
                "integration": name,
                "status": status,
                "enabled": c.enabled if c else env_ok,
                "settings": c.settings if c else {},
                "has_secrets": bool(c and c.secrets_encrypted) or env_ok,
                "env_configured": env_ok,
                "last_tested_at": c.last_tested_at if c else None,
                "last_test_result": c.last_test_result if c else None,
            }
        )
    return out


def upsert_integration(ctx: AuthContext, name: str, req: IntegrationConfigUpdate) -> dict:
    ctx.require(P.SETTINGS_MANAGE)
    if name not in {"llm", "malaffi", "sahatna", "smtp", "twilio"}:
        raise ValidationFailed(f"Unsupported integration: {name}")
    row = ctx.db.scalar(
        select(IntegrationConfig).where(IntegrationConfig.organization_id == ctx.org_id, IntegrationConfig.integration == name)
    )
    if row is None:
        row = IntegrationConfig(organization_id=ctx.org_id, integration=name)
        ctx.db.add(row)
    row.enabled = req.enabled
    row.settings = req.settings
    if req.secrets is not None:
        row.secrets_encrypted = encrypt_str(json.dumps(req.secrets))
    row.status = IntegrationStatus.CONFIGURED.value if req.enabled else IntegrationStatus.DISABLED.value
    ctx.audit("integration.update", "integration_config", details={"integration": name, "enabled": req.enabled})
    ctx.db.commit()
    return [x for x in list_integrations(ctx) if x["integration"] == name][0]


def test_integration(ctx: AuthContext, name: str) -> dict:
    ctx.require(P.SETTINGS_MANAGE)
    row = ctx.db.scalar(
        select(IntegrationConfig).where(IntegrationConfig.organization_id == ctx.org_id, IntegrationConfig.integration == name)
    )
    org_cfg = dict(row.settings) if row else {}
    if row and row.secrets_encrypted:
        from app.core.security import decrypt_str

        raw = decrypt_str(row.secrets_encrypted)
        if raw:
            org_cfg.update(json.loads(raw))

    if name == "malaffi":
        from app.integrations.malaffi import test_connection

        res = test_connection(org_cfg or None)
    elif name == "sahatna":
        from app.integrations.sahatna import test_connection as test_sahatna

        res = test_sahatna(org_cfg or None)
    elif name == "llm":
        from app.core.config import get_settings

        s = get_settings()
        provider = org_cfg.get("provider") or s.llm_provider
        has_key = bool(org_cfg.get("api_key") or s.llm_api_key)
        res = (
            {"status": IntegrationStatus.CONFIGURED.value, "connected": True, "message": f"LLM provider '{provider}' credentials configured."}
            if provider != "none" and has_key
            else {"status": IntegrationStatus.NOT_CONFIGURED.value, "connected": False, "message": "No LLM provider API key configured."}
        )
    elif name == "smtp":
        from app.core.config import get_settings

        s = get_settings()
        ok = bool((org_cfg.get("host") or s.smtp_host) and (org_cfg.get("from_address") or s.smtp_from))
        res = (
            {"status": IntegrationStatus.CONFIGURED.value, "connected": True, "message": "SMTP host and sender configured."}
            if ok
            else {"status": IntegrationStatus.NOT_CONFIGURED.value, "connected": False, "message": "SMTP host/sender not configured."}
        )
    elif name == "twilio":
        from app.core.config import get_settings

        s = get_settings()
        ok = bool((org_cfg.get("account_sid") or s.twilio_account_sid) and (org_cfg.get("auth_token") or s.twilio_auth_token))
        res = (
            {"status": IntegrationStatus.CONFIGURED.value, "connected": True, "message": "Twilio credentials configured."}
            if ok
            else {"status": IntegrationStatus.NOT_CONFIGURED.value, "connected": False, "message": "Twilio credentials not configured."}
        )
    else:
        raise ValidationFailed(f"Unsupported integration: {name}")

    if row is None:
        row = IntegrationConfig(organization_id=ctx.org_id, integration=name, enabled=res.get("connected", False))
        ctx.db.add(row)
    row.status = res["status"]
    row.last_tested_at = utcnow()
    row.last_test_result = res
    ctx.audit("integration.test", "integration_config", details={"integration": name, "status": res["status"]})
    ctx.db.commit()
    return res
