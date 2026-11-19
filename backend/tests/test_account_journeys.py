import json, re, uuid
from datetime import timedelta
from sqlalchemy import select
from app.core.db import SessionLocal
from app.core.security import decrypt_str, hash_token
from app.core.config import get_settings
from app.models.messaging import EmailDelivery
from app.models.identity import PasswordResetToken, User
from app.models.base import utcnow
from app.tasks.queue import run_pending_jobs
from tests.conftest import bootstrap_org_and_admin, auth_headers


def post(c, path, body=None):
    return c.post("/api/v1" + path, headers=auth_headers(c), json=body)


def latest(category):
    with SessionLocal() as db:
        row = db.scalar(
            select(EmailDelivery)
            .where(EmailDelivery.category == category)
            .order_by(EmailDelivery.created_at.desc())
        )
        return (
            row.id,
            json.loads(decrypt_str(row.payload_encrypted))["body"],
            row.status,
        )


def token(body):
    return re.search(r"token=([A-Za-z0-9_-]+)", body).group(1)


def test_staff_invite_private_recovery_and_token_invalidation(client):
    bootstrap_org_and_admin(client)
    r = post(
        client,
        "/users",
        {
            "email": "new@staff.example.com",
            "full_name": "New Staff",
            "role": "clinician",
        },
    )
    assert r.status_code == 201, r.text
    _, mail, status = latest("activation")
    assert status == "not_configured"
    tok = token(mail)
    # Setup messages and tokens are encrypted at rest, not returned by the public reset API.
    with SessionLocal() as db:
        row = db.scalar(
            select(EmailDelivery).where(EmailDelivery.category == "activation")
        )
        assert tok not in row.payload_encrypted
    reset = post(
        client,
        "/auth/password-reset/confirm",
        {"token": tok, "new_password": "MyPrivatePass123!"},
    )
    assert reset.status_code == 200, reset.text
    assert (
        post(
            client,
            "/auth/password-reset/confirm",
            {"token": tok, "new_password": "AnotherPass123!"},
        ).status_code
        == 401
    )
    known = client.post(
        "/api/v1/auth/password-reset/request", json={"email": "new@staff.example.com"}
    ).json()
    _, mail, _ = latest("reset")
    first = token(mail)
    unknown = client.post(
        "/api/v1/auth/password-reset/request",
        json={"email": "unknown@staff.example.com"},
    ).json()
    assert known == unknown and "delivery_status" not in known
    client.post(
        "/api/v1/auth/password-reset/request", json={"email": "new@staff.example.com"}
    )
    assert (
        post(
            client,
            "/auth/password-reset/confirm",
            {"token": first, "new_password": "AnotherPass123!"},
        ).status_code
        == 401
    )
    _, mail, _ = latest("reset")
    new = token(mail)
    assert (
        post(
            client,
            "/auth/password-reset/confirm",
            {"token": new, "new_password": "AnotherPass123!"},
        ).status_code
        == 200
    )


def test_new_patient_email_link_creates_session_and_right_portal(client):
    bootstrap_org_and_admin(client)
    p = post(
        client,
        "/patients",
        {
            "mrn": "SETUP1",
            "given_name": "New",
            "family_name": "Patient",
            "tracks": ["core"],
        },
    ).json()
    invite = post(
        client,
        f"/patients/{p['id']}/portal-invitations",
        {"recipient_email": "patient@setup.example.com"},
    )
    assert invite.status_code == 201, invite.text
    data = invite.json()
    tok = data["invitation_token"]
    assert data["delivery_status"] == "not_configured"
    assert (
        client.post(
            "/api/v1/auth/portal-invitations/inspect", json={"token": tok}
        ).json()["existing_account"]
        is False
    )
    post(client, "/auth/logout")
    body = {
        "token": tok,
        "new_password": "MyPrivatePass123!",
        "full_name": "New Patient",
    }
    r = client.post("/api/v1/auth/complete-portal-invitation", json=body)
    assert r.status_code == 200, r.text
    assert r.json()["role"] == "patient"
    assert client.get("/api/v1/portal/me").json()["track"] == "core"
    assert (
        client.post("/api/v1/auth/complete-portal-invitation", json=body).status_code
        == 409
    )


def test_expired_patient_link_and_existing_account_not_reset(client):
    bootstrap_org_and_admin(client)
    p = post(
        client,
        "/patients",
        {
            "mrn": "SETUP2",
            "given_name": "Existing",
            "family_name": "Patient",
            "tracks": ["loop"],
        },
    ).json()
    inv = post(
        client,
        f"/patients/{p['id']}/portal-invitations",
        {"recipient_email": "admin@adwellness.ae"},
    ).json()
    r = client.post(
        "/api/v1/auth/complete-portal-invitation",
        json={
            "token": inv["invitation_token"],
            "new_password": "OtherPrivate123!",
            "full_name": "Existing",
        },
    )
    assert r.status_code == 409
    from app.models.identity import PortalInvitation

    with SessionLocal() as db:
        row = db.scalar(
            select(PortalInvitation).where(
                PortalInvitation.token_hash == hash_token(inv["invitation_token"])
            )
        )
        row.expires_at = utcnow() - timedelta(seconds=1)
        db.commit()
    assert (
        client.post(
            "/api/v1/auth/portal-invitations/inspect",
            json={"token": inv["invitation_token"]},
        ).status_code
        == 404
    )


