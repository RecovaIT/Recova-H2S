"""Channel-wide durable retries & provider delivery-receipt verification (F21)."""

from __future__ import annotations

import base64
import hashlib
import hmac
import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import get_settings
from app.core.db import SessionLocal
from app.core.security import encrypt_str
from app.integrations import notifications as notif_mod
from app.models.base import utcnow
from app.models.care import Notification, Referral
from app.models.clinical import Consent, Patient
from app.models.enums import ConsentScope, ConsentStatus, NotificationChannel, NotificationStatus
from app.models.ops import Job
from tests.conftest import auth_headers, bootstrap_org_and_admin


def _grant_consent(db, org_id: uuid.UUID, patient_id: uuid.UUID, scopes: list[str]) -> None:
    now = utcnow()
    for scope in scopes:
        db.add(
            Consent(
                organization_id=org_id,
                patient_id=patient_id,
                scope=scope,
                status=ConsentStatus.GRANTED.value,
                method="electronic",
                effective_at=now,
            )
        )


def test_sms_durable_retry_consent_guard_and_twilio_receipt_webhook(client: TestClient, monkeypatch):
    sess = bootstrap_org_and_admin(client)
    org_id = uuid.UUID(sess["active_organization"]["id"])
    headers = auth_headers(client)

    with SessionLocal() as db:
        patient = Patient(
            organization_id=org_id,
            mrn="PAT-RETRY-001",
            given_name="Samira",
            family_name="Al-Hashimi",
            phone_encrypted=encrypt_str("+971501234567"),
            is_active=True,
        )
        db.add(patient)
        db.flush()
        _grant_consent(
            db,
            org_id,
            patient.id,
            [ConsentScope.DATA_PROCESSING.value, ConsentScope.OPTIONAL_CHANNELS.value],
        )
        referral = Referral(
            organization_id=org_id,
            patient_id=patient.id,
            track="loop",
            pathway="primary_care",
            status="approved",
            priority="routine",
            reason="Follow-up visit",
        )
        db.add(referral)
        db.flush()
        patient_id = patient.id
        referral_id = referral.id

        # 1st attempt fails -> durable job scheduled
        monkeypatch.setattr(
            notif_mod,
            "send_twilio_direct",
            lambda **_kw: {"status": "failed", "provider": "twilio", "error": "HTTP 503 upstream"},
        )
        notif = notif_mod.dispatch_notification(
            db,
            organization_id=org_id,
            channel=NotificationChannel.SMS,
            category="referral_notification",
            subject="Appointment update",
            body="Your care team has approved your follow-up.",
            recipient_patient=patient,
            referral_id=referral_id,
        )
        notif_id = notif.id
        db.commit()

        assert notif.status == NotificationStatus.FAILED.value
        job = db.scalar(
            select(Job).where(Job.job_type == "notification.deliver", Job.organization_id == org_id)
        )
        assert job is not None
        assert job.payload["notification_id"] == str(notif_id)

        # Retry succeeds -> notification becomes sent and referral advances to patient_notified
        monkeypatch.setattr(
            notif_mod,
            "send_twilio_direct",
            lambda **_kw: {
                "status": "sent",
                "provider": "twilio",
                "provider_message_id": "SM-RECEIPT-123",
            },
        )
        res = notif_mod.deliver_notification_retry(db, notif_id)
        db.commit()
        assert res["status"] == "sent"
        assert res["attempts"] == 2
        assert db.get(Referral, referral_id).status == "patient_notified"

    # Webhook signature verification + delivery receipt
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "twilio-test-secret-token")
    get_settings.cache_clear()
    try:
        bad = client.post(
            "/api/v1/notifications/webhooks/twilio-status",
            data={"MessageSid": "SM-RECEIPT-123", "MessageStatus": "delivered"},
            headers={"X-Twilio-Signature": "invalid-signature"},
        )
        assert bad.status_code == 403

        webhook_url = str(client.base_url).rstrip("/") + "/api/v1/notifications/webhooks/twilio-status"
        params = {"MessageSid": "SM-RECEIPT-123", "MessageStatus": "delivered"}
        payload = webhook_url + "".join(f"{k}{params[k]}" for k in sorted(params))
        sig = base64.b64encode(
            hmac.new(b"twilio-test-secret-token", payload.encode("utf-8"), hashlib.sha1).digest()
        ).decode("ascii")

        good = client.post(
            "/api/v1/notifications/webhooks/twilio-status",
            data=params,
            headers={"X-Twilio-Signature": sig},
        )
        assert good.status_code == 200, good.text
        assert good.json()["status"] == "delivered"

        with SessionLocal() as db:
            updated = db.get(Notification, notif_id)
            assert updated is not None
            assert updated.status == NotificationStatus.DELIVERED.value
            assert updated.delivered_at is not None

        # Manual retry on already-delivered notification returns 422
        dup_retry = client.post(f"/api/v1/notifications/{notif_id}/retry", headers=headers)
        assert dup_retry.status_code == 422

        # Consent revocation cancels pending SMS retry cleanly
        with SessionLocal() as db:
            db.add(
                Consent(
                    organization_id=org_id,
                    patient_id=patient_id,
                    scope=ConsentScope.OPTIONAL_CHANNELS.value,
                    status=ConsentStatus.REVOKED.value,
                    method="electronic",
                    effective_at=utcnow(),
                    revoked_at=utcnow(),
                )
            )
            pending = Notification(
                organization_id=org_id,
                channel=NotificationChannel.WHATSAPP.value,
                status=NotificationStatus.FAILED.value,
                category="reminder",
                recipient_patient_id=patient_id,
                subject="Reminder",
                body="Upcoming check",
                attempts=1,
            )
            db.add(pending)
            db.flush()
            pending_id = pending.id
            db.commit()

            cancelled = notif_mod.deliver_notification_retry(db, pending_id)
            assert cancelled["status"] == "cancelled"
    finally:
        monkeypatch.delenv("TWILIO_AUTH_TOKEN", raising=False)
        get_settings.cache_clear()


