"""Shared 6-Agent Gated Pipeline Orchestrator."""

from __future__ import annotations

import time
import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.agent3_aggregator import run_agent3
from app.agents.agent4_scoring import run_agent4
from app.agents.agent5_synthesis import run_agent5
from app.agents.agent6_referral import run_agent6
from app.agents.gate1_consent import run_gate1
from app.agents.gate2_emergency import run_gate2
from app.core import audit
from app.core.errors import NotFound, ValidationFailed
from app.core.events import event_bus
from app.core.permissions import Track
from app.engine.scoring import ALGORITHM_VERSION
from app.models.base import utcnow
from app.models.clinical import Patient, TrackEnrollment
from app.models.engine import AgentStepResult, PipelineRun
from app.models.enums import RiskTier, RunStatus, StepStatus, SynthesisStatus

AGENT_DEFINITIONS = [
    ("gate1_consent", "Gate 1: Consent, Governance & Guardrail Agent", 1),
    ("gate2_emergency", "Gate 2: Emergency Red-Flag Bypass Agent", 2),
    ("agent3_aggregator", "Agent 3: Longitudinal Signal & Context Aggregator", 3),
    ("agent4_scoring", "Agent 4: Deterministic Baseline & Drift Scoring Engine", 4),
    ("agent5_synthesis", "Agent 5: Clinical Synthesis & Explainability Agent", 5),
    ("agent6_referral", "Agent 6: Closed-Loop Care & Referral Orchestrator", 6),
]


def create_pipeline_run(
    db: Session,
    *,
    organization_id: uuid.UUID,
    patient_id: uuid.UUID,
    track: str,
    trigger: str = "manual",
    triggered_by_id: uuid.UUID | None = None,
    as_of: datetime | None = None,
    idempotency_key: str | None = None,
    benchmark_run_id: uuid.UUID | None = None,
) -> PipelineRun:
    if track not in {t.value for t in Track}:
        raise ValidationFailed(f"Unsupported track: {track}")
    if idempotency_key:
        existing = db.scalar(
            select(PipelineRun).where(
                PipelineRun.organization_id == organization_id,
                PipelineRun.idempotency_key == idempotency_key,
            )
        )
        if existing is not None:
            return existing

    patient = db.scalar(
        select(Patient).where(Patient.id == patient_id, Patient.organization_id == organization_id)
    )
    if patient is None:
        raise NotFound("Patient not found in active organisation")

    run = PipelineRun(
        organization_id=organization_id,
        patient_id=patient.id,
        track=track,
        status=RunStatus.QUEUED.value,
        trigger=trigger,
        triggered_by_id=triggered_by_id,
        idempotency_key=idempotency_key,
        algorithm_version=ALGORITHM_VERSION,
        as_of=as_of or utcnow(),
        benchmark_run_id=benchmark_run_id,
    )
    db.add(run)
    db.flush()

    for key, name, order in AGENT_DEFINITIONS:
        db.add(
            AgentStepResult(
                run_id=run.id,
                agent_key=key,
                agent_name=name,
                step_order=order,
                status=StepStatus.WAITING.value,
            )
        )
    db.flush()
    return run


