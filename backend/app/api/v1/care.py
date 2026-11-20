"""Clinical reviews, closed-loop referrals, interventions, notifications, and outcome verification."""

from __future__ import annotations

import hmac
import uuid

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.deps import AuthContext, requires
from app.core import audit
from app.core.config import get_settings
from app.core.db import get_db
from app.core.errors import Forbidden
from app.core.permissions import P
from app.schemas.common import Page, PageParams
from app.schemas.workflow import (
    ClinicalReviewCreate,
    ClinicalReviewOut,
    InterventionCreate,
    InterventionOut,
    InterventionUpdateRequest,
    NotificationOut,
    OutcomeVerificationCreate,
    OutcomeVerificationOut,
    ReferralBookRequest,
    ReferralCompleteRequest,
    ReferralCreate,
    ReferralDetailOut,
    ReferralNotifyRequest,
    ReferralOut,
)
from app.services import care as care_svc

reviews_router = APIRouter(prefix="/clinical-reviews", tags=["clinical-reviews"])
referrals_router = APIRouter(prefix="/referrals", tags=["referrals"])
interventions_router = APIRouter(prefix="/interventions", tags=["interventions"])
notifications_router = APIRouter(prefix="/notifications", tags=["notifications"])
outcomes_router = APIRouter(prefix="/outcomes", tags=["outcomes"])


@reviews_router.get("", response_model=Page[ClinicalReviewOut])
def list_reviews(
    params: PageParams = Depends(),
    patient_id: uuid.UUID | None = Query(None),
    run_id: uuid.UUID | None = Query(None),
    ctx: AuthContext = Depends(requires(P.REVIEWS_READ)),
):
    return care_svc.list_reviews(ctx, params, patient_id=patient_id, run_id=run_id)


@reviews_router.post("", response_model=ClinicalReviewOut, status_code=201)
def create_review(
    req: ClinicalReviewCreate, ctx: AuthContext = Depends(requires(P.REVIEWS_SIGN))
):
    return care_svc.create_clinical_review(ctx, req)


@referrals_router.get("", response_model=Page[ReferralOut])
def list_referrals(
    params: PageParams = Depends(),
    track: str | None = Query(None),
    status: str | None = Query(None),
    patient_id: uuid.UUID | None = Query(None),
    sla_status: str | None = Query(None),
    ctx: AuthContext = Depends(requires(P.REFERRALS_READ)),
):
    return care_svc.list_referrals(
        ctx,
        params,
        track=track,
        status=status,
        patient_id=patient_id,
        sla_status=sla_status,
    )


@referrals_router.post("", response_model=ReferralOut, status_code=201)
def create_referral(
    req: ReferralCreate, ctx: AuthContext = Depends(requires(P.REFERRALS_WRITE))
):
    return care_svc.create_referral(ctx, req)


@referrals_router.post("/evaluate-slas")
def run_sla_evaluation(ctx: AuthContext = Depends(requires(P.REFERRALS_WRITE))):
    return care_svc.evaluate_referral_slas(ctx.db, organization_id=ctx.org_id)


@referrals_router.get("/{referral_id}", response_model=ReferralDetailOut)
def get_referral(
    referral_id: uuid.UUID, ctx: AuthContext = Depends(requires(P.REFERRALS_READ))
):
    r, ov = care_svc.get_referral(ctx, referral_id)
    out = ReferralDetailOut.model_validate(r)
    out.outcome_verification = OutcomeVerificationOut.model_validate(ov) if ov else None
    return out


@referrals_router.post("/{referral_id}/notify")
def notify_patient(
    referral_id: uuid.UUID,
    req: ReferralNotifyRequest,
    ctx: AuthContext = Depends(requires(P.REFERRALS_WRITE)),
):
    r, n = care_svc.notify_patient_for_referral(ctx, referral_id, req)
    return {
        "referral": ReferralOut.model_validate(r),
        "notification": NotificationOut.model_validate(n),
    }


