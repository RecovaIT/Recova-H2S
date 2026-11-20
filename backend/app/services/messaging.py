"""Account email patterns adapted from recova-api: trusted links and escaped templates.

The challenge service uses its own PostgreSQL outbox; it never imports production
configuration or credentials. SMTP acceptance is recorded as sent, never delivered.
"""

import json
import html
import uuid
from datetime import timedelta
from urllib.parse import urlencode, urlsplit
from sqlalchemy import select
from app.core.config import get_settings
from app.core.security import encrypt_str, decrypt_str, mask
from app.models.messaging import EmailDelivery
from app.models.base import utcnow
from app.models.care import Notification


def public_link(path, **params):
    origin = get_settings().frontend_base_url.rstrip("/")
    parsed = urlsplit(origin)
    if (
        parsed.scheme not in ("http", "https")
        or not parsed.netloc
        or parsed.username
        or parsed.password
    ):
        raise ValueError(
            "FRONTEND_BASE_URL must be a trusted HTTP(S) application origin"
        )
    if not path.startswith("/") or path.startswith("//"):
        raise ValueError("Only application-relative links are supported")
    return origin + path + ("?" + urlencode(params) if params else "")


def queue_email(
    db,
    *,
    to,
    subject,
    body,
    category,
    organization_id=None,
    user_id=None,
    key=None,
    expires_at=None,
    notification_id=None,
):
    key = key or f"{category}:{uuid.uuid4()}"
    previous = db.scalar(
        select(EmailDelivery).where(EmailDelivery.idempotency_key == key)
    )
    if previous:
        return previous
    subject = " ".join(subject.split())[:200]
    # Escaping follows recova-api/app/core/email_safety.py. No credentials in templates.
    markup = (
        '<html><body style="font-family:Arial,sans-serif;color:#003e5e"><h2>Recova</h2><p>'
        + html.escape(body).replace("\n", "<br>")
        + "</p><hr><p>If you did not request this, contact your facility.</p></body></html>"
    )
    row = EmailDelivery(
        organization_id=organization_id,
        user_id=user_id,
        notification_id=notification_id,
        category=category,
        subject=subject,
        recipient_encrypted=encrypt_str(to),
        payload_encrypted=encrypt_str(json.dumps({"body": body, "html": markup})),
        status="queued" if get_settings().smtp_configured else "not_configured",
        last_error=(
            None
            if get_settings().smtp_configured
            else "Account email sender is not configured"
        ),
        idempotency_key=key,
        expires_at=expires_at,
    )
    db.add(row)
    db.flush()
    if row.status == "queued":
        from app.tasks.queue import enqueue

        enqueue(
            db,
            "email.deliver",
            {"email_id": str(row.id)},
            organization_id=organization_id,
            idempotency_key=f"email:{row.id}:0",
            max_attempts=1,
        )
    return row


def cancel_pending(db, user_id, categories):
    for row in db.scalars(
        select(EmailDelivery).where(
            EmailDelivery.user_id == user_id,
            EmailDelivery.category.in_(categories),
            EmailDelivery.status.in_(["queued", "failed", "not_configured"]),
        )
    ):
        row.status = "cancelled"
        row.next_attempt_at = None


