"""Role & permission model.

Default role → permission mappings live here (versioned with code). Organisation
administrators can override them per organisation via the `role_permission_overrides`
table (grant/revoke), which is enforced by FastAPI dependencies.
"""

from __future__ import annotations

from enum import StrEnum


class Role(StrEnum):
    PLATFORM_ADMIN = "platform_admin"
    ORG_ADMIN = "org_admin"
    CLINICIAN = "clinician"
    PSYCHIATRIST = "psychiatrist"
    CARE_COORDINATOR = "care_coordinator"
    SCREENING_COORDINATOR = "screening_coordinator"
    OCC_HEALTH_DIRECTOR = "occ_health_director"
    SUPERVISOR = "supervisor"
    AUTHORITY_USER = "authority_user"
    PATIENT = "patient"


class Track(StrEnum):
    CORE = "core"          # Recova Core — relapse prevention
    LOOP = "loop"          # Recova Loop — IFHAS screening-to-care
    NEURO = "neuro"        # Recova Neuro — cognitive monitoring
    WORKSAFE = "worksafe"  # Recova WorkSafe — workforce health


class P(StrEnum):
    """Permission codes."""

    ORG_READ = "org:read"
    ORG_MANAGE = "org:manage"
    USERS_READ = "users:read"
    USERS_MANAGE = "users:manage"
    PATIENTS_READ = "patients:read"
    PATIENTS_WRITE = "patients:write"
    PATIENTS_PHI = "patients:read_identifiable"
    CONSENTS_READ = "consents:read"
    CONSENTS_WRITE = "consents:write"
    OBSERVATIONS_READ = "observations:read"
    OBSERVATIONS_WRITE = "observations:write"
    COGNITIVE_ADMINISTER = "cognitive:administer"
    PIPELINE_RUN = "pipeline:run"
    PIPELINE_READ = "pipeline:read"
    AGENTS_INSPECT = "agents:inspect"
    REVIEWS_READ = "reviews:read"
    REVIEWS_SIGN = "reviews:sign"
    REFERRALS_READ = "referrals:read"
    REFERRALS_WRITE = "referrals:write"
    OUTCOMES_VERIFY = "outcomes:verify"
    INTERVENTIONS_READ = "interventions:read"
    INTERVENTIONS_WRITE = "interventions:write"
    NOTIFICATIONS_READ = "notifications:read"
    NOTIFICATIONS_SEND = "notifications:send"
    WORKFORCE_AGGREGATE = "workforce:read_aggregate"
    WORKFORCE_IDENTIFIABLE = "workforce:read_identifiable"
    WORKFORCE_WRITE = "workforce:write"
    WORKFORCE_MANAGE = "workforce:manage"
    BENCHMARKS_READ = "benchmarks:read"
    BENCHMARKS_RUN = "benchmarks:run"
    FHIR_EXPORT = "fhir:export"
    AUDIT_READ = "audit:read"
    SETTINGS_READ = "settings:read"
    SETTINGS_MANAGE = "settings:manage"
    REPORTS_READ = "reports:read"
    AUTHORITY_PUBLISH = "authority:publish"
    AUTHORITY_REPORTS = "authority:reports"
    PORTAL_SELF = "portal:self"
    PLATFORM_ADMIN = "platform:admin"


ALL_PERMISSIONS: frozenset[str] = frozenset(p.value for p in P)

_CLINICAL_BASE = {
    P.ORG_READ, P.PATIENTS_READ, P.PATIENTS_WRITE, P.PATIENTS_PHI, P.CONSENTS_READ, P.CONSENTS_WRITE,
    P.OBSERVATIONS_READ, P.OBSERVATIONS_WRITE, P.PIPELINE_RUN, P.PIPELINE_READ, P.AGENTS_INSPECT,
    P.REVIEWS_READ, P.REFERRALS_READ, P.REFERRALS_WRITE, P.INTERVENTIONS_READ, P.INTERVENTIONS_WRITE,
    P.NOTIFICATIONS_READ, P.NOTIFICATIONS_SEND, P.FHIR_EXPORT, P.REPORTS_READ, P.BENCHMARKS_READ,
    P.SETTINGS_READ, P.USERS_READ,
}

