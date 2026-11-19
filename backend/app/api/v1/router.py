"""Versioned API v1 router registry."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.account_setup import router as account_setup_router
from app.api.v1.authority import authority_router, notices_router
from app.api.v1.care import (
    interventions_router,
    notifications_router,
    outcomes_router,
    referrals_router,
    reviews_router,
)
from app.api.v1.clinical import (
    checkins_router,
    cognitive_router,
    consents_router,
    observations_router,
    patients_router,
    screenings_router,
    wearables_router,
    workforce_router,
)
from app.api.v1.engine import agents_router, baselines_router, pipeline_router, scoring_router
from app.api.v1.ops import benchmarks_router, fhir_router, reports_router, settings_router
from app.api.v1.orgs_users import audit_router, orgs_router, users_router
from app.api.v1.portal import router as portal_router

api_v1_router = APIRouter()
for r in [
    auth_router,
    account_setup_router,
    orgs_router,
    users_router,
    patients_router,
    consents_router,
    observations_router,
    wearables_router,
    checkins_router,
    screenings_router,
    cognitive_router,
    workforce_router,
    baselines_router,
    scoring_router,
    pipeline_router,
    agents_router,
    reviews_router,
    referrals_router,
    interventions_router,
    notifications_router,
    outcomes_router,
    benchmarks_router,
    fhir_router,
    audit_router,
    settings_router,
    reports_router,
    portal_router,
    notices_router,
    authority_router,
]:
    api_v1_router.include_router(r)
