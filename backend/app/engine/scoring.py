"""Agent 4: Deterministic Baseline and Longitudinal Drift Scoring Engine.

Strict architectural invariant:
- Pure mathematical Python calculations ONLY. Zero LLM involvement.
- Every mathematical input, confounder multiplier, baseline window, zero-variance guard
  and algorithm version is persisted for full reproducibility and clinical audit.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass, field
from typing import Any

from app.engine.metrics import METRIC_CATALOG, TRACK_CONFIGS, TrackMetricConfig, TrackScoringConfig
from app.models.enums import RiskTier

ALGORITHM_VERSION = "1.2.0"


@dataclass(frozen=True)
class ConfounderProfile:
    hearing_status: str | None = None              # normal|mild_loss|moderate_loss|severe_loss|aided
    vision_status: str | None = None               # normal|corrected|mild_impairment|severe_impairment
    primary_language_matches_assessment: bool | None = True
    education_level: str | None = None             # none|primary|secondary|tertiary|postgraduate
    cognitive_session_index: int = 1
    shift_work: bool = False
    poor_sleep_confounder: bool = False


@dataclass
class MetricWindowInput:
    metric_code: str
    baseline_values: list[float]                   # chronological window means (3..5 stable windows)
    current_values: list[float]                    # current evaluation window values
    baseline_labels: list[str] = field(default_factory=list)
    existing_baseline_mean: float | None = None
    existing_baseline_sd: float | None = None
    existing_baseline_n: int = 0


@dataclass
class MetricScoreDetail:
    metric_code: str
    label: str
    unit: str
    direction: str
    baseline_status: str                           # established|insufficient
    baseline_n: int
    baseline_mean: float | None
    sample_sd_raw: float | None
    sample_sd_used: float | None
    zero_variance_guarded: bool
    raw_se: float | None
    confounder_multiplier: float
    confounders_applied: list[str]
    adjusted_se: float | None
    practice_gain_offset: float
    current_observation: float | None
    current_n: int
    z_score: float | None
    abs_z: float | None
    drift_direction: str                           # worsening|improving|neutral|indeterminate
    risk_tier: str
    reference_alert: str | None                    # if baseline insufficient & reference cutoff triggered
    weight: float


@dataclass
class DeterministicScoreBundle:
    algorithm_version: str
    track: str
    config_hash: str
    risk_tier: RiskTier
    confidence_index: float
    composite_index: float | None
    primary_metric_code: str | None
    primary_z: float | None
    metric_results: list[MetricScoreDetail]
    missing_streams: list[str]
    confounders_applied: list[str]
    config_snapshot: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "algorithm_version": self.algorithm_version,
            "track": self.track,
            "config_hash": self.config_hash,
            "risk_tier": self.risk_tier.value,
            "confidence_index": self.confidence_index,
            "composite_index": self.composite_index,
            "primary_metric_code": self.primary_metric_code,
            "primary_z": self.primary_z,
            "metric_results": [asdict(m) for m in self.metric_results],
            "missing_streams": self.missing_streams,
            "confounders_applied": self.confounders_applied,
            "config_snapshot": self.config_snapshot,
        }


def classify_z(abs_z: float) -> RiskTier:
    if abs_z >= 1.96:
        return RiskTier.RED
    if abs_z >= 1.0:
        return RiskTier.AMBER
    return RiskTier.GREEN


def _confounder_adjustment(metric_code: str, track: str, conf: ConfounderProfile) -> tuple[float, list[str]]:
    """Compute documented SE expansion multiplier and list of applied confounders."""
    mult = 1.0
    applied: list[str] = []

    if track == "neuro" and metric_code.startswith("cog_"):
        if conf.hearing_status in {"mild_loss", "moderate_loss", "severe_loss"} and metric_code in {
            "cog_auditory_accuracy", "cog_sequence_accuracy", "cog_recall_accuracy"
        }:
            factor = 1.25 if conf.hearing_status == "mild_loss" else 1.35
            mult *= factor
            applied.append(f"hearing_status:{conf.hearing_status} (x{factor:.2f} SE)")
        if conf.vision_status in {"mild_impairment", "severe_impairment"} and metric_code in {
            "cog_visual_accuracy", "cog_sequence_accuracy", "cog_rule_switch_accuracy", "cog_reaction_time_ms"
        }:
            factor = 1.25 if conf.vision_status == "mild_impairment" else 1.35
            mult *= factor
            applied.append(f"vision_status:{conf.vision_status} (x{factor:.2f} SE)")
        if conf.primary_language_matches_assessment is False and metric_code in {
            "cog_recall_accuracy", "cog_rule_switch_accuracy"
        }:
            mult *= 1.15
            applied.append("language_mismatch (x1.15 SE)")
        if conf.education_level in {"none", "primary"}:
            mult *= 1.10
            applied.append(f"education_level:{conf.education_level} (x1.10 SE)")
        if conf.poor_sleep_confounder:
            mult *= 1.15
            applied.append("acute_sleep_deprivation_confounder (x1.15 SE)")

    if track == "core" and conf.shift_work and metric_code in {"sleep_hours", "hrv_rmssd"}:
        mult *= 1.15
        applied.append("shift_work_schedule (x1.15 SE)")

    # Bound maximum SE expansion so confounders cannot suppress extreme genuine collapse indefinitely.
    mult = min(round(mult, 4), 1.75)
    return mult, applied


def _practice_offset(
    metric_cfg: TrackMetricConfig,
    baseline_mean: float,
    direction: str,
    track_cfg: TrackScoringConfig,
    session_index: int,
) -> float:
    if not metric_cfg.apply_practice_effect or session_index <= 1 or track_cfg.practice_gain_rate <= 0:
        return 0.0
    # Diminishing logarithmic practice effect: 0 on session 1, grows sub-linearly and capped.
    pct = min(track_cfg.practice_gain_rate * math.log(session_index), track_cfg.max_practice_gain_pct)
    # Accuracy improves upward (+pct); reaction time improves downward (-pct).
    sign = -1.0 if direction == "higher_is_worse" else 1.0
    return round(sign * pct * baseline_mean, 4)


def _reference_alert(metric_code: str, value: float) -> str | None:
    spec = METRIC_CATALOG.get(metric_code)
    if spec is None:
        return None
    if spec.ref_red_high is not None and value >= spec.ref_red_high:
        return "RED"
    if spec.ref_red_low is not None and value <= spec.ref_red_low:
        return "RED"
    if spec.ref_amber_high is not None and value >= spec.ref_amber_high:
        return "AMBER"
    if spec.ref_amber_low is not None and value <= spec.ref_amber_low:
        return "AMBER"
    return "GREEN"


def score_metric(
    inp: MetricWindowInput,
    metric_cfg: TrackMetricConfig,
    track_cfg: TrackScoringConfig,
    conf: ConfounderProfile,
) -> MetricScoreDetail:
    spec = METRIC_CATALOG[inp.metric_code]
    valid_current = [v for v in inp.current_values if v is not None and math.isfinite(v)]
    current_mean = round(sum(valid_current) / len(valid_current), 4) if valid_current else None

    # Use persisted PersonalBaseline if established and no raw baseline slice provided,
    # otherwise compute deterministically from the first min..max stable baseline windows.
    valid_base = [v for v in inp.baseline_values if v is not None and math.isfinite(v)]
    if len(valid_base) >= track_cfg.min_baseline_windows:
        window = valid_base[: track_cfg.max_baseline_windows]
        n = len(window)
        mean = sum(window) / n
        variance = sum((x - mean) ** 2 for x in window) / max(n - 1, 1)
        sd_raw = math.sqrt(variance)
    elif inp.existing_baseline_mean is not None and inp.existing_baseline_n >= track_cfg.min_baseline_windows:
        n = inp.existing_baseline_n
        mean = inp.existing_baseline_mean
        sd_raw = inp.existing_baseline_sd or 0.0
    else:
        # Insufficient baseline windows: NEVER invent Z=0. Report insufficient explicitly.
        ref_tier = None
        tier = RiskTier.INDETERMINATE.value
        if current_mean is not None and metric_cfg.use_reference_fallback:
            ref_tier = _reference_alert(inp.metric_code, current_mean)
            if ref_tier in {"AMBER", "RED", "GREEN"}:
                tier = ref_tier
        return MetricScoreDetail(
            metric_code=spec.code,
            label=spec.label,
            unit=spec.unit,
            direction=spec.direction,
            baseline_status="insufficient",
            baseline_n=len(valid_base),
            baseline_mean=round(sum(valid_base) / len(valid_base), 4) if valid_base else None,
            sample_sd_raw=None,
            sample_sd_used=None,
            zero_variance_guarded=False,
            raw_se=None,
            confounder_multiplier=1.0,
            confounders_applied=[],
            adjusted_se=None,
            practice_gain_offset=0.0,
            current_observation=current_mean,
            current_n=len(valid_current),
            z_score=None,
            abs_z=None,
            drift_direction="indeterminate",
            risk_tier=tier,
            reference_alert=ref_tier,
            weight=metric_cfg.weight,
        )

    zero_guarded = sd_raw < spec.default_sd_floor
    sd_used = spec.default_sd_floor if zero_guarded else sd_raw
    raw_se = sd_used / math.sqrt(n)
    mult, conf_notes = _confounder_adjustment(spec.code, track_cfg.track, conf)
    adjusted_se = raw_se * mult
    practice_offset = _practice_offset(metric_cfg, mean, spec.direction, track_cfg, conf.cognitive_session_index)

    if current_mean is None:
        return MetricScoreDetail(
            metric_code=spec.code,
            label=spec.label,
            unit=spec.unit,
            direction=spec.direction,
            baseline_status="established",
            baseline_n=n,
            baseline_mean=round(mean, 4),
            sample_sd_raw=round(sd_raw, 4),
            sample_sd_used=round(sd_used, 4),
            zero_variance_guarded=zero_guarded,
            raw_se=round(raw_se, 4),
            confounder_multiplier=mult,
            confounders_applied=conf_notes,
            adjusted_se=round(adjusted_se, 4),
            practice_gain_offset=practice_offset,
            current_observation=None,
            current_n=0,
            z_score=None,
            abs_z=None,
            drift_direction="indeterminate",
            risk_tier=RiskTier.INDETERMINATE.value,
            reference_alert=None,
            weight=metric_cfg.weight,
        )

    # Guard against numerical zero even after sd_floor
    denom = adjusted_se if adjusted_se > 1e-9 else 1e-9
    z = (current_mean - (mean + practice_offset)) / denom
    abs_z = abs(z)

    if abs_z < 0.25:
        drift_dir = "neutral"
    elif spec.direction == "lower_is_worse":
        drift_dir = "worsening" if z < 0 else "improving"
    elif spec.direction == "higher_is_worse":
        drift_dir = "worsening" if z > 0 else "improving"
    else:
        drift_dir = "worsening" if abs_z >= 1.0 else "neutral"

    # Clinical rule: favourable improvement (e.g. sleep improving from 6h to 8h)
    # should not raise a RED clinical decline alarm, while still recording raw Z-score.
    # Only worsening or two-sided deviations escalate RiskTier; improvements stay GREEN
    # unless reference cutoff triggers.
    if drift_dir == "improving":
        tier = RiskTier.GREEN
    else:
        tier = classify_z(abs_z)

    ref_tier = _reference_alert(spec.code, current_mean) if metric_cfg.use_reference_fallback else None
    if ref_tier == "RED" and tier != RiskTier.RED:
        tier = RiskTier.RED
    elif ref_tier == "AMBER" and tier == RiskTier.GREEN:
        tier = RiskTier.AMBER

    return MetricScoreDetail(
        metric_code=spec.code,
        label=spec.label,
        unit=spec.unit,
        direction=spec.direction,
        baseline_status="established",
        baseline_n=n,
        baseline_mean=round(mean, 4),
        sample_sd_raw=round(sd_raw, 4),
        sample_sd_used=round(sd_used, 4),
        zero_variance_guarded=zero_guarded,
        raw_se=round(raw_se, 4),
        confounder_multiplier=mult,
        confounders_applied=conf_notes,
        adjusted_se=round(adjusted_se, 4),
        practice_gain_offset=practice_offset,
        current_observation=current_mean,
        current_n=len(valid_current),
        z_score=round(z, 4),
        abs_z=round(abs_z, 4),
        drift_direction=drift_dir,
        risk_tier=tier.value,
        reference_alert=ref_tier,
        weight=metric_cfg.weight,
    )


def compute_track_score(
    track: str,
    metric_inputs: dict[str, MetricWindowInput],
    present_streams: set[str],
    confounders: ConfounderProfile,
) -> DeterministicScoreBundle:
    """Run deterministic baseline & drift scoring across all metrics configured for a track."""
    track_cfg = TRACK_CONFIGS[track]
    details: list[MetricScoreDetail] = []
    all_conf_notes: list[str] = []

    for mcfg in track_cfg.metrics:
        inp = metric_inputs.get(mcfg.metric_code)
        if inp is None:
            continue
        if not inp.baseline_values and not inp.current_values and inp.existing_baseline_mean is None:
            continue
        d = score_metric(inp, mcfg, track_cfg, confounders)
        details.append(d)
        for c in d.confounders_applied:
            if c not in all_conf_notes:
                all_conf_notes.append(c)

    missing_streams = [s for s in track_cfg.expected_streams if s not in present_streams]

    # Confidence Index starts at 100, degrades for missing expected streams and immature baselines.
    confidence = 100.0 - len(missing_streams) * track_cfg.stream_missing_penalty
    scorable = [d for d in details if d.z_score is not None]
    insufficient_only = [d for d in details if d.baseline_status == "insufficient" and d.current_observation is not None]
    if details and not scorable and insufficient_only:
        confidence = min(confidence, 55.0)
    elif any(d.baseline_n < track_cfg.max_baseline_windows and d.baseline_status == "established" for d in details):
        confidence -= 5.0
    confidence = round(max(15.0, min(100.0, confidence)), 1)

    # Aggregate dimensionless Z-magnitudes via documented worst-tier + weighted RMS composite.
    # Incompatible units are NEVER summed or averaged raw.
    tier_rank = {
        RiskTier.INDETERMINATE.value: 0,
        RiskTier.GREEN.value: 1,
        RiskTier.AMBER.value: 2,
        RiskTier.RED.value: 3,
    }
    overall_tier = RiskTier.INDETERMINATE
    primary_metric_code: str | None = None
    primary_z: float | None = None
    composite_index: float | None = None

    active_scored = [d for d in details if d.risk_tier != RiskTier.INDETERMINATE.value]
    if active_scored:
        # Highest severity metric drives the track's risk tier (conservative clinical safety).
        worst = max(
            active_scored,
            key=lambda d: (tier_rank.get(d.risk_tier, 0), (d.abs_z or 0.0) * d.weight),
        )
        overall_tier = RiskTier(worst.risk_tier)
        primary_metric_code = worst.metric_code
        primary_z = worst.z_score

        worsening_or_scored = [d for d in details if d.z_score is not None]
        if worsening_or_scored:
            w_sum = sum(d.weight for d in worsening_or_scored)
            sq = sum(d.weight * ((d.abs_z or 0.0) if d.drift_direction != "improving" else 0.0) ** 2 for d in worsening_or_scored)
            composite_index = round(math.sqrt(sq / max(w_sum, 1e-9)), 4)

    snapshot = {
        "algorithm_version": ALGORITHM_VERSION,
        "track": track,
        "min_baseline_windows": track_cfg.min_baseline_windows,
        "max_baseline_windows": track_cfg.max_baseline_windows,
        "evaluation_window_days": track_cfg.evaluation_window_days,
        "practice_gain_rate": track_cfg.practice_gain_rate,
        "aggregation_method": "max_severity_tier + weighted_rms_worsening_z",
        "metrics_configured": [asdict(m) for m in track_cfg.metrics],
    }
    cfg_hash = hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()[:16]

    return DeterministicScoreBundle(
        algorithm_version=ALGORITHM_VERSION,
        track=track,
        config_hash=cfg_hash,
        risk_tier=overall_tier,
        confidence_index=confidence,
        composite_index=composite_index,
        primary_metric_code=primary_metric_code,
        primary_z=primary_z,
        metric_results=details,
        missing_streams=missing_streams,
        confounders_applied=all_conf_notes,
        config_snapshot=snapshot,
    )
