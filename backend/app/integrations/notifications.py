"""Notification delivery adapters (In-App, SMTP Email, Twilio SMS/WhatsApp, Sahatna).

Truthful delivery invariant:
- Never mark an external notification as `delivered` or `sent` unless the provider
  actually accepted/confirmed it.
- Unconfigured external channels record status `not_configured` with an explanation.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import smtplib
import uuid
from datetime import timedelta
from email.message import EmailMessage

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.errors import NotFound, ValidationFailed
from app.core.security import decrypt_str, mask
from app.models.base import utcnow
from app.models.care import Notification, Referral, ReferralEvent
from app.models.clinical import Patient
from app.models.enums import NotificationChannel, NotificationStatus
from app.models.identity import User
from app.models.ops import IntegrationConfig


def send_email_direct(
    *,
    to_address: str,
    subject: str,
    body: str,
    html_body: str | None = None,
    smtp_cfg: dict | None = None,
    settings: Settings | None = None,
) -> dict:
    s = settings or get_settings()
    host = (smtp_cfg or {}).get("host") or s.smtp_host
    port = int((smtp_cfg or {}).get("port") or s.smtp_port)
    username = (smtp_cfg or {}).get("username") or s.smtp_username
    password = (smtp_cfg or {}).get("password") or s.smtp_password
    from_addr = (smtp_cfg or {}).get("from_address") or s.smtp_from
    use_tls = bool(
        (smtp_cfg or {}).get("use_tls")
        if smtp_cfg and "use_tls" in smtp_cfg
        else s.smtp_use_tls
    )

    if not host or not from_addr:
        return {
            "status": NotificationStatus.NOT_CONFIGURED.value,
            "provider": "smtp",
            "error": "SMTP host/from not configured",
        }

    msg = EmailMessage()
    msg["From"] = from_addr
    msg["To"] = to_address
    msg["Subject"] = " ".join(subject.split())[:200]
    msg.set_content(body)
    if html_body:
        msg.add_alternative(html_body, subtype="html")
    try:
        smtp_class = smtplib.SMTP_SSL if port == 465 else smtplib.SMTP
        with smtp_class(host, port, timeout=15) as server:
            if use_tls and port != 465:
                server.starttls()
            if username:
                server.login(username, password)
            server.send_message(msg)
        # SMTP relays accept for forwarding; mark `sent`, not `delivered` until DSN/webhook.
        return {
            "status": NotificationStatus.SENT.value,
            "provider": "smtp",
            "provider_message_id": None,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "status": NotificationStatus.FAILED.value,
            "provider": "smtp",
            "error": f"SMTP submission failed ({type(exc).__name__}). Check server connection and sender settings.",
        }


def test_smtp_connection(smtp_cfg: dict | None = None) -> dict:
    s = get_settings()
    cfg = smtp_cfg or {}
    host = cfg.get("host") or s.smtp_host
    port = int(cfg.get("port") or s.smtp_port)
    if not host or not (cfg.get("from_address") or s.smtp_from):
        return {
            "status": "not_configured",
            "connected": False,
            "message": "SMTP host and sender are required",
        }
    try:
        cls = smtplib.SMTP_SSL if port == 465 else smtplib.SMTP
        with cls(host, port, timeout=10) as server:
            server.ehlo()
            if port != 465 and cfg.get("use_tls", s.smtp_use_tls):
                server.starttls()
                server.ehlo()
            username = cfg.get("username") or s.smtp_username
            if username:
                server.login(username, cfg.get("password") or s.smtp_password)
        return {
            "status": "connected",
            "connected": True,
            "message": "SMTP connection verified. Inbox delivery still requires a controlled send.",
        }
    except Exception:
        return {
            "status": "failed",
            "connected": False,
            "message": "SMTP connection or authentication failed. Check host, port, TLS and credentials.",
        }


def send_twilio_direct(
    *,
    to_number: str,
    body: str,
    whatsapp: bool = False,
    twilio_cfg: dict | None = None,
    settings: Settings | None = None,
) -> dict:
    s = settings or get_settings()
    sid = (twilio_cfg or {}).get("account_sid") or s.twilio_account_sid
    token = (twilio_cfg or {}).get("auth_token") or s.twilio_auth_token
    from_num = (
        ((twilio_cfg or {}).get("whatsapp_from") or s.twilio_whatsapp_from)
        if whatsapp
        else ((twilio_cfg or {}).get("from_number") or s.twilio_from_number)
    )
    if not sid or not token or not from_num:
        return {
            "status": NotificationStatus.NOT_CONFIGURED.value,
            "provider": "twilio",
            "error": "Twilio credentials or sender number not configured",
        }

    to_fmt = (
        f"whatsapp:{to_number}"
        if whatsapp and not to_number.startswith("whatsapp:")
        else to_number
    )
    from_fmt = (
        f"whatsapp:{from_num}"
        if whatsapp and not from_num.startswith("whatsapp:")
        else from_num
    )
    try:
        r = httpx.post(
            f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json",
            auth=(sid, token),
            data={"To": to_fmt, "From": from_fmt, "Body": body},
            timeout=15,
        )
        r.raise_for_status()
        data = r.json()
        return {
            "status": NotificationStatus.SENT.value,
            "provider": "twilio",
            "provider_message_id": data.get("sid"),
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "status": NotificationStatus.FAILED.value,
            "provider": "twilio",
            "error": f"{type(exc).__name__}: {exc}",
        }


def dispatch_notification(
    db: Session,
    *,
    organization_id: uuid.UUID,
    channel: NotificationChannel | str,
    category: str,
    subject: str,
    body: str,
    recipient_user: User | None = None,
    recipient_patient: Patient | None = None,
    referral_id: uuid.UUID | None = None,
    emergency_event_id: uuid.UUID | None = None,
    idempotency_key: str | None = None,
    org_integrations: dict[str, dict] | None = None,
) -> Notification:
    """Persist and dispatch a notification truthfully according to channel & config."""
    if idempotency_key:
        from sqlalchemy import select

        existing = db.scalar(
            select(Notification).where(Notification.idempotency_key == idempotency_key)
        )
        if existing is not None:
            return existing

    ch = NotificationChannel(channel)
    now = utcnow()
    addr: str | None = None
    masked_addr: str | None = None

    if ch == NotificationChannel.EMAIL:
        if recipient_user:
            addr = recipient_user.email
        elif recipient_patient and recipient_patient.email_encrypted:
            addr = decrypt_str(recipient_patient.email_encrypted)
        masked_addr = mask(addr, 3) if addr else None
    elif ch in {NotificationChannel.SMS, NotificationChannel.WHATSAPP}:
        if recipient_user and recipient_user.phone_encrypted:
            addr = decrypt_str(recipient_user.phone_encrypted)
        elif recipient_patient and recipient_patient.phone_encrypted:
            addr = decrypt_str(recipient_patient.phone_encrypted)
        masked_addr = mask(addr, 4) if addr else None

    notif = Notification(
        organization_id=organization_id,
        channel=ch.value,
        status=NotificationStatus.QUEUED.value,
        category=category,
        recipient_user_id=recipient_user.id if recipient_user else None,
        recipient_patient_id=recipient_patient.id if recipient_patient else None,
        recipient_address_masked=masked_addr,
        subject=subject,
        body=body,
        referral_id=referral_id,
        emergency_event_id=emergency_event_id,
        attempts=1,
        idempotency_key=idempotency_key,
    )
    db.add(notif)
    db.flush()

    if ch == NotificationChannel.IN_APP:
        # Persisting into the authenticated in-app inbox IS delivery to the platform inbox.
        notif.status = NotificationStatus.DELIVERED.value
        notif.provider = "recova_inbox"
        notif.sent_at = now
        notif.delivered_at = now
    elif ch == NotificationChannel.EMAIL:
        if not addr:
            notif.status = NotificationStatus.FAILED.value
            notif.last_error = "No email address on file for recipient"
        else:
            from app.services.messaging import queue_email

            delivery = queue_email(
                db,
                to=addr,
                subject=subject,
                body=body,
                category="notification",
                organization_id=organization_id,
                user_id=recipient_user.id if recipient_user else None,
                notification_id=notif.id,
                key=f"notification:{notif.id}",
            )
            notif.status = delivery.status
            notif.provider = "smtp_outbox"
            notif.last_error = delivery.last_error
    elif ch in {NotificationChannel.SMS, NotificationChannel.WHATSAPP, NotificationChannel.SAHATNA}:
        has_target = _send_external_notification(db, notif, org_integrations=org_integrations)
        if has_target and notif.status == NotificationStatus.FAILED.value and notif.attempts < 3:
            _enqueue_notification_retry(db, notif)

    return notif


def _load_org_integration(db: Session, organization_id: uuid.UUID, name: str) -> dict | None:
    row = db.scalar(
        select(IntegrationConfig).where(
            IntegrationConfig.organization_id == organization_id,
            IntegrationConfig.integration == name,
        )
    )
    if row is None or not row.enabled:
        return None
    cfg = dict(row.settings or {})
    if row.secrets_encrypted:
        raw = decrypt_str(row.secrets_encrypted)
        if raw:
            cfg.update(json.loads(raw))
    return cfg or None


def _external_consent_active(db: Session, patient_id: uuid.UUID) -> tuple[bool, str | None]:
    from app.agents.gate1_consent import evaluate_consents

    patient = db.get(Patient, patient_id)
    if patient is None or not patient.is_active:
        return False, "Patient record is inactive"
    scopes, _ = evaluate_consents(db, patient, utcnow())
    if not {"data_processing", "optional_channels"}.issubset(scopes):
        return False, "Patient external-channel consent is no longer active"
    return True, None


def _enqueue_notification_retry(db: Session, notif: Notification) -> None:
    from app.tasks.queue import enqueue

    run_after = utcnow() + timedelta(seconds=30 * 4 ** max(0, notif.attempts - 1))
    enqueue(
        db,
        "notification.deliver",
        {"notification_id": str(notif.id)},
        organization_id=notif.organization_id,
        idempotency_key=f"notification:{notif.id}:{notif.attempts}",
        run_after=run_after,
        max_attempts=1,
    )


def _advance_referral_on_notification_sent(db: Session, notif: Notification) -> None:
    if not notif.sent_at or not notif.referral_id:
        return
    referral = db.get(Referral, notif.referral_id)
    if referral and referral.status == "approved":
        referral.status = "patient_notified"
        db.add(
            ReferralEvent(
                referral_id=referral.id,
                event_type="notification",
                from_status="approved",
                to_status="patient_notified",
                actor_label=f"system:{notif.provider or notif.channel}_outbox",
                details={"notification_id": str(notif.id), "delivery_status": notif.status},
            )
        )


def _resolve_phone_target(db: Session, notif: Notification) -> str | None:
    user = db.get(User, notif.recipient_user_id) if notif.recipient_user_id else None
    if user and user.phone_encrypted:
        return decrypt_str(user.phone_encrypted)
    patient = db.get(Patient, notif.recipient_patient_id) if notif.recipient_patient_id else None
    if patient and patient.phone_encrypted:
        return decrypt_str(patient.phone_encrypted)
    return None


def _send_external_notification(
    db: Session,
    notif: Notification,
    *,
    org_integrations: dict[str, dict] | None = None,
) -> bool:
    """Attempt SMS/WhatsApp/Sahatna dispatch; returns True if target address/patient exists."""
    now = utcnow()
    ch = NotificationChannel(notif.channel)
    if ch in {NotificationChannel.SMS, NotificationChannel.WHATSAPP}:
        addr = _resolve_phone_target(db, notif)
        if not addr:
            notif.status = NotificationStatus.FAILED.value
            notif.last_error = "No phone number on file for recipient"
            return False
        twilio_cfg = (org_integrations or {}).get("twilio") or _load_org_integration(db, notif.organization_id, "twilio")
        res = send_twilio_direct(
            to_number=addr,
            body=f"{notif.subject}: {notif.body}",
            whatsapp=(ch == NotificationChannel.WHATSAPP),
            twilio_cfg=twilio_cfg,
        )
        notif.status = res["status"]
        notif.provider = res.get("provider")
        notif.provider_message_id = res.get("provider_message_id")
        notif.last_error = res.get("error")
        if res["status"] == NotificationStatus.SENT.value:
            notif.sent_at = now
        return True

    if ch == NotificationChannel.SAHATNA:
        if notif.recipient_patient_id is None:
            notif.status = NotificationStatus.FAILED.value
            notif.last_error = "Patient identifier required for Sahatna nudge."
            return False
        sahatna_cfg = (org_integrations or {}).get("sahatna") or _load_org_integration(db, notif.organization_id, "sahatna")
        res = send_sahatna_nudge(
            patient_id=notif.recipient_patient_id,
            subject=notif.subject,
            body=notif.body,
            sahatna_cfg=sahatna_cfg,
        )
        notif.status = res["status"]
        notif.provider = "sahatna"
        notif.provider_message_id = res.get("provider_message_id")
        notif.last_error = res.get("error")
        if res["status"] == NotificationStatus.SENT.value:
            notif.sent_at = now
        return True
    return False


def deliver_notification_retry(db: Session, notification_id: uuid.UUID) -> dict:
    """Durable background retry handler for failed SMS/WhatsApp/Sahatna notifications."""
    notif = db.scalar(select(Notification).where(Notification.id == notification_id).with_for_update())
    if not notif or notif.status in {NotificationStatus.SENT.value, NotificationStatus.DELIVERED.value}:
        return {"status": "skipped"}
    if notif.channel not in {NotificationChannel.SMS.value, NotificationChannel.WHATSAPP.value, NotificationChannel.SAHATNA.value}:
        return {"status": "skipped"}
    if notif.recipient_patient_id:
        ok, reason = _external_consent_active(db, notif.recipient_patient_id)
        if not ok:
            notif.status = NotificationStatus.FAILED.value
            notif.last_error = reason
            return {"status": "cancelled", "reason": reason}

    notif.attempts += 1
    has_target = _send_external_notification(db, notif)
    if notif.status == NotificationStatus.SENT.value:
        _advance_referral_on_notification_sent(db, notif)
    elif has_target and notif.status == NotificationStatus.FAILED.value and notif.attempts < 3:
        _enqueue_notification_retry(db, notif)
    return {"status": notif.status, "attempts": notif.attempts}


def retry_notification_manual(db: Session, org_id: uuid.UUID, notification_id: uuid.UUID) -> Notification:
    """Operator-triggered retry for failed/unconfigured notifications within org_id."""
    notif = db.scalar(
        select(Notification).where(Notification.id == notification_id, Notification.organization_id == org_id)
    )
    if notif is None:
        raise NotFound("Notification not found")
    if notif.channel == NotificationChannel.IN_APP.value:
        raise ValidationFailed("In-app notifications do not require external retry")
    if notif.status == NotificationStatus.DELIVERED.value:
        raise ValidationFailed("Notification has already been delivered")

    if notif.recipient_patient_id:
        ok, reason = _external_consent_active(db, notif.recipient_patient_id)
        if not ok:
            notif.status = NotificationStatus.FAILED.value
            notif.last_error = reason
            raise ValidationFailed(reason or "Patient external-channel consent is not active")

    if notif.channel == NotificationChannel.EMAIL.value:
        from app.models.messaging import EmailDelivery
        from app.services.messaging import deliver_email

        email_row = db.scalar(select(EmailDelivery).where(EmailDelivery.notification_id == notif.id))
        if email_row is None:
            raise ValidationFailed("Email outbox record missing for this notification")
        if not get_settings().smtp_configured:
            raise ValidationFailed("SMTP sender is still not configured")
        email_row.status = "queued"
        email_row.attempts = 0
        email_row.last_error = None
        deliver_email(db, email_row.id)
        db.refresh(notif)
        return notif

    notif.attempts += 1
    _send_external_notification(db, notif)
    if notif.status == NotificationStatus.SENT.value:
        _advance_referral_on_notification_sent(db, notif)
    return notif


def verify_twilio_signature(url: str, params: dict[str, str], signature: str, auth_token: str) -> bool:
    """Verify X-Twilio-Signature (HMAC-SHA1 base64 over URL + sorted form params)."""
    if not signature or not auth_token:
        return False
    payload = url + "".join(f"{k}{params[k]}" for k in sorted(params))
    digest = hmac.new(auth_token.encode("utf-8"), payload.encode("utf-8"), hashlib.sha1).digest()
    expected = base64.b64encode(digest).decode("ascii")
    return hmac.compare_digest(expected, signature.strip())


def apply_provider_receipt(
    db: Session,
    *,
    notif: Notification,
    provider_status: str,
    error_detail: str | None = None,
) -> Notification:
    """Apply an external provider delivery-receipt state transition truthfully."""
    norm = provider_status.strip().lower()
    now = utcnow()
    if norm in {"delivered", "read"}:
        notif.status = NotificationStatus.DELIVERED.value
        notif.delivered_at = notif.delivered_at or now
        if norm == "read":
            notif.read_at = notif.read_at or now
        notif.last_error = None
        _advance_referral_on_notification_sent(db, notif)
    elif norm in {"failed", "undelivered", "canceled", "cancelled", "rejected"}:
        notif.status = NotificationStatus.FAILED.value
        notif.last_error = (error_detail or f"Provider reported delivery status: {norm}")[:500]
    elif norm in {"sent", "queued", "sending", "accepted"}:
        if notif.status != NotificationStatus.DELIVERED.value:
            notif.status = NotificationStatus.SENT.value
            notif.sent_at = notif.sent_at or now
    return notif
