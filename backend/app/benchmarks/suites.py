"""Isolated synthetic benchmark fixture suite (never shown as real patients)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SUITE_NAME = "Recova Multi-Track Clinical & Safety Benchmark Suite"
SUITE_VERSION = "2026.1.0"


@dataclass(frozen=True)
class BenchmarkCaseSpec:
    case_id: str
    track: str
    scenario: str
    category: str  # normal|gradual_decline|missing_data|acute_emergency|confounder|consent
    grant_data_consent: bool
    baseline_days: dict[str, list[float]]
    current_days: dict[str, list[float]]
    checkin_text: str | None = None
    checkin_symptoms: list[str] = field(default_factory=list)
    self_reported_crisis: bool = False
    phq9_items: list[int] | None = None
    hearing_status: str = "normal"
    vision_status: str = "normal"
    # Expectations checked against real pipeline execution outputs
    expected_run_status: str = "completed"
    expected_risk_tier: str | None = None
    expected_emergency: bool = False
    expected_positive_drift: bool | None = None  # for sensitivity/specificity
    expected_max_confidence: float | None = None
    expected_consent_blocked: bool = False


BENCHMARK_SUITE: list[BenchmarkCaseSpec] = [
    # --- TRACK 1: RECOVA CORE ---
    BenchmarkCaseSpec(
        case_id="BM-CORE-01",
        track="core",
        scenario="Core: Stable Recovery Control (7.5h sleep, stable HRV & mood)",
        category="normal",
        grant_data_consent=True,
        baseline_days={
            "sleep_hours": [7.5, 7.8, 7.2, 7.6, 7.4],
            "hrv_rmssd": [52.0, 54.0, 50.0, 53.0, 51.0],
            "resting_hr": [62.0, 61.0, 63.0, 62.0, 61.0],
            "mood_score": [8.0, 8.0, 7.5, 8.0, 8.0],
        },
        current_days={
            "sleep_hours": [7.4, 7.5, 7.6],
            "hrv_rmssd": [51.5, 53.0, 52.0],
            "resting_hr": [62.0, 61.5, 62.0],
            "mood_score": [8.0, 8.0, 8.0],
        },
        checkin_text="Attended group session, sleeping steadily, low cravings.",
        expected_risk_tier="GREEN",
        expected_positive_drift=False,
    ),
    BenchmarkCaseSpec(
        case_id="BM-CORE-02",
        track="core",
        scenario="Core: Pre-Relapse Sleep & Autonomic Drift (4-day drop to 4.2h sleep)",
        category="gradual_decline",
        grant_data_consent=True,
        baseline_days={
            "sleep_hours": [7.8, 7.5, 7.6, 7.7, 7.4],
            "hrv_rmssd": [58.0, 56.0, 57.0, 59.0, 55.0],
            "resting_hr": [60.0, 61.0, 59.0, 60.0, 61.0],
            "mood_score": [8.0, 7.5, 8.0, 7.5, 8.0],
        },
        current_days={
            "sleep_hours": [5.1, 4.8, 4.2],
            "hrv_rmssd": [38.0, 35.0, 34.0],
            "resting_hr": [74.0, 76.0, 78.0],
            "mood_score": [4.0, 3.5, 3.0],
        },
        checkin_text="Struggling to sleep and feeling restless cravings at night.",
        expected_risk_tier="RED",
        expected_positive_drift=True,
    ),
    BenchmarkCaseSpec(
        case_id="BM-CORE-03",
        track="core",
        scenario="Core: Missing Smartwatch Sensor Stream (Check-in only graceful degradation)",
        category="missing_data",
        grant_data_consent=True,
        baseline_days={
            "mood_score": [7.5, 7.8, 7.2, 7.6, 7.4],
            "craving_score": [2.0, 1.5, 2.0, 2.0, 1.5],
        },
        current_days={
            "mood_score": [6.5, 6.2],
            "craving_score": [3.5, 4.0],
        },
        checkin_text="Took smartwatch off for charging; voice check-in completed.",
        expected_max_confidence=70.0,
    ),
    BenchmarkCaseSpec(
        case_id="BM-CORE-04",
        track="core",
        scenario="Core: Acute Suicidal Ideation Crisis (Gate 2 Emergency Bypass)",
        category="acute_emergency",
        grant_data_consent=True,
        baseline_days={"sleep_hours": [7.2, 7.4, 7.1, 7.3]},
        current_days={"sleep_hours": [3.0]},
        checkin_text="I feel hopeless and want to end my life tonight.",
        self_reported_crisis=True,
        expected_run_status="emergency_bypass",
        expected_risk_tier="EMERGENCY_BYPASS",
        expected_emergency=True,
        expected_positive_drift=True,
    ),
    BenchmarkCaseSpec(
        case_id="BM-CORE-05",
        track="core",
        scenario="Core: Severe Withdrawal Seizure Indicators (Gate 2 Emergency Bypass)",
        category="acute_emergency",
        grant_data_consent=True,
        baseline_days={"sleep_hours": [7.0, 7.1, 7.2, 7.0]},
        current_days={"resting_hr": [155.0]},
        checkin_text="Experiencing severe withdrawal tremors and visual hallucinations.",
        checkin_symptoms=["severe_withdrawal"],
        expected_run_status="emergency_bypass",
        expected_risk_tier="EMERGENCY_BYPASS",
        expected_emergency=True,
        expected_positive_drift=True,
    ),
    BenchmarkCaseSpec(
        case_id="BM-CONSENT-01",
        track="core",
        scenario="Governance: Missing Mandatory Consent Blocks Routine Analysis",
        category="consent",
        grant_data_consent=False,
        baseline_days={"sleep_hours": [7.2, 7.4, 7.3]},
        current_days={"sleep_hours": [5.0]},
        checkin_text="Normal routine check-in.",
        expected_run_status="blocked",
        expected_consent_blocked=True,
    ),
    # --- TRACK 2: RECOVA LOOP (IFHAS) ---
    BenchmarkCaseSpec(
        case_id="BM-LOOP-01",
        track="loop",
        scenario="Loop: Stable IFHAS Cardiometabolic Control",
        category="normal",
        grant_data_consent=True,
        baseline_days={
            "hba1c": [5.3, 5.4, 5.3, 5.4],
            "bp_systolic": [118.0, 120.0, 117.0, 119.0],
            "phq9_score": [2.0, 3.0, 2.0, 2.0],
            "steps": [7500.0, 7800.0, 7400.0, 7600.0],
        },
        current_days={
            "hba1c": [5.4],
            "bp_systolic": [119.0],
            "phq9_score": [2.0],
            "steps": [7550.0],
        },
        expected_risk_tier="GREEN",
        expected_positive_drift=False,
    ),
    BenchmarkCaseSpec(
        case_id="BM-LOOP-02",
        track="loop",
        scenario="Loop: IFHAS HbA1c & Blood Pressure Drift (5.4% -> 6.9%)",
        category="gradual_decline",
        grant_data_consent=True,
        baseline_days={
            "hba1c": [5.4, 5.5, 5.4, 5.6],
            "bp_systolic": [122.0, 124.0, 121.0, 123.0],
            "phq9_score": [3.0, 4.0, 3.0, 3.0],
            "steps": [6500.0, 6200.0, 6400.0, 6300.0],
        },
        current_days={
            "hba1c": [6.8, 6.9],
            "bp_systolic": [146.0, 148.0],
            "phq9_score": [11.0],
            "steps": [3900.0],
        },
        expected_risk_tier="RED",
        expected_positive_drift=True,
    ),
    BenchmarkCaseSpec(
        case_id="BM-LOOP-03",
        track="loop",
        scenario="Loop: PHQ-9 Item 9 Self-Harm Flag (Gate 2 Emergency Bypass)",
        category="acute_emergency",
        grant_data_consent=True,
        baseline_days={"phq9_score": [4.0, 5.0, 4.0, 5.0]},
        current_days={"phq9_score": [19.0]},
        phq9_items=[2, 2, 2, 2, 2, 2, 2, 2, 3],
        expected_run_status="emergency_bypass",
        expected_risk_tier="EMERGENCY_BYPASS",
        expected_emergency=True,
        expected_positive_drift=True,
    ),
    # --- TRACK 3: RECOVA NEURO ---
    BenchmarkCaseSpec(
        case_id="BM-NEURO-01",
        track="neuro",
        scenario="Neuro: Stable Cognitive Longitudinal Baseline",
        category="normal",
        grant_data_consent=True,
        baseline_days={
            "cog_sequence_accuracy": [90.0, 92.0, 88.0, 91.0],
            "cog_reaction_time_ms": [420.0, 410.0, 430.0, 415.0],
            "cog_rule_switch_accuracy": [88.0, 90.0, 87.0, 89.0],
            "cog_recall_accuracy": [86.0, 88.0, 85.0, 87.0],
            "sleep_hours": [7.2, 7.4, 7.1, 7.3],
        },
        current_days={
            "cog_sequence_accuracy": [91.0],
            "cog_reaction_time_ms": [418.0],
            "cog_rule_switch_accuracy": [89.0],
            "cog_recall_accuracy": [87.0],
            "sleep_hours": [7.3],
        },
        expected_risk_tier="GREEN",
        expected_positive_drift=False,
    ),
    BenchmarkCaseSpec(
        case_id="BM-NEURO-02",
        track="neuro",
        scenario="Neuro: Mild Presbycusis Confounder (SE Expanded — Avoids False Red)",
        category="confounder",
        grant_data_consent=True,
        hearing_status="mild_loss",
        baseline_days={
            "cog_auditory_accuracy": [88.0, 90.0, 86.0, 89.0],
            "sleep_hours": [7.2, 7.1, 7.3, 7.2],
        },
        current_days={
            "cog_auditory_accuracy": [86.5],
            "sleep_hours": [7.1],
        },
        expected_risk_tier="GREEN",
        expected_positive_drift=False,
    ),
    BenchmarkCaseSpec(
        case_id="BM-NEURO-03",
        track="neuro",
        scenario="Neuro: Actionable Executive & Recall Decline (All Streams Present)",
        category="gradual_decline",
        grant_data_consent=True,
        baseline_days={
            "cog_sequence_accuracy": [90.0, 91.0, 89.0, 90.0],
            "cog_reaction_time_ms": [410.0, 405.0, 415.0, 412.0],
            "cog_rule_switch_accuracy": [88.0, 89.0, 87.0, 88.0],
            "cog_recall_accuracy": [88.0, 89.0, 87.0, 88.0],
            "sleep_hours": [7.2, 7.4, 7.3, 7.1],
        },
        current_days={
            "cog_sequence_accuracy": [62.0],
            "cog_reaction_time_ms": [690.0],
            "cog_rule_switch_accuracy": [58.0],
            "cog_recall_accuracy": [55.0],
            "sleep_hours": [7.1],
        },
        expected_risk_tier="RED",
        expected_positive_drift=True,
    ),
    # --- TRACK 4: RECOVA WORKSAFE ---
    BenchmarkCaseSpec(
        case_id="BM-OSH-01",
        track="worksafe",
        scenario="WorkSafe: Normal Shift Readiness & Thermal Recovery",
        category="normal",
        grant_data_consent=True,
        baseline_days={
            "core_temp_est_c": [36.9, 37.0, 36.8, 37.0],
            "hr_recovery_minutes": [8.0, 9.0, 8.5, 8.0],
            "hrv_rmssd": [55.0, 56.0, 54.0, 55.0],
            "readiness_score": [9.0, 8.5, 9.0, 9.0],
        },
        current_days={
            "core_temp_est_c": [37.0],
            "hr_recovery_minutes": [8.5],
            "hrv_rmssd": [54.5],
            "readiness_score": [8.8],
        },
        expected_risk_tier="GREEN",
        expected_positive_drift=False,
    ),
    BenchmarkCaseSpec(
        case_id="BM-OSH-02",
        track="worksafe",
        scenario="WorkSafe: Delayed HR Recovery & Core Temp Drift (Heat Fatigue)",
        category="gradual_decline",
        grant_data_consent=True,
        baseline_days={
            "core_temp_est_c": [36.9, 37.0, 36.8, 37.1],
            "hr_recovery_minutes": [8.0, 9.0, 8.5, 9.5],
            "hrv_rmssd": [54.0, 55.0, 53.0, 56.0],
            "sleep_debt_hours": [0.5, 1.0, 0.5, 1.0],
        },
        current_days={
            "core_temp_est_c": [38.7],
            "hr_recovery_minutes": [24.0],
            "hrv_rmssd": [34.0],
            "sleep_debt_hours": [6.5],
        },
        expected_risk_tier="RED",
        expected_positive_drift=True,
    ),
    BenchmarkCaseSpec(
        case_id="BM-OSH-03",
        track="worksafe",
        scenario="WorkSafe: Suspected Exertional Heatstroke Core Temp >= 40C (Gate 2 Bypass)",
        category="acute_emergency",
        grant_data_consent=True,
        baseline_days={"core_temp_est_c": [37.0, 37.1, 36.9, 37.0]},
        current_days={"core_temp_est_c": [40.3]},
        checkin_text="Worker dizzy and disoriented during afternoon outdoor shift.",
        checkin_symptoms=["heatstroke_confusion"],
        expected_run_status="emergency_bypass",
        expected_risk_tier="EMERGENCY_BYPASS",
        expected_emergency=True,
        expected_positive_drift=True,
    ),
]
