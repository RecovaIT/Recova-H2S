"""Create 30 synthetic participant accounts. Run from backend with python -m scripts.seed_portal_demo."""

import csv
import secrets
from pathlib import Path
from datetime import timedelta
from sqlalchemy import select
from app.core.config import get_settings
from app.core.db import SessionLocal
from app.core.security import hash_password
from app.models.identity import Organization, User, Membership
from app.models.clinical import Patient, TrackEnrollment, Consent, Observation, CheckIn
from app.models.base import utcnow

SCENARIOS = {
    "core": [
        "Stable recovery",
        "Sleep decline",
        "Missed check-ins",
        "Wearable disconnected",
        "Consent pending",
        "Urgent support",
        "Follow-up booked",
        "First day",
    ],
    "loop": [
        "Routine screening",
        "Screening follow-up",
        "Appointment booked",
        "Missed appointment",
        "Missing results",
        "Consent pending",
        "New referral",
        "Public health notice",
    ],
    "neuro": [
        "First assessment",
        "Established baseline",
        "Hearing adjustment",
        "Vision adjustment",
        "Repeat activity",
        "Missing sleep data",
        "Review pending",
    ],
    "worksafe": [
        "Ready for shift",
        "Fatigue check",
        "Hot worksite",
        "Missing wearable",
        "Night shift",
        "Return to work",
        "Worksite notice",
    ],
}
NAMES = ["Amara", "Omar", "Zainab", "Tariq", "Lina", "Yusuf", "Ada", "Samira"]


def main():
    if get_settings().environment == "production":
        raise RuntimeError(
            "Synthetic account provisioning is restricted to development/test"
        )
    output = Path(__file__).resolve().parents[3] / "output" / "portal-test-accounts.csv"
    output.parent.mkdir(exist_ok=True)
    prior = {}
    credential_source = output.with_suffix(".pending.csv")
    if not credential_source.exists():
        credential_source = output
    if credential_source.exists():
        with credential_source.open() as handle:
            prior = {row["email"]: row for row in csv.DictReader(handle)}
    rows = []
    now = utcnow()
    with SessionLocal() as db:
        for track, scenarios in SCENARIOS.items():
            slug = f"portal-demo-{track}"
            org = db.scalar(select(Organization).where(Organization.slug == slug))
            if org is None:
                org = Organization(
                    name={
                        "core": "Recova Recovery Centre",
                        "loop": "Recova Community Clinic",
                        "neuro": "Recova Brain Health Centre",
                        "worksafe": "Recova WorkSafe Facility",
                    }[track],
                    slug=slug,
                    enabled_tracks=[track],
                    org_type="employer" if track == "worksafe" else "clinic",
                    settings={"synthetic_demo": True},
                )
                db.add(org)
                db.flush()
            for index, scenario in enumerate(scenarios, 1):
                email = f"{track}{index:02}@demo.recova.example.com"
                user = db.scalar(select(User).where(User.email == email))
                if user is not None:
                    if email not in prior:
                        raise RuntimeError(
                            "Existing demo user has no local credential record. Reset explicitly through account management."
                        )
                    rows.append(prior[email])
                    continue
                password = "Recova-" + secrets.token_urlsafe(12) + "7"
                user = User(
                    email=email,
                    full_name=f"{NAMES[index-1]} Demo",
                    password_hash=hash_password(password),
                )
                db.add(user)
                db.flush()
                db.add(
                    Membership(user_id=user.id, organization_id=org.id, role="patient")
                )
                patient = Patient(
                    organization_id=org.id,
                    mrn=f"PORTAL-{track}-{index}",
                    given_name=NAMES[index - 1],
                    family_name="Demo",
                    portal_user_id=user.id,
                    is_synthetic=True,
                    participant_type="employee" if track == "worksafe" else "patient",
                    hearing_status=(
                        "mild_loss" if scenario == "Hearing adjustment" else "normal"
                    ),
                    vision_status=(
                        "corrected" if scenario == "Vision adjustment" else "normal"
                    ),
                )
                db.add(patient)
                db.flush()
                care = [
                    {
                        "id": "care-1",
                        "title": "Care team follow-up",
                        "detail": "Contact your facility to confirm your next review.",
                        "status": "To arrange",
                    }
                ]
                if "booked" in scenario.lower():
                    care = [
                        {
                            "id": "care-1",
                            "title": "Follow-up consultation",
                            "detail": "Synthetic appointment for testing the care view.",
                            "status": "Booked",
                            "at": (now + timedelta(days=2)).isoformat(),
                        }
                    ]
                notice = {
                    "id": "notice-1",
                    "title": "Keeping well in hot weather",
                    "body": "A synthetic public-health notice to test communication across every programme. Follow your facility's guidance and contact your care team with concerns.",
                    "issuer": "Demo public-health team",
                    "severity": "Information",
                }
                db.add(
                    TrackEnrollment(
                        organization_id=org.id,
                        patient_id=patient.id,
                        track=track,
                        enrolled_at=now,
                        context={
                            "scenario": scenario,
                            "portal_care": care,
                            "portal_notices": [notice],
                            "portal_acknowledged": [],
                        },
                    )
                )
                if scenario != "Consent pending":
                    for scope in ["data_processing", "wearable_ingestion"]:
                        db.add(
                            Consent(
                                organization_id=org.id,
                                patient_id=patient.id,
                                scope=scope,
                                status="granted",
                                method="electronic",
                                effective_at=now - timedelta(days=20),
                                granted_by_name="Synthetic fixture",
                                evidence_reference="demo-fixture",
                            )
                        )
                if scenario not in {
                    "First day",
                    "First assessment",
                    "Missing wearable",
                    "Wearable disconnected",
                    "Missing results",
                    "Consent pending",
                }:
                    for day in range(14):
                        sleep = 7.4 + (day % 3) * 0.1
                        if (
                            scenario
                            in {"Sleep decline", "Fatigue check", "Night shift"}
                            and day < 4
                        ):
                            sleep = 4.3 + day * 0.3
                        for metric, value, unit in [
                            ("sleep_hours", sleep, "h"),
                            ("hrv_rmssd", 48 + day % 5, "ms"),
                            ("resting_hr", 64 + day % 4, "bpm"),
                            ("steps", 4800 + day * 130, "count"),
                        ]:
                            db.add(
                                Observation(
                                    organization_id=org.id,
                                    patient_id=patient.id,
                                    track=track,
                                    metric_code=metric,
                                    value_num=value,
                                    unit=unit,
                                    effective_at=now - timedelta(days=day, hours=2),
                                    source="wearable",
                                    provenance={"synthetic_fixture": True},
                                )
                            )
                rows.append(
                    {
                        "email": email,
                        "password": password,
                        "programme": track,
                        "scenario": scenario,
                        "facility": org.name,
                        "url": get_settings().frontend_base_url.rstrip("/") + "/login",
                    }
                )
        # Credentials and accounts are written together before committing; retry preserves passwords.
        temporary = output.with_suffix(".pending.csv")
        with temporary.open("w", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=[
                    "email",
                    "password",
                    "programme",
                    "scenario",
                    "facility",
                    "url",
                ],
            )
            writer.writeheader()
            writer.writerows(rows)
        db.commit()
        temporary.replace(output)
    print(f"Created or retained {len(rows)} accounts. Credentials saved to {output}")
    enrich_scenarios()


