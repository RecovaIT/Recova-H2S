"""Benchmark runner executing isolated synthetic fixtures through the real 6-agent pipeline."""

from __future__ import annotations

import time
import uuid
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.agent3_aggregator import run_agent3
from app.agents.orchestrator import create_pipeline_run, execute_pipeline_run
from app.benchmarks.suites import BENCHMARK_SUITE, SUITE_NAME, SUITE_VERSION, BenchmarkCaseSpec
from app.engine.metrics import METRIC_CATALOG
from app.engine.scoring import ALGORITHM_VERSION, compute_track_score
from app.models.base import utcnow
from app.models.clinical import CheckIn, Consent, Observation, Patient, ScreeningRecord, TrackEnrollment
from app.models.engine import PipelineRun, ScoringResult
from app.models.enums import ConsentScope, ConsentStatus, ObservationSource
from app.models.ops import BenchmarkCaseResult, BenchmarkRun


def create_benchmark_run(
    db: Session,
    *,
    organization_id: uuid.UUID,
    tracks: list[str],
    started_by_id: uuid.UUID | None = None,
) -> BenchmarkRun:
    br = BenchmarkRun(
        organization_id=organization_id,
        suite_name=SUITE_NAME,
        suite_version=SUITE_VERSION,
        algorithm_version=ALGORITHM_VERSION,
        tracks=tracks,
        status="queued",
        started_by_id=started_by_id,
    )
    db.add(br)
    db.flush()
    return br


def execute_benchmark_run(db: Session, benchmark_run_id: uuid.UUID) -> BenchmarkRun:
    br = db.get(BenchmarkRun, benchmark_run_id)
    if br is None:
        raise ValueError("BenchmarkRun not found")

    br.status = "running"
    br.started_at = utcnow()
    db.commit()

    selected_tracks = set(br.tracks or ["core", "loop", "neuro", "worksafe"])
    cases = [c for c in BENCHMARK_SUITE if c.track in selected_tracks]
    now = utcnow()

    tp = fp = tn = fn = 0
    emerg_total = emerg_caught = 0
    missing_total = missing_passed = 0
    consistency_total = consistency_passed = 0
    agent_failures = 0
    durations: list[float] = []
    passed_count = 0

    for spec in cases:
        res_row = _execute_single_case(db, br, spec, now)
        if res_row.duration_ms is not None:
            durations.append(res_row.duration_ms)
        if res_row.passed:
            passed_count += 1

        actual = res_row.actual
        if actual.get("run_status") == "failed":
            agent_failures += 1

        if spec.expected_emergency:
            emerg_total += 1
            if actual.get("is_emergency"):
                emerg_caught += 1

        if spec.category == "missing_data":
            missing_total += 1
            if res_row.passed:
                missing_passed += 1

        if actual.get("scoring_consistent") is not None:
            consistency_total += 1
            if actual.get("scoring_consistent"):
                consistency_passed += 1

        if spec.expected_positive_drift is not None:
            pred_pos = bool(actual.get("is_emergency") or actual.get("risk_tier") in {"AMBER", "RED"})
            if spec.expected_positive_drift and pred_pos:
                tp += 1
            elif spec.expected_positive_drift and not pred_pos:
                fn += 1
            elif not spec.expected_positive_drift and pred_pos:
                fp += 1
            else:
                tn += 1

    sensitivity = round(100.0 * tp / (tp + fn), 2) if (tp + fn) else None
    specificity = round(100.0 * tn / (tn + fp), 2) if (tn + fp) else None
    emerg_acc = round(100.0 * emerg_caught / emerg_total, 2) if emerg_total else None
    missing_rate = round(100.0 * missing_passed / missing_total, 2) if missing_total else None
    consistency_rate = round(100.0 * consistency_passed / consistency_total, 2) if consistency_total else None

    br.status = "completed"
    br.finished_at = utcnow()
    br.total_cases = len(cases)
    br.passed_cases = passed_count
    br.metrics = {
        "sensitivity_pct": sensitivity,
        "specificity_pct": specificity,
        "emergency_detection_accuracy_pct": emerg_acc,
        "true_positives": tp,
        "false_positives": fp,
        "true_negatives": tn,
        "false_negatives": fn,
        "missing_data_pass_rate_pct": missing_rate,
        "scoring_consistency_pct": consistency_rate,
        "agent_execution_failures": agent_failures,
        "mean_duration_ms": round(sum(durations) / len(durations), 2) if durations else None,
        "max_duration_ms": round(max(durations), 2) if durations else None,
        "note": "All metrics calculated directly from executed synthetic benchmark cases; zero hardcoded figures.",
    }
    db.commit()
    return br


