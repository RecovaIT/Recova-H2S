"""Recipient-bound setup and operational mail status. No public delivery diagnostics."""

import uuid
from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.api.deps import AuthContext, requires, get_auth_context, client_ip
from app.api.v1.auth import _set_session_cookies
from app.core.db import get_db
from app.core.errors import Conflict, NotFound, Unauthorized, ValidationFailed
from app.core.permissions import P
from app.core.security import (
    hash_token,
    hash_password,
    validate_password_strength,
    mask,
)
from app.core.rate_limit import limiter
from app.models.base import utcnow
from app.models.identity import (
    User,
    Organization,
    Membership,
    PortalInvitation,
    ParticipantAccountLink,
    PasswordResetToken,
)
from app.models.clinical import Patient
from app.models.messaging import EmailDelivery
from app.services import auth as auth_svc
from app.services.messaging import delivery_view, account_link, queue_email

router = APIRouter(tags=["account-setup"])


def invitation(db, token, lock=False):
    stmt = select(PortalInvitation).where(
        PortalInvitation.token_hash == hash_token(token)
    )
    inv = db.scalar(stmt.with_for_update() if lock else stmt)
    if inv is None or inv.revoked_at or inv.expires_at <= utcnow():
        raise NotFound(
            "This invitation is invalid, expired or replaced. Ask your facility for a new invitation."
        )
    org = db.get(Organization, inv.organization_id)
    patient = db.get(Patient, inv.patient_id)
    if org is None or not org.is_active or patient is None or not patient.is_active:
        raise NotFound("This invitation is no longer available. Contact your facility.")
    return inv, org, patient


class InvitationLookup(BaseModel):
    token: str = Field(min_length=8, max_length=256)


@router.post("/auth/portal-invitations/inspect")
def inspect_invitation(
    body: InvitationLookup, request: Request, db: Session = Depends(get_db)
):
    limiter.check(f"invitation:{client_ip(request)}", 30, 60)
    inv, org, _ = invitation(db, body.token)
    return {
        "facility": org.name,
        "email_masked": mask(inv.recipient_email, 3),
        "existing_account": bool(
            db.scalar(select(User.id).where(User.email == inv.recipient_email))
        ),
        "used": bool(inv.accepted_at),
        "expires_at": inv.expires_at,
    }


class Setup(BaseModel):
    token: str = Field(min_length=8, max_length=256)
    new_password: str = Field(min_length=10, max_length=128)
    full_name: str = Field(min_length=2, max_length=200)


