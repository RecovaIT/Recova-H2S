"""Organisation, role permission overrides, user and membership services."""

from __future__ import annotations

import uuid
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import AuthContext
from app.core import audit
from app.core.config import get_settings
from app.core.errors import Conflict, Forbidden, NotFound, ValidationFailed
from app.core.permissions import (
    ALL_PERMISSIONS,
    DEFAULT_ROLE_PERMISSIONS,
    P,
    Role,
    effective_permissions,
)
from app.core.security import (
    hash_password,
    hash_token,
    new_token,
    validate_password_strength,
)
from app.models.base import utcnow
from app.models.identity import (
    Membership,
    Organization,
    PasswordResetToken,
    RolePermissionOverride,
    User,
    UserSession,
)
from app.schemas.identity import (
    MembershipOut,
    MembershipUpdateRequest,
    OrganizationCreate,
    OrganizationUpdate,
    PrimaryProgrammeSelectionRequest,
    RolePermissionOverrideInput,
    UserCreateRequest,
    UserUpdateRequest,
    UserWithMembershipsOut,
)


def list_organizations(ctx: AuthContext) -> list[Organization]:
    if ctx.user.is_platform_admin:
        return list(
            ctx.db.scalars(select(Organization).order_by(Organization.name)).all()
        )
    org_ids = list(
        ctx.db.scalars(
            select(Membership.organization_id).where(
                Membership.user_id == ctx.user.id, Membership.is_active.is_(True)
            )
        ).all()
    )
    if not org_ids:
        return []
    return list(
        ctx.db.scalars(
            select(Organization)
            .where(Organization.id.in_(org_ids))
            .order_by(Organization.name)
        ).all()
    )


def create_organization(ctx: AuthContext, req: OrganizationCreate) -> Organization:
    ctx.require(P.PLATFORM_ADMIN)
    existing = ctx.db.scalar(
        select(Organization).where(Organization.slug == req.slug.lower())
    )
    if existing:
        raise Conflict(f"Organisation slug '{req.slug}' already exists")
    tracks = list(dict.fromkeys(t.value for t in req.enabled_tracks))
    if not tracks:
        raise ValidationFailed("At least one track must be enabled")
    primary_prog = (
        req.primary_programme.value
        if req.primary_programme
        else (tracks[0] if len(tracks) == 1 else tracks[0])
    )
    if primary_prog not in tracks:
        tracks.insert(0, primary_prog)
    config_status = (
        "configured"
        if (req.primary_programme is not None or len(tracks) == 1)
        else "pending_selection"
    )
    org = Organization(
        name=req.name.strip(),
        slug=req.slug.strip().lower(),
        org_type=req.org_type,
        primary_programme=primary_prog,
        programme_configuration_status=config_status,
        enabled_tracks=tracks,
        country=req.country,
        emirate=req.emirate,
        settings={"shared_population_health_provisioned": True},
        data_retention_days=req.data_retention_days,
    )
    ctx.db.add(org)
    ctx.db.flush()
    membership = Membership(
        user_id=ctx.user.id,
        organization_id=org.id,
        role=Role.ORG_ADMIN.value,
        is_active=True,
        department_ids=[],
    )
    ctx.db.add(membership)
    ctx.audit(
        "organization.create",
        "organization",
        org.id,
        details={"slug": org.slug, "primary_programme": primary_prog},
    )
    ctx.db.commit()
    return org


def update_organization(
    ctx: AuthContext, org_id: uuid.UUID, req: OrganizationUpdate
) -> Organization:
    if org_id != ctx.org_id and not ctx.user.is_platform_admin:
        raise Forbidden("Cannot modify another organisation")
    ctx.require(P.ORG_MANAGE)
    org = ctx.db.get(Organization, org_id)
    if org is None:
        raise NotFound("Organisation not found")

    before = {
        "name": org.name,
        "org_type": org.org_type,
        "enabled_tracks": org.enabled_tracks,
        "is_active": org.is_active,
        "data_retention_days": org.data_retention_days,
    }
    if req.name is not None:
        org.name = req.name.strip()
    if req.org_type is not None:
        org.org_type = req.org_type
    if req.enabled_tracks is not None:
        if not ctx.user.is_platform_admin:
            raise Forbidden(
                "Only platform administrators can modify enabled tracks; submit a programme request instead."
            )
        org.enabled_tracks = list(dict.fromkeys(t.value for t in req.enabled_tracks))
    if req.is_active is not None:
        if not ctx.user.is_platform_admin:
            raise Forbidden(
                "Only platform administrators can activate or deactivate organisations"
            )
        org.is_active = req.is_active
    if req.country is not None:
        org.country = req.country
    if req.emirate is not None:
        org.emirate = req.emirate
    if req.settings is not None:
        org.settings = {**(org.settings or {}), **req.settings}
    if req.data_retention_days is not None:
        org.data_retention_days = req.data_retention_days

    after = {
        "name": org.name,
        "org_type": org.org_type,
        "enabled_tracks": org.enabled_tracks,
        "is_active": org.is_active,
        "data_retention_days": org.data_retention_days,
    }
    ctx.audit(
        "organization.update", "organization", org.id, changes=audit.diff(before, after)
    )
    ctx.db.commit()
    return org