def enrich_scenarios():
    """Repeatable fixture details distinguish completed, overdue and screening scenarios."""
    with SessionLocal() as db:
        organizations = list(
            db.scalars(
                select(Organization).where(
                    Organization.slug.in_(
                        [f"portal-demo-{track}" for track in SCENARIOS]
                    )
                )
            )
        )
        for org in organizations:
            for enrollment in db.scalars(
                select(TrackEnrollment).where(TrackEnrollment.organization_id == org.id)
            ):
                scenario = enrollment.context.get("scenario", "")
                patient = db.get(Patient, enrollment.patient_id)
                if not patient.is_synthetic:
                    continue
                if enrollment.track in {"core", "worksafe"} and scenario not in {
                    "First day",
                    "Consent pending",
                    "Missing wearable",
                }:
                    exists = db.scalar(
                        select(CheckIn).where(
                            CheckIn.patient_id == patient.id,
                            CheckIn.extra["fixture"].astext == "portal-scenario-v1",
                        )
                    )
                    if exists is None:
                        urgent = scenario == "Urgent support"
                        db.add(
                            CheckIn(
                                organization_id=org.id,
                                patient_id=patient.id,
                                track=enrollment.track,
                                kind=(
                                    "readiness"
                                    if enrollment.track == "worksafe"
                                    else "text"
                                ),
                                effective_at=utcnow()
                                - timedelta(
                                    days=3 if scenario == "Missed check-ins" else 0
                                ),
                                mood_score=2 if urgent else 7,
                                stress_score=9 if urgent else 3,
                                text=(
                                    "Synthetic urgent-support request for testing."
                                    if urgent
                                    else "Synthetic daily reflection for testing."
                                ),
                                self_reported_crisis=urgent,
                                extra={"fixture": "portal-scenario-v1"},
                            )
                        )
                if enrollment.track == "loop" and scenario not in {
                    "Missing results",
                    "Consent pending",
                }:
                    for metric, value, unit in [
                        (
                            "hba1c",
                            (
                                7.8
                                if scenario in {"Screening follow-up", "New referral"}
                                else 5.4
                            ),
                            "%",
                        ),
                        ("bp_systolic", 128, "mmHg"),
                        ("bp_diastolic", 82, "mmHg"),
                    ]:
                        exists = db.scalar(
                            select(Observation).where(
                                Observation.patient_id == patient.id,
                                Observation.metric_code == metric,
                            )
                        )
                        if exists is None:
                            db.add(
                                Observation(
                                    organization_id=org.id,
                                    patient_id=patient.id,
                                    track="loop",
                                    metric_code=metric,
                                    value_num=value,
                                    unit=unit,
                                    effective_at=utcnow() - timedelta(days=2),
                                    source="manual",
                                    provenance={"synthetic_fixture": True},
                                )
                            )
        db.commit()


if __name__ == "__main__":
    main()
