"""Patient/participant, track enrollment, and consent management services."""

from __future__ import annotations

import json
import uuid

from sqlalchemy import or_, select
from sqlalchemy.orm import selectinload

from app.api.deps import AuthContext
from app.core import audit
from app.core.errors import Conflict, NotFound, ValidationFailed
from app.core.permissions import P, Track
from app.core.security import decrypt_str, encrypt_str, mask
from app.models.base import utcnow
from app.models.clinical import Consent, Department, Patient, TrackEnrollment
from app.models.enums import ConsentStatus
from app.models.identity import Membership, User
from app.models.care import InsurancePlan
from app.schemas.clinical import (
    ConsentCreate,
    EnrollmentCreate,
    PatientCreate,
    PatientDetailOut,
    PatientUpdate,
)
from app.schemas.common import PageParams, paginate


def _validate_patient_links(ctx, req):
    for field, model in [
        ("department_id", Department),
        ("insurance_plan_id", InsurancePlan),
    ]:
        value = getattr(req, field, None)
        if (
            value
            and ctx.db.scalar(
                select(model.id).where(
                    model.id == value, model.organization_id == ctx.org_id
                )
            )
            is None
        ):
            raise ValidationFailed(
                f'{field.replace("_", " ")} must belong to the active facility'
            )
    if req.primary_clinician_id:
        clinician = ctx.db.scalar(
            select(User)
            .join(Membership, Membership.user_id == User.id)
            .where(
                User.id == req.primary_clinician_id,
                User.is_active.is_(True),
                User.license_number.is_not(None),
                User.license_number != "",
                Membership.organization_id == ctx.org_id,
                Membership.is_active.is_(True),
                Membership.role.in_(
                    [
                        "clinician",
                        "psychiatrist",
                        "occ_health_director",
                        "org_admin",
                        "platform_admin",
                    ]
                ),
            )
        )
        if not clinician:
            raise ValidationFailed(
                "Assign an active practitioner with a recorded licence in this facility"
            )


def _patient_detail(p: Patient) -> PatientDetailOut:
    nat = decrypt_str(p.national_id_encrypted) if p.national_id_encrypted else None
    phone = decrypt_str(p.phone_encrypted) if p.phone_encrypted else None
    email = decrypt_str(p.email_encrypted) if p.email_encrypted else None
    ins_id = (
        decrypt_str(p.insurance_member_id_encrypted)
        if p.insurance_member_id_encrypted
        else None
    )
    out = PatientDetailOut.model_validate(p)
    out.national_id_masked = mask(nat, 4) if nat else None
    out.phone_masked = mask(phone, 4) if phone else None
    out.email_masked = mask(email, 3) if email else None
    out.insurance_member_id_masked = mask(ins_id, 3) if ins_id else None
    return out


def list_patients(
    ctx: AuthContext,
    params: PageParams,
    *,
    track: str | None = None,
    risk_tier: str | None = None,
    department_id: uuid.UUID | None = None,
    active_only: bool = True,
) -> dict:
    ctx.require(P.PATIENTS_READ)
    ctx.require(P.PATIENTS_PHI)
    if track:
        ctx.require_track(track)
    stmt = (
        select(Patient)
        .options(selectinload(Patient.enrollments))
        .where(Patient.organization_id == ctx.org_id, Patient.is_synthetic.is_(False))
    )
    if active_only:
        stmt = stmt.where(Patient.is_active.is_(True))
    if department_id:
        stmt = stmt.where(Patient.department_id == department_id)
    if params.q:
        like = f"%{params.q.strip()}%"
        stmt = stmt.where(
            or_(
                Patient.mrn.ilike(like),
                Patient.given_name.ilike(like),
                Patient.family_name.ilike(like),
            )
        )
    if track or risk_tier:
        sub = select(TrackEnrollment.patient_id).where(
            TrackEnrollment.organization_id == ctx.org_id
        )
        if track:
            sub = sub.where(TrackEnrollment.track == track)
        if risk_tier:
            sub = sub.where(TrackEnrollment.latest_risk_tier == risk_tier)
        stmt = stmt.where(Patient.id.in_(sub))

    return paginate(
        ctx.db,
        stmt,
        params,
        sortable={
            "mrn": Patient.mrn,
            "family_name": Patient.family_name,
            "created_at": Patient.created_at,
        },
        default_sort=Patient.created_at.desc(),
    )


