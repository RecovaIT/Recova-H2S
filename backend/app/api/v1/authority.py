"""Shared population-health notice publishing, scope governance, reporting, and recipient acknowledgement endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, Body, Depends
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.api.deps import AuthContext, get_auth_context, requires
from app.core.errors import Forbidden, NotFound, ValidationFailed
from app.core.permissions import P, Role
from app.models.base import utcnow
from app.models.clinical import Patient, TrackEnrollment
from app.models.enums import NoticeRecipientState
from app.models.identity import AuthorityScope, Membership, Organization, User
from app.models.ops import NoticeAcknowledgement, NoticeRecipient, PublicHealthNotice

notices_router = APIRouter(prefix="/notices", tags=["notices"])
authority_router = APIRouter(prefix="/authority", tags=["authority"])


class AuthorityScopeCreate(BaseModel):
    user_id: uuid.UUID
    organization_id: uuid.UUID | None = None
    assigned_emirates: list[str] = Field(default_factory=list)
    assigned_facility_ids: list[str] = Field(default_factory=list)
    can_publish: bool = True
    can_view_reports: bool = True
    min_suppression_k: int = Field(default=5, ge=3, le=50)


class AuthorityScopeOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    organization_id: uuid.UUID | None = None
    assigned_emirates: list[str]
    assigned_facility_ids: list[str]
    can_publish: bool
    can_view_reports: bool
    min_suppression_k: int
    is_active: bool


class NoticeCreate(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    message: str = Field(min_length=10, max_length=4000)
    plain_language_action: str | None = Field(default=None, max_length=1000)
    issuer: str = Field(default="Recova Public Health Authority", min_length=2, max_length=160)
    category: str = Field(default="advisory", max_length=60)
    severity: str = Field(default="info", pattern=r"^(info|advisory|urgent)$")
    scope_emirate: str | None = Field(default=None, max_length=80)
    facility_ids: list[str] = Field(default_factory=list)
    eligible_programmes: list[str] = Field(default_factory=lambda: ["core", "loop", "neuro", "worksafe"])
    acknowledgement_required: bool = True
    expires_in_days: int = Field(default=14, ge=1, le=365)
    starts_at: datetime | None = None
    idempotency_key: str | None = Field(default=None, max_length=120)


class NoticeUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=200)
    message: str | None = Field(default=None, min_length=10, max_length=4000)
    plain_language_action: str | None = Field(default=None, max_length=1000)
    category: str | None = Field(default=None, max_length=60)
    severity: str | None = Field(default=None, pattern=r"^(info|advisory|urgent)$")
    scope_emirate: str | None = Field(default=None, max_length=80)
    facility_ids: list[str] | None = None
    eligible_programmes: list[str] | None = None
    acknowledgement_required: bool | None = None


class NoticePublishOptions(BaseModel):
    idempotency_key: str | None = Field(default=None, max_length=120)
    external_channels: list[str] = Field(default_factory=list)


class NoticeOut(BaseModel):
    id: uuid.UUID
    title: str
    message: str
    plain_language_action: str | None = None
    issuer: str
    category: str
    severity: str
    scope_emirate: str | None = None
    facility_ids: list[str] = Field(default_factory=list)
    eligible_programmes: list[str]
    acknowledgement_required: bool
    status: str
    version: int
    starts_at: datetime | None = None
    published_at: datetime | None = None
    expires_at: datetime | None = None
    withdrawn_at: datetime | None = None
    acknowledgement_count: int = 0
    read_count: int = 0
    acknowledged: bool = False
    recipient_state: str | None = None
    read_at: datetime | None = None
    acknowledged_at: datetime | None = None


def _effective_status(notice: PublicHealthNotice, now: datetime) -> str:
    if notice.status == "published" and notice.expires_at and notice.expires_at <= now:
        return "expired"
    return notice.status


def _to_out(
    notice: PublicHealthNotice,
    *,
    now: datetime | None = None,
    ack_count: int = 0,
    read_count: int = 0,
    acknowledged: bool = False,
    recipient: NoticeRecipient | None = None,
) -> NoticeOut:
    ts = now or utcnow()
    eff_status = _effective_status(notice, ts)
    rec_state = recipient.state if recipient else ("acknowledged" if acknowledged else "available")
    return NoticeOut(
        id=notice.id,
        title=notice.title,
        message=notice.message,
        plain_language_action=notice.plain_language_action,
        issuer=notice.issuer,
        category=notice.category,
        severity=notice.severity,
        scope_emirate=notice.scope_emirate,
        facility_ids=list(notice.facility_ids or []),
        eligible_programmes=list(notice.eligible_programmes or []),
        acknowledgement_required=notice.acknowledgement_required,
        status=eff_status,
        version=notice.version,
        starts_at=notice.starts_at,
        published_at=notice.published_at,
        expires_at=notice.expires_at,
        withdrawn_at=notice.withdrawn_at,
        acknowledgement_count=ack_count,
        read_count=read_count,
        acknowledged=acknowledged or (rec_state == NoticeRecipientState.ACKNOWLEDGED.value),
        recipient_state=rec_state,
        read_at=recipient.read_at if recipient else None,
        acknowledged_at=recipient.acknowledged_at if recipient else None,
    )


def _active_authority_scope(
    ctx: AuthContext,
    *,
    for_publish: bool = False,
    for_reports: bool = False,
) -> AuthorityScope | None:
    if ctx.user.is_platform_admin:
        return None
    if ctx.role not in (Role.AUTHORITY_USER, Role.ORG_ADMIN):
        raise Forbidden("Authority notice management requires authority or administrator scope.")
    scope = ctx.db.scalar(
        select(AuthorityScope)
        .where(AuthorityScope.user_id == ctx.user.id, AuthorityScope.is_active.is_(True))
        .order_by(AuthorityScope.created_at.desc())
        .limit(1)
    )
    if scope is None:
        raise Forbidden("No active authority scope has been assigned to your account.")
    if for_publish and not scope.can_publish:
        raise Forbidden("Your assigned authority scope does not allow notice publishing.")
    if for_reports and not scope.can_view_reports:
        raise Forbidden("Your assigned authority scope does not allow population reporting.")
    return scope


def _validate_target_within_scope(
    scope: AuthorityScope | None,
    *,
    scope_emirate: str | None,
    facility_ids: list[str],
) -> None:
    if scope is None:
        return
    allowed_emirates = {e.strip().lower() for e in (scope.assigned_emirates or []) if e}
    allowed_facilities = {str(f) for f in (scope.assigned_facility_ids or []) if f}

    if allowed_emirates:
        if not scope_emirate:
            if not (facility_ids and allowed_facilities and set(facility_ids).issubset(allowed_facilities)):
                raise Forbidden("Authority scope requires targeting within your assigned emirate or facilities.")
        elif scope_emirate.strip().lower() not in allowed_emirates:
            raise Forbidden(f"Emirate '{scope_emirate}' is outside your assigned authority scope.")

    if allowed_facilities:
        if not facility_ids:
            if not (scope_emirate and allowed_emirates and scope_emirate.strip().lower() in allowed_emirates):
                raise Forbidden("Authority scope restricts publishing to assigned facilities.")
        elif not set(facility_ids).issubset(allowed_facilities):
            raise Forbidden("One or more selected facilities are outside your assigned authority scope.")


def _matching_orgs_and_audience(
    ctx: AuthContext,
    *,
    scope_emirate: str | None,
    facility_ids: list[str],
    eligible_programmes: list[str],
) -> tuple[list[Organization], list[Membership]]:
    orgs = ctx.db.scalars(select(Organization).where(Organization.is_active.is_(True))).all()
    prog_set = set(eligible_programmes or ["core", "loop", "neuro", "worksafe"])
    fac_set = set(str(f) for f in (facility_ids or []))
    matched_orgs: list[Organization] = []
    for org in orgs:
        if (org.settings or {}).get("synthetic_demo"):
            continue
        if scope_emirate and (not org.emirate or org.emirate.lower() != scope_emirate.lower()):
            continue
        if fac_set and str(org.id) not in fac_set:
            continue
        org_progs = set(org.enabled_tracks or [])
        if org.primary_programme:
            org_progs.add(org.primary_programme)
        if prog_set and org_progs and not (org_progs & prog_set):
            continue
        matched_orgs.append(org)

    if not matched_orgs:
        return [], []
    org_ids = [o.id for o in matched_orgs]
    mems = list(
        ctx.db.scalars(
            select(Membership).where(Membership.organization_id.in_(org_ids), Membership.is_active.is_(True))
        ).all()
    )
    return matched_orgs, mems


def _is_notice_visible_to_ctx(notice: PublicHealthNotice, org: Organization | None, ctx: AuthContext, now: datetime) -> bool:
    if _effective_status(notice, now) != "published":
        return False
    if notice.starts_at and notice.starts_at > now:
        return False
    if notice.scope_emirate:
        if org is None or not org.emirate or notice.scope_emirate.lower() != org.emirate.lower():
            return False
    if notice.facility_ids:
        if org is None or str(org.id) not in set(notice.facility_ids):
            return False
    org_progs = set(org.enabled_tracks or []) if org else set()
    if org and org.primary_programme:
        org_progs.add(org.primary_programme)
    if org_progs and notice.eligible_programmes and not (org_progs & set(notice.eligible_programmes)):
        return False
    return True


@notices_router.get("", response_model=list[NoticeOut])
def list_visible_notices(ctx: AuthContext = Depends(get_auth_context)):
    org = ctx.db.get(Organization, ctx.org_id)
    now = utcnow()
    rows = ctx.db.scalars(
        select(PublicHealthNotice)
        .where(PublicHealthNotice.status == "published")
        .order_by(PublicHealthNotice.published_at.desc())
    ).all()
    acked_ids = set(
        ctx.db.scalars(
            select(NoticeAcknowledgement.notice_id).where(NoticeAcknowledgement.user_id == ctx.user.id)
        ).all()
    )
    recs = {
        r.notice_id: r
        for r in ctx.db.scalars(select(NoticeRecipient).where(NoticeRecipient.user_id == ctx.user.id)).all()
    }
    visible: list[NoticeOut] = []
    for row in rows:
        if not _is_notice_visible_to_ctx(row, org, ctx, now):
            continue
        visible.append(_to_out(row, now=now, acknowledged=row.id in acked_ids, recipient=recs.get(row.id)))
    return visible


@notices_router.get("/{notice_id}", response_model=NoticeOut)
def get_visible_notice(notice_id: uuid.UUID, ctx: AuthContext = Depends(get_auth_context)):
    org = ctx.db.get(Organization, ctx.org_id)
    notice = ctx.db.get(PublicHealthNotice, notice_id)
    now = utcnow()
    if notice is None or not _is_notice_visible_to_ctx(notice, org, ctx, now):
        raise NotFound("Notice not found")
    rec = ctx.db.scalar(
        select(NoticeRecipient).where(NoticeRecipient.notice_id == notice_id, NoticeRecipient.user_id == ctx.user.id)
    )
    ack = ctx.db.scalar(
        select(NoticeAcknowledgement.id).where(
            NoticeAcknowledgement.notice_id == notice_id, NoticeAcknowledgement.user_id == ctx.user.id
        )
    )
    return _to_out(notice, now=now, acknowledged=ack is not None, recipient=rec)


@notices_router.post("/{notice_id}/read")
def mark_notice_read(notice_id: uuid.UUID, ctx: AuthContext = Depends(get_auth_context)):
    org = ctx.db.get(Organization, ctx.org_id)
    notice = ctx.db.get(PublicHealthNotice, notice_id)
    now = utcnow()
    if notice is None or not _is_notice_visible_to_ctx(notice, org, ctx, now):
        raise NotFound("Published notice not found")
    rec = ctx.db.scalar(
        select(NoticeRecipient).where(NoticeRecipient.notice_id == notice_id, NoticeRecipient.user_id == ctx.user.id)
    )
    if rec is None:
        rec = NoticeRecipient(
            notice_id=notice_id,
            user_id=ctx.user.id,
            organization_id=ctx.org_id,
            state=NoticeRecipientState.READ.value,
            read_at=now,
        )
        ctx.db.add(rec)
    elif rec.state == NoticeRecipientState.AVAILABLE.value:
        rec.state = NoticeRecipientState.READ.value
        rec.read_at = rec.read_at or now
    ctx.audit("notice.read", "public_health_notice", notice_id)
    ctx.db.commit()
    return {"notice_id": str(notice_id), "state": rec.state, "read_at": rec.read_at}


@notices_router.post("/{notice_id}/acknowledgements")
def acknowledge_notice(notice_id: uuid.UUID, ctx: AuthContext = Depends(get_auth_context)):
    org = ctx.db.get(Organization, ctx.org_id)
    notice = ctx.db.get(PublicHealthNotice, notice_id)
    now = utcnow()
    if notice is None or not _is_notice_visible_to_ctx(notice, org, ctx, now):
        raise NotFound("Published notice not found")
    existing = ctx.db.scalar(
        select(NoticeAcknowledgement).where(
            NoticeAcknowledgement.notice_id == notice_id,
            NoticeAcknowledgement.user_id == ctx.user.id,
        )
    )
    rec = ctx.db.scalar(
        select(NoticeRecipient).where(NoticeRecipient.notice_id == notice_id, NoticeRecipient.user_id == ctx.user.id)
    )
    if existing is None:
        ack = NoticeAcknowledgement(
            notice_id=notice_id,
            user_id=ctx.user.id,
            organization_id=ctx.org_id,
            acknowledged_at=now,
        )
        ctx.db.add(ack)
        if rec is None:
            ctx.db.add(
                NoticeRecipient(
                    notice_id=notice_id,
                    user_id=ctx.user.id,
                    organization_id=ctx.org_id,
                    state=NoticeRecipientState.ACKNOWLEDGED.value,
                    read_at=now,
                    acknowledged_at=now,
                )
            )
        else:
            rec.state = NoticeRecipientState.ACKNOWLEDGED.value
            rec.read_at = rec.read_at or now
            rec.acknowledged_at = now
        ctx.audit("notice.acknowledge", "public_health_notice", notice_id)
        ctx.db.commit()
        return {"notice_id": str(notice_id), "acknowledged": True, "acknowledged_at": ack.acknowledged_at}
    return {"notice_id": str(notice_id), "acknowledged": True, "acknowledged_at": existing.acknowledged_at}


# --- Authority Scope Administration ---
@authority_router.get("/scopes", response_model=list[AuthorityScopeOut])
def list_authority_scopes(ctx: AuthContext = Depends(get_auth_context)):
    if ctx.user.is_platform_admin:
        rows = ctx.db.scalars(select(AuthorityScope).order_by(AuthorityScope.created_at.desc())).all()
    else:
        rows = ctx.db.scalars(
            select(AuthorityScope).where(AuthorityScope.user_id == ctx.user.id, AuthorityScope.is_active.is_(True))
        ).all()
    return [
        AuthorityScopeOut(
            id=r.id,
            user_id=r.user_id,
            organization_id=r.organization_id,
            assigned_emirates=list(r.assigned_emirates or []),
            assigned_facility_ids=list(r.assigned_facility_ids or []),
            can_publish=r.can_publish,
            can_view_reports=r.can_view_reports,
            min_suppression_k=r.min_suppression_k,
            is_active=r.is_active,
        )
        for r in rows
    ]


@authority_router.post("/scopes", response_model=AuthorityScopeOut, status_code=201)
def create_authority_scope(req: AuthorityScopeCreate, ctx: AuthContext = Depends(requires(P.PLATFORM_ADMIN))):
    target_user = ctx.db.get(User, req.user_id)
    if target_user is None:
        raise NotFound("User not found")
    scope = AuthorityScope(
        user_id=req.user_id,
        organization_id=req.organization_id,
        assigned_emirates=[e.strip() for e in req.assigned_emirates if e.strip()],
        assigned_facility_ids=[str(f) for f in req.assigned_facility_ids],
        can_publish=req.can_publish,
        can_view_reports=req.can_view_reports,
        min_suppression_k=req.min_suppression_k,
        is_active=True,
        granted_by_id=ctx.user.id,
    )
    ctx.db.add(scope)
    ctx.db.flush()
    ctx.audit(
        "authority.scope.assign",
        "authority_scope",
        scope.id,
        details={
            "user_id": str(req.user_id),
            "emirates": scope.assigned_emirates,
            "facilities": scope.assigned_facility_ids,
        },
    )
    ctx.db.commit()
    return AuthorityScopeOut(
        id=scope.id,
        user_id=scope.user_id,
        organization_id=scope.organization_id,
        assigned_emirates=list(scope.assigned_emirates or []),
        assigned_facility_ids=list(scope.assigned_facility_ids or []),
        can_publish=scope.can_publish,
        can_view_reports=scope.can_view_reports,
        min_suppression_k=scope.min_suppression_k,
        is_active=scope.is_active,
    )


@authority_router.delete("/scopes/{scope_id}")
def revoke_authority_scope(scope_id: uuid.UUID, ctx: AuthContext = Depends(requires(P.PLATFORM_ADMIN))):
    scope = ctx.db.get(AuthorityScope, scope_id)
    if scope is None:
        raise NotFound("Authority scope not found")
    scope.is_active = False
    ctx.audit("authority.scope.revoke", "authority_scope", scope.id, details={"user_id": str(scope.user_id)})
    ctx.db.commit()
    return {"revoked": True, "id": str(scope.id)}


# --- Authority Notice Lifecycle ---
@authority_router.get("/notices", response_model=list[NoticeOut])
def list_authority_notices(ctx: AuthContext = Depends(get_auth_context)):
    scope = _active_authority_scope(ctx)
    now = utcnow()
    rows = ctx.db.scalars(select(PublicHealthNotice).order_by(PublicHealthNotice.created_at.desc())).all()
    if scope is not None:
        allowed_em = {e.lower() for e in (scope.assigned_emirates or [])}
        allowed_fac = set(str(f) for f in (scope.assigned_facility_ids or []))
        filtered = []
        for r in rows:
            if allowed_em and (not r.scope_emirate or r.scope_emirate.lower() not in allowed_em):
                if not (allowed_fac and r.facility_ids and set(r.facility_ids).issubset(allowed_fac)):
                    continue
            if allowed_fac and not (r.facility_ids and set(r.facility_ids).issubset(allowed_fac)):
                if not (allowed_em and r.scope_emirate and r.scope_emirate.lower() in allowed_em):
                    continue
            filtered.append(r)
        rows = filtered

    ack_counts = dict(
        ctx.db.execute(
            select(NoticeAcknowledgement.notice_id, func.count(NoticeAcknowledgement.id))
            .group_by(NoticeAcknowledgement.notice_id)
        ).all()
    )
    read_counts = dict(
        ctx.db.execute(
            select(NoticeRecipient.notice_id, func.count(NoticeRecipient.id))
            .where(NoticeRecipient.state.in_([NoticeRecipientState.READ.value, NoticeRecipientState.ACKNOWLEDGED.value]))
            .group_by(NoticeRecipient.notice_id)
        ).all()
    )
    return [
        _to_out(
            r,
            now=now,
            ack_count=int(ack_counts.get(r.id, 0)),
            read_count=int(read_counts.get(r.id, 0)),
        )
        for r in rows
    ]


@authority_router.post("/notices/preview")
def preview_draft_payload(req: NoticeCreate, ctx: AuthContext = Depends(get_auth_context)):
    scope = _active_authority_scope(ctx, for_publish=True)
    _validate_target_within_scope(scope, scope_emirate=req.scope_emirate, facility_ids=req.facility_ids)
    orgs, mems = _matching_orgs_and_audience(
        ctx,
        scope_emirate=req.scope_emirate,
        facility_ids=req.facility_ids,
        eligible_programmes=req.eligible_programmes,
    )
    unique_users = {m.user_id for m in mems}
    return {
        "title": req.title.strip(),
        "message": req.message.strip(),
        "severity": req.severity,
        "scope_emirate": req.scope_emirate,
        "facility_ids": req.facility_ids,
        "eligible_programmes": req.eligible_programmes,
        "organization_count": len(orgs),
        "recipient_count": len(unique_users),
        "organizations": [{"id": str(o.id), "name": o.name, "emirate": o.emirate} for o in orgs],
    }


@authority_router.post("/notices", response_model=NoticeOut, status_code=201)
def create_authority_notice(req: NoticeCreate, ctx: AuthContext = Depends(get_auth_context)):
    scope = _active_authority_scope(ctx, for_publish=True)
    _validate_target_within_scope(scope, scope_emirate=req.scope_emirate, facility_ids=req.facility_ids)

    idem = req.idempotency_key.strip() if req.idempotency_key else None
    if idem:
        existing = ctx.db.scalar(select(PublicHealthNotice).where(PublicHealthNotice.idempotency_key == idem))
        if existing is not None:
            return _to_out(existing)

    now = utcnow()
    notice = PublicHealthNotice(
        organization_id=ctx.organization.id if ctx.organization else None,
        title=req.title.strip(),
        message=req.message.strip(),
        plain_language_action=req.plain_language_action.strip() if req.plain_language_action else None,
        issuer=req.issuer.strip(),
        category=req.category.strip(),
        severity=req.severity,
        scope_emirate=req.scope_emirate.strip() if req.scope_emirate else None,
        facility_ids=[str(f) for f in req.facility_ids],
        eligible_programmes=req.eligible_programmes,
        acknowledgement_required=req.acknowledgement_required,
        status="draft",
        version=1,
        idempotency_key=idem,
        starts_at=req.starts_at or now,
        expires_at=now + timedelta(days=req.expires_in_days),
        created_by_id=ctx.user.id,
    )
    ctx.db.add(notice)
    try:
        ctx.db.flush()
    except IntegrityError:
        ctx.db.rollback()
        if idem:
            existing = ctx.db.scalar(select(PublicHealthNotice).where(PublicHealthNotice.idempotency_key == idem))
            if existing is not None:
                return _to_out(existing)
        raise
    ctx.audit("authority.notice.create_draft", "public_health_notice", notice.id, details={"severity": notice.severity})
    ctx.db.commit()
    ctx.db.refresh(notice)
    return _to_out(notice, now=now)


@authority_router.post("/notices/{notice_id}/preview")
def preview_existing_notice(notice_id: uuid.UUID, ctx: AuthContext = Depends(get_auth_context)):
    scope = _active_authority_scope(ctx, for_publish=True)
    notice = ctx.db.get(PublicHealthNotice, notice_id)
    if notice is None:
        raise NotFound("Notice not found")
    _validate_target_within_scope(scope, scope_emirate=notice.scope_emirate, facility_ids=list(notice.facility_ids or []))
    orgs, mems = _matching_orgs_and_audience(
        ctx,
        scope_emirate=notice.scope_emirate,
        facility_ids=list(notice.facility_ids or []),
        eligible_programmes=list(notice.eligible_programmes or []),
    )
    unique_users = {m.user_id for m in mems}
    return {
        "notice_id": str(notice.id),
        "status": _effective_status(notice, utcnow()),
        "version": notice.version,
        "title": notice.title,
        "message": notice.message,
        "organization_count": len(orgs),
        "recipient_count": len(unique_users),
        "organizations": [{"id": str(o.id), "name": o.name, "emirate": o.emirate} for o in orgs],
    }


@authority_router.patch("/notices/{notice_id}", response_model=NoticeOut)
def update_authority_notice(notice_id: uuid.UUID, req: NoticeUpdate, ctx: AuthContext = Depends(get_auth_context)):
    scope = _active_authority_scope(ctx, for_publish=True)
    notice = ctx.db.get(PublicHealthNotice, notice_id)
    if notice is None:
        raise NotFound("Notice not found")
    if notice.status == "withdrawn":
        raise ValidationFailed("Withdrawn notices cannot be edited.")

    new_emirate = req.scope_emirate.strip() if req.scope_emirate is not None else notice.scope_emirate
    new_facilities = [str(f) for f in req.facility_ids] if req.facility_ids is not None else list(notice.facility_ids or [])
    _validate_target_within_scope(scope, scope_emirate=new_emirate, facility_ids=new_facilities)

    if req.title is not None:
        notice.title = req.title.strip()
    if req.message is not None:
        notice.message = req.message.strip()
    if req.plain_language_action is not None:
        notice.plain_language_action = req.plain_language_action.strip()
    if req.category is not None:
        notice.category = req.category.strip()
    if req.severity is not None:
        notice.severity = req.severity
    if req.scope_emirate is not None:
        notice.scope_emirate = new_emirate
    if req.facility_ids is not None:
        notice.facility_ids = new_facilities
    if req.eligible_programmes is not None:
        notice.eligible_programmes = req.eligible_programmes
    if req.acknowledgement_required is not None:
        notice.acknowledgement_required = req.acknowledgement_required

    if notice.status == "published":
        notice.version += 1
        ctx.audit("authority.notice.revise", "public_health_notice", notice.id, details={"version": notice.version})
    else:
        ctx.audit("authority.notice.update_draft", "public_health_notice", notice.id, details={"version": notice.version})
    ctx.db.commit()
    ctx.db.refresh(notice)
    return _to_out(notice)


@authority_router.post("/notices/{notice_id}/publish", response_model=NoticeOut)
def publish_authority_notice(
    notice_id: uuid.UUID,
    opts: NoticePublishOptions | None = Body(default=None),
    ctx: AuthContext = Depends(get_auth_context),
):
    scope = _active_authority_scope(ctx, for_publish=True)
    notice = ctx.db.get(PublicHealthNotice, notice_id)
    if notice is None:
        raise NotFound("Notice not found")
    _validate_target_within_scope(scope, scope_emirate=notice.scope_emirate, facility_ids=list(notice.facility_ids or []))
    if notice.status == "withdrawn":
        raise ValidationFailed("Withdrawn notices cannot be republished; create a new draft.")

    now = utcnow()
    if notice.expires_at and notice.expires_at <= now:
        raise ValidationFailed("Expired notices cannot be published.")

    # Idempotent if already published with matching idempotency_key or repeat publish on same version
    if notice.status == "published":
        return _to_out(notice, now=now)

    orgs, mems = _matching_orgs_and_audience(
        ctx,
        scope_emirate=notice.scope_emirate,
        facility_ids=list(notice.facility_ids or []),
        eligible_programmes=list(notice.eligible_programmes or []),
    )

    notice.status = "published"
    notice.published_at = now

    # Create scoped available NoticeRecipient records
    org_map = {o.id: o for o in orgs}
    seen_users: set[uuid.UUID] = set()
    for m in mems:
        if m.user_id in seen_users:
            continue
        seen_users.add(m.user_id)
        existing_rec = ctx.db.scalar(
            select(NoticeRecipient).where(NoticeRecipient.notice_id == notice.id, NoticeRecipient.user_id == m.user_id)
        )
        if existing_rec is None:
            ctx.db.add(
                NoticeRecipient(
                    notice_id=notice.id,
                    user_id=m.user_id,
                    organization_id=m.organization_id,
                    state=NoticeRecipientState.AVAILABLE.value,
                    provider_delivery_status="in_app_available",
                )
            )

    # Optional external channels (POP08): only dispatch when org permits channel and adapter is configured
    requested_channels = (opts.external_channels if opts else []) or []
    if requested_channels:
        from app.integrations.notifications import dispatch_notification
        from app.models.enums import NotificationChannel

        for org_id, org in org_map.items():
            permitted = set((org.settings or {}).get("permitted_channels") or ["in_app"])
            for ch_name in requested_channels:
                if ch_name not in permitted or ch_name == "in_app":
                    continue
                if ch_name not in {c.value for c in NotificationChannel}:
                    continue
                org_mems = [m for m in mems if m.organization_id == org_id and m.role != Role.PATIENT.value]
                for m in org_mems[:5]:
                    u = ctx.db.get(User, m.user_id)
                    if u and u.is_active:
                        dispatch_notification(
                            ctx.db,
                            organization_id=org_id,
                            channel=ch_name,
                            category="public_health_notice",
                            subject=notice.title,
                            body=notice.message,
                            recipient_user=u,
                            idempotency_key=f"notice:{notice.id}:v{notice.version}:u:{u.id}:{ch_name}",
                        )

    ctx.audit(
        "authority.notice.publish",
        "public_health_notice",
        notice.id,
        details={
            "version": notice.version,
            "organization_count": len(orgs),
            "recipient_count": len(seen_users),
        },
    )
    ctx.db.commit()
    ctx.db.refresh(notice)
    return _to_out(notice, now=now)


@authority_router.post("/notices/{notice_id}/withdraw", response_model=NoticeOut)
def withdraw_authority_notice(notice_id: uuid.UUID, ctx: AuthContext = Depends(get_auth_context)):
    scope = _active_authority_scope(ctx, for_publish=True)
    notice = ctx.db.get(PublicHealthNotice, notice_id)
    if notice is None:
        raise NotFound("Notice not found")
    _validate_target_within_scope(scope, scope_emirate=notice.scope_emirate, facility_ids=list(notice.facility_ids or []))
    notice.status = "withdrawn"
    notice.withdrawn_at = utcnow()
    notice.withdrawn_by_id = ctx.user.id
    ctx.audit("authority.notice.withdraw", "public_health_notice", notice.id, details={"version": notice.version})
    ctx.db.commit()
    ctx.db.refresh(notice)
    return _to_out(notice)


@authority_router.get("/reports")
def authority_population_reports(ctx: AuthContext = Depends(get_auth_context)):
    """Aggregate population-health notice delivery and programme counts with k-anonymity suppression (POP07)."""
    scope = _active_authority_scope(ctx, for_reports=True)
    k_threshold = scope.min_suppression_k if scope else 5
    now = utcnow()

    orgs = ctx.db.scalars(select(Organization).where(Organization.is_active.is_(True))).all()
    scoped_orgs: list[Organization] = []
    allowed_em = {e.lower() for e in (scope.assigned_emirates or [])} if scope else set()
    allowed_fac = set(str(f) for f in (scope.assigned_facility_ids or [])) if scope else set()

    for o in orgs:
        if (o.settings or {}).get("synthetic_demo"):
            continue
        if scope is not None:
            em_ok = not allowed_em or (o.emirate and o.emirate.lower() in allowed_em)
            fac_ok = not allowed_fac or str(o.id) in allowed_fac
            if not (em_ok and fac_ok):
                continue
        scoped_orgs.append(o)

    scoped_org_ids = [o.id for o in scoped_orgs]
    programme_summary: dict[str, dict] = {}
    if scoped_org_ids:
        pat_counts = dict(
            ctx.db.execute(
                select(TrackEnrollment.track, func.count(TrackEnrollment.id))
                .join(Patient, Patient.id == TrackEnrollment.patient_id)
                .where(
                    TrackEnrollment.organization_id.in_(scoped_org_ids),
                    TrackEnrollment.status == "active",
                    Patient.is_active.is_(True),
                    Patient.is_synthetic.is_(False),
                )
                .group_by(TrackEnrollment.track)
            ).all()
        )
        for prog in ("core", "loop", "neuro", "worksafe"):
            cnt = int(pat_counts.get(prog, 0))
            suppressed = 0 < cnt < k_threshold
            programme_summary[prog] = {
                "participant_count": None if suppressed else cnt,
                "suppressed_k_anonymity": suppressed,
                "k_threshold": k_threshold,
            }

    notices = ctx.db.scalars(select(PublicHealthNotice).order_by(PublicHealthNotice.created_at.desc()).limit(50)).all()
    notice_summaries = []
    for n in notices:
        if scope is not None:
            if allowed_em and (not n.scope_emirate or n.scope_emirate.lower() not in allowed_em):
                continue
            if allowed_fac and not (n.facility_ids and set(n.facility_ids).issubset(allowed_fac)):
                continue
        total_rec = ctx.db.scalar(
            select(func.count(NoticeRecipient.id)).where(NoticeRecipient.notice_id == n.id)
        ) or 0
        read_rec = ctx.db.scalar(
            select(func.count(NoticeRecipient.id)).where(
                NoticeRecipient.notice_id == n.id,
                NoticeRecipient.state.in_([NoticeRecipientState.READ.value, NoticeRecipientState.ACKNOWLEDGED.value]),
            )
        ) or 0
        ack_rec = ctx.db.scalar(
            select(func.count(NoticeAcknowledgement.id)).where(NoticeAcknowledgement.notice_id == n.id)
        ) or 0
        suppressed_notice = 0 < int(total_rec) < k_threshold
        notice_summaries.append(
            {
                "notice_id": str(n.id),
                "title": n.title,
                "status": _effective_status(n, now),
                "version": n.version,
                "scope_emirate": n.scope_emirate,
                "suppressed_k_anonymity": suppressed_notice,
                "recipient_count": None if suppressed_notice else int(total_rec),
                "read_count": None if suppressed_notice else int(read_rec),
                "acknowledgement_count": None if suppressed_notice else int(ack_rec),
            }
        )

    return {
        "k_threshold": k_threshold,
        "scoped_organization_count": len(scoped_orgs),
        "programme_summary": programme_summary,
        "notice_summaries": notice_summaries,
    }
