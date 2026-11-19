"""Organisations, users, RBAC overrides, audit logs and background jobs endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select

from app.api.deps import AuthContext, get_auth_context, requires
from app.core.errors import Conflict, Forbidden, NotFound, ValidationFailed
from app.core.permissions import ALL_PERMISSIONS, P, Role
from app.models.base import utcnow
from app.models.identity import Organization, ProgrammeRequest
from app.models.ops import AuditEvent, Job
from app.schemas.common import Message, Page, PageParams, paginate
from app.schemas.identity import (
    AuditEventOut,
    JobOut,
    MembershipOut,
    MembershipUpdateRequest,
    OrganizationCreate,
    OrganizationOut,
    OrganizationUpdate,
    PrimaryProgrammeSelectionRequest,
    ProgrammeRequestCreate,
    ProgrammeRequestOut,
    ProgrammeRequestReview,
    RolePermissionOverrideInput,
    RolePermissionView,
    UserCreateRequest,
    UserOut,
    UserUpdateRequest,
    UserWithMembershipsOut,
)
from app.services import organizations as org_svc

orgs_router = APIRouter(prefix="/organizations", tags=["organizations"])
users_router = APIRouter(prefix="/users", tags=["users"])
audit_router = APIRouter(prefix="/audit-logs", tags=["audit-logs"])


@orgs_router.get("", response_model=list[OrganizationOut])
def list_organizations(ctx: AuthContext = Depends(get_auth_context)):
    return org_svc.list_organizations(ctx)


@orgs_router.post("", response_model=OrganizationOut, status_code=201)
def create_organization(req: OrganizationCreate, ctx: AuthContext = Depends(get_auth_context)):
    return org_svc.create_organization(ctx, req)


@orgs_router.patch("/{organization_id}", response_model=OrganizationOut)
def update_organization(organization_id: uuid.UUID, req: OrganizationUpdate, ctx: AuthContext = Depends(get_auth_context)):
    return org_svc.update_organization(ctx, organization_id, req)


@orgs_router.post("/{organization_id}/select-primary-programme", response_model=OrganizationOut)
def select_primary_programme(
    organization_id: uuid.UUID,
    req: PrimaryProgrammeSelectionRequest,
    ctx: AuthContext = Depends(get_auth_context),
):
    return org_svc.select_primary_programme(ctx, organization_id, req)


@orgs_router.get("/permissions/catalog")
def list_all_permissions(ctx: AuthContext = Depends(requires(P.ORG_READ))):
    return {"permissions": sorted(ALL_PERMISSIONS)}


@orgs_router.get("/permissions/roles", response_model=list[RolePermissionView])
def list_role_permissions(ctx: AuthContext = Depends(requires(P.ORG_READ))):
    return org_svc.list_role_permissions(ctx)


@orgs_router.post("/permissions/overrides")
def set_role_override(req: RolePermissionOverrideInput, ctx: AuthContext = Depends(requires(P.ORG_MANAGE))):
    return org_svc.set_role_permission_override(ctx, req)


@orgs_router.delete("/permissions/overrides", response_model=Message)
def delete_role_override(role: Role, permission: str, ctx: AuthContext = Depends(requires(P.ORG_MANAGE))):
    org_svc.delete_role_permission_override(ctx, role, permission)
    return Message(message="Permission override removed")


@orgs_router.get("/programme-requests", response_model=list[ProgrammeRequestOut])
def list_programme_requests(ctx: AuthContext = Depends(requires(P.ORG_READ))):
    stmt = select(ProgrammeRequest).order_by(ProgrammeRequest.created_at.desc())
    if not ctx.user.is_platform_admin:
        stmt = stmt.where(ProgrammeRequest.organization_id == ctx.org_id)
    rows = ctx.db.scalars(stmt).all()
    org_names = {
        o.id: o.name
        for o in ctx.db.scalars(select(Organization)).all()
    }
    out: list[ProgrammeRequestOut] = []
    for row in rows:
        item = ProgrammeRequestOut.model_validate(row)
        item.organization_name = org_names.get(row.organization_id)
        out.append(item)
    return out


@orgs_router.post("/programme-requests", response_model=ProgrammeRequestOut, status_code=201)
def create_programme_request(req: ProgrammeRequestCreate, ctx: AuthContext = Depends(requires(P.ORG_MANAGE))):
    org = ctx.db.get(Organization, ctx.org_id)
    if org is None:
        raise NotFound("Organisation not found")
    if req.requested_programme.value in (org.enabled_tracks or []):
        raise Conflict(f"Programme '{req.requested_programme.value}' is already enabled for this organisation.")
    existing = ctx.db.scalar(
        select(ProgrammeRequest).where(
            ProgrammeRequest.organization_id == ctx.org_id,
            ProgrammeRequest.requested_programme == req.requested_programme.value,
            ProgrammeRequest.status == "pending",
        )
    )
    if existing is not None:
        raise Conflict("A pending request for this programme already exists.")
    pr = ProgrammeRequest(
        organization_id=ctx.org_id,
        requested_programme=req.requested_programme.value,
        justification=req.justification.strip(),
        status="pending",
        requested_by_id=ctx.user.id,
    )
    ctx.db.add(pr)
    ctx.db.flush()
    ctx.audit("organization.programme_request.create", "programme_request", pr.id, details={"requested_programme": pr.requested_programme})
    ctx.db.commit()
    ctx.db.refresh(pr)
    out = ProgrammeRequestOut.model_validate(pr)
    out.organization_name = org.name
    return out


@orgs_router.post("/programme-requests/{request_id}/review", response_model=ProgrammeRequestOut)
def review_programme_request(request_id: uuid.UUID, req: ProgrammeRequestReview, ctx: AuthContext = Depends(get_auth_context)):
    if not ctx.user.is_platform_admin:
        raise Forbidden("Only platform administrators can approve or reject additional programme requests.")
    pr = ctx.db.get(ProgrammeRequest, request_id)
    if pr is None:
        raise NotFound("Programme request not found")
    if pr.status != "pending":
        raise ValidationFailed(f"Programme request is already {pr.status}")
    pr.status = req.decision
    pr.reviewed_by_id = ctx.user.id
    pr.reviewed_at = utcnow()
    pr.review_note = req.review_note
    org = ctx.db.get(Organization, pr.organization_id)
    if req.decision == "approved" and org is not None:
        tracks = list(org.enabled_tracks or [])
        if pr.requested_programme not in tracks:
            tracks.append(pr.requested_programme)
            org.enabled_tracks = tracks
    ctx.audit(
        f"organization.programme_request.{req.decision}",
        "programme_request",
        pr.id,
        details={"requested_programme": pr.requested_programme, "organization_id": str(pr.organization_id)},
    )
    ctx.db.commit()
    ctx.db.refresh(pr)
    out = ProgrammeRequestOut.model_validate(pr)
    out.organization_name = org.name if org else None
    return out


@users_router.get("", response_model=list[UserWithMembershipsOut])
def list_users(ctx: AuthContext = Depends(requires(P.USERS_READ))):
    return org_svc.list_org_users(ctx)


@users_router.post("", status_code=201)
def create_user(req: UserCreateRequest, ctx: AuthContext = Depends(requires(P.USERS_MANAGE))):
    return org_svc.create_or_invite_user(ctx, req)


@users_router.patch("/{user_id}", response_model=UserOut)
def update_user(user_id: uuid.UUID, req: UserUpdateRequest, ctx: AuthContext = Depends(requires(P.USERS_MANAGE))):
    return org_svc.update_org_user(ctx, user_id, req)


@users_router.patch("/memberships/{membership_id}", response_model=MembershipOut)
def update_membership(membership_id: uuid.UUID, req: MembershipUpdateRequest, ctx: AuthContext = Depends(requires(P.USERS_MANAGE))):
    return org_svc.update_membership(ctx, membership_id, req)


@audit_router.get("", response_model=Page[AuditEventOut])
def list_audit_logs(
    params: PageParams = Depends(),
    action: str | None = Query(None),
    resource_type: str | None = Query(None),
    patient_id: uuid.UUID | None = Query(None),
    outcome: str | None = Query(None),
    ctx: AuthContext = Depends(requires(P.AUDIT_READ)),
):
    stmt = select(AuditEvent).where(AuditEvent.organization_id == ctx.org_id)
    if action:
        stmt = stmt.where(AuditEvent.action.ilike(f"%{action}%"))
    if resource_type:
        stmt = stmt.where(AuditEvent.resource_type == resource_type)
    if patient_id:
        stmt = stmt.where(AuditEvent.patient_id == patient_id)
    if outcome:
        stmt = stmt.where(AuditEvent.outcome == outcome)
    return paginate(
        ctx.db,
        stmt,
        params,
        sortable={"occurred_at": AuditEvent.occurred_at, "action": AuditEvent.action},
        default_sort=AuditEvent.occurred_at.desc(),
    )


@audit_router.get("/jobs", response_model=Page[JobOut])
def list_jobs(
    params: PageParams = Depends(),
    status: str | None = Query(None),
    ctx: AuthContext = Depends(requires(P.ORG_READ)),
):
    stmt = select(Job).where(Job.organization_id == ctx.org_id)
    if status:
        stmt = stmt.where(Job.status == status)
    return paginate(
        ctx.db,
        stmt,
        params,
        sortable={"created_at": Job.created_at, "status": Job.status},
        default_sort=Job.created_at.desc(),
    )