def get_patient(ctx: AuthContext, patient_id: uuid.UUID) -> PatientDetailOut:
    ctx.require(P.PATIENTS_READ)
    ctx.require(P.PATIENTS_PHI)
    p = ctx.db.scalar(
        select(Patient)
        .options(selectinload(Patient.enrollments))
        .where(
            Patient.id == patient_id,
            Patient.organization_id == ctx.org_id,
            Patient.is_synthetic.is_(False),
        )
    )
    if p is None:
        raise NotFound("Patient not found")
    ctx.audit("patient.view", "patient", p.id, patient_id=p.id)
    ctx.db.commit()
    return _patient_detail(p)


def create_patient(ctx: AuthContext, req: PatientCreate) -> PatientDetailOut:
    ctx.require(P.PATIENTS_WRITE)
    ctx.require(P.PATIENTS_PHI)
    _validate_patient_links(ctx, req)
    if req.tracks:
        selected_tracks = list(dict.fromkeys(req.tracks))
    else:
        default_prog = (
            ctx.organization.primary_programme
            if ctx.organization and ctx.organization.primary_programme
            else (
                ctx.organization.enabled_tracks[0]
                if ctx.organization and ctx.organization.enabled_tracks
                else "core"
            )
        )
        selected_tracks = [Track(default_prog)]
    for t in selected_tracks:
        ctx.require_track(t.value)

    existing = ctx.db.scalar(
        select(Patient.id).where(
            Patient.organization_id == ctx.org_id, Patient.mrn == req.mrn.strip()
        )
    )
    if existing:
        raise Conflict(
            f"MRN / Participant ID '{req.mrn}' already exists in this organisation"
        )

    if req.department_id:
        dept = ctx.db.scalar(
            select(Department).where(
                Department.id == req.department_id,
                Department.organization_id == ctx.org_id,
            )
        )
        if dept is None:
            raise ValidationFailed("Department not found in active organisation")

    p = Patient(
        organization_id=ctx.org_id,
        participant_type=req.participant_type.value,
        mrn=req.mrn.strip(),
        given_name=req.given_name.strip(),
        family_name=req.family_name.strip(),
        date_of_birth=req.date_of_birth,
        sex=req.sex,
        preferred_language=req.preferred_language,
        national_id_encrypted=encrypt_str(req.national_id),
        phone_encrypted=encrypt_str(req.phone),
        email_encrypted=encrypt_str(str(req.email)) if req.email else None,
        emergency_contact_encrypted=(
            encrypt_str(json.dumps(req.emergency_contact))
            if req.emergency_contact
            else None
        ),
        education_level=req.education_level,
        primary_language_matches_assessment=req.primary_language_matches_assessment,
        hearing_status=req.hearing_status,
        vision_status=req.vision_status,
        clinical_history=req.clinical_history,
        insurance_plan_id=req.insurance_plan_id,
        insurance_member_id_encrypted=encrypt_str(req.insurance_member_id),
        department_id=req.department_id,
        job_role=req.job_role,
        primary_clinician_id=req.primary_clinician_id,
        created_by_id=ctx.user.id,
        is_synthetic=False,
    )
    ctx.db.add(p)
    ctx.db.flush()

    now = utcnow()
    for t in selected_tracks:
        ctx.db.add(
            TrackEnrollment(
                organization_id=ctx.org_id,
                patient_id=p.id,
                track=t.value,
                status="active",
                enrolled_at=now,
                context={},
                authority_actor_id=ctx.user.id,
                authority_reason="Primary facility registration",
                history=[
                    {
                        "action": "enrolled",
                        "track": t.value,
                        "actor_id": str(ctx.user.id),
                        "actor_email": ctx.user.email,
                        "at": now.isoformat(),
                        "reason": "Primary facility registration",
                    }
                ],
            )
        )
    ctx.audit(
        "patient.create",
        "patient",
        p.id,
        patient_id=p.id,
        details={"mrn": p.mrn, "tracks": [t.value for t in selected_tracks]},
    )
    ctx.db.commit()
    p = ctx.db.scalar(
        select(Patient)
        .options(selectinload(Patient.enrollments))
        .where(Patient.id == p.id)
    )
    assert p is not None
    return _patient_detail(p)


