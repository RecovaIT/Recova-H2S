"""Registered background job handlers and periodic schedules."""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.agents.orchestrator import execute_pipeline_run
from app.benchmarks.runner import execute_benchmark_run
from app.models.ops import Job
from app.services.care import evaluate_referral_slas
from app.tasks.queue import periodic, register


@register("pipeline.run")
def handle_pipeline_run(db: Session, job: Job) -> dict:
    run_id = uuid.UUID(job.payload["run_id"])
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
    return evaluate_referral_slas(db, organization_id=org_id)


# Run SLA & missed-appointment monitoring every 5 minutes in background worker
periodic("referrals.sla_monitor", every_seconds=300)
