"""Authentication, session, password recovery, and one-time bootstrap endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Query, Request, Response
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from app.api.deps import AuthContext, client_ip, get_auth_context
from app.core.config import get_settings
from app.core.db import get_db
from app.schemas.common import Message
from app.schemas.identity import (
    BootstrapRequest,
    ChangePasswordRequest,
    LoginRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    PortalInvitationAcceptRequest,
    SessionResponse,
    SwitchOrganizationRequest,
)
from app.services import auth as auth_svc

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_session_cookies(response: Response, session_token: str, csrf_token: str) -> None:
    s = get_settings()
    max_age = s.session_ttl_minutes * 60
    response.set_cookie(
        key=s.session_cookie_name,
        value=session_token,
        httponly=True,
        secure=s.cookie_secure,
        samesite=s.cookie_samesite,
        max_age=max_age,
        path="/",
    )
    response.set_cookie(
        key=s.csrf_cookie_name,
        value=csrf_token,
        httponly=False,
        secure=s.cookie_secure,
        samesite=s.cookie_samesite,
        max_age=max_age,
        path="/",
    )


def _clear_session_cookies(response: Response) -> None:
    s = get_settings()
    response.delete_cookie(s.session_cookie_name, path="/")
    response.delete_cookie(s.csrf_cookie_name, path="/")


@router.get("/status")
def auth_status(db: Session = Depends(get_db)) -> dict:
    return {"needs_bootstrap": auth_svc.needs_bootstrap(db)}


@router.post("/bootstrap", response_model=SessionResponse, status_code=201)
def bootstrap(req: BootstrapRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    sess_resp, raw_sess, raw_csrf = auth_svc.bootstrap_platform(
        db,
        req,
        ip_address=client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    _set_session_cookies(response, raw_sess, raw_csrf)
    return sess_resp


@router.post("/register-organization", response_model=SessionResponse, status_code=201)
def register_organization(req: BootstrapRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    """Provision a new isolated tenant organisation and sign in its initial Org Admin."""
    sess_resp, raw_sess, raw_csrf = auth_svc.register_organization(
        db,
        req,
        ip_address=client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    _set_session_cookies(response, raw_sess, raw_csrf)
    return sess_resp


@router.post("/login", response_model=SessionResponse)
def login(req: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    sess_resp, raw_sess, raw_csrf = auth_svc.login(
        db,
        email=req.email,
        password=req.password,
        organization_id=req.organization_id,
        ip_address=client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    _set_session_cookies(response, raw_sess, raw_csrf)
    return sess_resp


@router.post("/logout", response_model=Message)
def logout(response: Response, ctx: AuthContext = Depends(get_auth_context)):
    auth_svc.logout(ctx)
    _clear_session_cookies(response)
    return Message(message="Logged out")


@router.get("/me", response_model=SessionResponse)
def me(ctx: AuthContext = Depends(get_auth_context)):
    return auth_svc.current_session(ctx)


@router.post("/csrf")
def refresh_csrf(response: Response, ctx: AuthContext = Depends(get_auth_context)):
    s = get_settings()
    raw_csrf = auth_svc.rotate_csrf(ctx)
    response.set_cookie(
        key=s.csrf_cookie_name,
        value=raw_csrf,
        httponly=False,
        secure=s.cookie_secure,
        samesite=s.cookie_samesite,
        max_age=s.session_ttl_minutes * 60,
        path="/",
    )
    return {"csrf_token": raw_csrf}


@router.post("/switch-organization", response_model=SessionResponse)
def switch_organization(req: SwitchOrganizationRequest, ctx: AuthContext = Depends(get_auth_context)):
    return auth_svc.switch_organization(ctx, req.organization_id)


@router.post("/password-reset/request")
def password_reset_request(req: PasswordResetRequest, request: Request, db: Session = Depends(get_db)):
    return auth_svc.request_password_reset(db, req.email, ip_address=client_ip(request))


@router.post("/password-reset/confirm", response_model=Message)
def password_reset_confirm(req: PasswordResetConfirm, request: Request, db: Session = Depends(get_db)):
    auth_svc.confirm_password_reset(db, req.token, req.new_password, ip_address=client_ip(request))
    return Message(message="Password updated successfully")


@router.post("/change-password", response_model=Message)
def change_password(req: ChangePasswordRequest, ctx: AuthContext = Depends(get_auth_context)):
    auth_svc.change_password(ctx, req.current_password, req.new_password)
    return Message(message="Password changed")


@router.post("/accept-portal-invitation", response_model=Message)
def accept_portal_invitation(
    token: str | None = Query(default=None),
    body: PortalInvitationAcceptRequest | None = Body(default=None),
    ctx: AuthContext = Depends(get_auth_context),
):
    """Verify a single-use, expiring, recipient-bound invitation and create ParticipantAccountLink."""
    from sqlalchemy import select
    from app.core.errors import Conflict, Forbidden, NotFound, ValidationFailed
    from app.core.security import hash_token
    from app.models.base import utcnow
    from app.models.clinical import Patient
    from app.models.identity import Membership, ParticipantAccountLink, PortalInvitation

    raw_token = (body.token if body is not None else token) or ""
    raw_token = raw_token.strip()
    if not raw_token:
        raise ValidationFailed("Invitation token is required.")

    now = utcnow()
    inv = ctx.db.scalar(select(PortalInvitation).where(PortalInvitation.token_hash == hash_token(raw_token)).with_for_update())
    if inv is None or inv.revoked_at is not None or inv.purpose != "portal_link":
        raise NotFound("Invalid or revoked portal invitation.")
    if inv.expires_at < now:
        raise ValidationFailed("Portal invitation has expired.")
    if inv.recipient_email.lower() != ctx.user.email.lower():
        raise Forbidden("This invitation is bound to a different recipient email.")

    patient = ctx.db.get(Patient, inv.patient_id)
    from app.models.identity import Organization
    invited_org=ctx.db.get(Organization,inv.organization_id)
    if patient is None or not patient.is_active or patient.organization_id != inv.organization_id or invited_org is None or not invited_org.is_active:
        raise NotFound("Linked participant record not found.")

    if inv.accepted_at is not None:
        if inv.accepted_by_user_id == ctx.user.id or patient.portal_user_id == ctx.user.id:
            member=ctx.db.scalar(select(Membership).where(Membership.user_id==ctx.user.id,Membership.organization_id==inv.organization_id,Membership.is_active.is_(True)))
            if not member:raise Forbidden('Facility access is disabled. Contact your facility.')
            ctx.session.active_organization_id=inv.organization_id
            ctx.db.commit()
            return Message(message="Portal invitation accepted and participant record linked.")
        raise Conflict("This portal invitation has already been used.")

    existing_link_for_user = ctx.db.scalar(
        select(ParticipantAccountLink).where(
            ParticipantAccountLink.user_id == ctx.user.id,
            ParticipantAccountLink.organization_id == inv.organization_id,
            ParticipantAccountLink.revoked_at.is_(None),
        )
    )
    if existing_link_for_user is not None and existing_link_for_user.patient_id != patient.id:
        raise Conflict("Your account is already linked to another participant record in this facility.")

    existing_link_for_patient = ctx.db.scalar(
        select(ParticipantAccountLink).where(
            ParticipantAccountLink.patient_id == patient.id,
            ParticipantAccountLink.revoked_at.is_(None),
        )
    )
    if existing_link_for_patient is not None and existing_link_for_patient.user_id != ctx.user.id:
        raise Conflict("This participant record is already linked to another portal account.")

    patient.portal_user_id = ctx.user.id
    inv.accepted_at = now
    inv.accepted_by_user_id = ctx.user.id

    if existing_link_for_user is None:
        ctx.db.add(
            ParticipantAccountLink(
                organization_id=inv.organization_id,
                user_id=ctx.user.id,
                patient_id=patient.id,
                verified_at=now,
                verification_source="invitation",
            )
        )

    existing_mem = ctx.db.scalar(
        select(Membership).where(
            Membership.user_id == ctx.user.id,
            Membership.organization_id == inv.organization_id,
        )
    )
    if existing_mem is None:
        ctx.db.add(
            Membership(
                user_id=ctx.user.id,
                organization_id=inv.organization_id,
                role="patient",
                is_active=True,
                department_ids=[],
            )
        )
    elif not existing_mem.is_active:
        raise Forbidden('Facility access is disabled. Ask the facility to restore access before accepting.')

    ctx.user.email_verified_at=now
    ctx.session.active_organization_id = inv.organization_id

    ctx.audit(
        "patient.portal_invitation.accept",
        "portal_invitation",
        inv.id,
        patient_id=patient.id,
        details={"patient_id": str(patient.id), "organization_id": str(inv.organization_id)},
    )
    ctx.db.commit()
    return Message(message="Portal invitation accepted and participant record linked.")