def update_patient(
    ctx: AuthContext, patient_id: uuid.UUID, req: PatientUpdate
) -> PatientDetailOut:
    ctx.require(P.PATIENTS_WRITE)
    ctx.require(P.PATIENTS_PHI)
    _validate_patient_links(ctx, req)
    p = ctx.db.scalar(
        select(Patient)
        .options(selectinload(Patient.enrollments))
        .where(
            Patient.id == patient_id,
            Patient.organization_id == ctx.org_id,
            Patient.is_synthetic.is_(False),
        )
    )
    if p is None:
        raise NotFound("Patient not found")

    before = {
        "preferred_language": p.preferred_language,
        "hearing_status": p.hearing_status,
        "vision_status": p.vision_status,
        "is_active": p.is_active,
        "insurance_plan_id": str(p.insurance_plan_id) if p.insurance_plan_id else None,
    }
    if req.given_name is not None:
        p.given_name = req.given_name.strip()
    if req.family_name is not None:
        p.family_name = req.family_name.strip()
    if req.date_of_birth is not None:
        p.date_of_birth = req.date_of_birth
    if req.sex is not None:
        p.sex = req.sex
    if req.preferred_language is not None:
        p.preferred_language = req.preferred_language
    if req.phone is not None:
        p.phone_encrypted = encrypt_str(req.phone)
    if req.email is not None:
        p.email_encrypted = encrypt_str(str(req.email))
    if req.emergency_contact is not None:
        p.emergency_contact_encrypted = encrypt_str(json.dumps(req.emergency_contact))
    if req.education_level is not None:
        p.education_level = req.education_level
    if req.primary_language_matches_assessment is not None:
        p.primary_language_matches_assessment = req.primary_language_matches_assessment
    if req.hearing_status is not None:
        p.hearing_status = req.hearing_status
    if req.vision_status is not None:
        p.vision_status = req.vision_status
    if req.clinical_history is not None:
        p.clinical_history = req.clinical_history
    if req.insurance_plan_id is not None:
        p.insurance_plan_id = req.insurance_plan_id
    if req.insurance_member_id is not None:
        p.insurance_member_id_encrypted = encrypt_str(req.insurance_member_id)
    if req.department_id is not None:
        p.department_id = req.department_id
    if req.job_role is not None:
        p.job_role = req.job_role
    if req.primary_clinician_id is not None:
        p.primary_clinician_id = req.primary_clinician_id
    if req.is_active is not None:
        p.is_active = req.is_active

    after = {
        "preferred_language": p.preferred_language,
        "hearing_status": p.hearing_status,
        "vision_status": p.vision_status,
        "is_active": p.is_active,
        "insurance_plan_id": str(p.insurance_plan_id) if p.insurance_plan_id else None,
    }
    ctx.audit(
        "patient.update",
        "patient",
        p.id,
        patient_id=p.id,
        changes=audit.diff(before, after),
    )
    ctx.db.commit()
    return _patient_detail(p)