def _execute_single_case(db: Session, br: BenchmarkRun, spec: BenchmarkCaseSpec, now) -> BenchmarkCaseResult:
    # Create an isolated synthetic fixture patient (`is_synthetic=True`), run the real pipeline,
    # record traceability onto `BenchmarkCaseResult`, and delete the synthetic patient afterwards so
    # zero synthetic rows ever remain in the `patients` table.
    p = Patient(
        organization_id=br.organization_id,
        participant_type="employee" if spec.track == "worksafe" else "patient",
        mrn=f"SYNTH-{br.id.hex[:6]}-{spec.case_id}",
        given_name="Synthetic",
        family_name=spec.case_id,
        sex="unknown",
        preferred_language="en",
        hearing_status=spec.hearing_status,
        vision_status=spec.vision_status,
        is_synthetic=True,
    )
    db.add(p)
    db.flush()

    db.add(
        TrackEnrollment(
            organization_id=br.organization_id,
            patient_id=p.id,
            track=spec.track,
            status="active",
            enrolled_at=now - timedelta(days=30),
            context={"synthetic_benchmark": True},
        )
    )
    if spec.grant_data_consent:
        db.add(
            Consent(
                organization_id=br.organization_id,
                patient_id=p.id,
                scope=ConsentScope.DATA_PROCESSING.value,
                status=ConsentStatus.GRANTED.value,
                method="electronic",
                granted_by_name="Benchmark Fixture",
                effective_at=now - timedelta(days=30),
            )
        )

    # Populate baseline windows 14..10 days ago and current windows in last 3 days
    for metric_code, vals in spec.baseline_days.items():
        unit = METRIC_CATALOG[metric_code].unit if metric_code in METRIC_CATALOG else "unit"
        for i, v in enumerate(vals):
            db.add(
                Observation(
                    organization_id=br.organization_id,
                    patient_id=p.id,
                    track=spec.track,
                    metric_code=metric_code,
                    value_num=float(v),
                    unit=unit,
                    effective_at=now - timedelta(days=15 - i),
                    source=ObservationSource.WEARABLE.value if not metric_code.startswith("cog_") else ObservationSource.ASSESSMENT.value,
                )
            )
    for metric_code, vals in spec.current_days.items():
        unit = METRIC_CATALOG[metric_code].unit if metric_code in METRIC_CATALOG else "unit"
        for i, v in enumerate(vals):
            db.add(
                Observation(
                    organization_id=br.organization_id,
                    patient_id=p.id,
                    track=spec.track,
                    metric_code=metric_code,
                    value_num=float(v),
                    unit=unit,
                    effective_at=now - timedelta(days=len(vals) - i - 1, hours=2),
                    source=ObservationSource.WEARABLE.value if not metric_code.startswith("cog_") else ObservationSource.ASSESSMENT.value,
                )
            )

    if spec.checkin_text is not None or spec.checkin_symptoms or spec.self_reported_crisis:
        db.add(
            CheckIn(
                organization_id=br.organization_id,
                patient_id=p.id,
                track=spec.track,
                kind="text",
                effective_at=now - timedelta(hours=1),
                text=spec.checkin_text,
                symptoms=spec.checkin_symptoms,
                self_reported_crisis=spec.self_reported_crisis,
            )
        )

    if spec.phq9_items is not None:
        db.add(
            ScreeningRecord(
                organization_id=br.organization_id,
                patient_id=p.id,
                programme="IFHAS",
                screened_at=now - timedelta(hours=1),
                phq9_item_responses=spec.phq9_items,
            )
        )

    db.commit()

    t0 = time.perf_counter()
    run = create_pipeline_run(
        db,
        organization_id=br.organization_id,
        patient_id=p.id,
        track=spec.track,
        trigger="benchmark",
        as_of=now,
        benchmark_run_id=br.id,
    )
    db.commit()
    run = execute_pipeline_run(db, run.id)
    elapsed = round((time.perf_counter() - t0) * 1000, 2)

    sr = db.scalar(select(ScoringResult).where(ScoringResult.run_id == run.id))

    # Re-run pure scoring function to verify mathematical determinism
    scoring_consistent = None
    if sr is not None:
        agg = run_agent3(db, p, spec.track, now, present_streams=set())
        b2 = compute_track_score(spec.track, agg.metric_inputs, agg.present_streams, agg.confounders)
        scoring_consistent = (b2.risk_tier.value == sr.risk_tier and b2.primary_z == sr.primary_z)

    actual = {
        "run_status": run.status,
        "risk_tier": run.risk_tier,
        "is_emergency": run.is_emergency,
        "confidence_index": run.confidence_index,
        "primary_metric_code": sr.primary_metric_code if sr else None,
        "primary_z": sr.primary_z if sr else None,
        "missing_streams": sr.missing_streams if sr else [],
        "scoring_consistent": scoring_consistent,
    }

    failures: list[str] = []
    if run.status != spec.expected_run_status:
        failures.append(f"Expected run status '{spec.expected_run_status}', got '{run.status}'")
    if spec.expected_risk_tier is not None and run.risk_tier != spec.expected_risk_tier:
        failures.append(f"Expected risk_tier '{spec.expected_risk_tier}', got '{run.risk_tier}'")
    if run.is_emergency != spec.expected_emergency:
        failures.append(f"Expected is_emergency={spec.expected_emergency}, got {run.is_emergency}")
    if spec.expected_max_confidence is not None and (run.confidence_index or 100.0) > spec.expected_max_confidence:
        failures.append(f"Expected confidence <= {spec.expected_max_confidence}, got {run.confidence_index}")
    if scoring_consistent is False:
        failures.append("Determinism check failed: second scoring pass differed")

    expected_dict = {
        "run_status": spec.expected_run_status,
        "risk_tier": spec.expected_risk_tier,
        "is_emergency": spec.expected_emergency,
        "max_confidence": spec.expected_max_confidence,
        "consent_blocked": spec.expected_consent_blocked,
    }

    # Unlink patient_id from persisted run/scoring/referral/emergency rows and delete temporary synthetic patient
    from app.models.care import Intervention, Notification, Referral
    from app.models.engine import EmergencyEvent

    run.patient_id = None
    if sr is not None:
        sr.patient_id = None
    for row in db.scalars(select(Referral).where(Referral.run_id == run.id)).all():
        db.delete(row)
    for row in db.scalars(select(Intervention).where(Intervention.run_id == run.id)).all():
        db.delete(row)
    for row in db.scalars(select(EmergencyEvent).where(EmergencyEvent.run_id == run.id)).all():
        db.delete(row)
    for row in db.scalars(select(Notification).where(Notification.recipient_patient_id == p.id)).all():
        db.delete(row)
    db.flush()
    db.delete(p)

    case_row = BenchmarkCaseResult(
        benchmark_run_id=br.id,
        case_id=spec.case_id,
        track=spec.track,
        scenario=spec.scenario,
        category=spec.category,
        expected=expected_dict,
        actual=actual,
        passed=(len(failures) == 0),
        failure_details="; ".join(failures) if failures else None,
        pipeline_run_id=run.id,
        duration_ms=elapsed,
        executed_at=utcnow(),
    )
    db.add(case_row)
    db.commit()
    return case_row
