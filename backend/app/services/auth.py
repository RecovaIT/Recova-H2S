"""Authentication, session management, password recovery and bootstrap service."""

from __future__ import annotations

import uuid
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import AuthContext, resolve_permissions
from app.core import audit
from app.core.config import get_settings
from app.core.errors import Conflict, Forbidden, NotFound, Unauthorized, ValidationFailed
from app.core.permissions import Role
from app.core.rate_limit import limiter
from app.core.security import (
    hash_password,
    hash_token,
    new_token,
    validate_password_strength,
    verify_password,
)
from app.models.base import utcnow
from app.models.identity import Membership, Organization, PasswordResetToken, User, UserSession
from app.schemas.identity import BootstrapRequest, MembershipOut, OrganizationOut, SessionResponse, UserOut


def _session_payload(db: Session, user: User, sess: UserSession, raw_csrf: str | None = None) -> SessionResponse:
    memberships = db.scalars(
        select(Membership).where(Membership.user_id == user.id, Membership.is_active.is_(True))
    ).all()
    org_ids = [m.organization_id for m in memberships]
    orgs = {o.id: o for o in db.scalars(select(Organization).where(Organization.id.in_(org_ids))).all()} if org_ids else {}

    active_org: Organization | None = None
    active_role: Role | None = None
    if sess.active_organization_id:
        active_org = db.get(Organization, sess.active_organization_id)
        if active_org is not None and not active_org.is_active and not user.is_platform_admin:
            active_org = None
        if active_org is not None:
            m = next((x for x in memberships if x.organization_id == active_org.id), None)
            if m:
                active_role = Role(m.role)
            elif user.is_platform_admin:
                active_role = Role.PLATFORM_ADMIN
            else:
                active_org = None
    elif user.is_platform_admin:
        active_role = Role.PLATFORM_ADMIN

    perms, tracks = resolve_permissions(db, active_org, active_role, user.is_platform_admin)
    m_out = [
        MembershipOut(
            id=m.id,
            user_id=m.user_id,
            organization_id=m.organization_id,
            organization_name=orgs[m.organization_id].name if m.organization_id in orgs else None,
            organization_slug=orgs[m.organization_id].slug if m.organization_id in orgs else None,
            role=m.role,
            is_active=m.is_active,
            department_ids=list(m.department_ids or []),
        )
        for m in memberships
        if m.organization_id in orgs and orgs[m.organization_id].is_active
    ]
    return SessionResponse(
        user=UserOut.model_validate(user),
        active_organization=OrganizationOut.model_validate(active_org) if active_org else None,
        role=active_role.value if active_role else None,
        permissions=sorted(perms),
        tracks=sorted(tracks),
        memberships=m_out,
        csrf_token=raw_csrf,
    )


def needs_bootstrap(db: Session) -> bool:
    return (db.scalar(select(func.count(User.id))) or 0) == 0