def select_primary_programme(
    ctx: AuthContext, org_id: uuid.UUID, req: PrimaryProgrammeSelectionRequest
) -> Organization:
    """Resolve a legacy pending_selection organisation to an explicit primary programme."""
    if org_id != ctx.org_id and not ctx.user.is_platform_admin:
        raise Forbidden("Cannot configure another organisation")
    ctx.require(P.ORG_MANAGE)
    org = ctx.db.get(Organization, org_id)
    if org is None:
        raise NotFound("Organisation not found")
    if (
        org.programme_configuration_status == "configured"
        and not ctx.user.is_platform_admin
    ):
        raise Conflict(
            "Organisation primary programme is already configured; submit a programme request for changes."
        )

    before = {
        "primary_programme": org.primary_programme,
        "programme_configuration_status": org.programme_configuration_status,
        "enabled_tracks": list(org.enabled_tracks or []),
    }
    chosen = req.primary_programme.value
    org.primary_programme = chosen
    org.programme_configuration_status = "configured"
    if req.restrict_to_primary:
        org.enabled_tracks = [chosen]
    elif chosen not in (org.enabled_tracks or []):
        org.enabled_tracks = [*list(org.enabled_tracks or []), chosen]

    after = {
        "primary_programme": org.primary_programme,
        "programme_configuration_status": org.programme_configuration_status,
        "enabled_tracks": list(org.enabled_tracks or []),
    }
    ctx.audit(
        "organization.programme_selected",
        "organization",
        org.id,
        changes=audit.diff(before, after),
        details={"reason": req.reason, "restrict_to_primary": req.restrict_to_primary},
    )
    ctx.db.commit()
    ctx.db.refresh(org)
    return org


def list_role_permissions(ctx: AuthContext) -> list[dict]:
    ctx.require(P.ORG_READ)
    overrides = ctx.db.scalars(
        select(RolePermissionOverride).where(
            RolePermissionOverride.organization_id == ctx.org_id
        )
    ).all()
    by_role: dict[str, list[RolePermissionOverride]] = {}
    for o in overrides:
        by_role.setdefault(o.role, []).append(o)

    out = []
    for role in Role:
        if role == Role.PLATFORM_ADMIN:
            continue
        rows = by_role.get(role.value, [])
        grants = {r.permission for r in rows if r.effect == "grant"}
        revokes = {r.permission for r in rows if r.effect == "revoke"}
        eff = sorted(effective_permissions(role, grants, revokes))
        out.append(
            {
                "role": role.value,
                "default_permissions": sorted(DEFAULT_ROLE_PERMISSIONS[role]),
                "effective_permissions": eff,
                "overrides": [
                    {"permission": r.permission, "effect": r.effect} for r in rows
                ],
            }
        )
    return out


def set_role_permission_override(
    ctx: AuthContext, inp: RolePermissionOverrideInput
) -> dict:
    ctx.require(P.ORG_MANAGE)
    if (
        inp.role == Role.SUPERVISOR
        and inp.effect == "grant"
        and inp.permission not in DEFAULT_ROLE_PERMISSIONS[Role.SUPERVISOR]
    ):
        raise ValidationFailed(
            "Supervisors are limited to protected aggregate reporting. Individual care access requires a clinical role."
        )
    if inp.role == Role.PLATFORM_ADMIN:
        raise Forbidden(
            "Platform administrator permissions cannot be overridden per organisation"
        )
    if inp.permission not in ALL_PERMISSIONS or inp.permission == P.PLATFORM_ADMIN:
        raise ValidationFailed(f"Invalid or reserved permission: {inp.permission}")

    row = ctx.db.scalar(
        select(RolePermissionOverride).where(
            RolePermissionOverride.organization_id == ctx.org_id,
            RolePermissionOverride.role == inp.role.value,
            RolePermissionOverride.permission == inp.permission,
        )
    )
    if row is None:
        row = RolePermissionOverride(
            organization_id=ctx.org_id,
            role=inp.role.value,
            permission=inp.permission,
            effect=inp.effect,
        )
        ctx.db.add(row)
    else:
        row.effect = inp.effect
    ctx.audit(
        "rbac.override_set",
        "role_permission_override",
        details={
            "role": inp.role.value,
            "permission": inp.permission,
            "effect": inp.effect,
        },
    )
    ctx.db.commit()
    return {"role": inp.role.value, "permission": inp.permission, "effect": inp.effect}


