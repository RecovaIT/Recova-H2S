"""Registered background job handlers and periodic schedules."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.orchestrator import execute_pipeline_run
from app.benchmarks.runner import execute_benchmark_run
from app.core import audit
from app.models.base import utcnow
from app.models.engine import PipelineRun
from app.models.enums import RunStatus
from app.models.identity import Membership, User
from app.models.ops import Job
from app.services.care import evaluate_referral_slas
from app.tasks.queue import periodic, register


@register("pipeline.run")
def handle_pipeline_run(db: Session, job: Job) -> dict:
    run_id = uuid.UUID(job.payload["run_id"])
    run = db.get(PipelineRun, run_id)
    if run is not None and run.triggered_by_id is not None:
        user = db.get(User, run.triggered_by_id)
        membership = db.scalar(
            select(Membership).where(
                Membership.user_id == run.triggered_by_id,
                Membership.organization_id == run.organization_id,
                Membership.is_active.is_(True),
            )
        )
        if user is None or not user.is_active or (membership is None and not user.is_platform_admin):
            run.status = RunStatus.BLOCKED.value
            run.error = "Triggering account is no longer active or authorized for this organisation."
            run.finished_at = utcnow()
            audit.record(
                db,
                action="pipeline.queued_auth_blocked",
                resource_type="pipeline_run",
                resource_id=run.id,
                organization_id=run.organization_id,
                patient_id=run.patient_id,
                run_id=run.id,
                outcome="denied",
            )
            db.commit()
            return {"run_id": str(run.id), "status": run.status, "risk_tier": run.risk_tier}
    run = execute_pipeline_run(db, run_id)
    return {"run_id": str(run.id), "status": run.status, "risk_tier": run.risk_tier}


@register("benchmark.run")
def handle_benchmark_run(db: Session, job: Job) -> dict:
    br_id = uuid.UUID(job.payload["benchmark_run_id"])
    br = execute_benchmark_run(db, br_id)
    return {"benchmark_run_id": str(br.id), "passed": br.passed_cases, "total": br.total_cases}


@register("referrals.sla_monitor")
def handle_sla_monitor(db: Session, job: Job) -> dict:
    org_id = uuid.UUID(job.payload["organization_id"]) if job.payload.get("organization_id") else None
    from app.services.care import send_appointment_reminders
    send_appointment_reminders(db,org_id)
    return evaluate_referral_slas(db, organization_id=org_id)


# Run SLA & missed-appointment monitoring every 5 minutes in background worker
@register("email.deliver")
def handle_email(db: Session, job: Job) -> dict:
    from app.services.messaging import deliver_email
    return deliver_email(db, uuid.UUID(job.payload["email_id"]))


@register("notification.deliver")
def handle_notification_deliver(db: Session, job: Job) -> dict:
    from app.integrations.notifications import deliver_notification_retry

    return deliver_notification_retry(db, uuid.UUID(job.payload["notification_id"]))


@register("hie.push_malaffi")
def handle_hie_push_malaffi(db: Session, job: Job) -> dict:
    from app.api.v1.ops import execute_malaffi_push_for_patient

    if job.organization_id is None:
        return {"status": "skipped", "reason": "missing_organization_id"}
    return execute_malaffi_push_for_patient(
        db,
        organization_id=job.organization_id,
        patient_id=uuid.UUID(job.payload["patient_id"]),
        attempt=int(job.payload.get("attempt", 2)),
        raise_on_auth_error=False,
    )


periodic("referrals.sla_monitor", every_seconds=300)