@referrals_router.post("/{referral_id}/book", response_model=ReferralOut)
def book_referral(
    referral_id: uuid.UUID,
    req: ReferralBookRequest,
    ctx: AuthContext = Depends(requires(P.REFERRALS_WRITE)),
):
    return care_svc.book_referral(ctx, referral_id, req)


@referrals_router.post(
    "/{referral_id}/complete-consultation", response_model=ReferralOut
)
def complete_consultation(
    referral_id: uuid.UUID,
    req: ReferralCompleteRequest,
    ctx: AuthContext = Depends(requires(P.REFERRALS_WRITE)),
):
    return care_svc.complete_referral_consultation(ctx, referral_id, req)


@referrals_router.post("/{referral_id}/missed", response_model=ReferralOut)
def mark_missed(
    referral_id: uuid.UUID,
    notes: str | None = Query(None),
    ctx: AuthContext = Depends(requires(P.REFERRALS_WRITE)),
):
    return care_svc.mark_referral_missed(ctx, referral_id, notes=notes)


class CancelRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=1000)


@referrals_router.post("/{referral_id}/cancel", response_model=ReferralOut)
def cancel_referral(
    referral_id: uuid.UUID,
    req: CancelRequest,
    ctx: AuthContext = Depends(requires(P.REFERRALS_WRITE)),
):
    return care_svc.cancel_referral(ctx, referral_id, req.reason)


@outcomes_router.post(
    "/referral/{referral_id}/verify",
    response_model=OutcomeVerificationOut,
    status_code=201,
)
def verify_outcome(
    referral_id: uuid.UUID,
    req: OutcomeVerificationCreate,
    ctx: AuthContext = Depends(requires(P.OUTCOMES_VERIFY)),
):
    return care_svc.verify_referral_outcome(ctx, referral_id, req)


@interventions_router.get("", response_model=list[InterventionOut])
def list_interventions(
    track: str | None = Query(None),
    department_id: uuid.UUID | None = Query(None),
    ctx: AuthContext = Depends(requires(P.INTERVENTIONS_READ)),
):
    return care_svc.list_interventions(ctx, track=track, department_id=department_id)


@interventions_router.post("", response_model=InterventionOut, status_code=201)
def create_intervention(
    req: InterventionCreate, ctx: AuthContext = Depends(requires(P.INTERVENTIONS_WRITE))
):
    return care_svc.create_intervention(ctx, req)


@interventions_router.patch("/{intervention_id}", response_model=InterventionOut)
def update_intervention(
    intervention_id: uuid.UUID,
    req: InterventionUpdateRequest,
    ctx: AuthContext = Depends(requires(P.INTERVENTIONS_WRITE)),
):
    return care_svc.update_intervention(ctx, intervention_id, req)


@notifications_router.get("", response_model=Page[NotificationOut])
def list_notifications(
    params: PageParams = Depends(),
    ctx: AuthContext = Depends(requires(P.NOTIFICATIONS_READ)),
):
    return care_svc.list_notifications(ctx, params)


@notifications_router.post("/{notification_id}/read", response_model=NotificationOut)
def read_notification(
    notification_id: uuid.UUID,
    ctx: AuthContext = Depends(requires(P.NOTIFICATIONS_READ)),
):
    return care_svc.mark_notification_read(ctx, notification_id)


@notifications_router.post("/{notification_id}/retry", response_model=NotificationOut)
def retry_notification(
    notification_id: uuid.UUID,
    ctx: AuthContext = Depends(requires(P.USERS_MANAGE)),
):
    from app.integrations.notifications import retry_notification_manual

    notif = retry_notification_manual(ctx.db, ctx.org_id, notification_id)
    ctx.audit(
        "notification.retry",
        "notification",
        notif.id,
        patient_id=notif.recipient_patient_id,
        details={"channel": notif.channel, "status": notif.status, "attempts": notif.attempts},
    )
    ctx.db.commit()
    ctx.db.refresh(notif)
    return notif


