"""Canonical biomarker/signal catalog, unit normalization, and track scoring configurations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Direction = Literal["lower_is_worse", "higher_is_worse", "two_sided"]


@dataclass(frozen=True)
class MetricSpec:
    code: str
    label: str
    unit: str
    stream_name: str
    direction: Direction
    valid_min: float
    valid_max: float
    default_sd_floor: float
    loinc_code: str
    loinc_display: str
    # Optional clinical reference cutoffs for single-visit screening/OSH alerts when
    # < 3 baseline windows exist (never substituted for personal Z-score; reported separately).
    ref_amber_high: float | None = None
    ref_red_high: float | None = None
    ref_amber_low: float | None = None
    ref_red_low: float | None = None


METRIC_CATALOG: dict[str, MetricSpec] = {
    # --- Core / Shared Wearable & Check-in ---
    "sleep_hours": MetricSpec(
        code="sleep_hours", label="Sleep Duration", unit="h", stream_name="wearable_sleep",
        direction="lower_is_worse", valid_min=0.0, valid_max=20.0, default_sd_floor=0.25,
        loinc_code="93832-4", loinc_display="Sleep duration",
        ref_amber_low=5.5, ref_red_low=4.5,
    ),
    "hrv_rmssd": MetricSpec(
        code="hrv_rmssd", label="Heart Rate Variability (RMSSD)", unit="ms", stream_name="wearable_hrv",
        direction="lower_is_worse", valid_min=3.0, valid_max=250.0, default_sd_floor=3.0,
        loinc_code="80404-7", loinc_display="R-R interval.standard deviation (Heart rate variability)",
    ),
    "resting_hr": MetricSpec(
        code="resting_hr", label="Resting Heart Rate", unit="bpm", stream_name="wearable_hr",
        direction="higher_is_worse", valid_min=25.0, valid_max=220.0, default_sd_floor=2.0,
        loinc_code="40443-4", loinc_display="Heart rate - resting",
        ref_amber_high=95.0, ref_red_high=110.0,
    ),
    "steps": MetricSpec(
        code="steps", label="Daily Steps", unit="steps/d", stream_name="wearable_activity",
        direction="lower_is_worse", valid_min=0.0, valid_max=100000.0, default_sd_floor=400.0,
        loinc_code="41950-7", loinc_display="Number of steps in 24 hour Measured",
    ),
    "mood_score": MetricSpec(
        code="mood_score", label="Self-Reported Mood (0-10)", unit="score", stream_name="daily_checkin",
        direction="lower_is_worse", valid_min=0.0, valid_max=10.0, default_sd_floor=0.5,
        loinc_code="72107-6", loinc_display="Mood score",
        ref_amber_low=4.0, ref_red_low=2.0,
    ),
    "craving_score": MetricSpec(
        code="craving_score", label="Craving Intensity (0-10)", unit="score", stream_name="daily_checkin",
        direction="higher_is_worse", valid_min=0.0, valid_max=10.0, default_sd_floor=0.5,
        loinc_code="89652-2", loinc_display="Craving severity score",
        ref_amber_high=5.0, ref_red_high=7.5,
    ),
    "stress_score": MetricSpec(
        code="stress_score", label="Perceived Stress (0-10)", unit="score", stream_name="daily_checkin",
        direction="higher_is_worse", valid_min=0.0, valid_max=10.0, default_sd_floor=0.5,
        loinc_code="93038-8", loinc_display="Stress level",
        ref_amber_high=6.0, ref_red_high=8.0,
    ),
    "sleep_quality": MetricSpec(
        code="sleep_quality", label="Sleep Quality (0-10)", unit="score", stream_name="daily_checkin",
        direction="lower_is_worse", valid_min=0.0, valid_max=10.0, default_sd_floor=0.5,
        loinc_code="93831-6", loinc_display="Sleep quality",
    ),
    # --- Loop (IFHAS Screening) ---
    "hba1c": MetricSpec(
        code="hba1c", label="Hemoglobin A1c", unit="%", stream_name="ifhas_labs",
        direction="higher_is_worse", valid_min=3.0, valid_max=20.0, default_sd_floor=0.15,
        loinc_code="4548-4", loinc_display="Hemoglobin A1c/Hemoglobin.total in Blood",
        ref_amber_high=5.7, ref_red_high=6.5,
    ),
    "bp_systolic": MetricSpec(
        code="bp_systolic", label="Systolic Blood Pressure", unit="mmHg", stream_name="ifhas_vitals",
        direction="higher_is_worse", valid_min=50.0, valid_max=280.0, default_sd_floor=4.0,
        loinc_code="8480-6", loinc_display="Systolic blood pressure",
        ref_amber_high=130.0, ref_red_high=140.0,
    ),
    "bp_diastolic": MetricSpec(
        code="bp_diastolic", label="Diastolic Blood Pressure", unit="mmHg", stream_name="ifhas_vitals",
        direction="higher_is_worse", valid_min=30.0, valid_max=180.0, default_sd_floor=3.0,
        loinc_code="8462-4", loinc_display="Diastolic blood pressure",
        ref_amber_high=85.0, ref_red_high=90.0,
    ),
    "phq9_score": MetricSpec(
        code="phq9_score", label="PHQ-9 Depression Score", unit="score", stream_name="ifhas_phq9",
        direction="higher_is_worse", valid_min=0.0, valid_max=27.0, default_sd_floor=1.0,
        loinc_code="44261-6", loinc_display="Patient Health Questionnaire 9 item (PHQ-9) total score",
        ref_amber_high=10.0, ref_red_high=15.0,
    ),
    "ldl_cholesterol": MetricSpec(
        code="ldl_cholesterol", label="LDL Cholesterol", unit="mg/dL", stream_name="ifhas_lipids",
        direction="higher_is_worse", valid_min=15.0, valid_max=500.0, default_sd_floor=6.0,
        loinc_code="13457-7", loinc_display="Cholesterol in LDL [Mass/volume] in Serum or Plasma",
        ref_amber_high=130.0, ref_red_high=160.0,
    ),
    "total_cholesterol": MetricSpec(
        code="total_cholesterol", label="Total Cholesterol", unit="mg/dL", stream_name="ifhas_lipids",
        direction="higher_is_worse", valid_min=50.0, valid_max=700.0, default_sd_floor=8.0,
        loinc_code="2093-3", loinc_display="Cholesterol [Mass/volume] in Serum or Plasma",
        ref_amber_high=200.0, ref_red_high=240.0,
    ),
    "hdl_cholesterol": MetricSpec(
        code="hdl_cholesterol", label="HDL Cholesterol", unit="mg/dL", stream_name="ifhas_lipids",
        direction="lower_is_worse", valid_min=10.0, valid_max=180.0, default_sd_floor=3.0,
        loinc_code="2085-9", loinc_display="Cholesterol in HDL [Mass/volume] in Serum or Plasma",
        ref_amber_low=45.0, ref_red_low=35.0,
    ),
    "triglycerides": MetricSpec(
        code="triglycerides", label="Triglycerides", unit="mg/dL", stream_name="ifhas_lipids",
        direction="higher_is_worse", valid_min=20.0, valid_max=2000.0, default_sd_floor=10.0,
        loinc_code="2571-8", loinc_display="Triglyceride [Mass/volume] in Serum or Plasma",
        ref_amber_high=150.0, ref_red_high=200.0,
    ),
    # --- Neuro (Multi-Cognitive Studio) ---
    "cog_sequence_accuracy": MetricSpec(
        code="cog_sequence_accuracy", label="Sequence Memory Accuracy", unit="%", stream_name="cognitive_sequence",
        direction="lower_is_worse", valid_min=0.0, valid_max=100.0, default_sd_floor=3.0,
        loinc_code="72171-2", loinc_display="Cognitive sequence recall accuracy",
    ),
    "cog_reaction_time_ms": MetricSpec(
        code="cog_reaction_time_ms", label="Cognitive Reaction Latency", unit="ms", stream_name="cognitive_sequence",
        direction="higher_is_worse", valid_min=80.0, valid_max=15000.0, default_sd_floor=25.0,
        loinc_code="72172-0", loinc_display="Cognitive response reaction time",
    ),
    "cog_visual_accuracy": MetricSpec(
        code="cog_visual_accuracy", label="Visual Sequence Accuracy", unit="%", stream_name="cognitive_sequence",
        direction="lower_is_worse", valid_min=0.0, valid_max=100.0, default_sd_floor=3.0,
        loinc_code="72173-8", loinc_display="Visual working memory accuracy",
    ),
    "cog_auditory_accuracy": MetricSpec(
        code="cog_auditory_accuracy", label="Auditory Sequence Accuracy", unit="%", stream_name="cognitive_sequence",
        direction="lower_is_worse", valid_min=0.0, valid_max=100.0, default_sd_floor=3.0,
        loinc_code="72174-6", loinc_display="Auditory working memory accuracy",
    ),
    "cog_rule_switch_accuracy": MetricSpec(
        code="cog_rule_switch_accuracy", label="Rule-Switching Accuracy", unit="%", stream_name="cognitive_executive",
        direction="lower_is_worse", valid_min=0.0, valid_max=100.0, default_sd_floor=3.0,
        loinc_code="72175-3", loinc_display="Executive set-shifting accuracy",
    ),
    "cog_recall_accuracy": MetricSpec(
        code="cog_recall_accuracy", label="Delayed Recall Accuracy", unit="%", stream_name="cognitive_recall",
        direction="lower_is_worse", valid_min=0.0, valid_max=100.0, default_sd_floor=3.0,
        loinc_code="72176-1", loinc_display="Delayed memory recall accuracy",
    ),
    # --- WorkSafe (Occupational Safety & Heat Stress) ---
    "core_temp_est_c": MetricSpec(
        code="core_temp_est_c", label="Estimated Core Body Temperature", unit="C", stream_name="wearable_thermal",
        direction="higher_is_worse", valid_min=33.0, valid_max=44.0, default_sd_floor=0.2,
        loinc_code="8310-5", loinc_display="Body temperature",
        ref_amber_high=37.8, ref_red_high=38.5,
    ),
    "hr_recovery_minutes": MetricSpec(
        code="hr_recovery_minutes", label="Post-Shift HR Recovery Time", unit="min", stream_name="wearable_thermal",
        direction="higher_is_worse", valid_min=1.0, valid_max=180.0, default_sd_floor=1.5,
        loinc_code="8867-4", loinc_display="Heart rate recovery duration",
        ref_amber_high=15.0, ref_red_high=20.0,
    ),
    "sleep_debt_hours": MetricSpec(
        code="sleep_debt_hours", label="Cumulative Sleep Debt", unit="h", stream_name="wearable_sleep",
        direction="higher_is_worse", valid_min=0.0, valid_max=40.0, default_sd_floor=0.5,
        loinc_code="93833-2", loinc_display="Sleep debt duration",
        ref_amber_high=3.0, ref_red_high=6.0,
    ),
    "ambient_temp_c": MetricSpec(
        code="ambient_temp_c", label="Workplace Ambient Temperature", unit="C", stream_name="workplace_env",
        direction="higher_is_worse", valid_min=-20.0, valid_max=65.0, default_sd_floor=1.0,
        loinc_code="75228-7", loinc_display="Ambient temperature",
        ref_amber_high=35.0, ref_red_high=40.0,
    ),
    "heat_index_c": MetricSpec(
        code="heat_index_c", label="Workplace Heat Index", unit="C", stream_name="workplace_env",
        direction="higher_is_worse", valid_min=-10.0, valid_max=75.0, default_sd_floor=1.0,
        loinc_code="75229-5", loinc_display="Apparent heat index temperature",
        ref_amber_high=38.0, ref_red_high=43.0,
    ),
    "shift_duration_hours": MetricSpec(
        code="shift_duration_hours", label="Shift Duration", unit="h", stream_name="workplace_env",
        direction="higher_is_worse", valid_min=0.0, valid_max=24.0, default_sd_floor=0.5,
        loinc_code="75230-3", loinc_display="Work shift duration",
        ref_amber_high=10.0, ref_red_high=12.0,
    ),
    "readiness_score": MetricSpec(
        code="readiness_score", label="Worker Shift Readiness (0-10)", unit="score", stream_name="worker_readiness",
        direction="lower_is_worse", valid_min=0.0, valid_max=10.0, default_sd_floor=0.5,
        loinc_code="75231-1", loinc_display="Pre-shift worker readiness score",
        ref_amber_low=5.0, ref_red_low=3.0,
    ),
}


@dataclass(frozen=True)
class TrackMetricConfig:
    metric_code: str
    weight: float = 1.0
    apply_practice_effect: bool = False
    use_reference_fallback: bool = False


@dataclass(frozen=True)
class TrackScoringConfig:
    track: str
    expected_streams: tuple[str, ...]
    metrics: tuple[TrackMetricConfig, ...]
    min_baseline_windows: int = 3
    max_baseline_windows: int = 5
    evaluation_window_days: int = 7
    practice_gain_rate: float = 0.0
    max_practice_gain_pct: float = 0.12
    stream_missing_penalty: float = 20.0


TRACK_CONFIGS: dict[str, TrackScoringConfig] = {
    "core": TrackScoringConfig(
        track="core",
        expected_streams=("wearable_sleep", "wearable_hrv", "wearable_hr", "daily_checkin"),
        metrics=(
            TrackMetricConfig("sleep_hours", weight=1.2),
            TrackMetricConfig("hrv_rmssd", weight=1.1),
            TrackMetricConfig("resting_hr", weight=1.0),
            TrackMetricConfig("mood_score", weight=1.2),
            TrackMetricConfig("craving_score", weight=1.3),
            TrackMetricConfig("stress_score", weight=1.0),
            TrackMetricConfig("steps", weight=0.6),
        ),
        stream_missing_penalty=18.0,
    ),
    "loop": TrackScoringConfig(
        track="loop",
        expected_streams=("ifhas_labs", "ifhas_vitals", "ifhas_phq9", "wearable_activity"),
        metrics=(
            TrackMetricConfig("hba1c", weight=1.4, use_reference_fallback=True),
            TrackMetricConfig("bp_systolic", weight=1.2, use_reference_fallback=True),
            TrackMetricConfig("bp_diastolic", weight=1.0, use_reference_fallback=True),
            TrackMetricConfig("phq9_score", weight=1.3, use_reference_fallback=True),
            TrackMetricConfig("ldl_cholesterol", weight=0.9, use_reference_fallback=True),
            TrackMetricConfig("hdl_cholesterol", weight=0.8, use_reference_fallback=True),
            TrackMetricConfig("triglycerides", weight=0.8, use_reference_fallback=True),
            TrackMetricConfig("steps", weight=0.6),
        ),
        stream_missing_penalty=15.0,
    ),
    "neuro": TrackScoringConfig(
        track="neuro",
        expected_streams=("cognitive_sequence", "cognitive_executive", "cognitive_recall", "wearable_sleep"),
        metrics=(
            TrackMetricConfig("cog_sequence_accuracy", weight=1.3, apply_practice_effect=True),
            TrackMetricConfig("cog_reaction_time_ms", weight=1.1, apply_practice_effect=True),
            TrackMetricConfig("cog_visual_accuracy", weight=1.0, apply_practice_effect=True),
            TrackMetricConfig("cog_auditory_accuracy", weight=1.0, apply_practice_effect=True),
            TrackMetricConfig("cog_rule_switch_accuracy", weight=1.2, apply_practice_effect=True),
            TrackMetricConfig("cog_recall_accuracy", weight=1.3, apply_practice_effect=True),
            TrackMetricConfig("sleep_hours", weight=0.7),
            TrackMetricConfig("hba1c", weight=0.6, use_reference_fallback=True),
        ),
        practice_gain_rate=0.04,  # 4% * ln(session_index), capped at 12%
        stream_missing_penalty=15.0,
    ),
    "worksafe": TrackScoringConfig(
        track="worksafe",
        expected_streams=("worker_readiness", "wearable_thermal", "wearable_hrv", "workplace_env"),
        metrics=(
            TrackMetricConfig("core_temp_est_c", weight=1.4, use_reference_fallback=True),
            TrackMetricConfig("hr_recovery_minutes", weight=1.3, use_reference_fallback=True),
            TrackMetricConfig("hrv_rmssd", weight=1.1),
            TrackMetricConfig("sleep_debt_hours", weight=1.1, use_reference_fallback=True),
            TrackMetricConfig("heat_index_c", weight=1.0, use_reference_fallback=True),
            TrackMetricConfig("readiness_score", weight=1.2, use_reference_fallback=True),
            TrackMetricConfig("shift_duration_hours", weight=0.8, use_reference_fallback=True),
        ),
        stream_missing_penalty=16.0,
    ),
}


def normalize_unit(metric_code: str, value: float, unit: str | None) -> tuple[float, str, list[str]]:
    """Convert compatible units to the metric's canonical unit and return quality flags."""
    spec = METRIC_CATALOG.get(metric_code)
    if spec is None:
        return value, unit or "unit", ["unknown_metric"]

    flags: list[str] = []
    u = (unit or spec.unit).strip()
    u_low = u.lower()

    if spec.unit == "C" and u_low in {"f", "degf", "°f", "fahrenheit"}:
        value = (value - 32.0) * 5.0 / 9.0
        u = "C"
        flags.append("unit_converted_f_to_c")
    elif spec.unit == "C" and u_low in {"c", "degc", "°c", "celsius"}:
        u = "C"
    elif spec.unit == "h" and u_low in {"min", "mins", "minute", "minutes"}:
        value = value / 60.0
        u = "h"
        flags.append("unit_converted_min_to_h")
    elif spec.unit == "h" and u_low in {"h", "hr", "hrs", "hour", "hours"}:
        u = "h"
    elif spec.unit == "ms" and u_low in {"s", "sec", "secs", "second", "seconds"}:
        value = value * 1000.0
        u = "ms"
        flags.append("unit_converted_s_to_ms")
    elif spec.unit == "min" and u_low in {"s", "sec", "seconds"}:
        value = value / 60.0
        u = "min"
        flags.append("unit_converted_s_to_min")
    elif u_low != spec.unit.lower():
        flags.append(f"unexpected_unit:{u}")

    if value < spec.valid_min or value > spec.valid_max:
        flags.append("out_of_physiological_bounds")

    return value, spec.unit, flags


def compute_heat_index_c(ambient_temp_c: float, relative_humidity_pct: float) -> float:
    """NOAA/NWS Rothfusz regression heat index in Celsius."""
    t_f = ambient_temp_c * 9.0 / 5.0 + 32.0
    rh = max(0.0, min(100.0, relative_humidity_pct))
    if t_f < 80.0:
        hi_f = 0.5 * (t_f + 61.0 + ((t_f - 68.0) * 1.2) + (rh * 0.094))
    else:
        hi_f = (
            -42.379
            + 2.04901523 * t_f
            + 10.14333127 * rh
            - 0.22475541 * t_f * rh
            - 0.00683783 * t_f * t_f
            - 0.05481717 * rh * rh
            + 0.00122874 * t_f * t_f * rh
            + 0.00085282 * t_f * rh * rh
            - 0.00000199 * t_f * t_f * rh * rh
        )
    return round((hi_f - 32.0) * 5.0 / 9.0, 2)
