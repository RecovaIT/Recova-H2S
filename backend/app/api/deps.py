"""Authentication / authorisation dependencies.

Every organisation-scoped request resolves an `AuthContext` that carries the active
organisation, the member's role and the effective permission set. Services must use
`ctx.org_id` to scope all queries (tenant isolation is enforced server-side).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any, Callable

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import audit
from app.core.config import get_settings
from app.core.db import get_db
from app.core.errors import Forbidden, Unauthorized
from app.core.permissions import DEFAULT_ROLE_TRACKS, P, Role, Track, effective_permissions
from app.core.security import constant_time_equals, hash_token
from app.models.base import utcnow
from app.models.identity import Membership, Organization, RolePermissionOverride, User, UserSession

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


@dataclass
class AuthContext:
    db: Session
    user: User
    session: UserSession
    organization: Organization | None
    membership: Membership | None
    role: Role | None
    permissions: set[str] = field(default_factory=set)
    tracks: set[str] = field(default_factory=set)
    ip_address: str | None = None
    request_id: str | None = None

    @property
    def user_id(self) -> uuid.UUID:
        return self.user.id

    @property
    def org_id(self) -> uuid.UUID:
        if self.organization is None:
            raise Forbidden("No active organisation selected", code="no_active_organization")
        return self.organization.id

    def has(self, perm: str) -> bool:
        return perm in self.permissions

    def require(self, *perms: str) -> None:
        missing = [p for p in perms if p not in self.permissions]
        if missing:
            self.audit_denied("permission.check", "permission", details={"missing": missing})
            raise Forbidden("You do not have permission to perform this action", details={"missing_permissions": missing})

    def require_track(self, track: str) -> None:
        if track not in self.tracks:
            self.audit_denied("track.access", "track", details={"track": track})
            raise Forbidden(f"Track '{track}' is not available to your role or organisation", code="track_forbidden")

    def audit(self, action: str, resource_type: str, resource_id: Any = None, **kw: Any) -> None:
        audit.record(
            self.db,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            organization_id=self.organization.id if self.organization else None,
            actor_user_id=self.user.id,
            actor_label=self.user.email,
            ip_address=self.ip_address,
            request_id=self.request_id,
            **kw,
        )

    def audit_denied(self, action: str, resource_type: str, details: dict | None = None) -> None:
        # Persist denial in its own transaction so it survives the request rollback.
        from app.core.db import SessionLocal

        with SessionLocal() as s:
            audit.record(
                s,
                action=action,
                resource_type=resource_type,
                organization_id=self.organization.id if self.organization else None,
                actor_user_id=self.user.id,
                actor_label=self.user.email,
                outcome="denied",
                details=details,
                ip_address=self.ip_address,
                request_id=self.request_id,
            )
            s.commit()


def client_ip(request: Request) -> str | None:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else None


def resolve_permissions(db: Session, org: Organization | None, role: Role | None, is_platform_admin: bool) -> tuple[set[str], set[str]]:
    if is_platform_admin and role is None:
        role = Role.PLATFORM_ADMIN
    if role is None:
        return set(), set()
    grants: set[str] = set()
    revokes: set[str] = set()
    if org is not None and role != Role.PLATFORM_ADMIN:
        rows = db.scalars(
            select(RolePermissionOverride).where(
                RolePermissionOverride.organization_id == org.id, RolePermissionOverride.role == role.value
            )
        ).all()
        for r in rows:
            (grants if r.effect == "grant" else revokes).add(r.permission)
    perms = effective_permissions(role, grants, revokes)
    if is_platform_admin:
        perms.add(P.PLATFORM_ADMIN)
    tracks = {t.value for t in DEFAULT_ROLE_TRACKS.get(role, frozenset())}
    if org is not None:
        tracks &= set(org.enabled_tracks or [])
    return perms, tracks


def _load_session(request: Request, db: Session) -> tuple[UserSession, User]:
    s = get_settings()
    raw = request.cookies.get(s.session_cookie_name)
    if not raw:
        raise Unauthorized("Authentication required")
    sess = db.scalar(select(UserSession).where(UserSession.token_hash == hash_token(raw)))
    now = utcnow()
    if sess is None or sess.revoked_at is not None or sess.expires_at <= now:
        raise Unauthorized("Session expired or invalid", code="session_expired")
    if sess.last_seen_at + timedelta(minutes=s.session_idle_timeout_minutes) <= now:
        sess.revoked_at = now
        db.commit()
        raise Unauthorized("Session timed out due to inactivity", code="session_expired")
    user = db.get(User, sess.user_id)
    if user is None or not user.is_active:
        raise Unauthorized("Account is inactive", code="account_inactive")
    if (now - sess.last_seen_at).total_seconds() > 60:
        sess.last_seen_at = now
        db.commit()
    return sess, user


def _check_csrf(request: Request, sess: UserSession) -> None:
    if request.method in SAFE_METHODS:
        return
    header = request.headers.get("x-csrf-token", "")
    if not header or not constant_time_equals(hash_token(header), sess.csrf_token_hash):
        raise Forbidden("CSRF token missing or invalid", code="csrf_failed")


def get_auth_context(request: Request, db: Session = Depends(get_db)) -> AuthContext:
    sess, user = _load_session(request, db)
    _check_csrf(request, sess)
    org: Organization | None = None
    membership: Membership | None = None
    role: Role | None = None
    if sess.active_organization_id:
        org = db.get(Organization, sess.active_organization_id)
        if org is not None and not org.is_active and not user.is_platform_admin:
            org = None
        if org is not None:
            membership = db.scalar(
                select(Membership).where(
                    Membership.user_id == user.id, Membership.organization_id == org.id, Membership.is_active.is_(True)
                )
            )
            if membership is not None:
                role = Role(membership.role)
            elif user.is_platform_admin:
                role = Role.PLATFORM_ADMIN
            else:
                org = None  # membership revoked since session started
    perms, tracks = resolve_permissions(db, org, role, user.is_platform_admin)
    return AuthContext(
        db=db,
        user=user,
        session=sess,
        organization=org,
        membership=membership,
        role=role,
        permissions=perms,
        tracks=tracks,
        ip_address=client_ip(request),
        request_id=getattr(request.state, "request_id", None),
    )


def get_org_context(ctx: AuthContext = Depends(get_auth_context)) -> AuthContext:
    _ = ctx.org_id  # raises if no organisation
    return ctx


def requires(*perms: str) -> Callable[..., AuthContext]:
    def dep(ctx: AuthContext = Depends(get_org_context)) -> AuthContext:
        ctx.require(*perms)
        return ctx

    return dep


def requires_track(track: Track | str, *perms: str) -> Callable[..., AuthContext]:
    def dep(ctx: AuthContext = Depends(get_org_context)) -> AuthContext:
        ctx.require_track(str(track))
        if perms:
            ctx.require(*perms)
        return ctx

    return dep
