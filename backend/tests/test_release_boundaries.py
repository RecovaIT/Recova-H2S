import uuid
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
from tests.conftest import auth_headers, bootstrap_org_and_admin
from tests.test_participant_portal import provision


def post(c, path, body=None):
    return c.post("/api/v1" + path, headers=auth_headers(c), json=body)


def test_patient_websocket_and_emergency_without_routine_consent(db, client):
    patient, _ = provision(db, client)
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect("/api/v1/pipeline/ws") as ws:
            ws.receive_json()
    assert exc.value.code == 4403
    post(client, "/portal/consents", {"scope": "data_processing", "granted": False})
    normal = post(
        client,
        "/portal/check-ins",
        {"mood": 5, "stress": 4, "request_id": str(uuid.uuid4())},
    )
    assert normal.status_code == 403
    urgent = post(
        client,
        "/portal/check-ins",
        {"mood": 1, "stress": 9, "crisis": True, "request_id": str(uuid.uuid4())},
    )
    assert urgent.status_code == 200, urgent.text
    assert urgent.json()["emergency"] is True
    from sqlalchemy import select
    from app.models.clinical import CheckIn

    row = db.scalar(select(CheckIn).where(CheckIn.patient_id == patient.id))
    assert row.mood_score is None and row.stress_score is None


def test_cross_patient_review_and_referral_state_machine(client):
    bootstrap_org_and_admin(client)

    def patient(mrn):
        return post(
            client,
            "/patients",
            {
                "mrn": mrn,
                "given_name": "Test",
                "family_name": "Boundary",
                "tracks": ["core"],
            },
        ).json()["id"]

    a, b = patient("ONE"), patient("TWO")
    cancelled = post(
        client,
        "/referrals",
        {
            "patient_id": b,
            "track": "core",
            "pathway": "primary_care",
            "reason": "Cancellation test",
        },
    ).json()
    assert (
        post(
            client,
            f"/referrals/{cancelled['id']}/cancel",
            {"reason": "Patient requested cancellation"},
        ).status_code
        == 200
    )
    assert (
        post(
            client,
            f"/referrals/{cancelled['id']}/book",
            {"appointment_at": "2026-11-20T10:00:00Z"},
        ).status_code
        == 422
    )
    post(client, "/consents", {"patient_id": a, "scope": "data_processing"})
    run = post(client, "/pipeline/runs", {"patient_id": a, "track": "core"}).json()
    ref = post(
        client,
        "/referrals",
        {
            "patient_id": b,
            "track": "core",
            "pathway": "primary_care",
            "reason": "Boundary test",
        },
    ).json()
    bad = post(
        client,
        "/clinical-reviews",
        {"run_id": run["id"], "referral_id": ref["id"], "decision": "approve_referral"},
    )
    assert bad.status_code == 422, bad.text
    assert (
        post(
            client,
            f"/outcomes/referral/{ref['id']}/verify",
            {"outcome": "stable", "verification_method": "record_review"},
        ).status_code
        == 422
    )
    assert (
        post(client, f"/referrals/{ref['id']}/complete-consultation", {}).status_code
        == 422
    )
    from app.models.base import utcnow

    assert (
        post(
            client,
            f"/referrals/{ref['id']}/book",
            {"appointment_at": utcnow().isoformat()},
        ).status_code
        == 200
    )
    assert (
        post(client, f"/referrals/{ref['id']}/complete-consultation", {}).status_code
        == 200
    )
    assert (
        post(
            client,
            f"/outcomes/referral/{ref['id']}/verify",
            {
                "outcome": "stable",
                "verification_method": "record_review",
                "follow_up_run_id": run["id"],
            },
        ).status_code
        == 422
    )
    assert (
        post(
            client,
            f"/outcomes/referral/{ref['id']}/verify",
            {"outcome": "stable", "verification_method": "record_review"},
        ).status_code
        == 201
    )
    assert (
        post(
            client,
            f"/referrals/{ref['id']}/book",
            {"appointment_at": utcnow().isoformat()},
        ).status_code
        == 422
    )


def test_tenant_cannot_disable_shared_or_platform_account(client):
    platform = bootstrap_org_and_admin(client)
    operator = platform["user"]["id"]
    client.post("/api/v1/auth/logout", headers=auth_headers(client))
    r = client.post(
        "/api/v1/auth/register-organization",
        json={
            "organization_name": "Other clinic",
            "organization_slug": "other-clinic",
            "primary_programme": "core",
            "enabled_tracks": ["core"],
            "admin_email": "other@clinic.example.com",
            "admin_full_name": "Clinic Owner",
            "admin_password": "OtherOwner123!",
        },
    )
    assert r.status_code == 201, r.text
    post(
        client,
        "/users",
        {
            "email": "admin@adwellness.ae",
            "full_name": "Existing Operator",
            "role": "clinician",
        },
    )
    assert (
        client.patch(
            "/api/v1/users/" + operator,
            headers=auth_headers(client),
            json={"is_active": False},
        ).status_code
        == 403
    )
    staff = post(
        client,
        "/users",
        {
            "email": "staff@clinic.example.com",
            "full_name": "Shared Staff",
            "role": "clinician",
            "password": "OtherOwner123!",
        },
    ).json()["user"]
    r = client.patch(
        "/api/v1/users/" + staff["id"],
        headers=auth_headers(client),
        json={"is_active": False},
    )
    assert r.status_code == 200
    users = client.get("/api/v1/users").json()
    assert next(u for u in users if u["id"] == staff["id"])["is_active"] is False
    from app.core.db import SessionLocal
    from app.models.identity import User

    with SessionLocal() as db:
        assert db.get(User, uuid.UUID(staff["id"])).is_active is True


