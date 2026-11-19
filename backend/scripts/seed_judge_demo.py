"""Resettable synthetic judge demonstration seed (1 org per programme + 5 scenario participants each).

Usage:
    cd backend
    .\\.venv\\Scripts\\python.exe -m scripts.seed_judge_demo --reset
"""

from __future__ import annotations

import argparse
import sys
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import delete, select

from app.agents.orchestrator import create_pipeline_run, execute_pipeline_run
from app.core.config import get_settings
from app.core.db import SessionLocal
from app.core.security import hash_password
from app.models.base import utcnow
from app.models.care import CareFacility, ClinicalReview, InsurancePlan, Referral
from app.models.clinical import CheckIn, Consent, Department, Observation, Patient, ScreeningRecord, TrackEnrollment, Workplace, WorkplaceAssessment
from app.models.enums import ConsentScope, ObservationSource, ReviewDecision
from app.models.identity import Membership, Organization, ParticipantAccountLink, User
from app.services.care import create_clinical_review

JUDGE_ORGS = [
    ("judge-demo-core", "Judge Demo: Recova Recovery Centre", "rehab_center", "core"),
    ("judge-demo-loop", "Judge Demo: Recova Loop Clinic", "clinic", "loop"),
    ("judge-demo-neuro", "Judge Demo: Recova Neuro Studio", "hospital", "neuro"),
    ("judge-demo-worksafe", "Judge Demo: Recova WorkSafe Site", "employer", "worksafe"),
]

SCENARIOS = [
    ("stable", "Amira", "Al-Mansoori"),
    ("gradual_decline", "Omar", "Al-Hashimi"),
    ("missing_data", "Lina", "Al-Suwaidi"),
    ("emergency", "Tariq", "Al-Zaabi"),
    ("absent_consent", "Zaid", "Al-Dhaheri"),
]


