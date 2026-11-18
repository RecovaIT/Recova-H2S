"""Shared population-health notice publishing and recipient acknowledgement endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.api.deps import AuthContext, get_auth_context, requires
from app.core.errors import Forbidden, NotFound, ValidationFailed
from app.core.permissions import P
from app.models.base import utcnow
from app.models.identity import Organization
from app.models.ops import NoticeAcknowledgement, PublicHealthNotice

notices_router = APIRouter(prefix="/notices", tags=["notices"])
authority_router = APIRouter(prefix="/authority", tags=["authority"])


class NoticeCreate(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    message: str = Field(min_length=10, max_length=4000)
    plain_language_action: str | None = Field(default=None, max_length=1000)
    issuer: str = Field(default="Recova Public Health Authority", min_length=2, max_length=160)
    category: str = Field(default="advisory", max_length=60)
    severity: str = Field(default="info", pattern=r"^(info|advisory|urgent)$")
    scope_emirate: str | None = Field(default=None, max_length=80)
    eligible_programmes: list[str] = Field(default_factory=lambda: ["core", "loop", "neuro", "worksafe"])
    acknowledgement_required: bool = True
    expires_in_days: int = Field(default=14, ge=1, le=365)


class NoticeOut(BaseModel):
    id: uuid.UUID
    title: str
    message: str
    plain_language_action: str | None = None
    issuer: str
    category: str
    severity: str
    scope_emirate: str | None = None
    eligible_programmes: list[str]
    acknowledgement_required: bool
    status: str
    version: int
    published_at: datetime | None = None
    expires_at: datetime | None = None
    acknowledgement_count: int = 0
    acknowledged: bool = False


def _to_out(notice: PublicHealthNotice, ack_count: int = 0, acknowledged: bool = False) -> NoticeOut:
    return NoticeOut(
        id=notice.id,
        title=notice.title,
        message=notice.message,
        plain_language_action=notice.plain_language_action,
        issuer=notice.issuer,
        category=notice.category,
        severity=notice.severity,
        scope_emirate=notice.scope_emirate,
        eligible_programmes=list(notice.eligible_programmes or []),
        acknowledgement_required=notice.acknowledgement_required,
        status=notice.status,
        version=notice.version,
        published_at=notice.published_at,
        expires_at=notice.expires_at,
        acknowledgement_count=ack_count,
        acknowledged=acknowledged,
    )


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
    org_tracks = set(org.enabled_tracks or []) if org else set()
    visible: list[NoticeOut] = []
    for row in rows:
        if row.expires_at and row.expires_at < now:
            continue
        if row.scope_emirate and org and org.emirate and row.scope_emirate.lower() != org.emirate.lower():
            continue
        if org_tracks and row.eligible_programmes and not (org_tracks & set(row.eligible_programmes)):
            continue
        visible.append(_to_out(row, acknowledged=row.id in acked_ids))
    return visible


@notices_router.post("/{notice_id}/acknowledgements")
def acknowledge_notice(notice_id: uuid.UUID, ctx: AuthContext = Depends(get_auth_context)):
    notice = ctx.db.get(PublicHealthNotice, notice_id)
    if notice is None or notice.status != "published":
        raise NotFound("Published notice not found")
    existing = ctx.db.scalar(
        select(NoticeAcknowledgement).where(
            NoticeAcknowledgement.notice_id == notice_id,
            NoticeAcknowledgement.user_id == ctx.user.id,
        )
    )
    if existing is None:
        ack = NoticeAcknowledgement(
            notice_id=notice_id,
            user_id=ctx.user.id,
            organization_id=ctx.org_id,
            acknowledged_at=utcnow(),
        )
        ctx.db.add(ack)
        ctx.audit("notice.acknowledge", "public_health_notice", notice_id)
        ctx.db.commit()
        return {"notice_id": str(notice_id), "acknowledged": True, "acknowledged_at": ack.acknowledged_at}
    return {"notice_id": str(notice_id), "acknowledged": True, "acknowledged_at": existing.acknowledged_at}


@authority_router.get("/notices", response_model=list[NoticeOut])
def list_authority_notices(ctx: AuthContext = Depends(requires(P.ORG_READ))):
    if not ctx.user.is_platform_admin and ctx.role not in ("org_admin",):
        raise Forbidden("Authority notice management requires authority or administrator scope.")
    rows = ctx.db.scalars(select(PublicHealthNotice).order_by(PublicHealthNotice.created_at.desc())).all()
    counts = dict(
        ctx.db.execute(
            select(NoticeAcknowledgement.notice_id, func.count(NoticeAcknowledgement.id))
            .group_by(NoticeAcknowledgement.notice_id)
        ).all()
    )
    return [_to_out(r, ack_count=int(counts.get(r.id, 0))) for r in rows]


@authority_router.post("/notices", response_model=NoticeOut, status_code=201)
def create_authority_notice(req: NoticeCreate, ctx: AuthContext = Depends(requires(P.ORG_MANAGE))):
    notice = PublicHealthNotice(
        title=req.title.strip(),
        message=req.message.strip(),
        plain_language_action=req.plain_language_action.strip() if req.plain_language_action else None,
        issuer=req.issuer.strip(),
        category=req.category.strip(),
        severity=req.severity,
        scope_emirate=req.scope_emirate.strip() if req.scope_emirate else None,
        eligible_programmes=req.eligible_programmes,
        acknowledgement_required=req.acknowledgement_required,
        status="draft",
        version=1,
        expires_at=utcnow() + timedelta(days=req.expires_in_days),
        created_by_id=ctx.user.id,
    )
    ctx.db.add(notice)
    ctx.db.flush()
    ctx.audit("authority.notice.create_draft", "public_health_notice", notice.id, details={"severity": notice.severity})
    ctx.db.commit()
    ctx.db.refresh(notice)
    return _to_out(notice)


@authority_router.post("/notices/{notice_id}/publish", response_model=NoticeOut)
def publish_authority_notice(notice_id: uuid.UUID, ctx: AuthContext = Depends(requires(P.ORG_MANAGE))):
    notice = ctx.db.get(PublicHealthNotice, notice_id)
    if notice is None:
        raise NotFound("Notice not found")
    if notice.status == "withdrawn":
        raise ValidationFailed("Withdrawn notices cannot be republished; create a new draft.")
    notice.status = "published"
    notice.published_at = utcnow()
    ctx.audit("authority.notice.publish", "public_health_notice", notice.id, details={"version": notice.version})
    ctx.db.commit()
    ctx.db.refresh(notice)
    return _to_out(notice)


@authority_router.post("/notices/{notice_id}/withdraw", response_model=NoticeOut)
def withdraw_authority_notice(notice_id: uuid.UUID, ctx: AuthContext = Depends(requires(P.ORG_MANAGE))):
    notice = ctx.db.get(PublicHealthNotice, notice_id)
    if notice is None:
        raise NotFound("Notice not found")
    notice.status = "withdrawn"
    ctx.audit("authority.notice.withdraw", "public_health_notice", notice.id)
    ctx.db.commit()
    ctx.db.refresh(notice)
    return _to_out(notice)
