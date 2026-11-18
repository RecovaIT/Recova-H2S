"""Benchmarks, FHIR R4 export/validation, settings (insurance/facilities/integrations), and reports."""

from __future__ import annotations

import json
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.api.deps import AuthContext, requires
from app.benchmarks.runner import create_benchmark_run, execute_benchmark_run
from app.benchmarks.suites import BENCHMARK_SUITE, SUITE_NAME, SUITE_VERSION
from app.core.errors import Forbidden, NotFound
from app.core.permissions import P
from app.core.security import decrypt_str
from app.integrations.fhir import build_patient_fhir_bundle, validate_fhir_bundle
from app.integrations.malaffi import push_fhir_bundle
from app.models.care import CareFacility, ClinicalReview, InsurancePlan, Notification, Referral
from app.models.clinical import Consent, Observation, Patient, ScreeningRecord, TrackEnrollment
from app.models.engine import AgentStepResult, EmergencyEvent, PipelineRun, ScoringResult
from app.models.enums import ConsentScope, ConsentStatus, EmergencyStatus, ReferralStatus, SlaStatus
from app.models.identity import Membership, Organization
from app.models.ops import BenchmarkRun, IntegrationConfig
from app.schemas.workflow import (
    BenchmarkRunCreate,
    BenchmarkRunDetailOut,
    BenchmarkRunOut,
    CareFacilityCreate,
    CareFacilityOut,
    InsurancePlanCreate,
    InsurancePlanOut,
    IntegrationConfigOut,
    IntegrationConfigUpdate,
)
from app.services import care as care_svc
from app.tasks.queue import enqueue

benchmarks_router = APIRouter(prefix="/benchmarks", tags=["benchmarks"])
fhir_router = APIRouter(prefix="/fhir", tags=["fhir"])
settings_router = APIRouter(prefix="/settings", tags=["settings"])
reports_router = APIRouter(prefix="/reports", tags=["reports"])


# --- Benchmarks ---
@benchmarks_router.get("/suite")
def benchmark_suite_catalog(ctx: AuthContext = Depends(requires(P.BENCHMARKS_READ))):
    return {
        "suite_name": SUITE_NAME,
        "suite_version": SUITE_VERSION,
        "total_cases": len(BENCHMARK_SUITE),
        "cases": [
            {
                "case_id": c.case_id,
                "track": c.track,
                "scenario": c.scenario,
                "category": c.category,
                "expected_risk_tier": c.expected_risk_tier,
                "expected_emergency": c.expected_emergency,
                "expected_consent_blocked": c.expected_consent_blocked,
            }
            for c in BENCHMARK_SUITE
        ],
    }


@benchmarks_router.get("/runs", response_model=list[BenchmarkRunOut])
def list_benchmark_runs(ctx: AuthContext = Depends(requires(P.BENCHMARKS_READ))):
    return list(
        ctx.db.scalars(
            select(BenchmarkRun).where(BenchmarkRun.organization_id == ctx.org_id).order_by(BenchmarkRun.created_at.desc()).limit(30)
        ).all()
    )


@benchmarks_router.post("/runs", response_model=BenchmarkRunDetailOut, status_code=201)
def start_benchmark_run(req: BenchmarkRunCreate, ctx: AuthContext = Depends(requires(P.BENCHMARKS_RUN))):
    br = create_benchmark_run(
        ctx.db,
        organization_id=ctx.org_id,
        tracks=[t.value for t in req.tracks],
        started_by_id=ctx.user.id,
    )
    if req.run_async:
        job = enqueue(
            ctx.db,
            "benchmark.run",
            {"benchmark_run_id": str(br.id)},
            organization_id=ctx.org_id,
            idempotency_key=f"benchmark:{br.id}",
            created_by_id=ctx.user.id,
            timeout_seconds=300,
        )
        br.job_id = job.id
        ctx.db.commit()
    else:
        ctx.db.commit()
        br = execute_benchmark_run(ctx.db, br.id)
    ctx.audit("benchmark.run", "benchmark_run", br.id, details={"tracks": br.tracks, "passed": br.passed_cases, "total": br.total_cases})
    ctx.db.commit()
    return _benchmark_detail(ctx, br.id)


