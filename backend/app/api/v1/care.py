"""Clinical reviews, closed-loop referrals, interventions, notifications, and outcome verification."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query

from app.api.deps import AuthContext, requires
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
def create_review(req: ClinicalReviewCreate, ctx: AuthContext = Depends(requires(P.REVIEWS_SIGN))):
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
    return care_svc.list_referrals(ctx, params, track=track, status=status, patient_id=patient_id, sla_status=sla_status)


@referrals_router.post("", response_model=ReferralOut, status_code=201)
def create_referral(req: ReferralCreate, ctx: AuthContext = Depends(requires(P.REFERRALS_WRITE))):
    return care_svc.create_referral(ctx, req)


@referrals_router.post("/evaluate-slas")
def run_sla_evaluation(ctx: AuthContext = Depends(requires(P.REFERRALS_WRITE))):
    return care_svc.evaluate_referral_slas(ctx.db, organization_id=ctx.org_id)


@referrals_router.get("/{referral_id}", response_model=ReferralDetailOut)
def get_referral(referral_id: uuid.UUID, ctx: AuthContext = Depends(requires(P.REFERRALS_READ))):
    r, ov = care_svc.get_referral(ctx, referral_id)
    out = ReferralDetailOut.model_validate(r)
    out.outcome_verification = OutcomeVerificationOut.model_validate(ov) if ov else None
    return out


@referrals_router.post("/{referral_id}/notify")
def notify_patient(referral_id: uuid.UUID, req: ReferralNotifyRequest, ctx: AuthContext = Depends(requires(P.REFERRALS_WRITE))):
    r, n = care_svc.notify_patient_for_referral(ctx, referral_id, req)
    return {"referral": ReferralOut.model_validate(r), "notification": NotificationOut.model_validate(n)}


@referrals_router.post("/{referral_id}/book", response_model=ReferralOut)
def book_referral(referral_id: uuid.UUID, req: ReferralBookRequest, ctx: AuthContext = Depends(requires(P.REFERRALS_WRITE))):
    return care_svc.book_referral(ctx, referral_id, req)


@referrals_router.post("/{referral_id}/complete-consultation", response_model=ReferralOut)
def complete_consultation(referral_id: uuid.UUID, req: ReferralCompleteRequest, ctx: AuthContext = Depends(requires(P.REFERRALS_WRITE))):
    return care_svc.complete_referral_consultation(ctx, referral_id, req)


@referrals_router.post("/{referral_id}/missed", response_model=ReferralOut)
def mark_missed(referral_id: uuid.UUID, notes: str | None = Query(None), ctx: AuthContext = Depends(requires(P.REFERRALS_WRITE))):
    return care_svc.mark_referral_missed(ctx, referral_id, notes=notes)


@outcomes_router.post("/referral/{referral_id}/verify", response_model=OutcomeVerificationOut, status_code=201)
def verify_outcome(referral_id: uuid.UUID, req: OutcomeVerificationCreate, ctx: AuthContext = Depends(requires(P.OUTCOMES_VERIFY))):
    return care_svc.verify_referral_outcome(ctx, referral_id, req)


@interventions_router.get("", response_model=list[InterventionOut])
def list_interventions(
    track: str | None = Query(None),
    department_id: uuid.UUID | None = Query(None),
    ctx: AuthContext = Depends(requires(P.INTERVENTIONS_READ)),
):
    return care_svc.list_interventions(ctx, track=track, department_id=department_id)


@interventions_router.post("", response_model=InterventionOut, status_code=201)
def create_intervention(req: InterventionCreate, ctx: AuthContext = Depends(requires(P.INTERVENTIONS_WRITE))):
    return care_svc.create_intervention(ctx, req)


@interventions_router.patch("/{intervention_id}", response_model=InterventionOut)
def update_intervention(intervention_id: uuid.UUID, req: InterventionUpdateRequest, ctx: AuthContext = Depends(requires(P.INTERVENTIONS_WRITE))):
    return care_svc.update_intervention(ctx, intervention_id, req)


@notifications_router.get("", response_model=Page[NotificationOut])
def list_notifications(params: PageParams = Depends(), ctx: AuthContext = Depends(requires(P.NOTIFICATIONS_READ))):
    return care_svc.list_notifications(ctx, params)


@notifications_router.post("/{notification_id}/read", response_model=NotificationOut)
def read_notification(notification_id: uuid.UUID, ctx: AuthContext = Depends(requires(P.NOTIFICATIONS_READ))):
    return care_svc.mark_notification_read(ctx, notification_id)