def deliver_email(db, email_id):
    row = db.scalar(
        select(EmailDelivery).where(EmailDelivery.id == email_id).with_for_update()
    )
    if not row or row.status in ("sent", "cancelled", "expired"):
        return {"status": "skipped"}
    now = utcnow()
    if row.expires_at and row.expires_at <= now:
        row.status = "expired"
        row.next_attempt_at = None
        return {"status": "expired"}
    if row.category == "portal_invitation":
        from app.models.identity import PortalInvitation

        invitation_id = uuid.UUID(row.idempotency_key.split(":", 1)[1])
        inv = db.get(PortalInvitation, invitation_id)
        if not inv or inv.accepted_at or inv.revoked_at:
            row.status = "cancelled"
            row.next_attempt_at = None
            return {"status": "cancelled"}
    from app.integrations.notifications import send_email_direct

    raw = decrypt_str(row.payload_encrypted)
    address = decrypt_str(row.recipient_encrypted)
    if not raw or not address:
        row.status = "failed"
        row.last_error = "Cannot decrypt the message. Check encryption key continuity."
        return {"status": "failed"}
    if row.notification_id:
        notice = db.get(Notification, row.notification_id)
        if notice and notice.recipient_patient_id:
            from app.models.clinical import Patient
            from app.agents.gate1_consent import evaluate_consents

            patient = db.get(Patient, notice.recipient_patient_id)
            scopes, _ = evaluate_consents(db, patient, now)
            if not patient.is_active or not {
                "data_processing",
                "optional_channels",
            }.issubset(scopes):
                row.status = "cancelled"
                row.last_error = "Patient external-channel consent is no longer active"
                notice.status = "failed"
                notice.last_error = row.last_error
                return {"status": "cancelled"}
    payload = json.loads(raw)
    result = send_email_direct(
        to_address=decrypt_str(row.recipient_encrypted) or "",
        subject=row.subject,
        body=payload.get("body", ""),
        html_body=payload.get("html"),
    )
    row.attempts += 1
    row.status = result["status"]
    row.last_error = result.get("error")
    row.next_attempt_at = None
    if row.status == "sent":
        row.sent_at = now
    if row.notification_id:
        notification = db.get(Notification, row.notification_id)
        if notification:
            notification.status = row.status
            notification.last_error = row.last_error
            if row.sent_at:
                notification.sent_at = row.sent_at
            if row.sent_at and notification.referral_id:
                from app.models.care import Referral, ReferralEvent

                referral = db.get(Referral, notification.referral_id)
                if referral and referral.status == "approved":
                    referral.status = "patient_notified"
                    db.add(
                        ReferralEvent(
                            referral_id=referral.id,
                            event_type="notification",
                            from_status="approved",
                            to_status="patient_notified",
                            actor_label="system:email_outbox",
                            details={
                                "notification_id": str(notification.id),
                                "delivery_status": "sent",
                            },
                        )
                    )
    if row.status == "failed" and row.attempts < 3:
        from app.tasks.queue import enqueue

        row.next_attempt_at = now + timedelta(seconds=30 * 4 ** (row.attempts - 1))
        enqueue(
            db,
            "email.deliver",
            {"email_id": str(row.id)},
            organization_id=row.organization_id,
            idempotency_key=f"email:{row.id}:{row.attempts}",
            run_after=row.next_attempt_at,
            max_attempts=1,
        )
    return {"status": row.status, "attempts": row.attempts}


def delivery_view(row):
    return {
        "id": str(row.id),
        "category": row.category,
        "subject": row.subject,
        "recipient": mask(decrypt_str(row.recipient_encrypted), 3),
        "status": row.status,
        "attempts": row.attempts,
        "last_error": row.last_error,
        "sent_at": row.sent_at,
        "expires_at": row.expires_at,
        "next_attempt_at": row.next_attempt_at,
        "created_at": row.created_at,
    }


def account_link(db, user, purpose, *, organization_id=None):
    from app.core.security import new_token, hash_token
    from app.models.identity import PasswordResetToken

    now = utcnow()
    for old in db.scalars(
        select(PasswordResetToken).where(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.purpose == purpose,
            PasswordResetToken.used_at.is_(None),
        )
    ):
        old.used_at = now
    cancel_pending(db, user.id, [purpose])
    token = new_token(32)
    ttl = (
        timedelta(minutes=get_settings().password_reset_ttl_minutes)
        if purpose == "reset"
        else timedelta(hours=48)
    )
    expires = now + ttl
    db.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=hash_token(token),
            purpose=purpose,
            expires_at=expires,
        )
    )
    path = "/verify-email" if purpose == "verify_email" else "/reset-password"
    title = {
        "reset": "Reset your Recova password",
        "activation": "Set up your Recova account",
        "verify_email": "Welcome to Recova - verify your email",
    }[purpose]
    row = queue_email(
        db,
        to=user.email,
        subject=title,
        body=f"Hello {user.full_name},\nUse this one-time link to continue:\n{public_link(path,token=token)}\nThis link expires at {expires.isoformat()}. Your password is never included in email.",
        category=purpose,
        organization_id=organization_id,
        user_id=user.id,
        expires_at=expires,
    )
    return row