@benchmarks_router.get("/runs/{benchmark_run_id}", response_model=BenchmarkRunDetailOut)
def get_benchmark_run(benchmark_run_id: uuid.UUID, ctx: AuthContext = Depends(requires(P.BENCHMARKS_READ))):
    return _benchmark_detail(ctx, benchmark_run_id)


def _benchmark_detail(ctx: AuthContext, benchmark_run_id: uuid.UUID) -> BenchmarkRunDetailOut:
    from app.models.ops import BenchmarkCaseResult

    br = ctx.db.scalar(
        select(BenchmarkRun).where(BenchmarkRun.id == benchmark_run_id, BenchmarkRun.organization_id == ctx.org_id)
    )
    if br is None:
        raise NotFound("Benchmark run not found")
    cases = ctx.db.scalars(
        select(BenchmarkCaseResult).where(BenchmarkCaseResult.benchmark_run_id == br.id).order_by(BenchmarkCaseResult.case_id)
    ).all()
    out = BenchmarkRunDetailOut.model_validate(br)
    out.cases = cases  # type: ignore[assignment]
    return out


# --- FHIR R4 ---
@fhir_router.get("/patients/{patient_id}/bundle")
def export_patient_fhir_bundle(
    patient_id: uuid.UUID,
    bundle_type: str = Query("transaction", pattern="^(transaction|collection)$"),
    ctx: AuthContext = Depends(requires(P.FHIR_EXPORT)),
):
    patient = ctx.db.scalar(
        select(Patient).where(Patient.id == patient_id, Patient.organization_id == ctx.org_id, Patient.is_synthetic.is_(False))
    )
    if patient is None:
        raise NotFound("Patient not found")
    consents = list(
        ctx.db.scalars(
            select(Consent).where(Consent.organization_id == ctx.org_id, Consent.patient_id == patient.id).order_by(Consent.effective_at.desc())
        ).all()
    )
    # Enforce HIE consent if patient explicitly revoked it
    revoked_hie = any(c.scope == ConsentScope.HIE_SHARING.value and c.status != ConsentStatus.GRANTED.value for c in consents)
    if revoked_hie:
        raise Forbidden("Patient has revoked HIE/FHIR sharing consent")

    observations = list(
        ctx.db.scalars(
            select(Observation)
            .where(Observation.organization_id == ctx.org_id, Observation.patient_id == patient.id)
            .order_by(Observation.effective_at.desc())
            .limit(50)
        ).all()
    )
    plan = ctx.db.get(InsurancePlan, patient.insurance_plan_id) if patient.insurance_plan_id else None
    latest_run = ctx.db.scalar(
        select(PipelineRun)
        .where(PipelineRun.organization_id == ctx.org_id, PipelineRun.patient_id == patient.id)
        .order_by(PipelineRun.created_at.desc())
        .limit(1)
    )
    latest_scoring = ctx.db.scalar(select(ScoringResult).where(ScoringResult.run_id == latest_run.id)) if latest_run else None
    latest_review = ctx.db.scalar(
        select(ClinicalReview).where(ClinicalReview.run_id == latest_run.id).order_by(ClinicalReview.signed_at.desc()).limit(1)
    ) if latest_run else None
    practitioner = ctx.db.get(type(ctx.user), patient.primary_clinician_id) if patient.primary_clinician_id else ctx.user
    refs = list(
        ctx.db.scalars(
            select(Referral).where(Referral.organization_id == ctx.org_id, Referral.patient_id == patient.id).order_by(Referral.created_at.desc()).limit(10)
        ).all()
    )
    facilities = {f.id: f for f in ctx.db.scalars(select(CareFacility).where(CareFacility.organization_id == ctx.org_id)).all()}
    ref_pairs = [(r, facilities.get(r.facility_id) if r.facility_id else None) for r in refs]
    screenings = list(
        ctx.db.scalars(
            select(ScreeningRecord).where(ScreeningRecord.organization_id == ctx.org_id, ScreeningRecord.patient_id == patient.id).order_by(ScreeningRecord.screened_at.desc()).limit(5)
        ).all()
    )
    notifs = list(
        ctx.db.scalars(
            select(Notification).where(Notification.organization_id == ctx.org_id, Notification.recipient_patient_id == patient.id).order_by(Notification.created_at.desc()).limit(10)
        ).all()
    )

    assert ctx.organization is not None
    bundle = build_patient_fhir_bundle(
        org=ctx.organization,
        patient=patient,
        consents=consents,
        observations=observations,
        plan=plan,
        latest_run=latest_run,
        latest_scoring=latest_scoring,
        latest_review=latest_review,
        practitioner=practitioner,
        referrals=ref_pairs,
        screenings=screenings,
        notifications=notifs,
        bundle_type=bundle_type,
    )
    validation = validate_fhir_bundle(bundle)
    ctx.audit("fhir.export", "patient", patient.id, patient_id=patient.id, details={"valid": validation["valid"], "entries": validation["total_entries"]})
    ctx.db.commit()
    return {"bundle": bundle, "validation": validation}