def test_supervisor_override_cannot_expose_individuals(db, client):
    session = bootstrap_org_and_admin(client)
    post(
        client,
        "/users",
        {
            "email": "sup@clinic.example.com",
            "full_name": "Supervisor",
            "role": "supervisor",
            "password": "Supervisor123!",
        },
    )
    denied = post(
        client,
        "/organizations/permissions/overrides",
        {
            "role": "supervisor",
            "permission": "workforce:read_identifiable",
            "effect": "grant",
        },
    )
    assert denied.status_code == 422
    from app.models.identity import RolePermissionOverride

    for perm in (
        "workforce:read_identifiable",
        "patients:read",
        "patients:read_identifiable",
        "pipeline:read",
        "interventions:read",
    ):
        db.add(
            RolePermissionOverride(
                organization_id=uuid.UUID(session["active_organization"]["id"]),
                role="supervisor",
                permission=perm,
                effect="grant",
            )
        )
    db.commit()
    client.post("/api/v1/auth/logout", headers=auth_headers(client))
    client.post(
        "/api/v1/auth/login",
        json={"email": "sup@clinic.example.com", "password": "Supervisor123!"},
    )
    assert client.get("/api/v1/workforce/identifiable-risks").status_code == 403
    for path in ("/patients", "/pipeline/runs", "/interventions", "/reports/overview"):
        assert client.get("/api/v1" + path).status_code == 403, path
    assert client.get("/api/v1/workforce/heatmap").status_code == 200


def test_reminders_are_patient_visible_and_idempotent(db, client):
    from datetime import timedelta
    from sqlalchemy import select, func
    from app.models.base import utcnow
    from app.models.care import Referral, Notification
    from app.services.care import send_appointment_reminders

    patient, _ = provision(db, client)
    ref = db.scalar(select(Referral).where(Referral.patient_id == patient.id))
    if ref is None:
        ref = Referral(
            organization_id=patient.organization_id,
            patient_id=patient.id,
            track="core",
            pathway="primary_care",
            priority="routine",
            reason="Reminder",
            status="booked",
            appointment_at=utcnow() + timedelta(hours=2),
        )
        db.add(ref)
        db.commit()
    else:
        ref.status = "booked"
        ref.appointment_at = utcnow() + timedelta(hours=2)
        db.commit()
    send_appointment_reminders(db, patient.organization_id)
    db.commit()
    send_appointment_reminders(db, patient.organization_id)
    db.commit()
    count = db.scalar(
        select(func.count())
        .select_from(Notification)
        .where(
            Notification.referral_id == ref.id, Notification.category == "care_update"
        )
    )
    assert count == 1

    care = client.get("/api/v1/portal/care")
    assert care.status_code == 200, care.text
    assert str(ref.id) in care.text


def test_patient_foreign_keys_and_care_assignment_cannot_cross_tenants(db, client):
    from app.models.identity import Organization, User, Membership
    from app.models.clinical import Department
    from app.models.care import InsurancePlan
    from app.core.security import hash_password

    session = bootstrap_org_and_admin(client)
    org = Organization(
        name="Other tenant", slug="other-boundary", enabled_tracks=["core"]
    )
    db.add(org)
    db.flush()
    user = User(
        email="other@boundary.example.com",
        full_name="Other Practitioner",
        password_hash=hash_password("PrivateOther123!"),
        license_number="TEST-OTHER",
    )
    db.add(user)
    db.flush()
    db.add(Membership(user_id=user.id, organization_id=org.id, role="clinician"))
    dept = Department(organization_id=org.id, name="Other Department")
    plan = InsurancePlan(organization_id=org.id, name="Other Plan", code="OTHER")
    db.add_all([dept, plan])
    db.commit()
    body = {
        "mrn": "LINKS",
        "given_name": "Boundary",
        "family_name": "Links",
        "tracks": ["core"],
    }
    assert (
        post(
            client, "/patients", {**body, "primary_clinician_id": str(user.id)}
        ).status_code
        == 422
    )
    created = post(client, "/patients", body)
    assert created.status_code == 201, created.text
    data = created.json()
    assert data["primary_clinician_id"] is None
    for field, value in [
        ("primary_clinician_id", user.id),
        ("department_id", dept.id),
        ("insurance_plan_id", plan.id),
    ]:
        response = client.patch(
            "/api/v1/patients/" + data["id"],
            headers=auth_headers(client),
            json={field: str(value)},
        )
        assert response.status_code == 422, response.text
    response = client.patch(
        "/api/v1/patients/" + data["id"],
        headers=auth_headers(client),
        json={"primary_clinician_id": session["user"]["id"]},
    )
    assert response.status_code == 200, response.text
