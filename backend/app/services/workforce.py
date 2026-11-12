"""WorkSafe services: workplaces, departments, environmental hazards, worker readiness, anonymised heatmaps."""

from __future__ import annotations

import uuid
from datetime import timedelta

from sqlalchemy import select

from app.agents.orchestrator import create_pipeline_run, execute_pipeline_run
from app.api.deps import AuthContext
from app.core.errors import Conflict, Forbidden, NotFound, ValidationFailed
from app.core.permissions import P
from app.engine.metrics import compute_heat_index_c
from app.models.base import utcnow
from app.models.care import Intervention
from app.models.clinical import (
    CheckIn,
    Consent,
    Department,
    Observation,
    Patient,
    TrackEnrollment,
    Workplace,
    WorkplaceAssessment,
)
from app.models.enums import ConsentScope, ConsentStatus, InterventionStatus, ObservationSource, RiskTier
from app.schemas.clinical import (
    DepartmentCreate,
    WorkerReadinessCreate,
    WorkplaceAssessmentCreate,
    WorkplaceCreate,
)


def list_workplaces(ctx: AuthContext) -> list[Workplace]:
    ctx.require(P.WORKFORCE_AGGREGATE)
    ctx.require_track("worksafe")
    return list(
        ctx.db.scalars(
            select(Workplace).where(Workplace.organization_id == ctx.org_id, Workplace.is_active.is_(True)).order_by(Workplace.name)
        ).all()
    )


def create_workplace(ctx: AuthContext, req: WorkplaceCreate) -> Workplace:
    ctx.require(P.WORKFORCE_MANAGE)
    ctx.require_track("worksafe")
    existing = ctx.db.scalar(
        select(Workplace.id).where(Workplace.organization_id == ctx.org_id, Workplace.name == req.name.strip())
    )
    if existing:
        raise Conflict("Workplace with that name already exists")
    wp = Workplace(
        organization_id=ctx.org_id,
        name=req.name.strip(),
        location=req.location,
        environment_type=req.environment_type,
    )
    ctx.db.add(wp)
    ctx.db.flush()
    ctx.audit("workplace.create", "workplace", wp.id, details={"name": wp.name})
    ctx.db.commit()
    return wp


def list_departments(ctx: AuthContext) -> list[Department]:
    ctx.require(P.WORKFORCE_AGGREGATE)
    ctx.require_track("worksafe")
    stmt = select(Department).where(Department.organization_id == ctx.org_id, Department.is_active.is_(True))
    # Scope supervisors with explicit department assignments
    if ctx.membership and ctx.membership.department_ids and not ctx.has(P.WORKFORCE_IDENTIFIABLE):
        stmt = stmt.where(Department.id.in_(ctx.membership.department_ids))
    return list(ctx.db.scalars(stmt.order_by(Department.name)).all())


def create_department(ctx: AuthContext, req: DepartmentCreate) -> Department:
    ctx.require(P.WORKFORCE_MANAGE)
    ctx.require_track("worksafe")
    existing = ctx.db.scalar(
        select(Department.id).where(Department.organization_id == ctx.org_id, Department.name == req.name.strip())
    )
    if existing:
        raise Conflict("Department with that name already exists")
    dept = Department(
        organization_id=ctx.org_id,
        workplace_id=req.workplace_id,
        name=req.name.strip(),
        min_group_size_for_reporting=req.min_group_size_for_reporting,
    )
    ctx.db.add(dept)
    ctx.db.flush()
    ctx.audit("department.create", "department", dept.id, details={"name": dept.name})
    ctx.db.commit()
    return dept


def record_workplace_assessment(ctx: AuthContext, req: WorkplaceAssessmentCreate) -> WorkplaceAssessment:
    ctx.require(P.WORKFORCE_WRITE)
    ctx.require_track("worksafe")
    heat_index = None
    if req.ambient_temp_c is not None and req.relative_humidity_pct is not None:
        heat_index = compute_heat_index_c(req.ambient_temp_c, req.relative_humidity_pct)
    wa = WorkplaceAssessment(
        organization_id=ctx.org_id,
        department_id=req.department_id,
        workplace_id=req.workplace_id,
        measured_at=req.measured_at or utcnow(),
        ambient_temp_c=req.ambient_temp_c,
        relative_humidity_pct=req.relative_humidity_pct,
        heat_index_c=heat_index,
        wbgt_c=req.wbgt_c,
        noise_db=req.noise_db,
        lighting_lux=req.lighting_lux,
        ergonomics_checklist=req.ergonomics_checklist,
        source=req.source,
        recorded_by_id=ctx.user.id,
    )
    ctx.db.add(wa)
    ctx.db.flush()
    ctx.audit("workplace_assessment.create", "workplace_assessment", wa.id, details={"heat_index_c": heat_index})
    ctx.db.commit()
    return wa