@fhir_router.post("/validate")
def validate_bundle(bundle: dict, ctx: AuthContext = Depends(requires(P.FHIR_EXPORT))):
    return validate_fhir_bundle(bundle)


@fhir_router.post("/patients/{patient_id}/push-malaffi")
def push_to_malaffi(patient_id: uuid.UUID, ctx: AuthContext = Depends(requires(P.FHIR_EXPORT))):
    exported = export_patient_fhir_bundle(patient_id, bundle_type="transaction", ctx=ctx)
    row = ctx.db.scalar(
        select(IntegrationConfig).where(IntegrationConfig.organization_id == ctx.org_id, IntegrationConfig.integration == "malaffi")
    )
    org_cfg = dict(row.settings) if row else {}
    if row and row.secrets_encrypted:
        raw = decrypt_str(row.secrets_encrypted)
        if raw:
            org_cfg.update(json.loads(raw))
    res = push_fhir_bundle(exported["bundle"], org_cfg or None)
    ctx.audit("fhir.push_malaffi", "patient", patient_id, patient_id=patient_id, details={"status": res.get("status")})
    ctx.db.commit()
    return res


# --- Settings: Insurance Plans, Care Facilities, Integrations ---
@settings_router.get("/insurance-plans", response_model=list[InsurancePlanOut])
def list_insurance_plans(ctx: AuthContext = Depends(requires(P.ORG_READ))):
    return care_svc.list_insurance_plans(ctx)


@settings_router.post("/insurance-plans", response_model=InsurancePlanOut, status_code=201)
def create_insurance_plan(req: InsurancePlanCreate, ctx: AuthContext = Depends(requires(P.SETTINGS_MANAGE))):
    return care_svc.create_insurance_plan(ctx, req)


@settings_router.get("/care-facilities", response_model=list[CareFacilityOut])
def list_care_facilities(ctx: AuthContext = Depends(requires(P.ORG_READ))):
    return care_svc.list_care_facilities(ctx)


@settings_router.post("/care-facilities", response_model=CareFacilityOut, status_code=201)
def create_care_facility(req: CareFacilityCreate, ctx: AuthContext = Depends(requires(P.SETTINGS_MANAGE))):
    return care_svc.create_care_facility(ctx, req)


@settings_router.get("/integrations", response_model=list[IntegrationConfigOut])
def list_integrations(ctx: AuthContext = Depends(requires(P.SETTINGS_READ))):
    return care_svc.list_integrations(ctx)


@settings_router.put("/integrations/{name}", response_model=IntegrationConfigOut)
def upsert_integration(name: str, req: IntegrationConfigUpdate, ctx: AuthContext = Depends(requires(P.SETTINGS_MANAGE))):
    return care_svc.upsert_integration(ctx, name, req)


@settings_router.post("/integrations/{name}/test")
def test_integration(name: str, ctx: AuthContext = Depends(requires(P.SETTINGS_MANAGE))):
    return care_svc.test_integration(ctx, name)


