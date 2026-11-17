"""Quick developer seed script to bootstrap the platform with standard test credentials
and rich demo clinical cohorts across Core, Loop, Neuro, and WorkSafe.

Usage:
    cd backend
    .\\.venv\\Scripts\\python.exe seed_demo.py
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.core.db import SessionLocal, engine
from app.core.security import encrypt_str
from app.models import Base
from app.models.clinical import (
    CheckIn,
    Consent,
    Department,
    Observation,
    Patient,
    ScreeningRecord,
    TrackEnrollment,
    Workplace,
    WorkplaceAssessment,
)
from app.models.engine import PersonalBaseline
from app.models.identity import Organization, User
from app.schemas.identity import BootstrapRequest, Track
from app.services.auth import bootstrap_platform, needs_bootstrap


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def main():
    print("Connecting to database...")
    try:
        with engine.connect() as conn:
            pass
    except Exception as e:
        print(f"\n[ERROR] Could not connect to PostgreSQL: {e}")
        print("\nPlease ensure PostgreSQL is running on localhost:5432 with database 'recova'.")
        print("Expected connection string: postgresql+psycopg://recova:recova@localhost:5432/recova")
        sys.exit(1)

    print("Ensuring tables are initialized...")
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        if needs_bootstrap(db):
            print("Bootstrapping platform with standard test credentials...")
            req = BootstrapRequest(
                organization_name="Abu Dhabi Health Hub",
                organization_slug="ad-health",
                org_type="hospital",
                enabled_tracks=[Track.CORE, Track.LOOP, Track.NEURO, Track.WORKSAFE],
                admin_email="admin@recova.ae",
                admin_full_name="Dr. Fatima Al-Hashimi",
                admin_password="Password123!",
                admin_license_number="DOH-2024-8842",
            )
            bootstrap_platform(db, req)
            print("Platform admin bootstrapped: admin@recova.ae / Password123!")

        org = db.scalar(select(Organization).where(Organization.slug == "ad-health"))
        if not org:
            org = db.scalar(select(Organization))
        admin_user = db.scalar(select(User).where(User.email == "admin@recova.ae"))
        if not admin_user:
            admin_user = db.scalar(select(User))

        print(f"Using Organization: {org.name} ({org.id})")

        # -------------------------------------------------------------
        # Seed WorkSafe Sites & Departments
        # -------------------------------------------------------------
        site = db.scalar(
            select(Workplace).where(Workplace.organization_id == org.id, Workplace.name == "Al Reem Construction Complex")
        )
        if not site:
            site = Workplace(
                organization_id=org.id,
                name="Al Reem Construction Complex",
                location="Al Reem Island, Abu Dhabi",
                environment_type="outdoor",
                is_active=True,
            )
            db.add(site)
            db.flush()

        dept = db.scalar(
            select(Department).where(Department.organization_id == org.id, Department.name == "Heavy Machinery Section")
        )
        if not dept:
            dept = Department(
                organization_id=org.id,
                workplace_id=site.id,
                name="Heavy Machinery Section",
                min_group_size_for_reporting=5,
                is_active=True,
            )
            db.add(dept)
            db.flush()

        # Seed Workplace Assessment (Environment)
        env = db.scalar(
            select(WorkplaceAssessment).where(
                WorkplaceAssessment.organization_id == org.id,
                WorkplaceAssessment.department_id == dept.id,
            )
        )
        if not env:
            env = WorkplaceAssessment(
                organization_id=org.id,
                department_id=dept.id,
                workplace_id=site.id,
                measured_at=utcnow() - timedelta(hours=2),
                ambient_temp_c=38.5,
                relative_humidity_pct=65.0,
                heat_index_c=47.2,
                wbgt_c=31.8,
                noise_db=82.0,
                lighting_lux=1200.0,
                ergonomics_checklist={"hydration_station_stocked": True, "shade_canopy_deployed": True},
                source="sensor",
                recorded_by_id=admin_user.id if admin_user else None,
            )
            db.add(env)

        # -------------------------------------------------------------
        # Seed Demo Patients & Observations
        # -------------------------------------------------------------
        patients_spec = [
            # Track Core
            {
                "mrn": "CORE-101",
                "given_name": "Ahmed",
                "family_name": "Al Mansoori",
                "preferred_language": "ar",
                "track": "core",
                "desc": "Case A: High Craving / Sub-acute Relapse Risk",
                "tier": "ELEVATED",
                "observations": [
                    ("craving_score", 9.0, "score", 0),
                    ("stress_score", 8.0, "score", 0),
                    ("mood_score", 3.0, "score", 0),
                    ("sleep_hours", 4.5, "h", 0),
                    ("craving_score", 7.0, "score", 2),
                    ("craving_score", 6.0, "score", 4),
                    ("craving_score", 4.0, "score", 7),
                    ("craving_score", 3.0, "score", 10),
                    ("craving_score", 3.0, "score", 14),
                ],
                "baseline": ("craving_score", 3.2, 0.6, 7),
            },
            {
                "mrn": "CORE-102",
                "given_name": "Layla",
                "family_name": "Mahmoud",
                "preferred_language": "en",
                "track": "core",
                "desc": "Case B: Moderate Drift Warning",
                "tier": "MODERATE",
                "observations": [
                    ("craving_score", 5.5, "score", 0),
                    ("stress_score", 6.0, "score", 0),
                    ("mood_score", 6.0, "score", 0),
                    ("sleep_hours", 6.0, "h", 0),
                    ("craving_score", 4.0, "score", 3),
                    ("craving_score", 3.0, "score", 7),
                    ("craving_score", 2.5, "score", 12),
                ],
                "baseline": ("craving_score", 2.8, 0.5, 6),
            },
            {
                "mrn": "CORE-103",
                "given_name": "Tariq",
                "family_name": "Saeed",
                "preferred_language": "ar",
                "track": "core",
                "desc": "Case C: Stable Maintenance Baseline",
                "tier": "LOW",
                "observations": [
                    ("craving_score", 1.5, "score", 0),
                    ("stress_score", 2.0, "score", 0),
                    ("mood_score", 8.5, "score", 0),
                    ("sleep_hours", 7.8, "h", 0),
                    ("craving_score", 1.0, "score", 3),
                    ("craving_score", 1.5, "score", 7),
                    ("craving_score", 1.2, "score", 14),
                ],
                "baseline": ("craving_score", 1.3, 0.3, 8),
            },
            {
                "mrn": "CORE-104",
                "given_name": "Noor",
                "family_name": "Hassan",
                "preferred_language": "en",
                "track": "core",
                "desc": "Case D: Emergency Red-Flag Crisis Bypass",
                "tier": "EMERGENCY_RED_FLAG",
                "observations": [
                    ("craving_score", 10.0, "score", 0),
                    ("stress_score", 10.0, "score", 0),
                    ("mood_score", 1.0, "score", 0),
                    ("sleep_hours", 2.0, "h", 0),
                ],
                "crisis": True,
            },
            # Track Loop
            {
                "mrn": "LOOP-201",
                "given_name": "Salem",
                "family_name": "Bin Rashid",
                "preferred_language": "ar",
                "track": "loop",
                "desc": "Loop Track: Cardiometabolic Drift (IFHAS Screened)",
                "tier": "MODERATE",
                "observations": [
                    ("hba1c", 8.4, "%", 0),
                    ("bp_systolic", 142.0, "mmHg", 0),
                    ("bp_diastolic", 92.0, "mmHg", 0),
                    ("phq9_score", 12.0, "score", 0),
                    ("total_cholesterol", 225.0, "mg/dL", 0),
                    ("steps", 3800.0, "steps/d", 0),
                    ("hba1c", 7.8, "%", 30),
                    ("hba1c", 7.2, "%", 60),
                ],
                "baseline": ("hba1c", 7.1, 0.3, 5),
            },
            # Track Neuro
            {
                "mrn": "NEURO-301",
                "given_name": "Fatima",
                "family_name": "Al Zaabi",
                "preferred_language": "en",
                "track": "neuro",
                "desc": "Neuro Track: Early Cognitive Wellness / Reaction Shifts",
                "tier": "LOW",
                "education": "secondary",
                "hearing": "normal",
                "vision": "normal",
                "observations": [
                    ("cog_auditory_accuracy", 88.0, "%", 0),
                    ("cog_visual_accuracy", 92.0, "%", 0),
                    ("cog_sequence_accuracy", 90.0, "%", 0),
                    ("cog_reaction_time_ms", 460.0, "ms", 0),
                    ("cog_auditory_accuracy", 89.0, "%", 3),
                    ("cog_auditory_accuracy", 91.0, "%", 7),
                    ("cog_auditory_accuracy", 90.0, "%", 14),
                ],
                "baseline": ("cog_auditory_accuracy", 90.5, 2.1, 6),
            },
            # Track WorkSafe
            {
                "mrn": "WORK-401",
                "given_name": "Rashid",
                "family_name": "Othman",
                "preferred_language": "en",
                "track": "worksafe",
                "desc": "WorkSafe Track: Heat-Stress Shift Readiness",
                "tier": "MODERATE",
                "dept_id": dept.id,
                "role": "Crane Operator",
                "observations": [
                    ("readiness_score", 6.0, "score", 0),
                    ("core_temp_est_c", 37.8, "degC", 0),
                    ("shift_hours", 7.5, "h", 0),
                    ("readiness_score", 8.0, "score", 2),
                    ("readiness_score", 9.0, "score", 5),
                ],
                "baseline": ("readiness_score", 8.5, 0.7, 5),
            },
        ]

        now = utcnow()
        for p_spec in patients_spec:
            p = db.scalar(select(Patient).where(Patient.organization_id == org.id, Patient.mrn == p_spec["mrn"]))
            if not p:
                p = Patient(
                    organization_id=org.id,
                    participant_type="employee" if p_spec["track"] == "worksafe" else "patient",
                    mrn=p_spec["mrn"],
                    given_name=p_spec["given_name"],
                    family_name=p_spec["family_name"],
                    preferred_language=p_spec["preferred_language"],
                    education_level=p_spec.get("education"),
                    hearing_status=p_spec.get("hearing"),
                    vision_status=p_spec.get("vision"),
                    department_id=p_spec.get("dept_id"),
                    job_role=p_spec.get("role"),
                    is_active=True,
                    is_synthetic=True,
                    created_by_id=admin_user.id if admin_user else None,
                )
                db.add(p)
                db.flush()

            # Active Consent
            cons = db.scalar(
                select(Consent).where(
                    Consent.organization_id == org.id,
                    Consent.patient_id == p.id,
                    Consent.scope == f"{p_spec['track']}_clinical_monitoring",
                )
            )
            if not cons:
                cons = Consent(
                    organization_id=org.id,
                    patient_id=p.id,
                    scope=f"{p_spec['track']}_clinical_monitoring",
                    status="granted",
                    method="electronic",
                    granted_by_name=f"{p.given_name} {p.family_name}",
                    recorded_by_id=admin_user.id if admin_user else None,
                    effective_at=now - timedelta(days=30),
                )
                db.add(cons)

            # Track Enrollment
            enroll = db.scalar(
                select(TrackEnrollment).where(
                    TrackEnrollment.organization_id == org.id,
                    TrackEnrollment.patient_id == p.id,
                    TrackEnrollment.track == p_spec["track"],
                )
            )
            if not enroll:
                enroll = TrackEnrollment(
                    organization_id=org.id,
                    patient_id=p.id,
                    track=p_spec["track"],
                    status="active",
                    enrolled_at=now - timedelta(days=20),
                    latest_risk_tier=p_spec.get("tier"),
                    context={"seed": True, "desc": p_spec["desc"]},
                )
                db.add(enroll)

            # Observations
            for code, val, unit, days_ago in p_spec.get("observations", []):
                eff = now - timedelta(days=days_ago)
                obs_exist = db.scalar(
                    select(Observation).where(
                        Observation.organization_id == org.id,
                        Observation.patient_id == p.id,
                        Observation.metric_code == code,
                        Observation.effective_at >= eff - timedelta(minutes=1),
                        Observation.effective_at <= eff + timedelta(minutes=1),
                    )
                )
                if not obs_exist:
                    obs = Observation(
                        organization_id=org.id,
                        patient_id=p.id,
                        track=p_spec["track"],
                        metric_code=code,
                        value_num=val,
                        unit=unit,
                        effective_at=eff,
                        source="checkin" if p_spec["track"] == "core" else "clinical",
                    )
                    db.add(obs)

            # Established Baseline
            if "baseline" in p_spec:
                b_code, b_mean, b_sd, b_n = p_spec["baseline"]
                base_exist = db.scalar(
                    select(PersonalBaseline).where(
                        PersonalBaseline.organization_id == org.id,
                        PersonalBaseline.patient_id == p.id,
                        PersonalBaseline.metric_code == b_code,
                    )
                )
                if not base_exist:
                    base = PersonalBaseline(
                        organization_id=org.id,
                        patient_id=p.id,
                        metric_code=b_code,
                        algorithm_version="v2.0",
                        status="established",
                        n_windows=b_n,
                        mean=b_mean,
                        sample_sd=b_sd,
                        established_at=now - timedelta(days=15),
                        window_start=now - timedelta(days=30),
                        window_end=now - timedelta(days=1),
                    )
                    db.add(base)

        db.commit()

        print("\n" + "=" * 60)
        print("  SUCCESSFULLY SEEDED DEMO DATA & CLINICAL COHORTS")
        print("=" * 60)
        print("  Organization : Abu Dhabi Health Hub (ad-health)")
        print("  Email        : admin@recova.ae")
        print("  Password     : Password123!")
        print("  Patients     : 7 seeded (Core A-D, Loop, Neuro, WorkSafe)")
        print("=" * 60)
        print("\nYou can now log in at http://localhost:3001/login (or http://localhost:3000/login)!")


if __name__ == "__main__":
    main()