def list_workplace_assessments(ctx: AuthContext, department_id: uuid.UUID | None = None) -> list[WorkplaceAssessment]:
    ctx.require(P.WORKFORCE_AGGREGATE)
    ctx.require_track("worksafe")
    stmt = select(WorkplaceAssessment).where(WorkplaceAssessment.organization_id == ctx.org_id)
    if department_id:
        stmt = stmt.where(WorkplaceAssessment.department_id == department_id)
    return list(ctx.db.scalars(stmt.order_by(WorkplaceAssessment.measured_at.desc()).limit(50)).all())


def record_worker_readiness(ctx: AuthContext, req: WorkerReadinessCreate) -> dict:
    ctx.require(P.OBSERVATIONS_WRITE)
    ctx.require_track("worksafe")
    p = ctx.db.scalar(
        select(Patient).where(Patient.id == req.patient_id, Patient.organization_id == ctx.org_id, Patient.is_synthetic.is_(False))
    )
    if p is None:
        raise NotFound("Employee/participant not found")

    now = utcnow()
    symptoms = []
    crisis = False
    if req.fatigue_feeling == "dizzy_heat_illness":
        symptoms.append("heatstroke_confusion")
        crisis = True

    chk = CheckIn(
        organization_id=ctx.org_id,
        patient_id=p.id,
        track="worksafe",
        kind="readiness",
        effective_at=now,
        mood_score=req.readiness_score,
        text=req.voice_note,
        transcript_source="browser_speech" if req.voice_note else "typed",
        symptoms=symptoms,
        self_reported_crisis=crisis,
        submitted_by_id=ctx.user.id,
        extra={"fatigue_feeling": req.fatigue_feeling, "hydrated": req.hydrated},
    )
    ctx.db.add(chk)
    ctx.db.flush()

    obs_list = [
        ("readiness_score", float(req.readiness_score), "score"),
        ("shift_duration_hours", req.shift_duration_hours, "h"),
        ("core_temp_est_c", req.core_temp_est_c, "C"),
        ("hr_recovery_minutes", req.hr_recovery_minutes, "min"),
        ("sleep_debt_hours", req.sleep_debt_hours, "h"),
        ("hrv_rmssd", req.hrv_rmssd, "ms"),
    ]
    for code, val, unit in obs_list:
        if val is not None:
            ctx.db.add(
                Observation(
                    organization_id=ctx.org_id,
                    patient_id=p.id,
                    track="worksafe",
                    metric_code=code,
                    value_num=float(val),
                    unit=unit,
                    effective_at=now,
                    source=ObservationSource.CHECKIN.value if code == "readiness_score" else ObservationSource.WEARABLE.value,
                    check_in_id=chk.id,
                    entered_by_id=ctx.user.id,
                )
            )

    enr = ctx.db.scalar(select(TrackEnrollment).where(TrackEnrollment.patient_id == p.id, TrackEnrollment.track == "worksafe"))
    if enr is None:
        ctx.db.add(
            TrackEnrollment(
                organization_id=ctx.org_id,
                patient_id=p.id,
                track="worksafe",
                status="active",
                enrolled_at=now,
                context={},
            )
        )
    ctx.audit("worker_readiness.create", "check_in", chk.id, patient_id=p.id, details={"fatigue": req.fatigue_feeling, "hydrated": req.hydrated})
    ctx.db.commit()

    run = None
    if req.trigger_pipeline:
        run = create_pipeline_run(
            ctx.db,
            organization_id=ctx.org_id,
            patient_id=p.id,
            track="worksafe",
            trigger="checkin",
            triggered_by_id=ctx.user.id,
            as_of=now,
        )
        ctx.db.commit()
        run = execute_pipeline_run(ctx.db, run.id)

    return {"check_in": chk, "run_id": run.id if run else None}