@notifications_router.post("/webhooks/twilio-status")
async def twilio_status_webhook(request: Request, db=Depends(get_db)):
    from app.integrations.notifications import (
        _load_org_integration,
        apply_provider_receipt,
        verify_twilio_signature,
    )
    from app.models.care import Notification

    form = await request.form()
    params = {str(k): str(v) for k, v in form.items()}
    sid = params.get("MessageSid") or params.get("SmsSid") or ""
    msg_status = params.get("MessageStatus") or params.get("SmsStatus") or ""
    if not sid or not msg_status:
        return {"updated": False, "reason": "missing_sid_or_status"}

    notif = db.scalar(select(Notification).where(Notification.provider_message_id == sid))
    org_cfg = _load_org_integration(db, notif.organization_id, "twilio") if notif else None
    auth_token = (org_cfg or {}).get("auth_token") or get_settings().twilio_auth_token
    sig = request.headers.get("X-Twilio-Signature", "")
    if not auth_token:
        raise Forbidden("Twilio webhook signature verification is not configured")
    raw_url = str(request.url)
    candidate_urls = [raw_url]
    if request.headers.get("x-forwarded-proto") == "https" and raw_url.startswith("http://"):
        candidate_urls.append("https://" + raw_url[len("http://"):])
    if not any(verify_twilio_signature(u, params, sig, auth_token) for u in candidate_urls):
        raise Forbidden("Invalid Twilio webhook signature")

    if notif is None:
        return {"updated": False, "reason": "unknown_message_sid"}
    err_parts = [p for p in [params.get("ErrorCode"), params.get("ErrorMessage")] if p]
    apply_provider_receipt(
        db,
        notif=notif,
        provider_status=msg_status,
        error_detail=" ".join(err_parts) if err_parts else None,
    )
    audit.record(
        db,
        action="notification.delivery_receipt",
        resource_type="notification",
        resource_id=notif.id,
        organization_id=notif.organization_id,
        patient_id=notif.recipient_patient_id,
        details={"provider": "twilio", "status": notif.status, "provider_status": msg_status},
    )
    db.commit()
    return {"updated": True, "notification_id": str(notif.id), "status": notif.status}


class SahatnaReceiptPayload(BaseModel):
    message_id: str = Field(..., min_length=1, max_length=200)
    status: str = Field(..., min_length=1, max_length=40)
    detail: str | None = Field(default=None, max_length=500)


@notifications_router.post("/webhooks/sahatna-status")
def sahatna_status_webhook(
    req: SahatnaReceiptPayload,
    request: Request,
    db=Depends(get_db),
):
    from app.integrations.notifications import _load_org_integration, apply_provider_receipt
    from app.models.care import Notification

    notif = db.scalar(
        select(Notification).where(
            Notification.provider == "sahatna",
            Notification.provider_message_id == req.message_id,
        )
    )
    org_cfg = _load_org_integration(db, notif.organization_id, "sahatna") if notif else None
    api_key = (org_cfg or {}).get("api_key") or get_settings().sahatna_api_key
    if not api_key:
        raise Forbidden("Sahatna webhook verification is not configured")
    auth_hdr = request.headers.get("Authorization", "")
    token = auth_hdr[7:].strip() if auth_hdr.startswith("Bearer ") else ""
    if not token or not hmac.compare_digest(token, api_key):
        raise Forbidden("Invalid Sahatna webhook credentials")

    if notif is None:
        return {"updated": False, "reason": "unknown_message_id"}
    apply_provider_receipt(
        db,
        notif=notif,
        provider_status=req.status,
        error_detail=req.detail,
    )
    audit.record(
        db,
        action="notification.delivery_receipt",
        resource_type="notification",
        resource_id=notif.id,
        organization_id=notif.organization_id,
        patient_id=notif.recipient_patient_id,
        details={"provider": "sahatna", "status": notif.status, "provider_status": req.status},
    )
    db.commit()
    return {"updated": True, "notification_id": str(notif.id), "status": notif.status}