# --- Reports / Dashboard Overview (100% real DB aggregates, zero mock numbers) ---
@reports_router.get("/overview")
def organization_overview(ctx: AuthContext = Depends(requires(P.ORG_READ))):
    org_id = ctx.org_id
    active_patients = ctx.db.scalar(
        select(func.count(Patient.id)).where(Patient.organization_id == org_id, Patient.is_active.is_(True), Patient.is_synthetic.is_(False))
    ) or 0
    open_emergencies = ctx.db.scalar(
        select(func.count(EmergencyEvent.id)).where(EmergencyEvent.organization_id == org_id, EmergencyEvent.status == EmergencyStatus.OPEN.value)
    ) or 0
    pending_referrals = ctx.db.scalar(
        select(func.count(Referral.id)).where(Referral.organization_id == org_id, Referral.status == ReferralStatus.PROPOSED.value)
    ) or 0
    open_referrals = ctx.db.scalar(
        select(func.count(Referral.id)).where(
            Referral.organization_id == org_id,
            Referral.status.in_([
                ReferralStatus.PROPOSED.value,
                ReferralStatus.APPROVED.value,
                ReferralStatus.PATIENT_NOTIFIED.value,
                ReferralStatus.BOOKED.value,
                ReferralStatus.MISSED.value,
                ReferralStatus.ESCALATED.value,
            ]),
        )
    ) or 0
    verified_outcomes = ctx.db.scalar(
        select(func.count(Referral.id)).where(Referral.organization_id == org_id, Referral.status == ReferralStatus.OUTCOME_VERIFIED.value)
    ) or 0
    sla_breaches = ctx.db.scalar(
        select(func.count(Referral.id)).where(Referral.organization_id == org_id, Referral.sla_status == SlaStatus.BREACHED.value)
    ) or 0
    total_runs = ctx.db.scalar(
        select(func.count(PipelineRun.id)).where(PipelineRun.organization_id == org_id, PipelineRun.benchmark_run_id.is_(None))
    ) or 0

    tier_rows = ctx.db.execute(
        select(TrackEnrollment.track, TrackEnrollment.latest_risk_tier, func.count(TrackEnrollment.id))
        .where(TrackEnrollment.organization_id == org_id, TrackEnrollment.status == "active")
        .group_by(TrackEnrollment.track, TrackEnrollment.latest_risk_tier)
    ).all()
    track_distribution: dict[str, dict[str, int]] = {}
    for trk, tier, cnt in tier_rows:
        bucket = track_distribution.setdefault(trk, {})
        bucket[tier or "UNSCORED"] = int(cnt)

    referral_rows = ctx.db.execute(
        select(Referral.status, func.count(Referral.id))
        .where(Referral.organization_id == org_id)
        .group_by(Referral.status)
    ).all()
    referral_funnel = {st: int(cnt) for st, cnt in referral_rows}

    return {
        "organization_id": str(org_id),
        "active_patients": int(active_patients),
        "open_emergencies": int(open_emergencies),
        "pending_clinician_reviews": int(pending_referrals),
        "open_referrals": int(open_referrals),
        "verified_outcomes": int(verified_outcomes),
        "sla_breaches": int(sla_breaches),
        "total_pipeline_runs": int(total_runs),
        "track_risk_distribution": track_distribution,
        "referral_funnel": referral_funnel,
    }


