"""Notification delivery adapters (In-App, SMTP Email, Twilio SMS/WhatsApp, Sahatna).

Truthful delivery invariant:
- Never mark an external notification as `delivered` or `sent` unless the provider
  actually accepted/confirmed it.
- Unconfigured external channels record status `not_configured` with an explanation.
"""

from __future__ import annotations

import smtplib
import uuid
from email.message import EmailMessage

import httpx
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.security import decrypt_str, mask
from app.models.base import utcnow
from app.models.care import Notification
from app.models.clinical import Patient
from app.models.enums import NotificationChannel, NotificationStatus
from app.models.identity import User


def send_email_direct(
    *,
    to_address: str,
    subject: str,
    body: str,
    smtp_cfg: dict | None = None,
    settings: Settings | None = None,
) -> dict:
    s = settings or get_settings()
    host = (smtp_cfg or {}).get("host") or s.smtp_host
    port = int((smtp_cfg or {}).get("port") or s.smtp_port)
    username = (smtp_cfg or {}).get("username") or s.smtp_username
    password = (smtp_cfg or {}).get("password") or s.smtp_password
    from_addr = (smtp_cfg or {}).get("from_address") or s.smtp_from
    use_tls = bool((smtp_cfg or {}).get("use_tls") if smtp_cfg and "use_tls" in smtp_cfg else s.smtp_use_tls)

    if not host or not from_addr:
        return {"status": NotificationStatus.NOT_CONFIGURED.value, "provider": "smtp", "error": "SMTP host/from not configured"}

    msg = EmailMessage()
    msg["From"] = from_addr
    msg["To"] = to_address
    msg["Subject"] = subject
    msg.set_content(body)
    try:
        with smtplib.SMTP(host, port, timeout=15) as server:
            if use_tls:
                server.starttls()
            if username:
                server.login(username, password)
            server.send_message(msg)
        # SMTP relays accept for forwarding; mark `sent`, not `delivered` until DSN/webhook.
        return {"status": NotificationStatus.SENT.value, "provider": "smtp", "provider_message_id": None}
    except Exception as exc:  # noqa: BLE001
        return {"status": NotificationStatus.FAILED.value, "provider": "smtp", "error": f"{type(exc).__name__}: {exc}"}


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
        return {"status": NotificationStatus.NOT_CONFIGURED.value, "provider": "twilio", "error": "Twilio credentials or sender number not configured"}

    to_fmt = f"whatsapp:{to_number}" if whatsapp and not to_number.startswith("whatsapp:") else to_number
    from_fmt = f"whatsapp:{from_num}" if whatsapp and not from_num.startswith("whatsapp:") else from_num
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
        return {"status": NotificationStatus.FAILED.value, "provider": "twilio", "error": f"{type(exc).__name__}: {exc}"}


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

        existing = db.scalar(select(Notification).where(Notification.idempotency_key == idempotency_key))
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
            res = send_email_direct(
                to_address=addr,
                subject=subject,
                body=body,
                smtp_cfg=(org_integrations or {}).get("smtp"),
            )
            notif.status = res["status"]
            notif.provider = res.get("provider")
            notif.provider_message_id = res.get("provider_message_id")
            notif.last_error = res.get("error")
            if res["status"] == NotificationStatus.SENT.value:
                notif.sent_at = now
    elif ch in {NotificationChannel.SMS, NotificationChannel.WHATSAPP}:
        if not addr:
            notif.status = NotificationStatus.FAILED.value
            notif.last_error = "No phone number on file for recipient"
        else:
            res = send_twilio_direct(
                to_number=addr,
                body=f"{subject}: {body}",
                whatsapp=(ch == NotificationChannel.WHATSAPP),
                twilio_cfg=(org_integrations or {}).get("twilio"),
            )
            notif.status = res["status"]
            notif.provider = res.get("provider")
            notif.provider_message_id = res.get("provider_message_id")
            notif.last_error = res.get("error")
            if res["status"] == NotificationStatus.SENT.value:
                notif.sent_at = now
    elif ch == NotificationChannel.SAHATNA:
        from app.integrations.sahatna import send_sahatna_nudge

        res = send_sahatna_nudge(
            patient_id=recipient_patient.id if recipient_patient else None,
            subject=subject,
            body=body,
            sahatna_cfg=(org_integrations or {}).get("sahatna"),
        )
        notif.status = res["status"]
        notif.provider = "sahatna"
        notif.provider_message_id = res.get("provider_message_id")
        notif.last_error = res.get("error")
        if res["status"] == NotificationStatus.SENT.value:
            notif.sent_at = now

    return notif
