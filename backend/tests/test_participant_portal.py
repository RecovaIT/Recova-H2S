"""Participant identity, consent, ingestion and retry regressions."""

import uuid
from sqlalchemy import select, func
from app.models.identity import Organization, User, Membership
from app.models.clinical import Patient, TrackEnrollment, Consent, Observation, CheckIn
from app.models.base import utcnow
from app.core.security import hash_password
from tests.conftest import auth_headers


def provision(db, client):
    org = Organization(
        name="Portal Test",
        slug="portal-test",
        enabled_tracks=["core"],
        org_type="clinic",
    )
    db.add(org)
    db.flush()
    patients = []
    for index in range(2):
        user = User(
            email=f"patient{index}@portal.example.com",
            full_name=f"Test {index}",
            password_hash=hash_password("PortalTest123!"),
        )
        db.add(user)
        db.flush()
        db.add(Membership(user_id=user.id, organization_id=org.id, role="patient"))
        patient = Patient(
            organization_id=org.id,
            mrn=f"P-{index}",
            given_name=f"Test {index}",
            family_name="Synthetic",
            portal_user_id=user.id,
            is_synthetic=True,
        )
        db.add(patient)
        db.flush()
        db.add(
            TrackEnrollment(
                organization_id=org.id,
                patient_id=patient.id,
                track="core",
                status="active",
                enrolled_at=utcnow(),
                context={},
            )
        )
        for scope in ["data_processing", "wearable_ingestion"]:
            db.add(
                Consent(
                    organization_id=org.id,
                    patient_id=patient.id,
                    scope=scope,
                    status="granted",
                    effective_at=utcnow(),
                )
            )
        patients.append(patient)
    db.commit()
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "patient0@portal.example.com", "password": "PortalTest123!"},
    )
    assert response.status_code == 200, response.text
    return patients


def test_participant_scope_and_rejected_identity_override(db, client):
    first, other = provision(db, client)
    assert client.get("/api/v1/portal/me").json()["name"] == first.given_name
    response = client.post(
        "/api/v1/portal/check-ins",
        headers=auth_headers(client),
        json={
            "mood": 6,
            "stress": 3,
            "request_id": str(uuid.uuid4()),
            "patient_id": str(other.id),
        },
    )
    assert response.status_code == 422
    assert client.get(f"/api/v1/patients/{other.id}").status_code == 403
    assert client.get("/api/v1/patients").status_code == 403


def test_participant_import_validation_retry_and_revocation(db, client):
    patient, _ = provision(db, client)
    payload = {
        "request_id": str(uuid.uuid4()),
        "readings": [
            {
                "metric": "sleep_hours",
                "value": 420,
                "unit": "minutes",
                "at": utcnow().isoformat(),
            }
        ],
    }
    headers = auth_headers(client)
    response = client.post(
        "/api/v1/portal/wearable-import", headers=headers, json=payload
    )
    assert response.status_code == 200, response.text
    assert response.json()["accepted"] == 1
    assert (
        client.post(
            "/api/v1/portal/wearable-import", headers=headers, json=payload
        ).json()["status"]
        == "already_received"
    )
    assert (
        db.scalar(
            select(func.count())
            .select_from(Observation)
            .where(Observation.patient_id == patient.id)
        )
        == 1
    )
    assert (
        db.scalar(
            select(Observation.value_num).where(Observation.patient_id == patient.id)
        )
        == 7
    )
    payload["request_id"] = str(uuid.uuid4())
    payload["readings"][0]["unit"] = "kg"
    assert (
        client.post(
            "/api/v1/portal/wearable-import", headers=headers, json=payload
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/v1/portal/consents",
            headers=headers,
            json={"scope": "wearable_ingestion", "granted": False},
        ).status_code
        == 200
    )
    payload["readings"][0]["unit"] = "minutes"
    assert (
        client.post(
            "/api/v1/portal/wearable-import", headers=headers, json=payload
        ).status_code
        == 403
    )


def test_participant_checkin_reaches_engine_once(db, client):
    patient, _ = provision(db, client)
    payload = {
        "request_id": str(uuid.uuid4()),
        "mood": 6,
        "stress": 3,
        "text": "Feeling settled today",
    }
    headers = auth_headers(client)
    response = client.post("/api/v1/portal/check-ins", headers=headers, json=payload)
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "completed"
    assert (
        client.post("/api/v1/portal/check-ins", headers=headers, json=payload).json()[
            "status"
        ]
        == "already_received"
    )
    assert (
        db.scalar(
            select(func.count())
            .select_from(CheckIn)
            .where(CheckIn.patient_id == patient.id)
        )
        == 1
    )
    assert client.get("/api/v1/portal/me").json()["checkins"][0]["mood"] == 6
    from app.models.engine import ClinicalSynthesis

    assert db.scalar(select(ClinicalSynthesis.status)) == "consent_not_granted"


def test_activity_is_programme_scoped_and_practice_results_are_server_derived(
    db, client
):
    from app.models.clinical import CognitiveAssessment

    patient, _ = provision(db, client)
    payload = {
        "request_id": str(uuid.uuid4()),
        "expected": [0, 1, 2],
        "response": [0, 2, 1],
        "correct": True,
        "reaction_time_ms": 1200,
    }
    headers = auth_headers(client)
    assert (
        client.post(
            "/api/v1/portal/activities", headers=headers, json=payload
        ).status_code
        == 403
    )
    enrollment = db.scalar(
        select(TrackEnrollment).where(TrackEnrollment.patient_id == patient.id)
    )
    enrollment.track = "neuro"
    db.commit()
    response = client.post("/api/v1/portal/activities", headers=headers, json=payload)
    assert response.status_code == 200, response.text
    assert (
        client.post("/api/v1/portal/activities", headers=headers, json=payload).json()[
            "id"
        ]
        == response.json()["id"]
    )
    assessment = db.scalar(
        select(CognitiveAssessment).where(CognitiveAssessment.patient_id == patient.id)
    )
    assert assessment.raw_trials[0]["correct"] is False
    assert assessment.status == "practice"
    assert (
        db.scalar(
            select(func.count())
            .select_from(Observation)
            .where(Observation.patient_id == patient.id)
        )
        == 0
    )
