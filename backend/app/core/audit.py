"""Audit logging service. Sensitive keys are scrubbed before persistence."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.models.base import utcnow
from app.models.ops import AuditEvent

SENSITIVE_KEYS = {
    "password", "password_hash", "token", "token_hash", "csrf", "secret", "api_key", "national_id",
    "phone", "email_address", "emergency_contact", "insurance_member_id", "authorization", "cookie",
}


def _scrub(value: Any) -> Any:
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            if any(s in str(k).lower() for s in SENSITIVE_KEYS):
                out[k] = "[redacted]"
            else:
                out[k] = _scrub(v)
        return out
    if isinstance(value, list):
        return [_scrub(v) for v in value]
    if isinstance(value, (uuid.UUID,)):
        return str(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def diff(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    changes = {}
    for k in set(before) | set(after):
        if before.get(k) != after.get(k):
            changes[k] = {"before": before.get(k), "after": after.get(k)}
    return _scrub(changes)


def record(
    db: Session,
    *,
    action: str,
    resource_type: str,
    resource_id: Any = None,
    organization_id: uuid.UUID | None = None,
    actor_user_id: uuid.UUID | None = None,
    actor_label: str = "system",
    patient_id: uuid.UUID | None = None,
    run_id: uuid.UUID | None = None,
    outcome: str = "success",
    changes: dict | None = None,
    details: dict | None = None,
    ip_address: str | None = None,
    request_id: str | None = None,
) -> AuditEvent:
    ev = AuditEvent(
        occurred_at=utcnow(),
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        actor_label=actor_label,
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id) if resource_id is not None else None,
        patient_id=patient_id,
        run_id=run_id,
        outcome=outcome,
        changes=_scrub(changes or {}),
        details=_scrub(details or {}),
        ip_address=ip_address,
        request_id=request_id,
    )
    db.add(ev)
    return ev
