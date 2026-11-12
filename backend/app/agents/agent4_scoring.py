"""Agent 4: Deterministic Baseline & Drift Scoring Agent."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.agent3_aggregator import AggregatedContext
from app.agents.schemas import Agent4Input, Agent4Output
from app.engine.scoring import ALGORITHM_VERSION, DeterministicScoreBundle, compute_track_score
from app.models.clinical import Patient
from app.models.engine import PersonalBaseline, ScoringResult


def run_agent4(
    db: Session,
    patient: Patient,
    track: str,
    run_id: uuid.UUID,
    as_of: datetime,
    ctx: AggregatedContext,
) -> tuple[Agent4Input, Agent4Output, DeterministicScoreBundle, ScoringResult]:
    inp = Agent4Input(
        track=track,
        algorithm_version=ALGORITHM_VERSION,
        metrics_count=len(ctx.metric_inputs),
    )
    bundle = compute_track_score(
        track=track,
        metric_inputs=ctx.metric_inputs,
        present_streams=ctx.present_streams,
        confounders=ctx.confounders,
    )

    # Persist/update PersonalBaseline rows for metrics that have >= 3 windows computed.
    for detail in bundle.metric_results:
        existing = db.scalar(
            select(PersonalBaseline).where(
                PersonalBaseline.patient_id == patient.id,
                PersonalBaseline.metric_code == detail.metric_code,
                PersonalBaseline.algorithm_version == ALGORITHM_VERSION,
            )
        )
        raw_inp = ctx.metric_inputs.get(detail.metric_code)
        if detail.baseline_status == "established" and raw_inp and len(raw_inp.baseline_values) >= 3:
            win = [
                {"window": raw_inp.baseline_labels[i] if i < len(raw_inp.baseline_labels) else f"w{i+1}", "value": v}
                for i, v in enumerate(raw_inp.baseline_values[:5])
            ]
            if existing is None:
                db.add(
                    PersonalBaseline(
                        organization_id=patient.organization_id,
                        patient_id=patient.id,
                        metric_code=detail.metric_code,
                        algorithm_version=ALGORITHM_VERSION,
                        status="established",
                        n_windows=detail.baseline_n,
                        mean=detail.baseline_mean,
                        sample_sd=detail.sample_sd_raw,
                        window_values=win,
                        established_at=as_of,
                    )
                )
            elif existing.status != "established":
                existing.status = "established"
                existing.n_windows = detail.baseline_n
                existing.mean = detail.baseline_mean
                existing.sample_sd = detail.sample_sd_raw
                existing.window_values = win
                existing.established_at = as_of

    sr = ScoringResult(
        organization_id=patient.organization_id,
        run_id=run_id,
        patient_id=patient.id,
        track=track,
        algorithm_version=ALGORITHM_VERSION,
        risk_tier=bundle.risk_tier.value,
        confidence_index=bundle.confidence_index,
        composite_index=bundle.composite_index,
        primary_metric_code=bundle.primary_metric_code,
        primary_z=bundle.primary_z,
        metric_results=[m for m in bundle.to_dict()["metric_results"]],
        missing_streams=bundle.missing_streams,
        confounders_applied=bundle.confounders_applied,
        config_snapshot=bundle.config_snapshot,
        computed_at=as_of,
    )
    db.add(sr)
    db.flush()

    out = Agent4Output(
        scoring_result_id=sr.id,
        algorithm_version=ALGORITHM_VERSION,
        risk_tier=bundle.risk_tier.value,
        confidence_index=bundle.confidence_index,
        composite_index=bundle.composite_index,
        primary_metric_code=bundle.primary_metric_code,
        primary_z=bundle.primary_z,
        missing_streams=bundle.missing_streams,
        confounders_applied=bundle.confounders_applied,
        metric_results=sr.metric_results,
    )
    return inp, out, bundle, sr
