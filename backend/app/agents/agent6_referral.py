"""Agent 6: Closed-Loop Care and Referral Orchestrator.

Matches deterministic risk tier + track + patient insurance plan against
organisation-configured CareFacility and InsurancePlan rows. Never invents
coverage or facility capacity; never auto-closes referrals or marks outcomes
verified without human verification.
"""

from __future__ import annotations

import uuid
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.schemas import Agent6Input, Agent6Output
from app.engine.scoring import DeterministicScoreBundle
from app.integrations.notifications import dispatch_notification
from app.models.base import utcnow
from app.models.care import CareFacility, InsurancePlan, Intervention, Referral, ReferralEvent
from app.models.clinical import Patient
from app.models.enums import (
    ConsentScope,
    InterventionStatus,
    InterventionType,
    NotificationChannel,
    ReferralPathway,
    ReferralPriority,
    ReferralStatus,
    RiskTier,
    SlaStatus,
)
from app.models.identity import Membership, User

# Track + RiskTier -> (pathway, priority, sla_hours, reason_template)
_ROUTING_RULES: dict[tuple[str, str], tuple[ReferralPathway, ReferralPriority, int, str]] = {
    ("core", RiskTier.RED.value): (
        ReferralPathway.ASYNC_TELECONSULT,
        ReferralPriority.URGENT,
        24,
        "Actionable pre-relapse physiological/behavioral drift (|Z| >= 1.96); urgent rehabilitation tele-consult recommended.",
    ),
    ("core", RiskTier.AMBER.value): (
        ReferralPathway.OUTPATIENT_THERAPIST,
        ReferralPriority.ROUTINE,
        72,
        "Early sub-clinical drift (1.0 <= |Z| < 1.96); outpatient therapist check-in recommended.",
    ),
    ("loop", RiskTier.RED.value): (
        ReferralPathway.SPECIALIST,
        ReferralPriority.URGENT,
        48,
        "Actionable IFHAS screening abnormality / longitudinal drift; urgent specialist/primary-care routing required.",
    ),
    ("loop", RiskTier.AMBER.value): (
        ReferralPathway.PRIMARY_CARE,
        ReferralPriority.ROUTINE,
        168,
        "Early IFHAS cardiometabolic or mood screening elevation; scheduled primary care follow-up recommended.",
    ),
    ("neuro", RiskTier.RED.value): (
        ReferralPathway.SPECIALIST,
        ReferralPriority.URGENT,
        72,
        "Confounder-adjusted cognitive longitudinal drift (|Z| >= 1.96); neurology / MoCA workup recommended.",
    ),
    ("neuro", RiskTier.AMBER.value): (
        ReferralPathway.PRIMARY_CARE,
        ReferralPriority.ROUTINE,
        336,
        "Early confounder-adjusted cognitive variance; primary care & sleep/metabolic review recommended.",
    ),
    ("worksafe", RiskTier.RED.value): (
        ReferralPathway.OCCUPATIONAL_HEALTH,
        ReferralPriority.URGENT,
        4,
        "Actionable heat-stress or fatigue drift; immediate occupational health review and shift mitigation required.",
    ),
    ("worksafe", RiskTier.AMBER.value): (
        ReferralPathway.OCCUPATIONAL_HEALTH,
        ReferralPriority.ROUTINE,
        24,
        "Early occupational heat-stress or fatigue drift; rest/hydration protocol and OSH review recommended.",
    ),
}


def _match_facility_and_coverage(
    db: Session,
    patient: Patient,
    pathway: ReferralPathway,
) -> tuple[InsurancePlan | None, str, CareFacility | None]:
    plan: InsurancePlan | None = None
    coverage_status = "no_plan"
    if patient.insurance_plan_id:
        plan = db.scalar(
            select(InsurancePlan).where(
                InsurancePlan.id == patient.insurance_plan_id,
                InsurancePlan.organization_id == patient.organization_id,
                InsurancePlan.is_active.is_(True),
            )
        )
        if plan is not None:
            if not plan.covered_pathways:
                coverage_status = "unknown"
            elif pathway.value in plan.covered_pathways:
                coverage_status = "covered"
            else:
                coverage_status = "not_covered"

    facilities = db.scalars(
        select(CareFacility).where(
            CareFacility.organization_id == patient.organization_id,
            CareFacility.is_active.is_(True),
            CareFacility.accepting_referrals.is_(True),
        )
    ).all()

    matching = [f for f in facilities if pathway.value in (f.pathways or [])]
    if not matching:
        # Emergency triage may route to any emergency-capable facility
        matching = [f for f in facilities if f.facility_type == "emergency"] if pathway == ReferralPathway.EMERGENCY_TRIAGE else []

    chosen: CareFacility | None = None
    if matching:
        if plan is not None:
            in_net = [f for f in matching if plan.id in (f.accepted_plan_ids or [])]
            chosen = sorted(in_net or matching, key=lambda f: f.typical_wait_days if f.typical_wait_days is not None else 999)[0]
            if in_net and coverage_status == "unknown":
                coverage_status = "covered"
            elif not in_net and plan is not None and coverage_status == "covered":
                # Plan covers pathway generally, but no configured facility lists this plan ID
                coverage_status = "not_covered"
        else:
            chosen = sorted(matching, key=lambda f: f.typical_wait_days if f.typical_wait_days is not None else 999)[0]

    return plan, coverage_status, chosen


