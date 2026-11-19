"""Integration tests verifying Recova Unified Platform PRD (2026-11-17) backend contracts."""

from __future__ import annotations

import uuid
from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.db import SessionLocal
from app.models.base import utcnow
from app.models.clinical import CognitiveAssessment, Consent, Observation, Patient, TrackEnrollment
from app.models.identity import Organization, ParticipantAccountLink, PortalInvitation, User
from app.models.ops import AuditEvent, Job, NoticeRecipient, PublicHealthNotice
from app.tasks.queue import run_pending_jobs
from tests.conftest import auth_headers, bootstrap_org_and_admin


def test_onboarding_validation_idempotency_and_legacy_resolution(client: TestClient):
    # Bootstrap initial platform org as multi-track legacy org
    sess = bootstrap_org_and_admin(client)
    legacy_org_id = sess["active_organization"]["id"]
    h = auth_headers(client)

    # Mark legacy org as pending_selection (simulating migrated multi-track org)
    with SessionLocal() as db:
        org = db.get(Organization, uuid.UUID(legacy_org_id))
        assert org is not None
        org.programme_configuration_status = "pending_selection"
        db.commit()

    me_pending = client.get("/api/v1/auth/me").json()
    assert me_pending["programme_configuration_status"] == "pending_selection"
    assert me_pending["capability_flags"]["requires_programme_selection"] is True

    # Dedicated administrator selection resolves legacy configuration & audits
    sel = client.post(
        f"/api/v1/organizations/{legacy_org_id}/select-primary-programme",
        headers=h,
        json={"primary_programme": "loop", "reason": "Facility primary focus is IFHAS screening"},
    )
    assert sel.status_code == 200, sel.text
    assert sel.json()["primary_programme"] == "loop"
    assert sel.json()["programme_configuration_status"] == "configured"

    # Log out for public registration tests
    client.post("/api/v1/auth/logout", headers=h)

    # ONB02: Reject conflicting primary_programme + multiple enabled_tracks
    bad_combo = client.post(
        "/api/v1/auth/register-organization",
        json={
            "organization_name": "Conflict Clinic",
            "organization_slug": "conflict-clinic",
            "org_type": "clinic",
            "primary_programme": "core",
            "enabled_tracks": ["core", "loop"],
            "admin_email": "conflict@clinic.ae",
            "admin_full_name": "Dr. Conflict",
            "admin_password": "StrongPassword123!",
        },
    )
    assert bad_combo.status_code == 422

    # ONB05/ONB06/ONB08: Single programme + consent choices + idempotency_key
    idem = f"onb-{uuid.uuid4()}"
    reg_payload = {
        "organization_name": "Sharjah Recovery Center",
        "organization_slug": "sharjah-recovery",
        "org_type": "rehab_center",
        "primary_programme": "core",
        "enabled_tracks": ["core"],
        "emirate": "Sharjah",
        "idempotency_key": idem,
        "permitted_channels": ["in_app", "email"],
        "responsible_contact": {"name": "Dr. Noura", "email": "noura@sharjah.ae"},
        "participation_consent": {
            "policy_version": "v2.1",
            "accepted_public_health_coordination": True,
            "external_synthesis_opt_in": True,
        },
        "admin_email": "admin@sharjahrecovery.ae",
        "admin_full_name": "Dr. Noura Al-Qasimi",
        "admin_password": "StrongPassword123!",
    }
    r1 = client.post("/api/v1/auth/register-organization", json=reg_payload)
    assert r1.status_code == 201, r1.text
    body = r1.json()
    assert body["primary_programme"] == "core"
    assert body["capability_flags"]["shared_population_health"] is True
    assert body["capability_flags"]["external_synthesis_opt_in"] is True
    org_id = body["active_organization"]["id"]

    # ONB06: Repeated submission with same idempotency_key or slug cannot create duplicate
    r2 = client.post(
        "/api/v1/auth/register-organization",
        json={**reg_payload, "organization_slug": "sharjah-recovery-2", "admin_email": "other@sharjahrecovery.ae"},
    )
    assert r2.status_code == 409

    # NAV02: org_admin cannot expand enabled_tracks via PATCH /organizations/{id}
    h_shj = auth_headers(client)
    patch_tracks = client.patch(
        f"/api/v1/organizations/{org_id}",
        headers=h_shj,
        json={"enabled_tracks": ["core", "loop"]},
    )
    assert patch_tracks.status_code == 403

    # NAV02: Staff in core-only org cannot query or create records in loop/neuro/worksafe
    assert client.get("/api/v1/patients?track=loop").status_code == 403
    assert client.get("/api/v1/referrals?track=neuro").status_code == 403
    assert client.get("/api/v1/workforce/heatmap").status_code == 403

    # PAT01: Patient creation without explicit tracks inherits facility's primary_programme ("core")
    p_res = client.post(
        "/api/v1/patients",
        headers=h_shj,
        json={"mrn": "SHJ-001", "given_name": "Huda", "family_name": "Al-Suwaidi"},
    )
    assert p_res.status_code == 201, p_res.text
    assert [e["track"] for e in p_res.json()["enrollments"]] == ["core"]