DEFAULT_ROLE_PERMISSIONS: dict[Role, frozenset[str]] = {
    Role.PLATFORM_ADMIN: ALL_PERMISSIONS,
    Role.ORG_ADMIN: frozenset(ALL_PERMISSIONS - {P.PLATFORM_ADMIN, P.PORTAL_SELF, P.AUTHORITY_PUBLISH, P.AUTHORITY_REPORTS}),
    Role.CLINICIAN: frozenset(_CLINICAL_BASE | {P.REVIEWS_SIGN, P.OUTCOMES_VERIFY, P.COGNITIVE_ADMINISTER, P.BENCHMARKS_RUN}),
    Role.PSYCHIATRIST: frozenset(_CLINICAL_BASE | {P.REVIEWS_SIGN, P.OUTCOMES_VERIFY, P.COGNITIVE_ADMINISTER}),
    Role.CARE_COORDINATOR: frozenset(_CLINICAL_BASE),
    Role.SCREENING_COORDINATOR: frozenset(_CLINICAL_BASE),
    Role.OCC_HEALTH_DIRECTOR: frozenset({
        P.ORG_READ, P.USERS_READ, P.PATIENTS_READ, P.PATIENTS_WRITE, P.PATIENTS_PHI, P.CONSENTS_READ,
        P.CONSENTS_WRITE, P.OBSERVATIONS_READ, P.OBSERVATIONS_WRITE, P.PIPELINE_RUN, P.PIPELINE_READ,
        P.AGENTS_INSPECT, P.REVIEWS_READ, P.REVIEWS_SIGN, P.REFERRALS_READ, P.REFERRALS_WRITE,
        P.OUTCOMES_VERIFY, P.INTERVENTIONS_READ, P.INTERVENTIONS_WRITE, P.NOTIFICATIONS_READ,
        P.NOTIFICATIONS_SEND, P.WORKFORCE_AGGREGATE, P.WORKFORCE_IDENTIFIABLE, P.WORKFORCE_WRITE,
        P.WORKFORCE_MANAGE, P.REPORTS_READ, P.BENCHMARKS_READ, P.SETTINGS_READ, P.FHIR_EXPORT,
    }),
    # Supervisors only ever see anonymised department aggregates by default.
    Role.SUPERVISOR: frozenset({
        P.ORG_READ, P.WORKFORCE_AGGREGATE,
    }),
    # Authority users coordinate scoped public-health notices & aggregate reporting only.
    Role.AUTHORITY_USER: frozenset({
        P.ORG_READ, P.AUTHORITY_PUBLISH, P.AUTHORITY_REPORTS, P.REPORTS_READ,
    }),
    Role.PATIENT: frozenset({P.PORTAL_SELF}),
}

DEFAULT_ROLE_TRACKS: dict[Role, frozenset[Track]] = {
    Role.PLATFORM_ADMIN: frozenset(Track),
    Role.ORG_ADMIN: frozenset(Track),
    Role.CLINICIAN: frozenset({Track.CORE, Track.LOOP, Track.NEURO}),
    Role.PSYCHIATRIST: frozenset({Track.CORE, Track.NEURO}),
    Role.CARE_COORDINATOR: frozenset({Track.CORE, Track.LOOP}),
    Role.SCREENING_COORDINATOR: frozenset({Track.LOOP}),
    Role.OCC_HEALTH_DIRECTOR: frozenset({Track.WORKSAFE}),
    Role.SUPERVISOR: frozenset({Track.WORKSAFE}),
    Role.AUTHORITY_USER: frozenset(),
    Role.PATIENT: frozenset(),
}


def effective_permissions(role: Role, grants: set[str] | None = None, revokes: set[str] | None = None) -> set[str]:
    perms = set(DEFAULT_ROLE_PERMISSIONS.get(role, frozenset()))
    if grants:
        perms |= {g for g in grants if g in ALL_PERMISSIONS and g != P.PLATFORM_ADMIN}
    if revokes:
        perms -= revokes
    if role == Role.SUPERVISOR:
        # Privacy ceiling applies to legacy grants too, across every API surface.
        perms &= set(DEFAULT_ROLE_PERMISSIONS[Role.SUPERVISOR])
    return perms
