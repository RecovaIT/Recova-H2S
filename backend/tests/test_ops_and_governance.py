"""Additional tests for background jobs, SLA escalation, k-anonymity, RBAC overrides, and password reset."""

from __future__ import annotations

from datetime import timedelta

from fastapi.testclient import TestClient

from app.core.db import SessionLocal
from app.models.base import utcnow
from app.models.care import Referral
from app.models.ops import Job
from app.services.care import evaluate_referral_slas
from app.tasks.queue import enqueue, register, run_pending_jobs
from tests.conftest import auth_headers, bootstrap_org_and_admin


def test_worksafe_k_anonymity_and_sla_escalation_and_jobs(client: TestClient):
    bootstrap_org_and_admin(client)
    h = auth_headers(client)

    # Create department with k=5 and only 2 workers
    dept = client.post(
        "/api/v1/workforce/departments",
        headers=h,
        json={"name": "Small Crane Crew", "min_group_size_for_reporting": 5},
    ).json()
    for i in range(2):
        emp = client.post(
            "/api/v1/patients",
            headers=h,
            json={"mrn": f"CRANE-{i}", "participant_type": "employee", "given_name": "Worker", "family_name": f"{i}", "department_id": dept["id"], "tracks": ["worksafe"]},
        ).json()
        client.post("/api/v1/consents", headers=h, json={"patient_id": emp["id"], "scope": "data_processing"})

    # Org Admin (has workforce:read_identifiable) sees counts
    hm_admin = client.get("/api/v1/workforce/heatmap").json()
    assert hm_admin[0]["suppressed_k_anonymity"] is False

    # Supervisor (only workforce:read_aggregate) gets k-anonymity suppression!
    client.post(
        "/api/v1/users",
        headers=h,
        json={"email": "sup2@adwellness.ae", "full_name": "Sup 2", "role": "supervisor", "password": "Supervisor123!"},
    )
    client.post("/api/v1/auth/logout", headers=h)
    client.post("/api/v1/auth/login", json={"email": "sup2@adwellness.ae", "password": "Supervisor123!"})
    hm_sup = client.get("/api/v1/workforce/heatmap").json()
    assert hm_sup[0]["suppressed_k_anonymity"] is True
    assert hm_sup[0]["risk_counts"] is None

    # Switch back to admin and test async pipeline job + SLA breach escalation
    client.post("/api/v1/auth/logout", headers=auth_headers(client))
    client.post("/api/v1/auth/login", json={"email": "admin@adwellness.ae", "password": "SecurePass123!"})
    h = auth_headers(client)

    p = client.post(
        "/api/v1/patients",
        headers=h,
        json={"mrn": "SLA-01", "given_name": "Omar", "family_name": "Al-Suwaidi", "tracks": ["loop"]},
    ).json()
    ref = client.post(
        "/api/v1/referrals",
        headers=h,
        json={
            "patient_id": p["id"],
            "track": "loop",
            "pathway": "primary_care",
            "priority": "urgent",
            "reason": "HbA1c elevated",
            "target_date": (utcnow() - timedelta(hours=2)).isoformat(),  # already past SLA
        },
    ).json()
    assert ref["sla_status"] == "on_track"

    res_sla = client.post("/api/v1/referrals/evaluate-slas", headers=h).json()
    assert res_sla["escalated"] == 1
    ref_after = client.get(f"/api/v1/referrals/{ref['id']}").json()
    assert ref_after["sla_status"] == "breached"
    assert ref_after["status"] == "escalated"

    # Test background job retry & failure tracking
    attempts_seen = {"count": 0}

    @register("test.flaky")
    def _flaky(_db, _job):
        attempts_seen["count"] += 1
        if attempts_seen["count"] == 1:
            raise RuntimeError("transient error")
        return {"ok": True}

    with SessionLocal() as s:
        job = enqueue(s, "test.flaky", {"x": 1}, max_attempts=2)
        jid = job.id
        s.commit()

    assert run_pending_jobs(10) == 1
    with SessionLocal() as s:
        j = s.get(Job, jid)
        assert j.status == "failed"
        assert j.attempts == 1
        j.run_after = utcnow() - timedelta(seconds=1)
        s.commit()

    assert run_pending_jobs(10) == 1
    with SessionLocal() as s:
        j = s.get(Job, jid)
        assert j.status == "succeeded"
        assert j.attempts == 2
        assert len(j.history) == 2


def test_rbac_override_and_user_deactivation(client: TestClient):
    bootstrap_org_and_admin(client)
    h = auth_headers(client)

    # Create coordinator (lacks benchmarks:run by default)
    u = client.post(
        "/api/v1/users",
        headers=h,
        json={"email": "coord@adwellness.ae", "full_name": "Coord", "role": "care_coordinator", "password": "CoordPass123!"},
    ).json()["user"]

    # Grant benchmarks:run override to care_coordinator
    r_ov = client.post(
        "/api/v1/organizations/permissions/overrides",
        headers=h,
        json={"role": "care_coordinator", "permission": "benchmarks:run", "effect": "grant"},
    )
    assert r_ov.status_code == 200

    client.post("/api/v1/auth/logout", headers=h)
    client.post("/api/v1/auth/login", json={"email": "coord@adwellness.ae", "password": "CoordPass123!"})
    me = client.get("/api/v1/auth/me").json()
    assert "benchmarks:run" in me["permissions"]

    # Deactivate coordinator as admin -> existing session immediately invalidates
    client.post("/api/v1/auth/logout", headers=auth_headers(client))
    client.post("/api/v1/auth/login", json={"email": "admin@adwellness.ae", "password": "SecurePass123!"})
    h = auth_headers(client)
    client.patch(f"/api/v1/users/{u['id']}", headers=h, json={"is_active": False}).raise_for_status()

    client.post("/api/v1/auth/logout", headers=h)
    assert client.post("/api/v1/auth/login", json={"email": "coord@adwellness.ae", "password": "CoordPass123!"}).status_code == 401