def test_portal_invitation_lifecycle_multi_facility_linking_and_portal_contracts(client: TestClient):
    bootstrap_org_and_admin(client)
    h_admin = auth_headers(client)

    # Create Neuro org and Loop org
    org_neuro = client.post(
        "/api/v1/organizations",
        headers=h_admin,
        json={"name": "Neuro Clinic", "slug": "neuro-clinic", "org_type": "clinic", "primary_programme": "neuro", "enabled_tracks": ["neuro"]},
    ).json()
    org_ws = client.post(
        "/api/v1/organizations",
        headers=h_admin,
        json={"name": "WorkSafe Site", "slug": "worksafe-site", "org_type": "employer", "primary_programme": "worksafe", "enabled_tracks": ["worksafe"]},
    ).json()

    # Switch to Neuro org, create patient, grant data_processing consent, and issue portal invitation
    client.post("/api/v1/auth/switch-organization", headers=h_admin, json={"organization_id": org_neuro["id"]}).raise_for_status()
    pat_neuro = client.post(
        "/api/v1/patients",
        headers=h_admin,
        json={"mrn": "NEU-10", "given_name": "Salma", "family_name": "Al-Mazrouei"},
    ).json()
    client.post("/api/v1/consents", headers=h_admin, json={"patient_id": pat_neuro["id"], "scope": "data_processing"}).raise_for_status()

    inv1 = client.post(
        f"/api/v1/patients/{pat_neuro['id']}/portal-invitations",
        headers=h_admin,
        json={"recipient_email": "salma.portal@example.ae"},
    )
    assert inv1.status_code == 201, inv1.text
    tok1 = inv1.json()["invitation_token"]

    # Replacement invitation invalidates tok1
    inv2 = client.post(
        f"/api/v1/patients/{pat_neuro['id']}/portal-invitations",
        headers=h_admin,
        json={"recipient_email": "salma.portal@example.ae"},
    )
    assert inv2.status_code == 201
    tok2 = inv2.json()["invitation_token"]

    # Also create a separate patient in WorkSafe org for the SAME portal user email (PAT04: separate records, no silent merge)
    client.post("/api/v1/auth/switch-organization", headers=h_admin, json={"organization_id": org_ws["id"]}).raise_for_status()
    pat_ws = client.post(
        "/api/v1/patients",
        headers=h_admin,
        json={"mrn": "WS-10", "participant_type": "employee", "given_name": "Salma", "family_name": "Al-Mazrouei"},
    ).json()
    client.post("/api/v1/consents", headers=h_admin, json={"patient_id": pat_ws["id"], "scope": "data_processing"}).raise_for_status()
    inv_ws = client.post(
        f"/api/v1/patients/{pat_ws['id']}/portal-invitations",
        headers=h_admin,
        json={"recipient_email": "salma.portal@example.ae"},
    ).json()

    # Create portal user and wrong-recipient user in DB
    with SessionLocal() as db:
        from app.core.security import hash_password

        u_salma = User(email="salma.portal@example.ae", full_name="Salma", password_hash=hash_password("SalmaPass123!"))
        u_wrong = User(email="wrong@example.ae", full_name="Wrong User", password_hash=hash_password("WrongPass123!"))
        db.add_all([u_salma, u_wrong])
        db.commit()

    # PAT03: Wrong recipient cannot accept invitation
    client.post("/api/v1/auth/logout", headers=h_admin)
    client.post("/api/v1/auth/login", json={"email": "wrong@example.ae", "password": "WrongPass123!"}).raise_for_status()
    assert client.post("/api/v1/auth/accept-portal-invitation", headers=auth_headers(client), json={"token": tok2}).status_code == 403

    # Salma logs in: before linking, portal/me returns 403 (no membership yet)
    client.post("/api/v1/auth/logout", headers=auth_headers(client))
    client.post("/api/v1/auth/login", json={"email": "salma.portal@example.ae", "password": "SalmaPass123!"}).raise_for_status()
    h_salma = auth_headers(client)

    # PAT03: Replaced tok1 fails safely; altered token fails safely
    assert client.post("/api/v1/auth/accept-portal-invitation", headers=h_salma, json={"token": tok1}).status_code == 404
    assert client.post("/api/v1/auth/accept-portal-invitation", headers=h_salma, json={"token": tok2 + "tampered"}).status_code == 404

    # Correct tok2 succeeds, and repeat acceptance is idempotent
    acc1 = client.post("/api/v1/auth/accept-portal-invitation", headers=h_salma, json={"token": tok2})
    assert acc1.status_code == 200, acc1.text
    acc2 = client.post("/api/v1/auth/accept-portal-invitation", headers=h_salma, json={"token": tok2})
    assert acc2.status_code == 200

    # Accept WorkSafe invitation as well -> same user now holds 2 distinct facility-scoped enrolments!
    acc_ws = client.post("/api/v1/auth/accept-portal-invitation", headers=h_salma, json={"token": inv_ws["invitation_token"]})
    assert acc_ws.status_code == 200, acc_ws.text

    me_salma = client.get("/api/v1/portal/me").json()
    assert len(me_salma["enrolments"]) == 2
    neuro_enr = next(e for e in me_salma["enrolments"] if e["programme"] == "neuro")
    ws_enr = next(e for e in me_salma["enrolments"] if e["programme"] == "worksafe")

    # POR02 & POR05: POST /api/v1/portal/cognitive-sessions saves observations + single pipeline run idempotently
    cog_req_id = str(uuid.uuid4())
    cog_payload = {
        "request_id": cog_req_id,
        "enrolment_id": neuro_enr["enrolment_id"],
        "task_version": "neuro-battery-v2",
        "assessment_language": "en",
        "raw_trials": [
            {"task_type": "sequence_4key", "modality": "visual", "expected": [1, 2, 3, 4], "response": [1, 2, 3, 4], "reaction_time_ms": 400, "correct": True},
            {"task_type": "rule_switch", "modality": "executive", "expected": ["odd"], "response": ["odd"], "reaction_time_ms": 450, "correct": True},
        ],
    }
    r_cog1 = client.post("/api/v1/portal/cognitive-sessions", headers=h_salma, json=cog_payload)
    assert r_cog1.status_code == 200, r_cog1.text
    assert r_cog1.json()["observations_saved"] >= 2
    assert r_cog1.json()["task_version"] == "neuro-battery-v2"
    r_cog2 = client.post("/api/v1/portal/cognitive-sessions", headers=h_salma, json=cog_payload)
    assert r_cog2.status_code == 200
    assert r_cog2.json()["status"] == "already_received"

    # POR03 & POR07: WorkSafe check-in retains shift & worksite context, and emergency shows escalation_instructions
    ws_chk = client.post(
        "/api/v1/portal/check-ins",
        headers=h_salma,
        json={
            "request_id": str(uuid.uuid4()),
            "enrolment_id": ws_enr["enrolment_id"],
            "mood": 2,
            "stress": 9,
            "text": "Feeling dizzy in heat",
            "fatigue_feeling": "dizzy_heat_illness",
            "shift": "Afternoon Shift B",
            "worksite": "Al Dhafra Sector 4",
            "hydrated": False,
        },
    )
    assert ws_chk.status_code == 200, ws_chk.text
    assert ws_chk.json()["emergency"] is True
    assert ws_chk.json()["escalation_instructions"]["en"]
    assert ws_chk.json()["escalation_instructions"]["ar"]
    assert ws_chk.json()["shift"] == "Afternoon Shift B"
    assert ws_chk.json()["worksite"] == "Al Dhafra Sector 4"

    # GET /api/v1/portal/care returns care endpoint cleanly
    care_res = client.get(f"/api/v1/portal/care?enrolment_id={ws_enr['enrolment_id']}")
    assert care_res.status_code == 200
    assert care_res.json()["track"] == "worksafe"