@reports_router.get("/platform-overview")
def platform_overview(ctx: AuthContext = Depends(requires(P.ORG_READ))):
    """Overall Recova Engine Command summary across customer centers, 4 sub-engines, and 6 agents."""
    if not ctx.user.is_platform_admin:
        raise Forbidden("Platform overview requires platform administrator context.")

    orgs = ctx.db.scalars(select(Organization).where(Organization.is_active.is_(True)).order_by(Organization.name)).all()
    patient_counts = dict(
        ctx.db.execute(
            select(Patient.organization_id, func.count(Patient.id))
            .where(Patient.is_active.is_(True), Patient.is_synthetic.is_(False))
            .group_by(Patient.organization_id)
        ).all()
    )
    user_counts = dict(
        ctx.db.execute(
            select(Membership.organization_id, func.count(Membership.id))
            .where(Membership.is_active.is_(True))
            .group_by(Membership.organization_id)
        ).all()
    )
    run_counts = dict(
        ctx.db.execute(
            select(PipelineRun.organization_id, func.count(PipelineRun.id))
            .where(PipelineRun.benchmark_run_id.is_(None))
            .group_by(PipelineRun.organization_id)
        ).all()
    )
    emergency_counts = dict(
        ctx.db.execute(
            select(EmergencyEvent.organization_id, func.count(EmergencyEvent.id))
            .where(EmergencyEvent.status == EmergencyStatus.OPEN.value)
            .group_by(EmergencyEvent.organization_id)
        ).all()
    )
    tier_rows = ctx.db.execute(
        select(TrackEnrollment.organization_id, TrackEnrollment.track, TrackEnrollment.latest_risk_tier, func.count(TrackEnrollment.id))
        .where(TrackEnrollment.status == "active")
        .group_by(TrackEnrollment.organization_id, TrackEnrollment.track, TrackEnrollment.latest_risk_tier)
    ).all()

    org_track_risks: dict[tuple[uuid.UUID, str], dict[str, int]] = {}
    for oid, trk, tier, cnt in tier_rows:
        bucket = org_track_risks.setdefault((oid, trk), {})
        bucket[tier or "UNSCORED"] = int(cnt)

    sub_engines: dict[str, dict] = {}
    for trk in ("core", "loop", "neuro", "worksafe"):
        centers = []
        risk_totals: dict[str, int] = {}
        total_patients = 0
        total_users = 0
        total_runs = 0
        total_emergencies = 0
        for org in orgs:
            primary = org.primary_programme or (org.enabled_tracks[0] if org.enabled_tracks else None)
            if primary != trk and trk not in (org.enabled_tracks or []):
                continue
            p_cnt = int(patient_counts.get(org.id, 0))
            u_cnt = int(user_counts.get(org.id, 0))
            r_cnt = int(run_counts.get(org.id, 0))
            e_cnt = int(emergency_counts.get(org.id, 0))
            r_dist = org_track_risks.get((org.id, trk), {})
            for k, v in r_dist.items():
                risk_totals[k] = risk_totals.get(k, 0) + v
            total_patients += p_cnt
            total_users += u_cnt
            total_runs += r_cnt
            total_emergencies += e_cnt
            centers.append(
                {
                    "id": str(org.id),
                    "name": org.name,
                    "slug": org.slug,
                    "org_type": org.org_type,
                    "emirate": org.emirate,
                    "primary_programme": primary,
                    "active_patients": p_cnt,
                    "staff_members": u_cnt,
                    "total_runs": r_cnt,
                    "open_emergencies": e_cnt,
                    "risk_distribution": r_dist,
                }
            )
        sub_engines[trk] = {
            "track": trk,
            "total_centers": len(centers),
            "total_patients": total_patients,
            "total_staff": total_users,
            "total_runs": total_runs,
            "open_emergencies": total_emergencies,
            "risk_distribution": risk_totals,
            "centers": centers,
        }

    step_rows = ctx.db.execute(
        select(AgentStepResult.agent_key, AgentStepResult.status, func.count(AgentStepResult.id))
        .group_by(AgentStepResult.agent_key, AgentStepResult.status)
    ).all()
    agent_telemetry: dict[str, dict[str, int]] = {}
    for akey, st, cnt in step_rows:
        bucket = agent_telemetry.setdefault(akey, {})
        bucket[st] = int(cnt)

    return {
        "total_centers": len(orgs),
        "total_active_patients": sum(int(v) for v in patient_counts.values()),
        "total_staff_members": sum(int(v) for v in user_counts.values()),
        "total_pipeline_runs": sum(int(v) for v in run_counts.values()),
        "open_emergencies": sum(int(v) for v in emergency_counts.values()),
        "sub_engines": sub_engines,
        "agent_telemetry": agent_telemetry,
    }