def _create_org_and_admin_session(
    db: Session,
    req: BootstrapRequest,
    *,
    is_platform_admin: bool,
    audit_action: str,
    enforce_single_programme: bool = False,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> tuple[SessionResponse, str, str]:
    problems = validate_password_strength(req.admin_password)
    if problems:
        raise ValidationFailed("; ".join(problems))

    if enforce_single_programme:
        if req.primary_programme is not None:
            resolved_tracks = [req.primary_programme.value]
            primary_prog = req.primary_programme.value
        elif len(req.enabled_tracks) == 1:
            resolved_tracks = [req.enabled_tracks[0].value]
            primary_prog = req.enabled_tracks[0].value
        else:
            raise ValidationFailed("Select exactly one primary programme during organisation registration.")
    else:
        if not req.enabled_tracks:
            raise ValidationFailed("Select at least one application track")
        resolved_tracks = [t.value for t in req.enabled_tracks]
        primary_prog = req.primary_programme.value if req.primary_programme else resolved_tracks[0]

    slug = req.organization_slug.strip().lower()
    email = req.admin_email.strip().lower()

    if db.scalar(select(Organization).where(Organization.slug == slug)) is not None:
        raise Conflict(f"Organisation slug '{slug}' already exists")
    if db.scalar(select(User).where(User.email == email)) is not None:
        raise Conflict(f"An account with email '{email}' already exists. Sign in or use another admin email.")

    org = Organization(
        name=req.organization_name.strip(),
        slug=slug,
        org_type=req.org_type,
        primary_programme=primary_prog,
        programme_configuration_status="configured",
        enabled_tracks=resolved_tracks,
        country="UAE",
        emirate="Abu Dhabi",
        data_retention_days=2555,
    )
    db.add(org)
    db.flush()

    user = User(
        email=email,
        full_name=req.admin_full_name.strip(),
        password_hash=hash_password(req.admin_password),
        is_active=True,
        is_platform_admin=is_platform_admin,
        preferred_language="en",
        license_number=req.admin_license_number,
        last_login_at=utcnow(),
    )
    db.add(user)
    db.flush()

    membership = Membership(
        user_id=user.id,
        organization_id=org.id,
        role=Role.ORG_ADMIN.value,
        is_active=True,
        department_ids=[],
    )
    db.add(membership)

    raw_session, raw_csrf, sess = _create_session(db, user, org.id, ip_address=ip_address, user_agent=user_agent)
    audit.record(
        db,
        action=audit_action,
        resource_type="organization",
        resource_id=org.id,
        organization_id=org.id,
        actor_user_id=user.id,
        actor_label=user.email,
        details={"slug": org.slug, "enabled_tracks": org.enabled_tracks},
        ip_address=ip_address,
    )
    db.commit()
    return _session_payload(db, user, sess, raw_csrf=raw_csrf), raw_session, raw_csrf


def bootstrap_platform(
    db: Session,
    req: BootstrapRequest,
    *,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> tuple[SessionResponse, str, str]:
    """One-time platform initialisation when zero users exist."""
    if not needs_bootstrap(db):
        raise Conflict("Platform has already been initialised")
    return _create_org_and_admin_session(
        db,
        req,
        is_platform_admin=True,
        audit_action="platform.bootstrap",
        ip_address=ip_address,
        user_agent=user_agent,
    )


def register_organization(
    db: Session,
    req: BootstrapRequest,
    *,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> tuple[SessionResponse, str, str]:
    """Self-service tenant organisation onboarding from the public login screen."""
    s = get_settings()
    limiter.check(f"register_org:{ip_address or 'unknown'}", s.rate_limit_login_per_minute, 60.0)
    return _create_org_and_admin_session(
        db,
        req,
        is_platform_admin=False,
        audit_action="organization.register",
        enforce_single_programme=True,
        ip_address=ip_address,
        user_agent=user_agent,
    )


def _create_session(
    db: Session,
    user: User,
    active_org_id: uuid.UUID | None,
    *,
    ip_address: str | None,
    user_agent: str | None,
) -> tuple[str, str, UserSession]:
    s = get_settings()
    raw_session = new_token(32)
    raw_csrf = new_token(24)
    now = utcnow()
    sess = UserSession(
        user_id=user.id,
        token_hash=hash_token(raw_session),
        csrf_token_hash=hash_token(raw_csrf),
        active_organization_id=active_org_id,
        expires_at=now + timedelta(minutes=s.session_ttl_minutes),
        last_seen_at=now,
        ip_address=ip_address,
        user_agent=(user_agent or "")[:400],
    )
    db.add(sess)
    db.flush()
    return raw_session, raw_csrf, sess


def login(
    db: Session,
    *,
    email: str,
    password: str,
    organization_id: uuid.UUID | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> tuple[SessionResponse, str, str]:
    s = get_settings()
    norm_email = email.strip().lower()
    limiter.check(f"login:{ip_address or 'unknown'}:{norm_email}", s.rate_limit_login_per_minute, 60.0)

    user = db.scalar(select(User).where(User.email == norm_email))
    now = utcnow()
    if user is None:
        raise Unauthorized("Invalid email or password")

    if user.locked_until and user.locked_until > now:
        raise Unauthorized("Account temporarily locked due to repeated failed attempts", code="account_locked")

    if not verify_password(password, user.password_hash):
        user.failed_login_count += 1
        if user.failed_login_count >= 5:
            user.locked_until = now + timedelta(minutes=15)
        audit.record(
            db,
            action="auth.login_failed",
            resource_type="user",
            resource_id=user.id,
            actor_user_id=user.id,
            actor_label=user.email,
            outcome="failure",
            ip_address=ip_address,
        )
        db.commit()
        raise Unauthorized("Invalid email or password")

    if not user.is_active:
        raise Unauthorized("Account is deactivated", code="account_inactive")

    memberships = db.scalars(
        select(Membership).where(Membership.user_id == user.id, Membership.is_active.is_(True))
    ).all()
    active_org_id: uuid.UUID | None = None
    if organization_id is not None:
        allowed = any(m.organization_id == organization_id for m in memberships) or user.is_platform_admin
        if not allowed:
            raise Forbidden("You do not belong to the requested organisation")
        org = db.get(Organization, organization_id)
        if org is None or (not org.is_active and not user.is_platform_admin):
            raise NotFound("Organisation not found or inactive")
        active_org_id = org.id
    elif memberships:
        for m in memberships:
            org = db.get(Organization, m.organization_id)
            if org is not None and org.is_active:
                active_org_id = org.id
                break
    elif user.is_platform_admin:
        first_org = db.scalar(select(Organization).where(Organization.is_active.is_(True)).limit(1))
        active_org_id = first_org.id if first_org else None

    user.failed_login_count = 0
    user.locked_until = None
    user.last_login_at = now
    raw_session, raw_csrf, sess = _create_session(db, user, active_org_id, ip_address=ip_address, user_agent=user_agent)
    audit.record(
        db,
        action="auth.login",
        resource_type="user_session",
        resource_id=sess.id,
        organization_id=active_org_id,
        actor_user_id=user.id,
        actor_label=user.email,
        ip_address=ip_address,
    )
    db.commit()
    return _session_payload(db, user, sess, raw_csrf=raw_csrf), raw_session, raw_csrf


def current_session(ctx: AuthContext) -> SessionResponse:
    return _session_payload(ctx.db, ctx.user, ctx.session)


def rotate_csrf(ctx: AuthContext) -> str:
    raw_csrf = new_token(24)
    ctx.session.csrf_token_hash = hash_token(raw_csrf)
    ctx.db.commit()
    return raw_csrf


def logout(ctx: AuthContext) -> None:
    ctx.session.revoked_at = utcnow()
    ctx.audit("auth.logout", "user_session", ctx.session.id)
    ctx.db.commit()


def switch_organization(ctx: AuthContext, organization_id: uuid.UUID) -> SessionResponse:
    org = ctx.db.get(Organization, organization_id)
    if org is None or (not org.is_active and not ctx.user.is_platform_admin):
        raise NotFound("Organisation not found")
    membership = ctx.db.scalar(
        select(Membership).where(
            Membership.user_id == ctx.user.id, Membership.organization_id == organization_id, Membership.is_active.is_(True)
        )
    )
    if membership is None and not ctx.user.is_platform_admin:
        ctx.audit_denied("auth.switch_org", "organization", details={"target_org_id": str(organization_id)})
        raise Forbidden("You do not have an active membership in that organisation")
    before = str(ctx.session.active_organization_id) if ctx.session.active_organization_id else None
    ctx.session.active_organization_id = org.id
    ctx.audit("auth.switch_org", "user_session", ctx.session.id, changes={"active_organization_id": {"before": before, "after": str(org.id)}})
    ctx.db.commit()
    return _session_payload(ctx.db, ctx.user, ctx.session)


def request_password_reset(db: Session, email: str, *, ip_address: str | None = None) -> dict:
    s = get_settings()
    norm = email.strip().lower()
    limiter.check(f"pwreset:{ip_address or 'unknown'}", 10, 60.0)
    user = db.scalar(select(User).where(User.email == norm, User.is_active.is_(True)))
    if user is None:
        return {"accepted": True, "delivery_status": "ignored_if_unknown"}

    raw_token = new_token(32)
    prt = PasswordResetToken(
        user_id=user.id,
        token_hash=hash_token(raw_token),
        purpose="reset",
        expires_at=utcnow() + timedelta(minutes=s.password_reset_ttl_minutes),
    )
    db.add(prt)
    audit.record(
        db,
        action="auth.password_reset_requested",
        resource_type="user",
        resource_id=user.id,
        actor_user_id=user.id,
        actor_label=user.email,
        ip_address=ip_address,
    )
    db.commit()

    # Attempt SMTP delivery if configured
    from app.integrations.notifications import send_email_direct

    reset_url = f"{s.frontend_base_url.rstrip('/')}/reset-password?token={raw_token}"
    delivery = send_email_direct(
        to_address=user.email,
        subject="Recova Password Reset",
        body=f"A password reset was requested for your Recova account.\nReset link (expires in {s.password_reset_ttl_minutes} minutes): {reset_url}",
    )
    return {"accepted": True, "delivery_status": delivery["status"], "detail": delivery.get("error")}


def confirm_password_reset(db: Session, token: str, new_password: str, *, ip_address: str | None = None) -> None:
    problems = validate_password_strength(new_password)
    if problems:
        raise ValidationFailed("; ".join(problems))
    now = utcnow()
    prt = db.scalar(select(PasswordResetToken).where(PasswordResetToken.token_hash == hash_token(token)))
    if prt is None or prt.used_at is not None or prt.expires_at <= now:
        raise Unauthorized("Password reset token is invalid or expired", code="invalid_token")
    user = db.get(User, prt.user_id)
    if user is None or not user.is_active:
        raise Unauthorized("Account is inactive")

    user.password_hash = hash_password(new_password)
    user.failed_login_count = 0
    user.locked_until = None
    prt.used_at = now
    # Revoke all active sessions on password reset
    sessions = db.scalars(select(UserSession).where(UserSession.user_id == user.id, UserSession.revoked_at.is_(None))).all()
    for sess in sessions:
        sess.revoked_at = now

    audit.record(
        db,
        action="auth.password_reset_confirmed",
        resource_type="user",
        resource_id=user.id,
        actor_user_id=user.id,
        actor_label=user.email,
        ip_address=ip_address,
    )
    db.commit()


def change_password(ctx: AuthContext, current_password: str, new_password: str) -> None:
    if not verify_password(current_password, ctx.user.password_hash):
        raise Unauthorized("Current password is incorrect")
    problems = validate_password_strength(new_password)
    if problems:
        raise ValidationFailed("; ".join(problems))
    ctx.user.password_hash = hash_password(new_password)
    now = utcnow()
    others = ctx.db.scalars(
        select(UserSession).where(
            UserSession.user_id == ctx.user.id, UserSession.id != ctx.session.id, UserSession.revoked_at.is_(None)
        )
    ).all()
    for s in others:
        s.revoked_at = now
    ctx.audit("auth.password_changed", "user", ctx.user.id)
    ctx.db.commit()