def get_department_heatmap(ctx: AuthContext) -> list[dict]:
    """Return anonymised department-level heat-stress & fatigue clusters.

    Enforces k-anonymity: if a department has fewer workers than
    `min_group_size_for_reporting` and the caller lacks `workforce:read_identifiable`,
    tier counts are suppressed so individuals cannot be re-identified.
    """
    ctx.require(P.WORKFORCE_AGGREGATE)
    ctx.require_track("worksafe")
    depts = list_departments(ctx)
    can_identify = ctx.has(P.WORKFORCE_IDENTIFIABLE)

    workers = ctx.db.scalars(
        select(Patient).where(
            Patient.organization_id == ctx.org_id,
            Patient.is_active.is_(True),
            Patient.is_synthetic.is_(False),
            Patient.department_id.is_not(None),
        )
    ).all()
    enrollments = {
        e.patient_id: e
        for e in ctx.db.scalars(
            select(TrackEnrollment).where(
                TrackEnrollment.organization_id == ctx.org_id,
                TrackEnrollment.track == "worksafe",
                TrackEnrollment.status == "active",
            )
        ).all()
    }
    open_interventions = ctx.db.scalars(
        select(Intervention).where(
            Intervention.organization_id == ctx.org_id,
            Intervention.track == "worksafe",
            Intervention.status.in_([InterventionStatus.PLANNED.value, InterventionStatus.IN_PROGRESS.value]),
        )
    ).all()

    recent_cutoff = utcnow() - timedelta(days=7)
    out: list[dict] = []
    for dept in depts:
        dept_workers = [w for w in workers if w.department_id == dept.id]
        n = len(dept_workers)
        latest_env = ctx.db.scalar(
            select(WorkplaceAssessment)
            .where(
                WorkplaceAssessment.organization_id == ctx.org_id,
                WorkplaceAssessment.department_id == dept.id,
                WorkplaceAssessment.measured_at >= recent_cutoff,
            )
            .order_by(WorkplaceAssessment.measured_at.desc())
            .limit(1)
        )
        dept_interventions = sum(1 for iv in open_interventions if iv.department_id == dept.id)

        if n > 0 and n < dept.min_group_size_for_reporting and not can_identify:
            out.append(
                {
                    "department_id": str(dept.id),
                    "department_name": dept.name,
                    "worker_count": n,
                    "k_anonymity_threshold": dept.min_group_size_for_reporting,
                    "suppressed_k_anonymity": True,
                    "risk_counts": None,
                    "latest_heat_index_c": latest_env.heat_index_c if latest_env else None,
                    "latest_ambient_temp_c": latest_env.ambient_temp_c if latest_env else None,
                    "open_interventions": dept_interventions,
                }
            )
            continue

        counts = {
            RiskTier.GREEN.value: 0,
            RiskTier.AMBER.value: 0,
            RiskTier.RED.value: 0,
            RiskTier.EMERGENCY_BYPASS.value: 0,
            RiskTier.INDETERMINATE.value: 0,
        }
        for w in dept_workers:
            enr = enrollments.get(w.id)
            t = enr.latest_risk_tier if enr and enr.latest_risk_tier in counts else RiskTier.INDETERMINATE.value
            counts[t] += 1

        out.append(
            {
                "department_id": str(dept.id),
                "department_name": dept.name,
                "worker_count": n,
                "k_anonymity_threshold": dept.min_group_size_for_reporting,
                "suppressed_k_anonymity": False,
                "risk_counts": counts,
                "latest_heat_index_c": latest_env.heat_index_c if latest_env else None,
                "latest_ambient_temp_c": latest_env.ambient_temp_c if latest_env else None,
                "open_interventions": dept_interventions,
            }
        )
    return out


def list_identifiable_worker_risks(ctx: AuthContext) -> list[dict]:
    """Only accessible to Occupational Health Directors / Org Admins when authorized."""
    ctx.require(P.WORKFORCE_IDENTIFIABLE)
    ctx.require_track("worksafe")
    workers = ctx.db.scalars(
        select(Patient).where(
            Patient.organization_id == ctx.org_id,
            Patient.is_active.is_(True),
            Patient.is_synthetic.is_(False),
            Patient.department_id.is_not(None),
        )
    ).all()
    enrollments = {
        e.patient_id: e
        for e in ctx.db.scalars(
            select(TrackEnrollment).where(TrackEnrollment.organization_id == ctx.org_id, TrackEnrollment.track == "worksafe")
        ).all()
    }
    res = []
    for w in workers:
        enr = enrollments.get(w.id)
        # Check consent for identifiable supervisor sharing if caller is a supervisor
        if ctx.role and ctx.role.value == "supervisor":
            has_consent = ctx.db.scalar(
                select(Consent.id).where(
                    Consent.patient_id == w.id,
                    Consent.scope == ConsentScope.SUPERVISOR_IDENTIFIABLE.value,
                    Consent.status == ConsentStatus.GRANTED.value,
                    Consent.revoked_at.is_(None),
                )
            )
            if not has_consent:
                continue
        res.append(
            {
                "patient_id": str(w.id),
                "mrn": w.mrn,
                "full_name": f"{w.given_name} {w.family_name}",
                "department_id": str(w.department_id),
                "job_role": w.job_role,
                "latest_risk_tier": enr.latest_risk_tier if enr else None,
                "latest_run_id": str(enr.latest_run_id) if enr and enr.latest_run_id else None,
                "latest_run_at": enr.latest_run_at.isoformat() if enr and enr.latest_run_at else None,
            }
        )
    return res
