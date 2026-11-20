"""End-to-end integration tests across all 6 agents, all 4 tracks, FHIR R4, and benchmarks."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from tests.conftest import auth_headers, bootstrap_org_and_admin


def test_core_end_to_end_closed_loop_and_fhir(client: TestClient):
    bootstrap_org_and_admin(client)
    h = auth_headers(client)

    # 1. Configure Insurance Plan & Care Facility
    plan = client.post(
        "/api/v1/settings/insurance-plans",
        headers=h,
        json={
            "code": "THIQA",
            "name": "Daman Thiqa Plan",
            "payer_name": "Daman",
            "network_tier": "Thiqa",
            "covered_pathways": ["async_teleconsult", "outpatient_therapist", "primary_care", "specialist"],
        },
    ).json()
    fac = client.post(
        "/api/v1/settings/care-facilities",
        headers=h,
        json={
            "name": "Al Ain Rehab Tele-Psychiatry",
            "facility_type": "teleconsult",
            "pathways": ["async_teleconsult", "outpatient_therapist"],
            "accepted_plan_ids": [plan["id"]],
            "typical_wait_days": 1,
        },
    ).json()

    # 2. Register patient
    p = client.post(
        "/api/v1/patients",
        headers=h,
        json={
            "mrn": "CORE-101",
            "given_name": "Tariq",
            "family_name": "Al-Mansoori",
            "sex": "male",
            "preferred_language": "ar",
            "insurance_plan_id": plan["id"],
            "tracks": ["core"],
        },
    ).json()
    pid = p["id"]

    # 3. Without consent, routine pipeline is BLOCKED at Gate 1
    now = datetime.now(timezone.utc)
    r_blocked = client.post(
        "/api/v1/pipeline/runs",
        headers=h,
        json={"patient_id": pid, "track": "core", "as_of": now.isoformat()},
    )
    assert r_blocked.status_code == 201
    assert r_blocked.json()["status"] == "blocked"
    assert r_blocked.json()["steps"][0]["status"] == "failed"

    # 4. Grant mandatory data_processing consent
    r_con = client.post(
        "/api/v1/consents",
        headers=h,
        json={"patient_id": pid, "scope": "data_processing", "method": "electronic"},
    )
    assert r_con.status_code == 201

    # 5. Ingest baseline wearable data (5 days stable) + recent drift (3 days low sleep)
    obs = []
    for i, sl in enumerate([7.8, 7.5, 7.6, 7.7, 7.4]):
        obs.append({"metric_code": "sleep_hours", "value_num": sl, "unit": "h", "effective_at": (now - timedelta(days=14 - i)).isoformat()})
        obs.append({"metric_code": "hrv_rmssd", "value_num": 56.0 + i, "unit": "ms", "effective_at": (now - timedelta(days=14 - i)).isoformat()})
    for i, sl in enumerate([5.0, 4.6, 4.2]):
        obs.append({"metric_code": "sleep_hours", "value_num": sl, "unit": "h", "effective_at": (now - timedelta(days=2 - i)).isoformat()})
        obs.append({"metric_code": "hrv_rmssd", "value_num": 34.0, "unit": "ms", "effective_at": (now - timedelta(days=2 - i)).isoformat()})

    r_wb = client.post(
        "/api/v1/wearables/ingest",
        headers=h,
        json={"patient_id": pid, "track": "core", "source_system": "sahatna", "observations": obs},
    )
    assert r_wb.status_code == 201
    assert r_wb.json()["batch"]["accepted_count"] == 16

    # 6. Submit daily voice check-in triggering pipeline
    r_chk = client.post(
        "/api/v1/check-ins",
        headers=h,
        json={
            "patient_id": pid,
            "track": "core",
            "kind": "voice",
            "mood_score": 4,
            "craving_score": 7,
            "text": "Poor sleep for three nights and rising anxiety.",
            "transcript_source": "browser_speech",
            "trigger_pipeline": True,
        },
    )
    assert r_chk.status_code == 201
    run_id = r_chk.json()["run_id"]
    run = client.get(f"/api/v1/pipeline/runs/{run_id}").json()
    assert run["status"] == "completed"
    assert run["risk_tier"] == "RED"
    assert run["scoring"]["primary_metric_code"] == "sleep_hours"
    assert run["scoring"]["primary_z"] < -1.96
    # Honest LLM status when unconfigured
    assert run["synthesis"]["status"] == "consent_not_granted"
    assert run["synthesis"]["summary_en"] is None

    # 7. Proposed referral created by Agent 6 with matching facility & Thiqa coverage
    refs = client.get(f"/api/v1/referrals?patient_id={pid}").json()["items"]
    assert len(refs) == 1
    ref = refs[0]
    assert ref["status"] == "proposed"
    assert ref["coverage_status"] == "covered"
    assert ref["facility_id"] == fac["id"]

    # Cannot notify patient before clinician sign-off
    assert (
        client.post(f"/api/v1/referrals/{ref['id']}/notify", headers=h, json={"channel": "in_app"}).status_code == 422
    )

    # 8. Clinician DECIDE-AI Sign-off
    r_rev = client.post(
        "/api/v1/clinical-reviews",
        headers=h,
        json={
            "run_id": run_id,
            "decision": "approve_referral",
            "agrees_with_tier": True,
            "clinician_notes": "Confirmed pre-relapse drift; proceed with tele-consult.",
            "notify_patient_channel": "in_app",
        },
    )
    assert r_rev.status_code == 201
    assert client.get(f"/api/v1/referrals/{ref['id']}").json()["status"] == "patient_notified"

    # 9. Book -> Complete -> Verify Outcome
    assert (
        client.post(
            f"/api/v1/referrals/{ref['id']}/book",
            headers=h,
            json={"appointment_at": (now + timedelta(hours=12)).isoformat(), "appointment_reference": "TC-9981"},
        ).json()["status"]
        == "booked"
    )
    assert (
        client.post(
            f"/api/v1/referrals/{ref['id']}/complete-consultation",
            headers=h,
            json={"notes": "Tele-consult completed, sleep hygiene plan adjusted."},
        ).json()["status"]
        == "consultation_completed"
    )
    assert (
        client.post(
            f"/api/v1/outcomes/referral/{ref['id']}/verify",
            headers=h,
            json={"outcome": "improved", "verification_method": "teleconsult", "notes": "Sleep restored to 7h."},
        ).status_code
        == 201
    )
    ref_final = client.get(f"/api/v1/referrals/{ref['id']}").json()
    assert ref_final["status"] == "outcome_verified"
    assert ref_final["outcome_verification"]["outcome"] == "improved"

    # 10. Export and validate HL7 FHIR R4 Bundle
    client.post('/api/v1/consents', headers=h, json={'patient_id':pid, 'scope':'hie_sharing'}).raise_for_status()
    fhir = client.get(f"/api/v1/fhir/patients/{pid}/bundle").json()
    assert fhir["validation"]["valid"] is True
    assert fhir["validation"]["resource_counts"]["Patient"] == 1
    assert fhir["validation"]["resource_counts"]["ServiceRequest"] == 1
    assert fhir["validation"]["resource_counts"]["CarePlan"] == 1

    # Audit log has recorded actions
    aud = client.get("/api/v1/audit-logs").json()
    assert aud["total"] >= 5


def test_gate2_emergency_bypass_and_truthful_notification(client: TestClient):
    bootstrap_org_and_admin(client)
    h = auth_headers(client)
    p = client.post(
        "/api/v1/patients",
        headers=h,
        json={"mrn": "EMG-01", "given_name": "Sultan", "family_name": "Al-Zaabi", "tracks": ["core"]},
    ).json()
    client.post("/api/v1/consents", headers=h, json={"patient_id": p["id"], "scope": "data_processing"}).raise_for_status()

    r_chk = client.post(
        "/api/v1/check-ins",
        headers=h,
        json={
            "patient_id": p["id"],
            "track": "core",
            "text": "I cannot go on, having suicidal thoughts.",
            "self_reported_crisis": True,
            "trigger_pipeline": True,
        },
    )
    assert r_chk.status_code == 201
    run = client.get(f"/api/v1/pipeline/runs/{r_chk.json()['run_id']}").json()
    assert run["status"] == "emergency_bypass"
    assert run["is_emergency"] is True
    assert run["risk_tier"] == "EMERGENCY_BYPASS"
    step_map = {s["agent_key"]: s for s in run["steps"]}
    assert step_map["gate2_emergency"]["status"] == "bypassed"
    assert step_map["agent3_aggregator"]["status"] == "skipped"
    assert step_map["agent4_scoring"]["status"] == "skipped"
    assert step_map["agent5_synthesis"]["status"] == "skipped"

    # Emergency event created and STAT referral escalated
    ems = client.get("/api/v1/agents/emergencies?status=open").json()
    assert len(ems) == 1
    notifs = client.get("/api/v1/notifications").json()["items"]
    in_app = [n for n in notifs if n["channel"] == "in_app"]
    emails = [n for n in notifs if n["channel"] == "email"]
    assert in_app and in_app[0]["status"] == "delivered"
    # Email is NOT configured in test env -> must NOT claim delivered!
    assert emails and emails[0]["status"] == "not_configured"


def test_loop_neuro_worksafe_and_benchmarks(client: TestClient):
    bootstrap_org_and_admin(client)
    h = auth_headers(client)

    # --- Loop IFHAS ---
    p_loop = client.post(
        "/api/v1/patients",
        headers=h,
        json={"mrn": "LOOP-1", "given_name": "Mariam", "family_name": "Al-Dhaheri", "tracks": ["loop"]},
    ).json()
    client.post("/api/v1/consents", headers=h, json={"patient_id": p_loop["id"], "scope": "data_processing"})
    r_scr = client.post(
        "/api/v1/screenings",
        headers=h,
        json={
            "patient_id": p_loop["id"],
            "hba1c": 7.1,
            "bp_systolic": 146,
            "bp_diastolic": 92,
            "phq9_item_responses": [1, 1, 1, 1, 1, 1, 1, 1, 0],
            "trigger_pipeline": True,
        },
    )
    assert r_scr.status_code == 201
    loop_run = client.get(f"/api/v1/pipeline/runs/{r_scr.json()['run_id']}").json()
    assert loop_run["risk_tier"] == "RED"
    passport = client.get(f"/api/v1/patients/{p_loop['id']}/passport").json()
    assert len(passport["referrals"]) == 1

    # --- Neuro Cognitive Studio ---
    p_neuro = client.post(
        "/api/v1/patients",
        headers=h,
        json={"mrn": "NEURO-1", "given_name": "Ahmed", "family_name": "Al-Remeithi", "hearing_status": "mild_loss", "tracks": ["neuro"]},
    ).json()
    client.post("/api/v1/consents", headers=h, json={"patient_id": p_neuro["id"], "scope": "data_processing"})
    r_cog = client.post(
        "/api/v1/cognitive-assessments",
        headers=h,
        json={
            "patient_id": p_neuro["id"],
            "assessment_language": "en",
            "raw_trials": [
                {"task_type": "sequence_4key", "modality": "visual", "expected": [1, 2, 3, 4], "response": [1, 2, 3, 4], "reaction_time_ms": 420, "correct": True},
                {"task_type": "audio_memory", "modality": "auditory", "expected": [2, 4, 1], "response": [2, 4, 1], "reaction_time_ms": 510, "correct": True},
                {"task_type": "rule_switch", "modality": "executive", "expected": ["even"], "response": ["even"], "reaction_time_ms": 480, "correct": True},
                {"task_type": "delayed_recall", "modality": "recall", "expected": ["palm"], "response": ["palm"], "reaction_time_ms": 550, "correct": True},
            ],
            "trigger_pipeline": True,
        },
    )
    assert r_cog.status_code == 201
    assert r_cog.json()["assessment"]["derived_metrics"]["cog_sequence_accuracy"] == 100.0

    # --- WorkSafe ---
    dept = client.post(
        "/api/v1/workforce/departments",
        headers=h,
        json={"name": "Outdoor Logistics A", "min_group_size_for_reporting": 5},
    ).json()
    env = client.post(
        "/api/v1/workforce/assessments",
        headers=h,
        json={"department_id": dept["id"], "ambient_temp_c": 41.0, "relative_humidity_pct": 55.0},
    ).json()
    assert env["heat_index_c"] > 45.0

    emp = client.post(
        "/api/v1/patients",
        headers=h,
        json={"mrn": "EMP-01", "participant_type": "employee", "given_name": "Zaid", "family_name": "Nuaimi", "department_id": dept["id"], "tracks": ["worksafe"]},
    ).json()
    client.post("/api/v1/consents", headers=h, json={"patient_id": emp["id"], "scope": "data_processing"})
    r_ready = client.post(
        "/api/v1/workforce/readiness",
        headers=h,
        json={"patient_id": emp["id"], "readiness_score": 3, "fatigue_feeling": "exhausted", "hydrated": False, "core_temp_est_c": 38.7, "hr_recovery_minutes": 24.0},
    )
    assert r_ready.status_code == 201
    ws_run = client.get(f"/api/v1/pipeline/runs/{r_ready.json()['run_id']}").json()
    assert ws_run["risk_tier"] == "RED"
    assert len(client.get("/api/v1/interventions?track=worksafe").json()) >= 2

    # --- Benchmarks ---
    r_bm = client.post("/api/v1/benchmarks/runs", headers=h, json={"tracks": ["core", "loop", "neuro", "worksafe"]})
    assert r_bm.status_code == 201, r_bm.text
    bm = r_bm.json()
    assert bm["total_cases"] == 15
    assert bm["passed_cases"] == 15, [c for c in bm["cases"] if not c["passed"]]
    assert bm["metrics"]["sensitivity_pct"] == 100.0
    assert bm["metrics"]["specificity_pct"] == 100.0
    assert bm["metrics"]["emergency_detection_accuracy_pct"] == 100.0
    assert bm["metrics"]["scoring_consistency_pct"] == 100.0

    # Synthetic benchmark cases must NOT appear in real patient list!
    pats = client.get("/api/v1/patients").json()
    assert all(x["mrn"] in {"CORE-101", "LOOP-1", "NEURO-1", "EMP-01"} for x in pats["items"])