def test_authority_scope_notices_out_of_scope_isolation_and_k_suppressed_reports(client: TestClient):
    bootstrap_org_and_admin(client)
    h_padmin = auth_headers(client)

    # Create two orgs in different emirates: Abu Dhabi (core) and Dubai (loop)
    org_ad = client.post(
        "/api/v1/organizations",
        headers=h_padmin,
        json={"name": "AD Care", "slug": "ad-care", "org_type": "clinic", "primary_programme": "core", "enabled_tracks": ["core"], "emirate": "Abu Dhabi"},
    ).json()
    org_dxb = client.post(
        "/api/v1/organizations",
        headers=h_padmin,
        json={"name": "DXB Care", "slug": "dxb-care", "org_type": "clinic", "primary_programme": "loop", "enabled_tracks": ["loop"], "emirate": "Dubai"},
    ).json()

    # Create staff in AD and DXB
    client.post("/api/v1/auth/switch-organization", headers=h_padmin, json={"organization_id": org_ad["id"]}).raise_for_status()
    client.post("/api/v1/users", headers=h_padmin, json={"email": "staff.ad@adcare.ae", "full_name": "AD Staff", "role": "clinician", "password": "StaffPassword123!"}).raise_for_status()
    client.post("/api/v1/auth/switch-organization", headers=h_padmin, json={"organization_id": org_dxb["id"]}).raise_for_status()
    client.post("/api/v1/users", headers=h_padmin, json={"email": "staff.dxb@dxbcare.ae", "full_name": "DXB Staff", "role": "clinician", "password": "StaffPassword123!"}).raise_for_status()

    # Create an Authority User with AuthorityScope restricted to Abu Dhabi ONLY
    u_auth = client.post(
        "/api/v1/users",
        headers=h_padmin,
        json={"email": "authority.ad@doh.ae", "full_name": "AD Authority Officer", "role": "authority_user", "password": "AuthorityPass123!"},
    ).json()["user"]
    sc = client.post(
        "/api/v1/authority/scopes",
        headers=h_padmin,
        json={"user_id": u_auth["id"], "assigned_emirates": ["Abu Dhabi"], "can_publish": True, "can_view_reports": True, "min_suppression_k": 5},
    )
    assert sc.status_code == 201, sc.text

    # Login as AD Authority Officer
    client.post("/api/v1/auth/logout", headers=h_padmin)
    client.post("/api/v1/auth/login", json={"email": "authority.ad@doh.ae", "password": "AuthorityPass123!"}).raise_for_status()
    h_auth = auth_headers(client)

    # POP02: Cannot publish to Dubai (outside assigned scope)
    r_dxb_forbidden = client.post(
        "/api/v1/authority/notices",
        headers=h_auth,
        json={
            "title": "Dubai Advisory",
            "message": "Dubai heat advisory message content here.",
            "severity": "advisory",
            "scope_emirate": "Dubai",
            "eligible_programmes": ["loop"],
        },
    )
    assert r_dxb_forbidden.status_code == 403

    # POP03: Preview & create draft for Abu Dhabi core programme
    draft_payload = {
        "title": "Abu Dhabi Heat Advisory",
        "message": "High ambient heat forecast across Abu Dhabi facilities this week.",
        "plain_language_action": "Ensure hydration checks prior to outdoor shifts.",
        "severity": "urgent",
        "scope_emirate": "Abu Dhabi",
        "eligible_programmes": ["core"],
        "idempotency_key": f"notice-{uuid.uuid4()}",
    }
    prev = client.post("/api/v1/authority/notices/preview", headers=h_auth, json=draft_payload)
    assert prev.status_code == 200, prev.text
    assert prev.json()["organization_count"] >= 1
    assert prev.json()["recipient_count"] >= 1

    draft = client.post("/api/v1/authority/notices", headers=h_auth, json=draft_payload)
    assert draft.status_code == 201, draft.text
    nid = draft.json()["id"]

    # Publish & revise (version increments 1 -> 2)
    pub = client.post(f"/api/v1/authority/notices/{nid}/publish", headers=h_auth)
    assert pub.status_code == 200
    assert pub.json()["status"] == "published"
    rev = client.patch(f"/api/v1/authority/notices/{nid}", headers=h_auth, json={"title": "Abu Dhabi Heat Advisory (Updated)"})
    assert rev.status_code == 200
    assert rev.json()["version"] == 2

    # POP07: Authority report applies k-anonymity suppression when count < 5
    rep = client.get("/api/v1/authority/reports")
    assert rep.status_code == 200
    summary = next(s for s in rep.json()["notice_summaries"] if s["notice_id"] == nid)
    assert summary["suppressed_k_anonymity"] is True
    assert summary["recipient_count"] is None

    # POP04: Out-of-scope DXB staff CANNOT see or retrieve notice by ID
    client.post("/api/v1/auth/logout", headers=h_auth)
    client.post("/api/v1/auth/login", json={"email": "staff.dxb@dxbcare.ae", "password": "StaffPassword123!"}).raise_for_status()
    assert all(n["id"] != nid for n in client.get("/api/v1/notices").json())
    assert client.get(f"/api/v1/notices/{nid}").status_code == 404

    # POP05: In-scope AD staff sees notice, marks read, and acknowledges
    client.post("/api/v1/auth/logout", headers=auth_headers(client))
    client.post("/api/v1/auth/login", json={"email": "staff.ad@adcare.ae", "password": "StaffPassword123!"}).raise_for_status()
    h_ad = auth_headers(client)
    assert any(n["id"] == nid for n in client.get("/api/v1/notices").json())
    assert client.get(f"/api/v1/notices/{nid}").status_code == 200
    assert client.post(f"/api/v1/notices/{nid}/read", headers=h_ad).json()["state"] == "read"
    assert client.post(f"/api/v1/notices/{nid}/acknowledgements", headers=h_ad).json()["acknowledged"] is True