def enroll_track(
    ctx: AuthContext, patient_id: uuid.UUID, req: EnrollmentCreate
) -> TrackEnrollment:
    ctx.require(P.PATIENTS_WRITE)
    ctx.require(P.PATIENTS_PHI)
    ctx.require_track(req.track.value)
    p = ctx.db.scalar(
        select(Patient).where(
            Patient.id == patient_id,
            Patient.organization_id == ctx.org_id,
            Patient.is_synthetic.is_(False),
        )
    )
    if p is None:
        raise NotFound("Patient not found")
    now = utcnow()
    reason = req.reason or "Authorised clinical enrolment update"
    existing = ctx.db.scalar(
        select(TrackEnrollment).where(
            TrackEnrollment.patient_id == p.id, TrackEnrollment.track == req.track.value
        )
    )
    if existing is not None:
        existing.status = "active"
        existing.context = {**(existing.context or {}), **req.context}
        existing.authority_actor_id = ctx.user.id
        existing.authority_reason = reason
        existing.history = [
            *list(existing.history or []),
            {
                "action": "reactivated",
                "track": req.track.value,
                "actor_id": str(ctx.user.id),
                "actor_email": ctx.user.email,
                "at": now.isoformat(),
                "reason": reason,
            },
        ]
        ctx.audit(
            "patient.enroll.reactivate",
            "track_enrollment",
            existing.id,
            patient_id=p.id,
            details={"track": req.track.value, "reason": reason},
        )
        ctx.db.commit()
        return existing
    enr = TrackEnrollment(
        organization_id=ctx.org_id,
        patient_id=p.id,
        track=req.track.value,
        status="active",
        enrolled_at=now,
        context=req.context,
        authority_actor_id=ctx.user.id,
        authority_reason=reason,
        history=[
            {
                "action": "enrolled",
                "track": req.track.value,
                "actor_id": str(ctx.user.id),
                "actor_email": ctx.user.email,
                "at": now.isoformat(),
                "reason": reason,
            }
        ],
    )
    ctx.db.add(enr)
    ctx.db.flush()
    ctx.audit(
        "patient.enroll",
        "track_enrollment",
        enr.id,
        patient_id=p.id,
        details={"track": req.track.value, "reason": reason},
    )
    ctx.db.commit()
    return enr


def list_consents(ctx: AuthContext, patient_id: uuid.UUID) -> list[Consent]:
    ctx.require(P.CONSENTS_READ)
    p = ctx.db.scalar(
        select(Patient).where(
            Patient.id == patient_id, Patient.organization_id == ctx.org_id
        )
    )
    if p is None:
        raise NotFound("Patient not found")
    return list(
        ctx.db.scalars(
            select(Consent)
            .where(Consent.organization_id == ctx.org_id, Consent.patient_id == p.id)
            .order_by(Consent.effective_at.desc())
        ).all()
    )


def record_consent(ctx: AuthContext, req: ConsentCreate) -> Consent:
    ctx.require(P.CONSENTS_WRITE)
    p = ctx.db.scalar(
        select(Patient).where(
            Patient.id == req.patient_id, Patient.organization_id == ctx.org_id
        )
    )
    if p is None:
        raise NotFound("Patient not found")
    c = Consent(
        organization_id=ctx.org_id,
        patient_id=p.id,
        scope=req.scope.value,
        status=ConsentStatus.GRANTED.value,
        method=req.method,
        policy_version=req.policy_version,
        authority_to_act=req.authority_to_act,
        actor_user_id=ctx.user.id,
        granted_by_name=req.granted_by_name or f"{p.given_name} {p.family_name}",
        recorded_by_id=ctx.user.id,
        effective_at=req.effective_at or utcnow(),
        expires_at=req.expires_at,
        evidence_reference=req.evidence_reference,
        notes=req.notes,
    )
    ctx.db.add(c)
    ctx.db.flush()
    ctx.audit(
        "consent.grant",
        "consent",
        c.id,
        patient_id=p.id,
        details={
            "scope": c.scope,
            "method": c.method,
            "policy_version": c.policy_version,
            "authority_to_act": c.authority_to_act,
        },
    )
    ctx.db.commit()
    return c


def revoke_consent(
    ctx: AuthContext, consent_id: uuid.UUID, reason: str | None = None
) -> Consent:
    ctx.require(P.CONSENTS_WRITE)
    c = ctx.db.scalar(
        select(Consent).where(
            Consent.id == consent_id, Consent.organization_id == ctx.org_id
        )
    )
    if c is None:
        raise NotFound("Consent record not found")
    c.status = ConsentStatus.REVOKED.value
    c.revoked_at = utcnow()
    if reason:
        c.notes = f"{c.notes or ''}\nRevoked: {reason}".strip()
    ctx.audit(
        "consent.revoke",
        "consent",
        c.id,
        patient_id=c.patient_id,
        details={"scope": c.scope, "reason": reason},
    )
    ctx.db.commit()
    return c