def test_verify_email_not_usable_as_password_token(client):
    bootstrap_org_and_admin(client)
    _, mail, _ = latest("verify_email")
    tok = token(mail)
    assert (
        post(
            client,
            "/auth/password-reset/confirm",
            {"token": tok, "new_password": "InvalidSwap123!"},
        ).status_code
        == 401
    )
    assert (
        client.post("/api/v1/auth/verify-email", json={"token": tok}).status_code == 200
    )
    assert (
        client.post("/api/v1/auth/verify-email", json={"token": tok}).status_code == 401
    )


def test_outbox_submission_retry_and_duplicate_worker_job(client, monkeypatch):
    bootstrap_org_and_admin(client)
    s = get_settings()
    monkeypatch.setattr(s, "smtp_host", "127.0.0.1")
    monkeypatch.setattr(s, "smtp_from", "local@recova.example.com")
    calls = []
    import app.integrations.notifications as adapters

    monkeypatch.setattr(
        adapters,
        "send_email_direct",
        lambda **kw: (calls.append(kw) or {"status": "sent", "provider": "local-test"}),
    )
    r = post(
        client,
        "/users",
        {
            "email": "queued@setup.example.com",
            "full_name": "Queued Staff",
            "role": "clinician",
        },
    )
    assert r.status_code == 201
    email_id, _, status = latest("activation")
    assert status == "queued"
    run_pending_jobs(20)
    with SessionLocal() as db:
        row = db.get(EmailDelivery, email_id)
        assert row.status == "sent" and row.attempts == 1
        from app.services.messaging import deliver_email

        deliver_email(db, email_id)
        db.commit()
    assert len(calls) == 1
    deliveries = client.get("/api/v1/settings/email-deliveries").json()
    assert any(r["status"] == "sent" for r in deliveries)
    # A different tenant cannot retry another tenant's outbox record.
    from app.services.messaging import queue_email

    with SessionLocal() as db:
        row = queue_email(
            db,
            to="private@setup.example.com",
            subject="Private",
            body="Private message",
            category="test",
            organization_id=None,
        )
        pid = row.id
        db.commit()
    assert post(client, f"/settings/email-deliveries/{pid}/retry").status_code == 404


def test_expired_links_are_not_sent_and_transport_failures_schedule_retry(
    client, monkeypatch
):
    bootstrap_org_and_admin(client)
    from app.services.messaging import queue_email, deliver_email
    from app.models.ops import Job

    settings = get_settings()
    monkeypatch.setattr(settings, "smtp_host", "127.0.0.1")
    monkeypatch.setattr(settings, "smtp_from", "local@example.com")
    calls = []
    import app.integrations.notifications as adapters

    monkeypatch.setattr(
        adapters,
        "send_email_direct",
        lambda **kw: (
            calls.append(kw)
            or {"status": "failed", "error": "Controlled connection failure"}
        ),
    )
    with SessionLocal() as db:
        expired = queue_email(
            db,
            to="local@example.com",
            subject="Expired",
            body="Expired setup",
            category="test",
            expires_at=utcnow() - timedelta(seconds=1),
        )
        deliver_email(db, expired.id)
        assert expired.status == "expired" and not calls
        failed = queue_email(
            db,
            to="local@example.com",
            subject="Retry",
            body="Retry setup",
            category="test",
        )
        deliver_email(db, failed.id)
        assert (
            failed.status == "failed"
            and failed.attempts == 1
            and failed.next_attempt_at > utcnow()
        )
        assert db.scalar(
            select(Job.id).where(Job.idempotency_key == f"email:{failed.id}:1")
        )
        db.commit()


def test_production_bootstrap_requires_operator_secret_and_blocks_first_public_signup(
    client, monkeypatch
):
    settings = get_settings()
    monkeypatch.setattr(settings, "environment", "production")
    secret = "operator-test-secret-with-at-least-32-characters"
    monkeypatch.setattr(settings, "bootstrap_setup_token", secret)
    body = {
        "organization_name": "Operator Clinic",
        "organization_slug": "operator-clinic",
        "admin_full_name": "Operator",
        "admin_email": "operator@example.com",
        "admin_password": "OperatorPrivate123!",
        "primary_programme": "core",
        "enabled_tracks": ["core"],
    }
    assert client.post("/api/v1/auth/bootstrap", json=body).status_code == 403
    assert (
        client.post("/api/v1/auth/register-organization", json=body).status_code == 403
    )
    with SessionLocal() as db:
        assert db.scalar(select(User.id)) is None
    body["bootstrap_setup_token"] = secret
    response = client.post("/api/v1/auth/bootstrap", json=body)
    assert response.status_code == 201, response.text
    assert response.json()["user"]["is_platform_admin"] is True
    assert secret not in response.text
    assert client.post("/api/v1/auth/bootstrap", json=body).status_code == 409
