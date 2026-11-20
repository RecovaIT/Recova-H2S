"""Comprehensive local/dev system test-case seeder covering all roles, sub-engines, and edge cases.

Usage:
    cd backend
    .\\.venv\\Scripts\\python.exe -m scripts.seed_all_test_cases --reset
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from app.core.config import get_settings
from app.core.db import SessionLocal
from app.core.security import hash_password
from app.models.base import utcnow
from app.models.clinical import Department, Patient, TrackEnrollment
from app.models.identity import Membership, Organization, ParticipantAccountLink, ProgrammeRequest, User
from scripts.seed_judge_demo import JUDGE_ORGS, seed_judge_demo

DEMO_PASS = "JudgeDemo123!"


def _ensure_user(db, *, email: str, full_name: str, is_platform_admin: bool = False, license_number: str | None = None) -> User:
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(
            email=email,
            full_name=full_name,
            password_hash=hash_password(DEMO_PASS),
            is_active=True,
            is_platform_admin=is_platform_admin,
            license_number=license_number,
        )
        db.add(user)
        db.flush()
    else:
        user.password_hash = hash_password(DEMO_PASS)
        user.is_active = True
        user.is_platform_admin = is_platform_admin
        if license_number:
            user.license_number = license_number
    return user


def _ensure_membership(db, *, user_id, org_id, role: str, department_ids: list | None = None) -> None:
    mem = db.scalar(
        select(Membership).where(Membership.user_id == user_id, Membership.organization_id == org_id)
    )
    if mem is None:
        db.add(
            Membership(
                user_id=user_id,
                organization_id=org_id,
                role=role,
                is_active=True,
                department_ids=department_ids or [],
            )
        )


def seed_all_test_cases(*, reset: bool = False) -> dict:
    if get_settings().environment == "production":
        raise RuntimeError("System test-case seeding is strictly prohibited in production.")

    base_summary = seed_judge_demo(reset=reset)

    with SessionLocal() as db:
        orgs_by_prog: dict[str, Organization] = {}
        for slug, _, _, prog in JUDGE_ORGS:
            org = db.scalar(select(Organization).where(Organization.slug == slug))
            if org is not None:
                orgs_by_prog[prog] = org

        # 1. Platform Admin (member of all 4 centers for multi-org switching & Overall Engine Command)
        plat_admin = _ensure_user(
            db,
            email="platform.admin@demo.recova.ae",
            full_name="Recova Platform Operator",
            is_platform_admin=True,
            license_number="DOH-PLAT-0001",
        )
        for org in orgs_by_prog.values():
            _ensure_membership(db, user_id=plat_admin.id, org_id=org.id, role="org_admin")

        # 2. Facility Admins (org_admin) per sub-engine center
        for prog, org in orgs_by_prog.items():
            f_admin = _ensure_user(
                db,
                email=f"admin.{prog}@demo.recova.ae",
                full_name=f"Facility Admin ({prog.title()})",
                license_number=f"DOH-ADM-{prog.upper()}",
            )
            _ensure_membership(db, user_id=f_admin.id, org_id=org.id, role="org_admin")

        # 3. Specialized Clinical & Operational Roles
        if "loop" in orgs_by_prog:
            sc = _ensure_user(
                db,
                email="coordinator.loop@demo.recova.ae",
                full_name="Nadia Screening Coordinator",
                license_number="DOH-SC-2010",
            )
            _ensure_membership(db, user_id=sc.id, org_id=orgs_by_prog["loop"].id, role="screening_coordinator")

        if "core" in orgs_by_prog:
            cc = _ensure_user(
                db,
                email="care.core@demo.recova.ae",
                full_name="Salim Care Coordinator",
                license_number="DOH-CC-1010",
            )
            _ensure_membership(db, user_id=cc.id, org_id=orgs_by_prog["core"].id, role="care_coordinator")

            psy = _ensure_user(
                db,
                email="psych.core@demo.recova.ae",
                full_name="Dr. Layla Psychiatrist",
                license_number="DOH-PSY-1020",
            )
            _ensure_membership(db, user_id=psy.id, org_id=orgs_by_prog["core"].id, role="psychiatrist")

        if "worksafe" in orgs_by_prog:
            ws_org = orgs_by_prog["worksafe"]
            dept = db.scalar(select(Department).where(Department.organization_id == ws_org.id))
            sup = _ensure_user(
                db,
                email="supervisor.worksafe@demo.recova.ae",
                full_name="Khalid Field Supervisor",
            )
            _ensure_membership(
                db,
                user_id=sup.id,
                org_id=ws_org.id,
                role="supervisor",
                department_ids=[dept.id] if dept else [],
            )

        # 4. Public Health Authority User
        if "loop" in orgs_by_prog:
            auth_user = _ensure_user(
                db,
                email="authority.abu-dhabi@demo.recova.ae",
                full_name="Abu Dhabi Public Health Authority",
                is_platform_admin=True,
                license_number="DOH-AUTH-9001",
            )
            _ensure_membership(db, user_id=auth_user.id, org_id=orgs_by_prog["loop"].id, role="org_admin")

        # 5. Multi-Enrolment Participant (Core + Loop)
        multi_user = _ensure_user(
            db,
            email="multi.patient@demo.recova.ae",
            full_name="Mariam Multi-Enrolled",
        )
        for prog in ("core", "loop"):
            if prog not in orgs_by_prog:
                continue
            org = orgs_by_prog[prog]
            _ensure_membership(db, user_id=multi_user.id, org_id=org.id, role="patient")
            mrn = f"MULTI-{prog.upper()}-01"
            pat = db.scalar(select(Patient).where(Patient.organization_id == org.id, Patient.mrn == mrn))
            if pat is None:
                pat = Patient(
                    organization_id=org.id,
                    participant_type="patient",
                    mrn=mrn,
                    given_name="Mariam",
                    family_name="Al-Ketbi",
                    preferred_language="en",
                    portal_user_id=multi_user.id if prog == "core" else None,
                    is_synthetic=True,
                )
                db.add(pat)
                db.flush()
                db.add(
                    TrackEnrollment(
                        organization_id=org.id,
                        patient_id=pat.id,
                        track=prog,
                        status="active",
                        enrolled_at=utcnow(),
                        latest_risk_tier="GREEN",
                    )
                )
                db.add(
                    ParticipantAccountLink(
                        organization_id=org.id,
                        patient_id=pat.id,
                        user_id=multi_user.id,
                        verified_at=utcnow(),
                        verification_source="seed_all_test_cases",
                    )
                )

        # 6. Pending Programme Expansion Request (Core center requesting Loop)
        if "core" in orgs_by_prog:
            core_org = orgs_by_prog["core"]
            existing_req = db.scalar(
                select(ProgrammeRequest).where(
                    ProgrammeRequest.organization_id == core_org.id,
                    ProgrammeRequest.requested_programme == "loop",
                    ProgrammeRequest.status == "pending",
                )
            )
            if existing_req is None:
                db.add(
                    ProgrammeRequest(
                        organization_id=core_org.id,
                        requested_programme="loop",
                        justification="Expanding rehabilitation center to include IFHAS metabolic screening.",
                        status="pending",
                        requested_by_id=plat_admin.id,
                    )
                )

        # 7. Legacy Multi-Track Org awaiting selection
        legacy_slug = "legacy-multi-org"
        legacy_org = db.scalar(select(Organization).where(Organization.slug == legacy_slug))
        if legacy_org is None:
            legacy_org = Organization(
                name="Legacy Multi-Track Clinic",
                slug=legacy_slug,
                org_type="clinic",
                primary_programme="core",
                programme_configuration_status="pending_selection",
                enabled_tracks=["core", "loop"],
                country="UAE",
                emirate="Dubai",
            )
            db.add(legacy_org)
            db.flush()
        legacy_admin = _ensure_user(
            db,
            email="legacy.admin@demo.recova.ae",
            full_name="Legacy Clinic Admin",
            license_number="DHA-LEG-001",
        )
        _ensure_membership(db, user_id=legacy_admin.id, org_id=legacy_org.id, role="org_admin")

        # 8. Account without active org membership
        _ensure_user(
            db,
            email="unlinked.user@demo.recova.ae",
            full_name="Unlinked Pending User",
        )

        db.commit()

    return {
        **base_summary,
        "extra_roles_seeded": True,
        "password_for_all_demo_accounts": DEMO_PASS,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed all Recova system test cases and credentials.")
    parser.add_argument("--reset", action="store_true", help="Reset judge demo organisations before seeding.")
    args = parser.parse_args()
    print(seed_all_test_cases(reset=args.reset))