@router.post("/auth/complete-portal-invitation")
def complete_invitation(
    body: Setup, request: Request, response: Response, db: Session = Depends(get_db)
):
    limiter.check(f"invitation-setup:{client_ip(request)}", 15, 60)
    inv, org, patient = invitation(db, body.token, True)
    if inv.accepted_at:
        raise Conflict("This invitation was already used. Sign in instead.")
    if db.scalar(select(User.id).where(User.email == inv.recipient_email)):
        raise Conflict(
            "An account already exists. Sign in with your current password, then accept this invitation."
        )
    if patient.portal_user_id or db.scalar(
        select(ParticipantAccountLink.id).where(
            ParticipantAccountLink.patient_id == patient.id
        )
    ):
        raise Conflict("This patient is already linked. Contact your facility.")
    problems = validate_password_strength(body.new_password)
    if problems:
        raise ValidationFailed("; ".join(problems))
    user = User(
        email=inv.recipient_email,
        full_name=body.full_name.strip(),
        password_hash=hash_password(body.new_password),
        email_verified_at=utcnow(),
    )
    db.add(user)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise Conflict(
            "An account was created for this email. Sign in and accept your invitation instead."
        )
    db.add(Membership(user_id=user.id, organization_id=org.id, role="patient"))
    db.add(
        ParticipantAccountLink(
            user_id=user.id,
            organization_id=org.id,
            patient_id=patient.id,
            verified_at=utcnow(),
            verification_source="invitation",
        )
    )
    patient.portal_user_id = user.id
    inv.accepted_at = utcnow()
    inv.accepted_by_user_id = user.id
    raw, csrf, sess = auth_svc._create_session(
        db,
        user,
        org.id,
        ip_address=client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    from app.core import audit

    audit.record(
        db,
        action="patient.portal_setup.complete",
        resource_type="patient",
        resource_id=patient.id,
        organization_id=org.id,
        actor_user_id=user.id,
        actor_label=user.email,
    )
    queue_email(
        db,
        to=user.email,
        subject="Your Recova portal is ready",
        body=f"Your portal for {org.name} is ready. You can now sign in using your own password.",
        category="welcome",
        user_id=user.id,
        organization_id=org.id,
    )
    db.commit()
    _set_session_cookies(response, raw, csrf)
    return auth_svc._session_payload(db, user, sess, csrf)


class TokenInput(BaseModel):
    token: str = Field(min_length=8, max_length=256)


@router.post("/auth/verify-email")
def verify_email(body: TokenInput, db: Session = Depends(get_db)):
    row = db.scalar(
        select(PasswordResetToken)
        .where(
            PasswordResetToken.token_hash == hash_token(body.token),
            PasswordResetToken.purpose == "verify_email",
        )
        .with_for_update()
    )
    if row is None or row.used_at or row.expires_at <= utcnow():
        raise Unauthorized("This verification link is invalid or expired")
    user = db.get(User, row.user_id)
    if not user or not user.is_active:
        raise Unauthorized("Account unavailable")
    user.email_verified_at = utcnow()
    row.used_at = utcnow()
    db.commit()
    return {"message": "Email address verified. You can return to Recova."}


@router.post("/auth/resend-verification")
def resend_verification(ctx: AuthContext = Depends(get_auth_context)):
    limiter.check(f"verify:{ctx.user.id}", 3, 60)
    row = account_link(ctx.db, ctx.user, "verify_email", organization_id=ctx.org_id)
    ctx.db.commit()
    return delivery_view(row)


@router.get("/settings/email-deliveries")
def list_deliveries(ctx: AuthContext = Depends(requires(P.USERS_MANAGE))):
    rows = ctx.db.scalars(
        select(EmailDelivery)
        .where(EmailDelivery.organization_id == ctx.org_id)
        .order_by(EmailDelivery.created_at.desc())
        .limit(100)
    ).all()
    return [delivery_view(r) for r in rows]


@router.post("/settings/email-deliveries/{delivery_id}/retry")
def retry_delivery(
    delivery_id: uuid.UUID, ctx: AuthContext = Depends(requires(P.USERS_MANAGE))
):
    row = ctx.db.scalar(
        select(EmailDelivery)
        .where(
            EmailDelivery.id == delivery_id, EmailDelivery.organization_id == ctx.org_id
        )
        .with_for_update()
    )
    if row is None:
        raise NotFound("Email delivery not found")
    if row.status not in ("failed", "not_configured"):
        raise Conflict("Only failed or unconfigured messages can be retried")
    if row.expires_at and row.expires_at <= utcnow():
        raise ValidationFailed("Link expired. Send a fresh invitation instead.")
    row.status = "queued"
    row.last_error = None
    from app.tasks.queue import enqueue

    enqueue(
        ctx.db,
        "email.deliver",
        {"email_id": str(row.id)},
        organization_id=ctx.org_id,
        idempotency_key=f"email-manual:{row.id}:{uuid.uuid4()}",
        max_attempts=1,
    )
    ctx.audit("email.retry", "email_delivery", row.id)
    ctx.db.commit()
    return delivery_view(row)


@router.post("/users/{user_id}/resend-activation")
def resend_activation(
    user_id: uuid.UUID, ctx: AuthContext = Depends(requires(P.USERS_MANAGE))
):
    member = ctx.db.scalar(
        select(Membership).where(
            Membership.user_id == user_id,
            Membership.organization_id == ctx.org_id,
            Membership.is_active.is_(True),
        )
    )
    user = ctx.db.get(User, user_id)
    if not member or not user or not user.is_active:
        raise NotFound("Active user not found in this facility")
    if user.is_platform_admin and not ctx.user.is_platform_admin:
        raise ValidationFailed(
            "Platform account setup is managed by platform administrators"
        )
    limiter.check(f"activation-resend:{ctx.user.id}:{user_id}", 3, 60)
    if user.email_verified_at:
        from app.services.messaging import public_link

        row = queue_email(
            ctx.db,
            to=user.email,
            subject="Access your Recova facility",
            body=f'Your facility has sent you an access reminder. Use your existing password to sign in: {public_link("/login")}',
            category="membership",
            user_id=user.id,
            organization_id=ctx.org_id,
        )
    else:
        row = account_link(ctx.db, user, "activation", organization_id=ctx.org_id)
    ctx.audit("user.activation.resend", "user", user_id)
    ctx.db.commit()
    return delivery_view(row)