def _clinical_recipients(db: Session, patient: Patient) -> list[User]:
    users: list[User] = []
    if patient.primary_clinician_id:
        u = db.get(User, patient.primary_clinician_id)
        if u and u.is_active:
            users.append(u)
    if not users:
        # Notify active clinicians/coordinators/admins in the organisation
        mems = db.scalars(
            select(Membership).where(
                Membership.organization_id == patient.organization_id,
                Membership.is_active.is_(True),
                Membership.role.in_(["clinician", "psychiatrist", "care_coordinator", "occ_health_director", "org_admin"]),
            )
        ).all()
        for m in mems[:5]:
            u = db.get(User, m.user_id)
            if u and u.is_active and u not in users:
                users.append(u)
    return users


def run_agent6(
    db: Session,
    patient: Patient,
    track: str,
    run_id: uuid.UUID,
    *,
    is_emergency: bool,
    bundle: DeterministicScoreBundle | None = None,
    emergency_event_id: uuid.UUID | None = None,
    active_scopes: set[str] | None = None,
) -> tuple[Agent6Input, Agent6Output]:
    risk_tier = RiskTier.EMERGENCY_BYPASS.value if is_emergency else (bundle.risk_tier.value if bundle else RiskTier.INDETERMINATE.value)
    inp = Agent6Input(
        track=track,
        risk_tier=risk_tier,
        is_emergency=is_emergency,
        insurance_plan_id=patient.insurance_plan_id,
    )
    now = utcnow()
    notifications_dispatched: list[dict] = []
    interventions_created: list[uuid.UUID] = []

    if is_emergency:
        pathway = ReferralPathway.EMERGENCY_TRIAGE
        priority = ReferralPriority.STAT
        sla_hours = 0.25  # 15 minutes emergency triage response target
        reason = "GATE 2 EMERGENCY BYPASS: Immediate acute crisis escalation required."
        rule_trace = {"source": "gate2_emergency", "risk_tier": risk_tier, "sla_hours": sla_hours}
    elif (track, risk_tier) in _ROUTING_RULES:
        pathway, priority, sla_hours, reason = _ROUTING_RULES[(track, risk_tier)]
        # For Loop PHQ-9 high risk, prefer therapist pathway
        if track == "loop" and bundle and bundle.primary_metric_code == "phq9_score" and risk_tier == RiskTier.RED.value:
            pathway = ReferralPathway.OUTPATIENT_THERAPIST
        rule_trace = {
            "source": "agent6_routing_table",
            "track": track,
            "risk_tier": risk_tier,
            "primary_metric": bundle.primary_metric_code if bundle else None,
            "primary_z": bundle.primary_z if bundle else None,
            "sla_hours": sla_hours,
        }
    else:
        # GREEN or INDETERMINATE: no referral opened automatically
        return inp, Agent6Output(
            pathway=ReferralPathway.ROUTINE_MONITORING.value,
            priority=ReferralPriority.ROUTINE.value,
            coverage_status="not_applicable",
            rule_trace={"source": "agent6_routing_table", "track": track, "risk_tier": risk_tier, "action": "continue_routine_monitoring"},
        )

    plan, coverage_status, facility = _match_facility_and_coverage(db, patient, pathway)

    # Deduplicate open referrals for same patient + track + pathway unless emergency
    existing_open = None
    if not is_emergency:
        existing_open = db.scalar(
            select(Referral).where(
                Referral.organization_id == patient.organization_id,
                Referral.patient_id == patient.id,
                Referral.track == track,
                Referral.pathway == pathway.value,
                Referral.status.in_(
                    [
                        ReferralStatus.PROPOSED.value,
                        ReferralStatus.APPROVED.value,
                        ReferralStatus.PATIENT_NOTIFIED.value,
                        ReferralStatus.BOOKED.value,
                        ReferralStatus.ESCALATED.value,
                    ]
                ),
            )
        )

    if existing_open is not None:
        referral = existing_open
        db.add(
            ReferralEvent(
                referral_id=referral.id,
                event_type="note",
                actor_label="system:agent6",
                details={"run_id": str(run_id), "note": f"Updated context from new pipeline run ({risk_tier})"},
            )
        )
    else:
        sla_due = now + timedelta(hours=sla_hours)
        initial_status = ReferralStatus.ESCALATED.value if is_emergency else ReferralStatus.PROPOSED.value
        referral = Referral(
            organization_id=patient.organization_id,
            patient_id=patient.id,
            run_id=run_id,
            track=track,
            pathway=pathway.value,
            priority=priority.value,
            status=initial_status,
            reason=reason,
            rule_trace={**rule_trace, "facility_matched": bool(facility), "coverage_status": coverage_status},
            facility_id=facility.id if facility else None,
            insurance_plan_id=plan.id if plan else None,
            coverage_status=coverage_status,
            owner_user_id=patient.primary_clinician_id,
            owner_facility_label=facility.name if facility else "Unassigned (configure facility)",
            target_date=sla_due,
            sla_due_at=sla_due,
            sla_status=SlaStatus.ON_TRACK.value,
            escalation_level=1 if is_emergency else 0,
            is_emergency=is_emergency,
        )
        db.add(referral)
        db.flush()
        db.add(
            ReferralEvent(
                referral_id=referral.id,
                event_type="status_change",
                from_status=None,
                to_status=initial_status,
                actor_label="system:agent6",
                details=referral.rule_trace,
            )
        )

    # WorkSafe actionable heat-stress / fatigue interventions
    if track == "worksafe" and (is_emergency or risk_tier in {RiskTier.AMBER.value, RiskTier.RED.value}):
        for itype, title, details in [
            (
                InterventionType.REST_BREAK.value,
                "Mandatory shaded cooling rest break (15-20 min)",
                "Triggered by WorkSafe physiological/heat-stress drift scoring.",
            ),
            (
                InterventionType.HYDRATION.value,
                "Electrolyte hydration & thermal recovery check",
                "Ensure fluid replacement and post-shift HR recovery check prior to resuming exertion.",
            ),
        ]:
            iv = Intervention(
                organization_id=patient.organization_id,
                track=track,
                patient_id=patient.id,
                department_id=patient.department_id,
                referral_id=referral.id,
                run_id=run_id,
                intervention_type=itype,
                status=InterventionStatus.PLANNED.value,
                title=title,
                details=details,
                rule_trace=rule_trace,
                due_at=now + timedelta(hours=1 if risk_tier == RiskTier.RED.value or is_emergency else 4),
                created_by_label="system:agent6",
            )
            db.add(iv)
            db.flush()
            interventions_created.append(iv.id)

    # Notifications:
    # - Emergency bypass: immediately notify clinical/OSH responders via in-app + email (if configured).
    # - Routine RED/AMBER: notify assigned clinician in-app that a proposed referral awaits DECIDE-AI sign-off.
    recipients = _clinical_recipients(db, patient)
    for u in recipients:
        n_inapp = dispatch_notification(
            db,
            organization_id=patient.organization_id,
            channel=NotificationChannel.IN_APP,
            category="emergency" if is_emergency else "referral",
            subject=("EMERGENCY BYPASS ALERT" if is_emergency else f"Clinical Review Required ({risk_tier})") + f": {patient.mrn}",
            body=reason,
            recipient_user=u,
            referral_id=referral.id,
            emergency_event_id=emergency_event_id,
            idempotency_key=f"run:{run_id}:user:{u.id}:in_app",
        )
        notifications_dispatched.append({"id": str(n_inapp.id), "channel": n_inapp.channel, "status": n_inapp.status})

        if is_emergency:
            n_email = dispatch_notification(
                db,
                organization_id=patient.organization_id,
                channel=NotificationChannel.EMAIL,
                category="emergency",
                subject=f"URGENT EMERGENCY ESCALATION — {patient.mrn}",
                body=f"Emergency bypass triggered on track {track}. Log into Recova immediately to acknowledge and triage.",
                recipient_user=u,
                referral_id=referral.id,
                emergency_event_id=emergency_event_id,
                idempotency_key=f"run:{run_id}:user:{u.id}:email",
            )
            notifications_dispatched.append({"id": str(n_email.id), "channel": n_email.channel, "status": n_email.status, "error": n_email.last_error})

    # Optional family/sponsor alert ONLY if emergency AND family_notification consent granted
    if is_emergency and active_scopes and ConsentScope.FAMILY_NOTIFICATION.value in active_scopes:
        n_fam = dispatch_notification(
            db,
            organization_id=patient.organization_id,
            channel=NotificationChannel.SMS,
            category="emergency",
            subject="Urgent Health Alert",
            body=f"Urgent health alert recorded for participant {patient.mrn}. Care team notified.",
            recipient_patient=patient,
            referral_id=referral.id,
            emergency_event_id=emergency_event_id,
            idempotency_key=f"run:{run_id}:family:sms",
        )
        notifications_dispatched.append({"id": str(n_fam.id), "channel": n_fam.channel, "status": n_fam.status, "error": n_fam.last_error})

    out = Agent6Output(
        pathway=pathway.value,
        priority=priority.value,
        referral_id=referral.id,
        referral_status=referral.status,
        coverage_status=coverage_status,
        facility_id=facility.id if facility else None,
        facility_name=facility.name if facility else None,
        sla_due_at=referral.sla_due_at,
        interventions_created=interventions_created,
        notifications_dispatched=notifications_dispatched,
        rule_trace=referral.rule_trace,
    )
    return inp, out
