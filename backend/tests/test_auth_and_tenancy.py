"""Integration tests for auth, RBAC, multi-tenant isolation, and audit logging."""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.conftest import auth_headers, bootstrap_org_and_admin


def test_auth_csrf_tenant_isolation_and_rbac(client: TestClient):
    # 1. Status indicates bootstrap required initially
    assert client.get("/api/v1/auth/status").json()["needs_bootstrap"] is True

    # 2. Bootstrap Org A & platform admin
    sess = bootstrap_org_and_admin(client)
    org_a_id = sess["active_organization"]["id"]
    assert sess["role"] == "org_admin"
    assert client.get("/api/v1/auth/status").json()["needs_bootstrap"] is False

    # Second bootstrap attempt must fail
    r_dup = client.post(
        "/api/v1/auth/bootstrap",
        json={
            "organization_name": "Duplicate",
            "organization_slug": "dup",
            "admin_email": "x@y.ae",
            "admin_full_name": "Duplicate Admin",
            "admin_password": "Password123!",
        },
    )
    assert r_dup.status_code == 409

    # 3. Create Org B and a Care Coordinator in Org A and Supervisor in Org A
    r_org_b = client.post(
        "/api/v1/organizations",
        headers=auth_headers(client),
        json={"name": "Dubai Care Clinic", "slug": "dubai-care", "org_type": "clinic", "enabled_tracks": ["core", "loop"]},
    )
    assert r_org_b.status_code == 201, r_org_b.text
    org_b_id = r_org_b.json()["id"]

    # Create a patient in Org A
    r_pat = client.post(
        "/api/v1/patients",
        headers=auth_headers(client),
        json={
            "mrn": "MRN-A-001",
            "given_name": "Rashid",
            "family_name": "Al-Maktoum",
            "preferred_language": "en",
            "tracks": ["core"],
        },
    )
    assert r_pat.status_code == 201, r_pat.text
    pat_a_id = r_pat.json()["id"]

    # Create a WorkSafe Supervisor in Org A
    r_sup = client.post(
        "/api/v1/users",
        headers=auth_headers(client),
        json={
            "email": "sup@adwellness.ae",
            "full_name": "Site Supervisor",
            "role": "supervisor",
            "password": "Supervisor123!",
        },
    )
    assert r_sup.status_code == 201

    # Switch admin to Org B and create an Org B user (clinician)
    r_sw = client.post(
        "/api/v1/auth/switch-organization",
        headers=auth_headers(client),
        json={"organization_id": org_b_id},
    )
    assert r_sw.status_code == 200
    r_doc_b = client.post(
        "/api/v1/users",
        headers=auth_headers(client),
        json={
            "email": "docb@dubaicare.ae",
            "full_name": "Dr. B",
            "role": "clinician",
            "password": "DoctorB123!",
        },
    )
    assert r_doc_b.status_code == 201

    # Logout admin and login as Org B clinician
    client.post("/api/v1/auth/logout", headers=auth_headers(client))
    r_login = client.post("/api/v1/auth/login", json={"email": "docb@dubaicare.ae", "password": "DoctorB123!"})
    assert r_login.status_code == 200

    # CSRF check: mutation without X-CSRF-Token must be 403
    r_no_csrf = client.post(
        "/api/v1/patients",
        json={"mrn": "X", "given_name": "A", "family_name": "B", "tracks": ["core"]},
    )
    assert r_no_csrf.status_code == 403

    # Tenant isolation: Org B clinician CANNOT access Org A patient or switch to Org A
    assert client.get(f"/api/v1/patients/{pat_a_id}").status_code == 404
    assert client.get("/api/v1/patients").json()["total"] == 0
    assert (
        client.post(
            "/api/v1/auth/switch-organization",
            headers=auth_headers(client),
            json={"organization_id": org_a_id},
        ).status_code
        == 403
    )

    # Login as Org A Supervisor: cannot access clinical patient list or identifiable workforce risks
    client.post("/api/v1/auth/logout", headers=auth_headers(client))
    assert client.post("/api/v1/auth/login", json={"email": "sup@adwellness.ae", "password": "Supervisor123!"}).status_code == 200
    assert client.get("/api/v1/patients").status_code == 403
    assert client.get("/api/v1/workforce/identifiable-risks").status_code == 403
    # Can access anonymised heatmap
    assert client.get("/api/v1/workforce/heatmap").status_code == 200