def test_queued_consent_revocation_and_live_reporting_excludes_synthetic(client: TestClient):
    bootstrap_org_and_admin(client)
    h = auth_headers(client)

    pat = client.post(
        "/api/v1/patients",
        headers=h,
        json={"mrn": "Q-01", "given_name": "Nasser", "family_name": "Al-Nuaimi", "tracks": ["core"]},
    ).json()
    con = client.post(
        "/api/v1/consents",
        headers=h,
        json={"patient_id": pat["id"], "scope": "data_processing"},
    ).json()

    # Queue an async pipeline run while consent is granted
    queued = client.post(
        "/api/v1/pipeline/runs",
        headers=h,
        json={"patient_id": pat["id"], "track": "core", "run_async": True},
    )
    assert queued.status_code == 201
    run_id = queued.json()["id"]
    assert queued.json()["status"] == "queued"

    # Revoke consent BEFORE the background worker processes the queued job!
    client.post(f"/api/v1/consents/{con['id']}/revoke", headers=h).raise_for_status()
    assert run_pending_jobs(10) >= 1

    run_after = client.get(f"/api/v1/pipeline/runs/{run_id}").json()
    assert run_after["status"] == "blocked"

    # Create a synthetic patient + emergency + run in the same org -> live overview must exclude it
    with SessionLocal() as db:
        from app.models.engine import EmergencyEvent

        syn = Patient(
            organization_id=uuid.UUID(run_after["organization_id"]),
            mrn="SYN-EXCL-1",
            given_name="Synth",
            family_name="Demo",
            is_synthetic=True,
        )
        db.add(syn)
        db.flush()
        db.add(
            EmergencyEvent(
                organization_id=syn.organization_id,
                patient_id=syn.id,
                track="core",
                status="open",
                rule_codes=["CRISIS_SUICIDAL_IDEATION"],
                evidence=[],
                rules_version="1.1.0",
            )
        )
        db.commit()

    ov = client.get("/api/v1/reports/overview").json()
    assert ov["active_patients"] == 1
    assert ov["open_emergencies"] == 0