def delete_role_permission_override(
    ctx: AuthContext, role: Role, permission: str
) -> None:
    ctx.require(P.ORG_MANAGE)
    row = ctx.db.scalar(
        select(RolePermissionOverride).where(
            RolePermissionOverride.organization_id == ctx.org_id,
            RolePermissionOverride.role == role.value,
            RolePermissionOverride.permission == permission,
        )
    )
    if row is None:
        raise NotFound("Override not found")
    ctx.db.delete(row)
    ctx.audit(
        "rbac.override_delete",
        "role_permission_override",
        details={"role": role.value, "permission": permission},
    )
    ctx.db.commit()


def list_org_users(ctx: AuthContext) -> list[UserWithMembershipsOut]:
    ctx.require(P.USERS_READ)
    memberships = ctx.db.scalars(
        select(Membership).where(Membership.organization_id == ctx.org_id)
    ).all()
    if not memberships:
        return []
    user_ids = [m.user_id for m in memberships]
    users = {
        u.id: u
        for u in ctx.db.scalars(
            select(User).where(User.id.in_(user_ids)).order_by(User.full_name)
        ).all()
    }
    m_by_user: dict[uuid.UUID, list[Membership]] = {}
    for m in memberships:
        m_by_user.setdefault(m.user_id, []).append(m)

    result: list[UserWithMembershipsOut] = []
    for u in users.values():
        ms = [
            MembershipOut(
                id=m.id,
                user_id=m.user_id,
                organization_id=m.organization_id,
                organization_name=ctx.organization.name if ctx.organization else None,
                organization_slug=ctx.organization.slug if ctx.organization else None,
                role=m.role,
                is_active=m.is_active,
                department_ids=list(m.department_ids or []),
            )
            for m in m_by_user.get(u.id, [])
        ]
        out = UserWithMembershipsOut.model_validate(u)
        out.is_active = bool(
            u.is_active and any(m.is_active for m in m_by_user.get(u.id, []))
        )
        out.memberships = ms
        result.append(out)
    return result


def create_or_invite_user(ctx: AuthContext, req: UserCreateRequest) -> dict:
    ctx.require(P.USERS_MANAGE)
    if req.role == Role.PLATFORM_ADMIN and not ctx.user.is_platform_admin:
        raise Forbidden("Only platform administrators can assign platform_admin")

    email = req.email.strip().lower()
    user = ctx.db.scalar(select(User).where(User.email == email))
    is_new_user = user is None
    activation_delivery: dict | None = None

    if user is None:
        raw_pw = req.password
        if raw_pw is not None:
            problems = validate_password_strength(raw_pw)
            if problems:
                raise ValidationFailed("; ".join(problems))
            pw_hash = hash_password(raw_pw)
            activated = True
        else:
            # Lock with unguessable secret until activation token sets a real password
            pw_hash = hash_password(new_token(32))
            activated = False

        user = User(
            email=email,
            full_name=req.full_name.strip(),
            password_hash=pw_hash,
            is_active=True,
            is_platform_admin=(req.role == Role.PLATFORM_ADMIN),
            preferred_language=req.preferred_language,
            license_number=req.license_number,
        )
        ctx.db.add(user)
        ctx.db.flush()

        if not activated or req.send_activation_email:
            from app.services.messaging import account_link, delivery_view

            activation_delivery = delivery_view(
                account_link(ctx.db, user, "activation", organization_id=ctx.org_id)
            )

    existing_membership = ctx.db.scalar(
        select(Membership).where(
            Membership.user_id == user.id, Membership.organization_id == ctx.org_id
        )
    )
    if existing_membership is not None:
        raise Conflict("User already belongs to this organisation")

    membership = Membership(
        user_id=user.id,
        organization_id=ctx.org_id,
        role=req.role.value,
        is_active=True,
        department_ids=req.department_ids,
    )
    ctx.db.add(membership)
    ctx.db.flush()

    if not is_new_user and req.send_activation_email:
        from app.services.messaging import queue_email, public_link, delivery_view

        activation_delivery = delivery_view(
            queue_email(
                ctx.db,
                to=user.email,
                subject="You have been added to a Recova facility",
                body=f'You now have access to {ctx.organization.name}. Sign in with your existing password:\n{public_link("/login")}',
                category="membership",
                organization_id=ctx.org_id,
                user_id=user.id,
            )
        )

    ctx.audit(
        "user.add_to_org",
        "membership",
        membership.id,
        details={"email": user.email, "role": req.role.value},
    )
    ctx.db.commit()

    out = UserWithMembershipsOut.model_validate(user)
    out.memberships = [
        MembershipOut(
            id=membership.id,
            user_id=user.id,
            organization_id=ctx.org_id,
            organization_name=ctx.organization.name if ctx.organization else None,
            organization_slug=ctx.organization.slug if ctx.organization else None,
            role=membership.role,
            is_active=membership.is_active,
            department_ids=list(membership.department_ids or []),
        )
    ]
    return {"user": out, "activation": activation_delivery}


