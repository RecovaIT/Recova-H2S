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


def test_public_organization_registration_isolation_and_conflicts(client):
    bootstrap_org_and_admin(client)

    # Platform admin creates a patient in Org A
    pat_a = client.post(
        "/api/v1/patients",
        headers=auth_headers(client),
        json={"mrn": "MRN-ORGA-01", "given_name": "Sara", "family_name": "Al-Maktoum"},
    )
    assert pat_a.status_code == 201, pat_a.text
    pat_a_id = pat_a.json()["id"]

    # Platform admin creates another org via /organizations and immediately gets switcher membership
    org_c = client.post(
        "/api/v1/organizations",
        headers=auth_headers(client),
        json={
            "name": "Al Ain Rehab",
            "slug": "al-ain-rehab",
            "org_type": "rehab_center",
            "enabled_tracks": ["core"],
        },
    )
    assert org_c.status_code == 201, org_c.text
    org_c_id = org_c.json()["id"]
    me_res = client.get("/api/v1/auth/me")
    assert me_res.status_code == 200
    assert any(m["organization_id"] == org_c_id for m in me_res.json()["memberships"])
    sw = client.post(
        "/api/v1/auth/switch-organization",
        headers=auth_headers(client),
        json={"organization_id": org_c_id},
    )
    assert sw.status_code == 200, sw.text
    assert sw.json()["active_organization"]["slug"] == "al-ain-rehab"

    # Log out
    assert client.post("/api/v1/auth/logout", headers=auth_headers(client)).status_code == 200
    assert client.get("/api/v1/auth/status").json()["needs_bootstrap"] is False

    # Public bootstrap remains permanently locked once an admin exists
    locked = client.post(
        "/api/v1/auth/bootstrap",
        json={
            "organization_name": "Rogue Org",
            "organization_slug": "rogue-org",
            "org_type": "clinic",
            "enabled_tracks": ["core"],
            "admin_email": "rogue@example.ae",
            "admin_full_name": "Rogue User",
            "admin_password": "StrongPassword99!",
        },
    )
    assert locked.status_code == 409

    # ONB02: Multiple tracks without single primary_programme are rejected with 422
    multi_reg = client.post(
        "/api/v1/auth/register-organization",
        json={
            "organization_name": "Multi Track Clinic",
            "organization_slug": "multi-track-clinic",
            "org_type": "clinic",
            "enabled_tracks": ["core", "loop"],
            "admin_email": "multi@dubaiclinic.ae",
            "admin_full_name": "Dr. Tariq Saeed",
            "admin_password": "DubaiClinicPass123!",
        },
    )
    assert multi_reg.status_code == 422

    # Self-service tenant registration creates isolated org + org_admin (non-platform-admin) + cookies
    reg = client.post(
        "/api/v1/auth/register-organization",
        json={
            "organization_name": "Dubai Care Clinic",
            "organization_slug": "dubai-clinic",
            "org_type": "clinic",
            "primary_programme": "core",
            "enabled_tracks": ["core"],
            "admin_email": "admin@dubaiclinic.ae",
            "admin_full_name": "Dr. Tariq Saeed",
            "admin_password": "DubaiClinicPass123!",
            "admin_license_number": "DHA-PHY-4402",
        },
    )
    assert reg.status_code == 201, reg.text
    body = reg.json()
    assert body["user"]["is_platform_admin"] is False
    assert body["role"] == "org_admin"
    assert body["active_organization"]["slug"] == "dubai-clinic"
    assert body["active_organization"]["primary_programme"] == "core"
    assert body["tracks"] == ["core"]
    assert client.cookies.get("recova_session")
    assert client.cookies.get("recova_csrf")

    # Tenant isolation holds strictly against Org A data and platform admin routes
    assert client.get("/api/v1/patients").json()["total"] == 0
    assert client.get(f"/api/v1/patients/{pat_a_id}").status_code == 404
    assert (
        client.post(
            "/api/v1/organizations",
            headers=auth_headers(client),
            json={"name": "Nope", "slug": "nope-org", "org_type": "clinic", "enabled_tracks": ["core"]},
        ).status_code
        == 403
    )

    # Duplicate slug or duplicate email are cleanly rejected with 409
    dup_slug = client.post(
        "/api/v1/auth/register-organization",
        json={
            "organization_name": "Another AD",
            "organization_slug": "ad-wellness",
            "org_type": "hospital",
            "enabled_tracks": ["core"],
            "admin_email": "fresh@other.ae",
            "admin_full_name": "Fresh Admin",
            "admin_password": "StrongPassword99!",
        },
    )
    assert dup_slug.status_code == 409

    dup_email = client.post(
        "/api/v1/auth/register-organization",
        json={
            "organization_name": "Fresh Org",
            "organization_slug": "fresh-org",
            "org_type": "hospital",
            "enabled_tracks": ["core"],
            "admin_email": "admin@adwellness.ae",
            "admin_full_name": "Duplicate Email Admin",
            "admin_password": "StrongPassword99!",
        },
    )
    assert dup_email.status_code == 409
