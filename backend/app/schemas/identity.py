"""Identity, authentication, organisation, user, audit and job schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.core.permissions import Role, Track
from app.schemas.common import ORMModel


class OrganizationOut(ORMModel):
    id: uuid.UUID
    name: str
    slug: str
    org_type: str
    primary_programme: str | None = None
    programme_configuration_status: str = "configured"
    enabled_tracks: list[str]
    is_active: bool
    country: str | None = None
    emirate: str | None = None
    settings: dict = Field(default_factory=dict)
    data_retention_days: int | None = None
    created_at: datetime


class OrganizationCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    slug: str = Field(min_length=2, max_length=80, pattern=r"^[a-z0-9-]+$")
    org_type: Literal["clinic", "rehab_center", "public_health", "employer", "hospital"] = "clinic"
    enabled_tracks: list[Track] = Field(default_factory=lambda: [Track.CORE, Track.LOOP, Track.NEURO, Track.WORKSAFE])
    country: str | None = Field(default="UAE", max_length=80)
    emirate: str | None = Field(default="Abu Dhabi", max_length=80)
    data_retention_days: int | None = Field(default=2555, ge=30, le=36500)


class OrganizationUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    org_type: Literal["clinic", "rehab_center", "public_health", "employer", "hospital"] | None = None
    enabled_tracks: list[Track] | None = None
    is_active: bool | None = None
    country: str | None = Field(default=None, max_length=80)
    emirate: str | None = Field(default=None, max_length=80)
    settings: dict | None = None
    data_retention_days: int | None = Field(default=None, ge=30, le=36500)


class MembershipOut(ORMModel):
    id: uuid.UUID
    user_id: uuid.UUID
    organization_id: uuid.UUID
    organization_name: str | None = None
    organization_slug: str | None = None
    role: str
    is_active: bool
    department_ids: list[uuid.UUID] = Field(default_factory=list)


class UserOut(ORMModel):
    id: uuid.UUID
    email: EmailStr
    full_name: str
    is_active: bool
    is_platform_admin: bool
    preferred_language: str
    license_number: str | None = None
    last_login_at: datetime | None = None
    created_at: datetime


class UserWithMembershipsOut(UserOut):
    memberships: list[MembershipOut] = Field(default_factory=list)


class BootstrapRequest(BaseModel):
    organization_name: str = Field(min_length=2, max_length=200)
    organization_slug: str = Field(min_length=2, max_length=80, pattern=r"^[a-z0-9-]+$")
    org_type: Literal["clinic", "rehab_center", "public_health", "employer", "hospital"] = "hospital"
    primary_programme: Track | None = None
    enabled_tracks: list[Track] = Field(default_factory=lambda: [Track.CORE, Track.LOOP, Track.NEURO, Track.WORKSAFE])
    admin_email: EmailStr
    admin_full_name: str = Field(min_length=2, max_length=200)
    admin_password: str = Field(min_length=10, max_length=128)
    admin_license_number: str | None = Field(default=None, max_length=80)


class ProgrammeRequestCreate(BaseModel):
    requested_programme: Track
    justification: str = Field(min_length=10, max_length=1000)


class ProgrammeRequestReview(BaseModel):
    decision: Literal["approved", "rejected"]
    review_note: str | None = Field(default=None, max_length=500)


class ProgrammeRequestOut(ORMModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    organization_name: str | None = None
    requested_programme: str
    justification: str
    status: str
    requested_by_id: uuid.UUID | None = None
    reviewed_by_id: uuid.UUID | None = None
    reviewed_at: datetime | None = None
    review_note: str | None = None
    created_at: datetime


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)
    organization_id: uuid.UUID | None = None


class SwitchOrganizationRequest(BaseModel):
    organization_id: uuid.UUID


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str = Field(min_length=16, max_length=256)
    new_password: str = Field(min_length=10, max_length=128)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=10, max_length=128)


class SessionResponse(BaseModel):
    user: UserOut
    active_organization: OrganizationOut | None
    role: str | None
    permissions: list[str]
    tracks: list[str]
    memberships: list[MembershipOut]
    csrf_token: str | None = None


class UserCreateRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=200)
    role: Role
    password: str | None = Field(default=None, min_length=10, max_length=128)
    preferred_language: Literal["en", "ar"] = "en"
    license_number: str | None = Field(default=None, max_length=80)
    department_ids: list[uuid.UUID] = Field(default_factory=list)
    send_activation_email: bool = False

    @field_validator("role")
    @classmethod
    def _no_platform_admin(cls, v: Role) -> Role:
        return v


class UserUpdateRequest(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=200)
    is_active: bool | None = None
    preferred_language: Literal["en", "ar"] | None = None
    license_number: str | None = Field(default=None, max_length=80)


class MembershipUpdateRequest(BaseModel):
    role: Role | None = None
    is_active: bool | None = None
    department_ids: list[uuid.UUID] | None = None


class RolePermissionOverrideInput(BaseModel):
    role: Role
    permission: str
    effect: Literal["grant", "revoke"]


class RolePermissionView(BaseModel):
    role: str
    default_permissions: list[str]
    effective_permissions: list[str]
    overrides: list[dict]


class AuditEventOut(ORMModel):
    id: uuid.UUID
    occurred_at: datetime
    organization_id: uuid.UUID | None
    actor_user_id: uuid.UUID | None
    actor_label: str
    action: str
    resource_type: str
    resource_id: str | None
    patient_id: uuid.UUID | None
    run_id: uuid.UUID | None
    outcome: str
    changes: dict
    details: dict
    ip_address: str | None
    request_id: str | None


class JobOut(ORMModel):
    id: uuid.UUID
    organization_id: uuid.UUID | None
    job_type: str
    status: str
    payload: dict
    result: dict | None
    attempts: int
    max_attempts: int
    timeout_seconds: int
    run_after: datetime
    started_at: datetime | None
    finished_at: datetime | None
    last_error: str | None
    history: list
    created_at: datetime