def update_org_user(
    ctx: AuthContext, user_id: uuid.UUID, req: UserUpdateRequest
) -> User:
    ctx.require(P.USERS_MANAGE)
    membership = ctx.db.scalar(
        select(Membership).where(
            Membership.user_id == user_id, Membership.organization_id == ctx.org_id
        )
    )
    if membership is None:
        raise NotFound("User is not a member of this organisation")
    user = ctx.db.get(User, user_id)
    assert user is not None

    if not ctx.user.is_platform_admin:
        if user.is_platform_admin:
            raise Forbidden(
                "Only platform administrators can change platform operator accounts"
            )
        shared = ctx.db.scalar(
            select(Membership.id).where(
                Membership.user_id == user.id, Membership.organization_id != ctx.org_id
            )
        )
        if shared and any(
            v is not None
            for v in (req.full_name, req.preferred_language, req.license_number)
        ):
            raise Forbidden(
                "Shared profile changes require the account owner or a platform administrator"
            )

    before = {
        "full_name": user.full_name,
        "is_active": user.is_active,
        "preferred_language": user.preferred_language,
        "membership_active": membership.is_active,
        "license_number": user.license_number,
    }
    if req.full_name is not None:
        user.full_name = req.full_name.strip()
    if req.is_active is not None:
        if user.id == ctx.user.id and not req.is_active:
            raise ValidationFailed("You cannot deactivate your own account")
        if ctx.user.is_platform_admin:
            user.is_active = req.is_active
        else:
            membership.is_active = req.is_active
        if not req.is_active:
            # Revoke active sessions immediately
            now = utcnow()
            for s in ctx.db.scalars(
                select(UserSession).where(
                    UserSession.user_id == user.id, UserSession.revoked_at.is_(None)
                )
            ).all():
                if ctx.user.is_platform_admin or s.active_organization_id == ctx.org_id:
                    s.revoked_at = now
    if req.preferred_language is not None:
        user.preferred_language = req.preferred_language
    if req.license_number is not None:
        user.license_number = req.license_number

    after = {
        "full_name": user.full_name,
        "is_active": user.is_active,
        "preferred_language": user.preferred_language,
        "membership_active": membership.is_active,
        "license_number": user.license_number,
    }
    ctx.audit("user.update", "user", user.id, changes=audit.diff(before, after))
    ctx.db.commit()
    return user


def update_membership(
    ctx: AuthContext, membership_id: uuid.UUID, req: MembershipUpdateRequest
) -> Membership:
    ctx.require(P.USERS_MANAGE)
    m = ctx.db.scalar(
        select(Membership).where(
            Membership.id == membership_id, Membership.organization_id == ctx.org_id
        )
    )
    if m is None:
        raise NotFound("Membership not found")
    before = {
        "role": m.role,
        "is_active": m.is_active,
        "department_ids": [str(d) for d in (m.department_ids or [])],
    }
    if req.role is not None:
        if req.role == Role.PLATFORM_ADMIN and not ctx.user.is_platform_admin:
            raise Forbidden("Only platform administrators can assign platform_admin")
        m.role = req.role.value
    if req.is_active is not None:
        if m.user_id == ctx.user.id and not req.is_active:
            raise ValidationFailed("You cannot deactivate your own membership")
        m.is_active = req.is_active
    if req.department_ids is not None:
        m.department_ids = req.department_ids

    after = {
        "role": m.role,
        "is_active": m.is_active,
        "department_ids": [str(d) for d in (m.department_ids or [])],
    }
    ctx.audit(
        "membership.update", "membership", m.id, changes=audit.diff(before, after)
    )
    ctx.db.commit()
    return m
