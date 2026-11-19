"""Clinical, track-specific data ingestion and WorkSafe API routers."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Body, Depends, Query
from pydantic import BaseModel, EmailStr
from sqlalchemy import select

from app.api.deps import AuthContext, requires, requires_track
from app.core.permissions import P, Track
from app.engine.metrics import METRIC_CATALOG
from app.models.care import CareFacility, InsurancePlan, Referral
from app.models.clinical import Consent, Observation, Patient
from app.models.engine import PipelineRun, ScoringResult
from app.schemas.clinical import (
    CheckInCreate,
    CheckInOut,
    CognitiveAssessmentCreate,
    CognitiveAssessmentOut,
    ConsentCreate,
    ConsentOut,
    DepartmentCreate,
    DepartmentOut,
    EnrollmentCreate,
    EnrollmentOut,
    ObservationCreate,
    ObservationOut,
    PatientCreate,
    PatientDetailOut,
    PatientSummaryOut,
    PatientUpdate,
    ScreeningCreate,
    ScreeningOut,
    WearableBatchCreate,
    WearableBatchOut,
    WorkerReadinessCreate,
    WorkplaceAssessmentCreate,
    WorkplaceAssessmentOut,
    WorkplaceCreate,
    WorkplaceOut,
)
from app.schemas.common import Page, PageParams
from app.services import patients as pat_svc
from app.services import signals as sig_svc
from app.services import workforce as wf_svc

patients_router = APIRouter(prefix="/patients", tags=["patients"])
consents_router = APIRouter(prefix="/consents", tags=["consents"])
observations_router = APIRouter(prefix="/observations", tags=["observations"])
wearables_router = APIRouter(prefix="/wearables", tags=["wearables"])
checkins_router = APIRouter(prefix="/check-ins", tags=["check-ins"])
screenings_router = APIRouter(prefix="/screenings", tags=["screenings"])
cognitive_router = APIRouter(prefix="/cognitive-assessments", tags=["cognitive-assessments"])
workforce_router = APIRouter(prefix="/workforce", tags=["workforce"])


# --- Patients ---
@patients_router.get("", response_model=Page[PatientSummaryOut])
def list_patients(
    params: PageParams = Depends(),
    track: str | None = Query(None),
    risk_tier: str | None = Query(None),
    department_id: uuid.UUID | None = Query(None),
    active_only: bool = Query(True),
    ctx: AuthContext = Depends(requires(P.PATIENTS_READ)),
):
    return pat_svc.list_patients(ctx, params, track=track, risk_tier=risk_tier, department_id=department_id, active_only=active_only)


@patients_router.post("", response_model=PatientDetailOut, status_code=201)
def create_patient(req: PatientCreate, ctx: AuthContext = Depends(requires(P.PATIENTS_WRITE))):
    return pat_svc.create_patient(ctx, req)


@patients_router.get("/{patient_id}", response_model=PatientDetailOut)
def get_patient(patient_id: uuid.UUID, ctx: AuthContext = Depends(requires(P.PATIENTS_READ))):
    return pat_svc.get_patient(ctx, patient_id)


@patients_router.patch("/{patient_id}", response_model=PatientDetailOut)
def update_patient(patient_id: uuid.UUID, req: PatientUpdate, ctx: AuthContext = Depends(requires(P.PATIENTS_WRITE))):
    return pat_svc.update_patient(ctx, patient_id, req)


@patients_router.post("/{patient_id}/enrollments", response_model=EnrollmentOut)
def enroll_patient(patient_id: uuid.UUID, req: EnrollmentCreate, ctx: AuthContext = Depends(requires(P.PATIENTS_WRITE))):
    return pat_svc.enroll_track(ctx, patient_id, req)


class PortalInvitationCreate(BaseModel):
    recipient_email: EmailStr


@patients_router.post("/{patient_id}/portal-invitations", status_code=201)
def create_portal_invitation(
    patient_id: uuid.UUID,
    recipient_email: EmailStr | None = Query(default=None),
    body: PortalInvitationCreate | None = Body(default=None),
    ctx: AuthContext = Depends(requires(P.PATIENTS_WRITE)),
):
    """Issue a single-use, expiring, recipient-bound portal invitation (stored as token hash)."""
    from datetime import timedelta
    from app.core.errors import ValidationFailed
    from app.core.security import hash_token, new_token
    from app.models.base import utcnow
    from app.models.identity import PortalInvitation

    email_val = (str(body.recipient_email) if body is not None else (str(recipient_email) if recipient_email else "")).strip().lower()
    if not email_val:
        raise ValidationFailed("recipient_email is required")

    detail = pat_svc.get_patient(ctx, patient_id)
    now = utcnow()
    # Invalidate any prior unused invitations for this patient
    prior = ctx.db.scalars(
        select(PortalInvitation).where(
            PortalInvitation.patient_id == detail.id,
            PortalInvitation.organization_id == ctx.org_id,
            PortalInvitation.accepted_at.is_(None),
            PortalInvitation.revoked_at.is_(None),
        )
    ).all()
    for inv in prior:
        inv.revoked_at = now

    raw_token = new_token(32)
    expires_at = now + timedelta(hours=72)
    inv = PortalInvitation(
        organization_id=ctx.org_id,
        patient_id=detail.id,
        recipient_email=email_val,
        token_hash=hash_token(raw_token),
        purpose="portal_link",
        expires_at=expires_at,
        created_by_id=ctx.user.id,
    )
    ctx.db.add(inv)
    ctx.db.flush()
    from app.services.messaging import queue_email, public_link
    from app.core.config import get_settings
    from app.models.messaging import EmailDelivery
    # A replacement invitation invalidates queued copies of the previous link.
    for old in ctx.db.scalars(select(EmailDelivery).where(EmailDelivery.organization_id == ctx.org_id, EmailDelivery.category == 'portal_invitation', EmailDelivery.idempotency_key.in_([f'portal-invite:{i.id}' for i in prior]))):
        if old.status != 'sent':
            old.status = 'cancelled'
    invitation_url = public_link('/accept-invitation', token=raw_token)
    delivery = queue_email(ctx.db,to=email_val,subject='Your Recova patient portal invitation',
        body=f'Your facility, {ctx.organization.name}, has invited you to your patient portal.\nOpen your private setup link:\n{invitation_url}\nIt expires in 72 hours. Existing users sign in with their current password.',
        category='portal_invitation',organization_id=ctx.org_id,key=f'portal-invite:{inv.id}',expires_at=expires_at)
    ctx.audit("patient.portal_invitation.issue", "portal_invitation", inv.id, patient_id=detail.id, details={"patient_id": str(detail.id)})
    ctx.db.commit()
    primary_prog = ctx.organization.primary_programme if ctx.organization else None
    return {
        "invitation_id": str(inv.id),
        "patient_id": str(detail.id),
        "organization_id": str(ctx.org_id),
        "organization_name": ctx.organization.name if ctx.organization else None,
        "primary_programme": primary_prog,
        "recipient_email": inv.recipient_email,
        "purpose": inv.purpose,
        "expires_at": inv.expires_at,
        "invitation_token": raw_token if get_settings().environment != 'production' else None,
        "delivery_status": delivery.status,
        "delivery_id": str(delivery.id),
        "invitation_url": invitation_url if get_settings().environment != 'production' else None,
    }


@patients_router.get("/{patient_id}/passport")
def get_family_health_passport(patient_id: uuid.UUID, ctx: AuthContext = Depends(requires(P.PATIENTS_READ))):
    """Recova Loop Family Health Passport: unified longitudinal screening, insurance & referral summary."""
    detail = pat_svc.get_patient(ctx, patient_id)
    plan = ctx.db.get(InsurancePlan, detail.insurance_plan_id) if detail.insurance_plan_id else None
    referrals = ctx.db.scalars(
        select(Referral).where(Referral.organization_id == ctx.org_id, Referral.patient_id == patient_id).order_by(Referral.created_at.desc())
    ).all()
    latest_obs = ctx.db.scalars(
        select(Observation)
        .where(Observation.organization_id == ctx.org_id, Observation.patient_id == patient_id)
        .order_by(Observation.effective_at.desc())
        .limit(30)
    ).all()
    latest_scoring = ctx.db.scalar(
        select(ScoringResult)
        .where(ScoringResult.organization_id == ctx.org_id, ScoringResult.patient_id == patient_id)
        .order_by(ScoringResult.computed_at.desc())
        .limit(1)
    )
    consents = ctx.db.scalars(
        select(Consent).where(Consent.organization_id == ctx.org_id, Consent.patient_id == patient_id).order_by(Consent.effective_at.desc())
    ).all()
    facilities = {
        f.id: f.name
        for f in ctx.db.scalars(select(CareFacility).where(CareFacility.organization_id == ctx.org_id)).all()
    }
    return {
        "patient": detail,
        "insurance_plan": {
            "id": str(plan.id),
            "code": plan.code,
            "name": plan.name,
            "network_tier": plan.network_tier,
            "covered_pathways": plan.covered_pathways,
        } if plan else None,
        "latest_risk_tier": latest_scoring.risk_tier if latest_scoring else None,
        "latest_confidence_index": latest_scoring.confidence_index if latest_scoring else None,
        "recent_observations": [ObservationOut.model_validate(o) for o in latest_obs],
        "referrals": [
            {
                "id": str(r.id),
                "track": r.track,
                "pathway": r.pathway,
                "status": r.status,
                "priority": r.priority,
                "coverage_status": r.coverage_status,
                "facility_name": facilities.get(r.facility_id) if r.facility_id else r.owner_facility_label,
                "sla_due_at": r.sla_due_at,
                "sla_status": r.sla_status,
                "appointment_at": r.appointment_at,
                "outcome_verified_at": r.outcome_verified_at,
            }
            for r in referrals
        ],
        "consents": [ConsentOut.model_validate(c) for c in consents],
    }


# --- Consents ---
@consents_router.get("/patient/{patient_id}", response_model=list[ConsentOut])
def list_consents(patient_id: uuid.UUID, ctx: AuthContext = Depends(requires(P.CONSENTS_READ))):
    return pat_svc.list_consents(ctx, patient_id)


@consents_router.post("", response_model=ConsentOut, status_code=201)
def record_consent(req: ConsentCreate, ctx: AuthContext = Depends(requires(P.CONSENTS_WRITE))):
    return pat_svc.record_consent(ctx, req)


@consents_router.post("/{consent_id}/revoke", response_model=ConsentOut)
def revoke_consent(consent_id: uuid.UUID, reason: str | None = Query(None), ctx: AuthContext = Depends(requires(P.CONSENTS_WRITE))):
    return pat_svc.revoke_consent(ctx, consent_id, reason=reason)


# --- Observations ---
@observations_router.get("/catalog")
def metric_catalog(ctx: AuthContext = Depends(requires(P.OBSERVATIONS_READ))):
    return [
        {
            "code": s.code,
            "label": s.label,
            "unit": s.unit,
            "stream_name": s.stream_name,
            "direction": s.direction,
            "valid_min": s.valid_min,
            "valid_max": s.valid_max,
            "loinc_code": s.loinc_code,
        }
        for s in METRIC_CATALOG.values()
    ]


@observations_router.get("/patient/{patient_id}", response_model=Page[ObservationOut])
def list_observations(
    patient_id: uuid.UUID,
    params: PageParams = Depends(),
    metric_code: str | None = Query(None),
    track: str | None = Query(None),
    ctx: AuthContext = Depends(requires(P.OBSERVATIONS_READ)),
):
    return sig_svc.list_observations(ctx, patient_id, params, metric_code=metric_code, track=track)


@observations_router.post("", response_model=ObservationOut, status_code=201)
def create_observation(req: ObservationCreate, ctx: AuthContext = Depends(requires(P.OBSERVATIONS_WRITE))):
    return sig_svc.record_observation(ctx, req)


# --- Wearables ---
@wearables_router.post("/ingest", status_code=201)
def ingest_wearables(req: WearableBatchCreate, ctx: AuthContext = Depends(requires(P.OBSERVATIONS_WRITE))):
    res = sig_svc.ingest_wearable_batch(ctx, req)
    return {"batch": WearableBatchOut.model_validate(res["batch"]), "run_id": res["run_id"]}


# --- Check-ins ---
@checkins_router.get("/patient/{patient_id}", response_model=list[CheckInOut])
def list_checkins(patient_id: uuid.UUID, ctx: AuthContext = Depends(requires(P.OBSERVATIONS_READ))):
    return sig_svc.list_checkins(ctx, patient_id)


@checkins_router.post("", status_code=201)
def create_checkin(req: CheckInCreate, ctx: AuthContext = Depends(requires(P.OBSERVATIONS_WRITE))):
    res = sig_svc.create_checkin(ctx, req)
    return {"check_in": CheckInOut.model_validate(res["check_in"]), "run_id": res["run_id"]}


# --- Screenings (Loop) ---
@screenings_router.get("/patient/{patient_id}", response_model=list[ScreeningOut])
def list_screenings(patient_id: uuid.UUID, ctx: AuthContext = Depends(requires_track(Track.LOOP, P.OBSERVATIONS_READ))):
    return sig_svc.list_screenings(ctx, patient_id)


@screenings_router.post("", status_code=201)
def create_screening(req: ScreeningCreate, ctx: AuthContext = Depends(requires_track(Track.LOOP, P.OBSERVATIONS_WRITE))):
    res = sig_svc.create_screening(ctx, req)
    return {"screening": ScreeningOut.model_validate(res["screening"]), "run_id": res["run_id"]}


# --- Cognitive Assessments (Neuro) ---
@cognitive_router.get("/patient/{patient_id}", response_model=list[CognitiveAssessmentOut])
def list_cognitive(patient_id: uuid.UUID, ctx: AuthContext = Depends(requires_track(Track.NEURO, P.OBSERVATIONS_READ))):
    return sig_svc.list_cognitive_assessments(ctx, patient_id)


@cognitive_router.post("", status_code=201)
def create_cognitive(req: CognitiveAssessmentCreate, ctx: AuthContext = Depends(requires_track(Track.NEURO, P.COGNITIVE_ADMINISTER))):
    res = sig_svc.create_cognitive_assessment(ctx, req)
    return {"assessment": CognitiveAssessmentOut.model_validate(res["assessment"]), "run_id": res["run_id"]}


# --- Workforce (WorkSafe) ---
@workforce_router.get("/workplaces", response_model=list[WorkplaceOut])
def list_workplaces(ctx: AuthContext = Depends(requires_track(Track.WORKSAFE, P.WORKFORCE_AGGREGATE))):
    return wf_svc.list_workplaces(ctx)


@workforce_router.post("/workplaces", response_model=WorkplaceOut, status_code=201)
def create_workplace(req: WorkplaceCreate, ctx: AuthContext = Depends(requires_track(Track.WORKSAFE, P.WORKFORCE_MANAGE))):
    return wf_svc.create_workplace(ctx, req)


@workforce_router.get("/departments", response_model=list[DepartmentOut])
def list_departments(ctx: AuthContext = Depends(requires_track(Track.WORKSAFE, P.WORKFORCE_AGGREGATE))):
    return wf_svc.list_departments(ctx)


@workforce_router.post("/departments", response_model=DepartmentOut, status_code=201)
def create_department(req: DepartmentCreate, ctx: AuthContext = Depends(requires_track(Track.WORKSAFE, P.WORKFORCE_MANAGE))):
    return wf_svc.create_department(ctx, req)


@workforce_router.get("/assessments", response_model=list[WorkplaceAssessmentOut])
def list_workplace_assessments(
    department_id: uuid.UUID | None = Query(None),
    ctx: AuthContext = Depends(requires_track(Track.WORKSAFE, P.WORKFORCE_AGGREGATE)),
):
    return wf_svc.list_workplace_assessments(ctx, department_id=department_id)


@workforce_router.post("/assessments", response_model=WorkplaceAssessmentOut, status_code=201)
def create_workplace_assessment(
    req: WorkplaceAssessmentCreate,
    ctx: AuthContext = Depends(requires_track(Track.WORKSAFE, P.WORKFORCE_WRITE)),
):
    return wf_svc.record_workplace_assessment(ctx, req)


@workforce_router.post("/readiness", status_code=201)
def submit_readiness(req: WorkerReadinessCreate, ctx: AuthContext = Depends(requires_track(Track.WORKSAFE, P.OBSERVATIONS_WRITE))):
    res = wf_svc.record_worker_readiness(ctx, req)
    return {"check_in": CheckInOut.model_validate(res["check_in"]), "run_id": res["run_id"]}


@workforce_router.get("/heatmap")
def department_heatmap(ctx: AuthContext = Depends(requires_track(Track.WORKSAFE, P.WORKFORCE_AGGREGATE))):
    return wf_svc.get_department_heatmap(ctx)


@workforce_router.get("/identifiable-risks")
def identifiable_worker_risks(ctx: AuthContext = Depends(requires_track(Track.WORKSAFE, P.WORKFORCE_IDENTIFIABLE))):
    return wf_svc.list_identifiable_worker_risks(ctx)
