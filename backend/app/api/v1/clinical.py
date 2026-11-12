"""Clinical, track-specific data ingestion and WorkSafe API routers."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
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