def test_sahatna_receipt_webhook_and_malaffi_retry_queue(client: TestClient, monkeypatch):
    sess = bootstrap_org_and_admin(client)
    org_id = uuid.UUID(sess["active_organization"]["id"])
    headers = auth_headers(client)

    with SessionLocal() as db:
        patient = Patient(
            organization_id=org_id,
            mrn="PAT-SAH-001",
            given_name="Khalid",
            family_name="Al-Mansoori",
            is_active=True,
        )
        db.add(patient)
        db.flush()
        _grant_consent(
            db,
            org_id,
            patient.id,
            [
                ConsentScope.DATA_PROCESSING.value,
                ConsentScope.OPTIONAL_CHANNELS.value,
                ConsentScope.HIE_SHARING.value,
            ],
        )
        notif = Notification(
            organization_id=org_id,
            channel=NotificationChannel.SAHATNA.value,
            status=NotificationStatus.SENT.value,
            category="appointment_reminder",
            recipient_patient_id=patient.id,
            provider="sahatna",
            provider_message_id="SAH-MSG-900",
            subject="Reminder",
            body="Your appointment is tomorrow.",
            attempts=1,
        )
        db.add(notif)
        db.commit()
        patient_id = patient.id
        notif_id = notif.id

    monkeypatch.setenv("SAHATNA_API_KEY", "sahatna-secret-key")
    get_settings.cache_clear()
    try:
        bad = client.post(
            "/api/v1/notifications/webhooks/sahatna-status",
            json={"message_id": "SAH-MSG-900", "status": "delivered"},
            headers={"Authorization": "Bearer wrong-key"},
        )
        assert bad.status_code == 403

        ok = client.post(
            "/api/v1/notifications/webhooks/sahatna-status",
            json={"message_id": "SAH-MSG-900", "status": "delivered"},
            headers={"Authorization": "Bearer sahatna-secret-key"},
        )
        assert ok.status_code == 200, ok.text
        assert ok.json()["status"] == "delivered"

        with SessionLocal() as db:
            row = db.get(Notification, notif_id)
            assert row is not None and row.delivered_at is not None
    finally:
        monkeypatch.delenv("SAHATNA_API_KEY", raising=False)
        get_settings.cache_clear()

    # Simulated Malaffi push error enqueues durable retry job
    from app.api.v1 import ops as ops_mod

    monkeypatch.setattr(
        ops_mod,
        "push_fhir_bundle",
        lambda _bundle, _cfg=None: {"status": "error", "submitted": False, "message": "Timeout"},
    )
    resp = client.post(f"/api/v1/fhir/patients/{patient_id}/push-malaffi", headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "error"
    assert body["queued_retry"] is True

    with SessionLocal() as db:
        hie_job = db.scalar(select(Job).where(Job.job_type == "hie.push_malaffi", Job.organization_id == org_id))
        assert hie_job is not None
        assert hie_job.payload["patient_id"] == str(patient_id)