def execute_pipeline_run(db: Session, run_id: uuid.UUID) -> PipelineRun:
    """Execute an existing PipelineRun through Gates 1-2 and Agents 3-6."""
    run = db.get(PipelineRun, run_id)
    if run is None:
        raise NotFound("PipelineRun not found")

    patient = db.get(Patient, run.patient_id) if run.patient_id else None
    if patient is None:
        raise NotFound("Patient not found")

    steps = {
        s.agent_key: s
        for s in db.scalars(select(AgentStepResult).where(AgentStepResult.run_id == run.id)).all()
    }

    t_run_start = time.perf_counter()
    run.status = RunStatus.RUNNING.value
    run.started_at = utcnow()
    db.commit()
    event_bus.publish_run(run.organization_id, run.id, "pipeline.started", {"track": run.track, "patient_id": str(patient.id)})

    def start_step(key: str) -> AgentStepResult:
        st = steps[key]
        st.status = StepStatus.RUNNING.value
        st.started_at = utcnow()
        db.commit()
        event_bus.publish_run(run.organization_id, run.id, "agent.step_started", {"agent_key": key, "step_order": st.step_order})
        return st

    def finish_step(key: str, status: StepStatus, message: str, inp_model, out_model, elapsed_ms: int) -> None:
        st = steps[key]
        st.status = status.value
        st.message = message
        st.input_payload = inp_model.model_dump(mode="json") if inp_model is not None else None
        st.output_payload = out_model.model_dump(mode="json") if out_model is not None else None
        st.finished_at = utcnow()
        st.duration_ms = elapsed_ms
        db.commit()
        event_bus.publish_run(
            run.organization_id,
            run.id,
            "agent.step_finished",
            {"agent_key": key, "step_order": st.step_order, "status": st.status, "message": message},
        )

    def skip_remaining(keys: list[str], reason: str) -> None:
        now = utcnow()
        for k in keys:
            st = steps[k]
            st.status = StepStatus.SKIPPED.value
            st.message = reason
            st.finished_at = now
        db.commit()

    # ---------------- GATE 1: Consent, Governance & Guardrail ----------------
    start_step("gate1_consent")
    t0 = time.perf_counter()
    g1_in, g1_out = run_gate1(db, patient, run.track, run.as_of)
    g1_ms = int((time.perf_counter() - t0) * 1000)

    if not g1_out.allow_routine_processing:
        finish_step(
            "gate1_consent",
            StepStatus.FAILED,
            "Routine processing blocked: mandatory data_processing consent is missing or revoked.",
            g1_in,
            g1_out,
            g1_ms,
        )
        if not g1_out.allow_emergency_screen:
            skip_remaining(["gate2_emergency", "agent3_aggregator", "agent4_scoring", "agent5_synthesis", "agent6_referral"], "Blocked at Gate 1 (no consent)")
            run.status = RunStatus.BLOCKED.value
            run.finished_at = utcnow()
            run.duration_ms = int((time.perf_counter() - t_run_start) * 1000)
            audit.record(db, action="pipeline.blocked", resource_type="pipeline_run", resource_id=run.id, organization_id=run.organization_id, patient_id=patient.id, run_id=run.id, outcome="denied")
            db.commit()
            return run
    else:
        g1_status = StepStatus.FLAGGED if g1_out.missing_streams else StepStatus.COMPLETED
        g1_msg = (
            f"Consent verified; {len(g1_out.missing_streams)} expected stream(s) missing (completeness {g1_out.data_completeness_pct}%)."
            if g1_out.missing_streams
            else "Consent verified and all expected streams present."
        )
        finish_step("gate1_consent", g1_status, g1_msg, g1_in, g1_out, g1_ms)

    # ---------------- GATE 2: Emergency Red-Flag Bypass ----------------
    start_step("gate2_emergency")
    t0 = time.perf_counter()
    g2_in, g2_out = run_gate2(db, patient, run.track, run.as_of, run_id=run.id, create_event=True)
    g2_ms = int((time.perf_counter() - t0) * 1000)

    if g2_out.emergency_triggered:
        finish_step(
            "gate2_emergency",
            StepStatus.BYPASSED,
            f"EMERGENCY BYPASS TRIGGERED ({', '.join(g2_out.rule_codes)}). Routine pipeline halted; initiating STAT triage.",
            g2_in,
            g2_out,
            g2_ms,
        )
        skip_remaining(["agent3_aggregator", "agent4_scoring", "agent5_synthesis"], "Bypassed by Gate 2 Emergency Red-Flag protocol")

        # Execute Agent 6 in emergency triage mode
        start_step("agent6_referral")
        t6 = time.perf_counter()
        a6_in, a6_out = run_agent6(
            db,
            patient,
            run.track,
            run.id,
            is_emergency=True,
            emergency_event_id=g2_out.emergency_event_id,
            active_scopes=set(g1_out.active_scopes),
        )
        a6_ms = int((time.perf_counter() - t6) * 1000)
        finish_step(
            "agent6_referral",
            StepStatus.FLAGGED,
            f"STAT emergency triage referral created ({a6_out.referral_id}).",
            a6_in,
            a6_out,
            a6_ms,
        )

        run.status = RunStatus.EMERGENCY_BYPASS.value
        run.risk_tier = RiskTier.EMERGENCY_BYPASS.value
        run.confidence_index = 100.0
        run.is_emergency = True
        run.finished_at = utcnow()
        run.duration_ms = int((time.perf_counter() - t_run_start) * 1000)
        _update_enrollment(db, patient, run)
        audit.record(
            db,
            action="pipeline.emergency_bypass",
            resource_type="pipeline_run",
            resource_id=run.id,
            organization_id=run.organization_id,
            patient_id=patient.id,
            run_id=run.id,
            details={"rule_codes": g2_out.rule_codes, "emergency_event_id": str(g2_out.emergency_event_id)},
        )
        db.commit()
        event_bus.publish_run(
            run.organization_id,
            run.id,
            "pipeline.emergency_bypass",
            {"patient_id": str(patient.id), "rule_codes": g2_out.rule_codes, "emergency_event_id": str(g2_out.emergency_event_id)},
        )
        return run

    # If consent was missing and Gate 2 found no emergency, block now
    if not g1_out.allow_routine_processing:
        finish_step("gate2_emergency", StepStatus.COMPLETED, "Emergency screen negative; routine processing remains blocked pending consent.", g2_in, g2_out, g2_ms)
        skip_remaining(["agent3_aggregator", "agent4_scoring", "agent5_synthesis", "agent6_referral"], "Blocked at Gate 1 (no data_processing consent)")
        run.status = RunStatus.BLOCKED.value
        run.finished_at = utcnow()
        run.duration_ms = int((time.perf_counter() - t_run_start) * 1000)
        audit.record(db, action="pipeline.blocked", resource_type="pipeline_run", resource_id=run.id, organization_id=run.organization_id, patient_id=patient.id, run_id=run.id, outcome="denied")
        db.commit()
        event_bus.publish_run(run.organization_id, run.id, "pipeline.finished", {"status": run.status})
        return run

    finish_step("gate2_emergency", StepStatus.COMPLETED, "No acute red-flag crisis indicators detected.", g2_in, g2_out, g2_ms)

    # ---------------- AGENT 3: Longitudinal Signal Aggregator ----------------
    start_step("agent3_aggregator")
    t0 = time.perf_counter()
    agg_ctx = run_agent3(db, patient, run.track, run.as_of, present_streams=set(g1_out.present_streams))
    a3_ms = int((time.perf_counter() - t0) * 1000)
    finish_step(
        "agent3_aggregator",
        StepStatus.COMPLETED,
        f"Aggregated {agg_ctx.agent_output.total_observations_considered} observations across {len(agg_ctx.metric_inputs)} metric(s).",
        agg_ctx.agent_input,
        agg_ctx.agent_output,
        a3_ms,
    )

    # ---------------- AGENT 4: Deterministic Baseline & Drift Scoring ----------------
    start_step("agent4_scoring")
    t0 = time.perf_counter()
    a4_in, a4_out, bundle, _ = run_agent4(db, patient, run.track, run.id, run.as_of, agg_ctx)
    a4_ms = int((time.perf_counter() - t0) * 1000)
    a4_status = StepStatus.FLAGGED if bundle.risk_tier in {RiskTier.AMBER, RiskTier.RED} else StepStatus.COMPLETED
    a4_msg = (
        f"Deterministic tier={bundle.risk_tier.value}, primary={bundle.primary_metric_code} (Z={bundle.primary_z}), confidence={bundle.confidence_index}%."
        if bundle.primary_z is not None
        else f"Deterministic tier={bundle.risk_tier.value}, confidence={bundle.confidence_index}% (insufficient personal baseline windows)."
    )
    finish_step("agent4_scoring", a4_status, a4_msg, a4_in, a4_out, a4_ms)

    run.scoring_config_hash = bundle.config_hash
    run.risk_tier = bundle.risk_tier.value
    run.confidence_index = bundle.confidence_index
    db.commit()

    # ---------------- AGENT 5: Clinical Synthesis & Explainability (LLM) ----------------
    start_step("agent5_synthesis")
    t0 = time.perf_counter()
    a5_in, a5_out, syn = run_agent5(
        db,
        patient,
        run.id,
        bundle,
        active_scopes=set(g1_out.active_scopes),
        revoked_scopes=set(g1_out.revoked_or_missing_scopes),
    )
    a5_ms = int((time.perf_counter() - t0) * 1000)
    if syn.status == SynthesisStatus.COMPLETED.value:
        a5_status = StepStatus.COMPLETED
        a5_msg = f"Bilingual DECIDE-AI clinical review draft generated ({syn.provider}/{syn.model})."
    elif syn.status in {SynthesisStatus.PROVIDER_NOT_CONFIGURED.value, SynthesisStatus.CONSENT_NOT_GRANTED.value}:
        a5_status = StepStatus.FLAGGED
        a5_msg = syn.error or f"Synthesis status: {syn.status}"
    else:
        a5_status = StepStatus.FAILED
        a5_msg = syn.error or f"Synthesis failed: {syn.status}"
    finish_step("agent5_synthesis", a5_status, a5_msg, a5_in, a5_out, a5_ms)

    # ---------------- AGENT 6: Closed-Loop Care & Referral Orchestrator ----------------
    start_step("agent6_referral")
    t0 = time.perf_counter()
    a6_in, a6_out = run_agent6(
        db,
        patient,
        run.track,
        run.id,
        is_emergency=False,
        bundle=bundle,
        active_scopes=set(g1_out.active_scopes),
    )
    a6_ms = int((time.perf_counter() - t0) * 1000)
    a6_msg = (
        f"Referral pathway={a6_out.pathway} (coverage={a6_out.coverage_status}, status={a6_out.referral_status}) awaiting clinician sign-off."
        if a6_out.referral_id
        else f"Routine monitoring continued ({bundle.risk_tier.value})."
    )
    finish_step("agent6_referral", StepStatus.COMPLETED, a6_msg, a6_in, a6_out, a6_ms)

    run.status = RunStatus.COMPLETED.value
    run.finished_at = utcnow()
    run.duration_ms = int((time.perf_counter() - t_run_start) * 1000)
    _update_enrollment(db, patient, run)
    audit.record(
        db,
        action="pipeline.completed",
        resource_type="pipeline_run",
        resource_id=run.id,
        organization_id=run.organization_id,
        patient_id=patient.id,
        run_id=run.id,
        details={"track": run.track, "risk_tier": run.risk_tier, "confidence_index": run.confidence_index},
    )
    db.commit()
    event_bus.publish_run(
        run.organization_id,
        run.id,
        "pipeline.finished",
        {"status": run.status, "risk_tier": run.risk_tier, "confidence_index": run.confidence_index},
    )
    return run


def _update_enrollment(db: Session, patient: Patient, run: PipelineRun) -> None:
    enr = db.scalar(
        select(TrackEnrollment).where(
            TrackEnrollment.patient_id == patient.id,
            TrackEnrollment.track == run.track,
        )
    )
    if enr is not None:
        enr.latest_risk_tier = run.risk_tier
        enr.latest_run_id = run.id
        enr.latest_run_at = run.finished_at
