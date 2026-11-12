"""Agent 3: Longitudinal Signal and Context Aggregator."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.schemas import Agent3Input, Agent3Output
from app.engine.metrics import METRIC_CATALOG, TRACK_CONFIGS, normalize_unit
from app.engine.scoring import ALGORITHM_VERSION, ConfounderProfile, MetricWindowInput
from app.models.clinical import CognitiveAssessment, Observation, Patient, WorkplaceAssessment
from app.models.engine import PersonalBaseline


@dataclass
class AggregatedContext:
    agent_input: Agent3Input
    agent_output: Agent3Output
    metric_inputs: dict[str, MetricWindowInput]
    present_streams: set[str]
    confounders: ConfounderProfile
    fhir_observations: list[Observation]


def _group_windows(rows: list[Observation], metric_code: str, *, is_cognitive: bool, eval_cutoff: datetime) -> tuple[list[float], list[str], list[float]]:
    """Aggregate observations into daily means (or individual session values for cognitive tests),
    splitting initial baseline candidates from the current evaluation window.
    """
    ordered = sorted(rows, key=lambda r: r.effective_at)
    if is_cognitive:
        # Each assessment session is a discrete window; latest session is current, earlier sessions form baseline.
        vals = []
        labels = []
        for r in ordered:
            if r.value_num is None:
                continue
            v, _, _ = normalize_unit(metric_code, r.value_num, r.unit)
            vals.append(v)
            labels.append(r.effective_at.date().isoformat())
        if len(vals) <= 1:
            return [], [], vals
        return vals[:-1], labels[:-1], [vals[-1]]

    # Daily bucketing
    by_day: dict[str, list[float]] = defaultdict(list)
    for r in ordered:
        if r.value_num is None:
            continue
        v, _, _ = normalize_unit(metric_code, r.value_num, r.unit)
        by_day[r.effective_at.date().isoformat()].append(v)

    day_keys = sorted(by_day)
    if not day_keys:
        return [], [], []

    day_means = [(k, sum(by_day[k]) / len(by_day[k])) for k in day_keys]
    cutoff_day = eval_cutoff.date().isoformat()

    base_vals: list[float] = []
    base_labels: list[str] = []
    curr_vals: list[float] = []

    # First try calendar split: observations strictly before eval_cutoff -> baseline, >= eval_cutoff -> current.
    # If all observations sit inside the evaluation window (e.g., recently enrolled patient with 6 daily points),
    # split chronologically as initial stable windows (first 3-5) vs latest window(s) if total >= 4.
    before = [(k, v) for k, v in day_means if k < cutoff_day]
    recent = [(k, v) for k, v in day_means if k >= cutoff_day]
    if len(before) >= 3 and recent:
        base_labels = [k for k, _ in before]
        base_vals = [v for _, v in before]
        curr_vals = [v for _, v in recent]
    elif len(day_means) >= 4:
        split = min(5, max(3, len(day_means) - max(1, len(day_means) // 3)))
        base_labels = [k for k, _ in day_means[:split]]
        base_vals = [v for _, v in day_means[:split]]
        curr_vals = [v for _, v in day_means[split:]]
    else:
        # < 4 total windows: current gets all recent so single-visit clinical reference cutoffs can fire if configured
        curr_vals = [v for _, v in day_means]

    return base_vals, base_labels, curr_vals


def run_agent3(
    db: Session,
    patient: Patient,
    track: str,
    as_of: datetime,
    *,
    present_streams: set[str],
) -> AggregatedContext:
    cfg = TRACK_CONFIGS[track]
    eval_cutoff = as_of - timedelta(days=cfg.evaluation_window_days)
    history_cutoff = as_of - timedelta(days=365)

    inp = Agent3Input(
        patient_id=patient.id,
        track=track,
        as_of=as_of,
        evaluation_window_days=cfg.evaluation_window_days,
    )

    obs_rows = db.scalars(
        select(Observation)
        .where(
            Observation.organization_id == patient.organization_id,
            Observation.patient_id == patient.id,
            Observation.effective_at <= as_of,
            Observation.effective_at >= history_cutoff,
            Observation.status != "entered_in_error",
        )
        .order_by(Observation.effective_at.asc())
    ).all()

    by_metric: dict[str, list[Observation]] = defaultdict(list)
    streams = set(present_streams)
    for o in obs_rows:
        by_metric[o.metric_code].append(o)
        spec = METRIC_CATALOG.get(o.metric_code)
        if spec:
            streams.add(spec.stream_name)

    # For WorkSafe, incorporate department workplace environmental readings if patient didn't log own.
    if track == "worksafe" and patient.department_id:
        env_rows = db.scalars(
            select(WorkplaceAssessment)
            .where(
                WorkplaceAssessment.organization_id == patient.organization_id,
                WorkplaceAssessment.department_id == patient.department_id,
                WorkplaceAssessment.measured_at <= as_of,
                WorkplaceAssessment.measured_at >= as_of - timedelta(days=30),
            )
            .order_by(WorkplaceAssessment.measured_at.asc())
        ).all()
        if env_rows:
            streams.add("workplace_env")
            for er in env_rows:
                if er.heat_index_c is not None and not by_metric.get("heat_index_c"):
                    by_metric["heat_index_c"].append(
                        Observation(
                            organization_id=patient.organization_id,
                            patient_id=patient.id,
                            track="worksafe",
                            metric_code="heat_index_c",
                            value_num=er.heat_index_c,
                            unit="C",
                            effective_at=er.measured_at,
                            source="workplace",
                        )
                    )

    # Load any existing established PersonalBaselines for this algorithm version
    existing_baselines = {
        b.metric_code: b
        for b in db.scalars(
            select(PersonalBaseline).where(
                PersonalBaseline.patient_id == patient.id,
                PersonalBaseline.algorithm_version == ALGORITHM_VERSION,
                PersonalBaseline.status == "established",
            )
        ).all()
    }

    metric_inputs: dict[str, MetricWindowInput] = {}
    base_counts: dict[str, int] = {}
    curr_counts: dict[str, int] = {}

    for mcfg in cfg.metrics:
        mcode = mcfg.metric_code
        rows = by_metric.get(mcode, [])
        eb = existing_baselines.get(mcode)
        if not rows and eb is None:
            continue
        is_cog = mcode.startswith("cog_")
        b_vals, b_labels, c_vals = _group_windows(rows, mcode, is_cognitive=is_cog, eval_cutoff=eval_cutoff)
        if eb is not None and len(b_vals) < cfg.min_baseline_windows:
            # Reuse persisted baseline when new query slice has only current observations
            curr_all = []
            for r in sorted(rows, key=lambda x: x.effective_at):
                if r.value_num is not None and r.effective_at >= eval_cutoff:
                    v, _, _ = normalize_unit(mcode, r.value_num, r.unit)
                    curr_all.append(v)
            if curr_all:
                c_vals = curr_all
        metric_inputs[mcode] = MetricWindowInput(
            metric_code=mcode,
            baseline_values=b_vals,
            baseline_labels=b_labels,
            current_values=c_vals,
            existing_baseline_mean=eb.mean if eb else None,
            existing_baseline_sd=eb.sample_sd if eb else None,
            existing_baseline_n=eb.n_windows if eb else 0,
        )
        base_counts[mcode] = max(len(b_vals), eb.n_windows if eb else 0)
        curr_counts[mcode] = len(c_vals)

    # Confounder profile (Neuro session index, sensory impairments, sleep confounder, shift work)
    cog_sessions = db.scalars(
        select(CognitiveAssessment)
        .where(
            CognitiveAssessment.organization_id == patient.organization_id,
            CognitiveAssessment.patient_id == patient.id,
            CognitiveAssessment.started_at <= as_of,
            CognitiveAssessment.status == "completed",
        )
    ).all()
    recent_sleep = [r.value_num for r in by_metric.get("sleep_hours", []) if r.value_num is not None and r.effective_at >= eval_cutoff]
    poor_sleep = bool(recent_sleep and (sum(recent_sleep) / len(recent_sleep)) < 5.0)
    shift_work = bool((patient.clinical_history or {}).get("shift_work"))

    confounders = ConfounderProfile(
        hearing_status=patient.hearing_status,
        vision_status=patient.vision_status,
        primary_language_matches_assessment=patient.primary_language_matches_assessment,
        education_level=patient.education_level,
        cognitive_session_index=max(1, len(cog_sessions)),
        shift_work=shift_work,
        poor_sleep_confounder=poor_sleep,
    )

    out = Agent3Output(
        present_streams=sorted(streams),
        metrics_with_data=sorted(metric_inputs.keys()),
        total_observations_considered=len(obs_rows),
        baseline_windows_count=base_counts,
        current_windows_count=curr_counts,
        confounders_detected={
            "hearing_status": confounders.hearing_status,
            "vision_status": confounders.vision_status,
            "language_matches": confounders.primary_language_matches_assessment,
            "education_level": confounders.education_level,
            "cognitive_session_index": confounders.cognitive_session_index,
            "poor_sleep_confounder": confounders.poor_sleep_confounder,
            "shift_work": confounders.shift_work,
        },
        fhir_observations_mapped=len(obs_rows),
    )

    return AggregatedContext(
        agent_input=inp,
        agent_output=out,
        metric_inputs=metric_inputs,
        present_streams=streams,
        confounders=confounders,
        fhir_observations=list(obs_rows),
    )
