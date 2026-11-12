"""Tests for deterministic mathematical scoring, unit normalization, and edge cases."""

from __future__ import annotations

import math

from app.engine.metrics import compute_heat_index_c, normalize_unit
from app.engine.scoring import ConfounderProfile, MetricWindowInput, compute_track_score
from app.models.enums import RiskTier


def test_unit_normalization_conversions():
    v, u, flags = normalize_unit("core_temp_est_c", 104.0, "F")
    assert round(v, 2) == 40.0
    assert u == "C"
    assert "unit_converted_f_to_c" in flags

    v2, u2, flags2 = normalize_unit("sleep_hours", 450.0, "minutes")
    assert round(v2, 2) == 7.5
    assert u2 == "h"
    assert "unit_converted_min_to_h" in flags2

    _, _, flags3 = normalize_unit("core_temp_est_c", 50.0, "C")
    assert "out_of_physiological_bounds" in flags3


def test_heat_index_computation():
    hi = compute_heat_index_c(40.0, 60.0)
    assert hi > 50.0
    hi_cool = compute_heat_index_c(22.0, 40.0)
    assert hi_cool < 25.0


def test_zero_variance_guard_prevents_division_by_zero():
    bundle = compute_track_score(
        "core",
        {
            "sleep_hours": MetricWindowInput(
                metric_code="sleep_hours",
                baseline_values=[7.0, 7.0, 7.0, 7.0],
                current_values=[4.5],
            )
        },
        present_streams={"wearable_sleep"},
        confounders=ConfounderProfile(),
    )
    d = bundle.metric_results[0]
    assert d.zero_variance_guarded is True
    assert d.sample_sd_raw == 0.0
    assert d.sample_sd_used == 0.25
    assert d.z_score is not None and math.isfinite(d.z_score)
    assert bundle.risk_tier == RiskTier.RED


def test_insufficient_baseline_returns_indeterminate_for_wearable():
    bundle = compute_track_score(
        "core",
        {
            "sleep_hours": MetricWindowInput(
                metric_code="sleep_hours",
                baseline_values=[7.0, 7.2],
                current_values=[5.0],
            )
        },
        present_streams={"wearable_sleep"},
        confounders=ConfounderProfile(),
    )
    d = bundle.metric_results[0]
    assert d.baseline_status == "insufficient"
    assert d.z_score is None
    assert bundle.risk_tier == RiskTier.INDETERMINATE
    assert bundle.confidence_index <= 55.0


def test_neuro_confounder_and_practice_effect_adjustments():
    # Without hearing confounder: 88 -> 84.5 on SD~1.5 (SE~0.75) would be Z ~ -4.6 (RED)
    # Wait: let's test an edge case where mild hearing loss expands SE enough to prevent false RED
    baseline = [88.0, 90.0, 86.0, 89.0]  # mean=88.25, SD_floor=3.0, raw_se=1.50
    current = [85.0]                     # diff = -3.25 -> raw Z = -2.17 (RED without adjustment), -1.73 (AMBER with 1.25x)
    no_conf = compute_track_score(
        "neuro",
        {"cog_auditory_accuracy": MetricWindowInput("cog_auditory_accuracy", baseline, current)},
        present_streams={"cognitive_sequence"},
        confounders=ConfounderProfile(hearing_status="normal"),
    )
    with_conf = compute_track_score(
        "neuro",
        {"cog_auditory_accuracy": MetricWindowInput("cog_auditory_accuracy", baseline, current)},
        present_streams={"cognitive_sequence"},
        confounders=ConfounderProfile(hearing_status="mild_loss"),
    )
    assert no_conf.metric_results[0].risk_tier == "RED"
    assert with_conf.metric_results[0].confounder_multiplier == 1.25
    assert with_conf.metric_results[0].risk_tier == "AMBER"

    # Session 2 adds logarithmic practice gain offset for cognitive accuracy
    sess2 = compute_track_score(
        "neuro",
        {"cog_sequence_accuracy": MetricWindowInput("cog_sequence_accuracy", [80.0, 82.0, 81.0, 83.0], [84.0])},
        present_streams={"cognitive_sequence"},
        confounders=ConfounderProfile(cognitive_session_index=2),
    )
    assert sess2.metric_results[0].practice_gain_offset > 0.0