def seed_judge_demo(*, reset: bool = False) -> dict:
    if get_settings().environment == "production":
        raise RuntimeError("Judge demo fixtures are restricted to non-production environments.")

    now = utcnow()
    created_orgs = 0
    created_patients = 0

    with SessionLocal() as db:
        slugs = [s for s, _, _, _ in JUDGE_ORGS]
        if reset:
            old_orgs = db.scalars(select(Organization).where(Organization.slug.in_(slugs))).all()
            for o in old_orgs:
                db.delete(o)
            db.commit()

        for slug, name, org_type, prog in JUDGE_ORGS:
            org = db.scalar(select(Organization).where(Organization.slug == slug))
            if org is not None:
                continue
            org = Organization(
                name=name,
                slug=slug,
                org_type=org_type,
                primary_programme=prog,
                programme_configuration_status="configured",
                enabled_tracks=[prog],
                country="UAE",
                emirate="Abu Dhabi",
                settings={
                    "synthetic_demo": True,
                    "judge_fixture": True,
                    "shared_population_health_provisioned": True,
                    "permitted_channels": ["in_app"],
                },
            )
            db.add(org)
            db.flush()
            created_orgs += 1

            staff_email = f"judge.{prog}.clinician@demo.recova.ae"
            staff = db.scalar(select(User).where(User.email == staff_email))
            if staff is None:
                staff = User(
                    email=staff_email,
                    full_name=f"Dr. Judge {prog.title()}",
                    password_hash=hash_password("JudgeDemo123!"),
                    is_active=True,
                    license_number=f"DOH-JUDGE-{prog.upper()}",
                )
                db.add(staff)
                db.flush()
            db.add(Membership(user_id=staff.id, organization_id=org.id, role="clinician" if prog != "worksafe" else "occ_health_director"))

            plan = InsurancePlan(
                organization_id=org.id,
                code=f"J-{prog.upper()}",
                name="Thiqa Comprehensive",
                covered_pathways=["async_teleconsult", "outpatient_therapist", "primary_care", "specialist", "occupational_health"],
            )
            fac = CareFacility(
                organization_id=org.id,
                name=f"Abu Dhabi {prog.title()} Referral Center",
                facility_type="occupational_health" if prog == "worksafe" else "specialist",
                pathways=["async_teleconsult", "outpatient_therapist", "primary_care", "specialist", "occupational_health", "emergency_triage"],
                typical_wait_days=1,
            )
            db.add_all([plan, fac])
            db.flush()
            fac.accepted_plan_ids = [plan.id]

            dept_id = None
            if prog == "worksafe":
                wp = Workplace(organization_id=org.id, name="Judge Demo Solar Site", location="Al Dhafra", environment_type="outdoor")
                db.add(wp)
                db.flush()
                dept = Department(organization_id=org.id, workplace_id=wp.id, name="Field Operations", min_group_size_for_reporting=5)
                db.add(dept)
                db.flush()
                dept_id = dept.id
                db.add(WorkplaceAssessment(organization_id=org.id, department_id=dept.id, workplace_id=wp.id, measured_at=now, ambient_temp_c=42.0, relative_humidity_pct=50.0, heat_index_c=52.0))

            for idx, (scenario, given, family) in enumerate(SCENARIOS, start=1):
                p_email = f"judge.{prog}.{scenario}@demo.recova.ae"
                p_user = db.scalar(select(User).where(User.email == p_email))
                if p_user is None:
                    p_user = User(
                        email=p_email,
                        full_name=f"{given} {family}",
                        password_hash=hash_password("JudgeDemo123!"),
                        is_active=True,
                    )
                    db.add(p_user)
                    db.flush()
                db.add(Membership(user_id=p_user.id, organization_id=org.id, role="patient"))

                patient = Patient(
                    organization_id=org.id,
                    participant_type="employee" if prog == "worksafe" else "patient",
                    mrn=f"JDG-{prog.upper()}-{idx:02d}",
                    given_name=given,
                    family_name=family,
                    preferred_language="en",
                    insurance_plan_id=plan.id,
                    department_id=dept_id,
                    primary_clinician_id=staff.id,
                    portal_user_id=p_user.id,
                    is_synthetic=True,
                )
                db.add(patient)
                db.flush()
                created_patients += 1

                db.add(
                    ParticipantAccountLink(
                        organization_id=org.id,
                        user_id=p_user.id,
                        patient_id=patient.id,
                        verified_at=now,
                        verification_source="seed",
                    )
                )
                db.add(
                    TrackEnrollment(
                        organization_id=org.id,
                        patient_id=patient.id,
                        track=prog,
                        status="active",
                        enrolled_at=now - timedelta(days=14),
                        context={"scenario": scenario},
                    )
                )

                if scenario != "absent_consent":
                    db.add(
                        Consent(
                            organization_id=org.id,
                            patient_id=patient.id,
                            scope=ConsentScope.DATA_PROCESSING.value,
                            status="granted",
                            method="electronic",
                            policy_version="v1.0",
                            authority_to_act="self",
                            effective_at=now - timedelta(days=14),
                        )
                    )

                metric = {
                    "core": ("sleep_hours", "h", 7.6, 4.6),
                    "loop": ("hba1c", "%", 5.5, 7.2),
                    "neuro": ("cog_sequence_accuracy", "%", 92.0, 74.0),
                    "worksafe": ("core_temp_est_c", "C", 36.8, 38.7),
                }[prog]
                m_code, m_unit, base_v, drift_v = metric

                if scenario in {"stable", "gradual_decline"}:
                    for d in range(10, 5, -1):
                        db.add(
                            Observation(
                                organization_id=org.id,
                                patient_id=patient.id,
                                track=prog,
                                metric_code=m_code,
                                value_num=base_v,
                                unit=m_unit,
                                effective_at=now - timedelta(days=d),
                                source=ObservationSource.WEARABLE.value,
                            )
                        )
                    recent_val = base_v if scenario == "stable" else drift_v
                    for d in range(2, -1, -1):
                        db.add(
                            Observation(
                                organization_id=org.id,
                                patient_id=patient.id,
                                track=prog,
                                metric_code=m_code,
                                value_num=recent_val,
                                unit=m_unit,
                                effective_at=now - timedelta(days=d),
                                source=ObservationSource.WEARABLE.value,
                            )
                        )
                elif scenario == "emergency":
                    db.add(
                        CheckIn(
                            organization_id=org.id,
                            patient_id=patient.id,
                            track=prog,
                            kind="text",
                            effective_at=now - timedelta(minutes=15),
                            mood_score=1,
                            stress_score=10,
                            text="Severe chest pain and feeling dizzy",
                            self_reported_crisis=True,
                        )
                    )

                db.commit()
                run = create_pipeline_run(
                    db,
                    organization_id=org.id,
                    patient_id=patient.id,
                    track=prog,
                    trigger="scheduled",
                    triggered_by_id=staff.id,
                    as_of=now,
                )
                db.commit()
                run = execute_pipeline_run(db, run.id)

                if scenario == "gradual_decline":
                    ref = db.scalar(select(Referral).where(Referral.run_id == run.id))
                    if ref is not None and ref.status == "proposed":
                        ref.status = "approved"
                        ref.approved_by_id = staff.id
                        ref.approved_at = now
                        db.add(
                            ClinicalReview(
                                organization_id=org.id,
                                run_id=run.id,
                                patient_id=patient.id,
                                reviewer_id=staff.id,
                                reviewer_role="clinician",
                                reviewer_license=staff.license_number,
                                decision=ReviewDecision.APPROVE_REFERRAL.value,
                                agrees_with_tier=True,
                                clinician_notes="Judge demo approved follow-up referral.",
                                signed_at=now,
                                signature_hash="judge-demo-signature",
                            )
                        )
                        db.commit()

    return {"organizations_created": created_orgs, "patients_created": created_patients}


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed or reset Recova judge demonstration data.")
    parser.add_argument("--reset", action="store_true", help="Delete and recreate judge demo organisations.")
    args = parser.parse_args()
    res = seed_judge_demo(reset=args.reset)
    print(f"Judge demo fixtures ready: {res}")


if __name__ == "__main__":
    main()
