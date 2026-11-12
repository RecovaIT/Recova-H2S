"""HL7 FHIR R4.0.1 serializer & structural/reference validator.

Supports:
- Patient, Practitioner, Organization, Observation, QuestionnaireResponse,
  Consent, Coverage, ServiceRequest, CarePlan, Communication, Encounter
- Transaction / Collection Bundle generation with strict urn:uuid reference integrity
- Structural & clinical-status validation
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from app.engine.metrics import METRIC_CATALOG
from app.models.care import CareFacility, ClinicalReview, InsurancePlan, Notification, Referral
from app.models.clinical import Consent, Observation, Patient, ScreeningRecord
from app.models.engine import PipelineRun, ScoringResult
from app.models.enums import ReferralStatus
from app.models.identity import Organization, User

FHIR_INTERPRETATION = {
    "GREEN": {"system": "http://terminology.hl7.org/CodeSystem/v3-ObservationInterpretation", "code": "N", "display": "Normal"},
    "AMBER": {"system": "http://terminology.hl7.org/CodeSystem/v3-ObservationInterpretation", "code": "A", "display": "Abnormal"},
    "RED": {"system": "http://terminology.hl7.org/CodeSystem/v3-ObservationInterpretation", "code": "AA", "display": "Critical abnormal"},
    "EMERGENCY_BYPASS": {"system": "http://terminology.hl7.org/CodeSystem/v3-ObservationInterpretation", "code": "HH", "display": "High alert / Emergency bypass"},
    "INDETERMINATE": {"system": "http://terminology.hl7.org/CodeSystem/v3-ObservationInterpretation", "code": "IND", "display": "Indeterminate"},
}


def _iso(dt: datetime | None) -> str:
    if dt is None:
        return datetime.now(timezone.utc).isoformat()
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def _urn(resource_type: str, rid: uuid.UUID | str) -> str:
    return f"urn:uuid:{resource_type.lower()}-{rid}"


def build_organization_resource(org: Organization) -> dict[str, Any]:
    return {
        "resourceType": "Organization",
        "id": str(org.id),
        "active": org.is_active,
        "name": org.name,
        "identifier": [{"system": "https://recova.health/org", "value": org.slug}],
        "type": [{"text": org.org_type}],
        "address": [{"state": org.emirate, "country": org.country}] if (org.emirate or org.country) else [],
    }


def build_patient_resource(patient: Patient, org_urn: str) -> dict[str, Any]:
    gender = (patient.sex or "unknown").lower()
    if gender not in {"male", "female", "other", "unknown"}:
        gender = "unknown"
    res: dict[str, Any] = {
        "resourceType": "Patient",
        "id": str(patient.id),
        "active": patient.is_active,
        "identifier": [
            {"use": "official", "system": "https://malaffi.ae/fhir/identifier/mrn", "value": patient.mrn},
            {"use": "secondary", "system": "https://sahatna.ae/fhir/identifier/participant", "value": f"SAH-{patient.id}"},
        ],
        "name": [{"use": "official", "family": patient.family_name, "given": [patient.given_name], "text": f"{patient.given_name} {patient.family_name}"}],
        "gender": gender,
        "managingOrganization": {"reference": org_urn},
        "communication": [{"language": {"coding": [{"system": "urn:ietf:bcp:47", "code": patient.preferred_language}]}, "preferred": True}],
    }
    if patient.date_of_birth:
        res["birthDate"] = patient.date_of_birth.isoformat()
    return res


def build_practitioner_resource(user: User) -> dict[str, Any]:
    res: dict[str, Any] = {
        "resourceType": "Practitioner",
        "id": str(user.id),
        "active": user.is_active,
        "name": [{"text": user.full_name}],
    }
    if user.license_number:
        res["identifier"] = [{"system": "https://doh.gov.ae/practitioner-license", "value": user.license_number}]
    return res


def build_consent_resource(consent: Consent, patient_urn: str, org_urn: str) -> dict[str, Any]:
    return {
        "resourceType": "Consent",
        "id": str(consent.id),
        "status": "active" if consent.status == "granted" and consent.revoked_at is None else "inactive",
        "scope": {
            "coding": [
                {
                    "system": "http://terminology.hl7.org/CodeSystem/consentscope",
                    "code": "patient-privacy",
                    "display": consent.scope,
                }
            ]
        },
        "category": [{"coding": [{"system": "https://recova.health/fhir/consent-scope", "code": consent.scope}]}],
        "patient": {"reference": patient_urn},
        "dateTime": _iso(consent.effective_at),
        "organization": [{"reference": org_urn}],
        "provision": {"type": "permit" if consent.status == "granted" else "deny"},
    }


def build_coverage_resource(plan: InsurancePlan, patient_urn: str) -> dict[str, Any]:
    return {
        "resourceType": "Coverage",
        "id": str(plan.id),
        "status": "active" if plan.is_active else "cancelled",
        "subscriberId": plan.code,
        "beneficiary": {"reference": patient_urn},
        "payor": [{"display": plan.payer_name or plan.name}],
        "class": [{"type": {"coding": [{"code": "plan"}]}, "value": plan.code, "name": plan.name}],
    }


def build_observation_resource(obs: Observation, patient_urn: str, status_override: str | None = None) -> dict[str, Any]:
    spec = METRIC_CATALOG.get(obs.metric_code)
    code_obj = {
        "coding": [
            {
                "system": "http://loinc.org" if spec else "https://recova.health/fhir/metric",
                "code": spec.loinc_code if spec else obs.metric_code,
                "display": spec.loinc_display if spec else obs.metric_code,
            }
        ],
        "text": spec.label if spec else obs.metric_code,
    }
    res: dict[str, Any] = {
        "resourceType": "Observation",
        "id": str(obs.id),
        "status": status_override or (obs.status if obs.status in {"registered", "preliminary", "final", "amended", "entered-in-error"} else "final"),
        "code": code_obj,
        "subject": {"reference": patient_urn},
        "effectiveDateTime": _iso(obs.effective_at),
    }
    if obs.value_num is not None:
        res["valueQuantity"] = {"value": round(obs.value_num, 4), "unit": obs.unit or (spec.unit if spec else "")}
    elif obs.value_text is not None:
        res["valueString"] = obs.value_text
    return res


def build_scoring_observation_resource(
    scoring: ScoringResult,
    patient_urn: str,
    *,
    signed_off: bool,
) -> dict[str, Any]:
    interp = FHIR_INTERPRETATION.get(scoring.risk_tier, FHIR_INTERPRETATION["INDETERMINATE"])
    components = [
        {"code": {"text": "Telemetry Confidence Index"}, "valueQuantity": {"value": scoring.confidence_index, "unit": "%"}},
    ]
    if scoring.composite_index is not None:
        components.append({"code": {"text": "Composite Weighted Drift Index"}, "valueQuantity": {"value": scoring.composite_index, "unit": "SE"}})
    for m in scoring.metric_results or []:
        if m.get("z_score") is not None:
            components.append(
                {
                    "code": {"text": f"{m['metric_code']} Z-Score"},
                    "valueQuantity": {"value": m["z_score"], "unit": "SE"},
                }
            )
    return {
        "resourceType": "Observation",
        "id": f"score-{scoring.id}",
        "status": "final" if signed_off else "preliminary",
        "code": {
            "coding": [{"system": "https://recova.health/fhir/observation", "code": f"recova-drift-{scoring.track}", "display": f"Recova Deterministic Longitudinal Drift ({scoring.track})"}],
            "text": f"Recova Agent 4 Deterministic Drift ({scoring.algorithm_version})",
        },
        "subject": {"reference": patient_urn},
        "effectiveDateTime": _iso(scoring.computed_at),
        "valueQuantity": {"value": scoring.primary_z if scoring.primary_z is not None else 0.0, "unit": "SE"},
        "interpretation": [{"coding": [interp]}],
        "component": components,
    }


def build_questionnaire_response(screening: ScreeningRecord, patient_urn: str) -> dict[str, Any]:
    items = []
    for idx, val in enumerate(screening.phq9_item_responses or [], start=1):
        items.append({"linkId": f"phq9-q{idx}", "answer": [{"valueInteger": int(val)}]})
    return {
        "resourceType": "QuestionnaireResponse",
        "id": str(screening.id),
        "questionnaire": "http://loinc.org/q/44249-1",
        "status": "completed",
        "subject": {"reference": patient_urn},
        "authored": _iso(screening.screened_at),
        "item": items,
    }


def build_encounter_resource(run: PipelineRun, patient_urn: str, org_urn: str) -> dict[str, Any]:
    return {
        "resourceType": "Encounter",
        "id": str(run.id),
        "status": "finished" if run.finished_at else "in-progress",
        "class": {"system": "http://terminology.hl7.org/CodeSystem/v3-ActCode", "code": "VR", "display": "virtual"},
        "type": [{"text": f"Recova {run.track} anticipatory pipeline run"}],
        "subject": {"reference": patient_urn},
        "serviceProvider": {"reference": org_urn},
        "period": {"start": _iso(run.started_at or run.created_at), "end": _iso(run.finished_at) if run.finished_at else None},
    }


def build_service_request_resource(
    referral: Referral,
    patient_urn: str,
    *,
    requester_urn: str | None = None,
    coverage_urn: str | None = None,
    reason_urn: str | None = None,
    facility: CareFacility | None = None,
) -> dict[str, Any]:
    status_map = {
        ReferralStatus.PROPOSED.value: "draft",
        ReferralStatus.APPROVED.value: "active",
        ReferralStatus.PATIENT_NOTIFIED.value: "active",
        ReferralStatus.BOOKED.value: "active",
        ReferralStatus.CONSULTATION_COMPLETED.value: "completed",
        ReferralStatus.OUTCOME_VERIFIED.value: "completed",
        ReferralStatus.MISSED.value: "active",
        ReferralStatus.ESCALATED.value: "active",
        ReferralStatus.CANCELLED.value: "revoked",
        ReferralStatus.REJECTED.value: "revoked",
    }
    priority = referral.priority if referral.priority in {"routine", "urgent", "stat", "asap"} else "routine"
    sr: dict[str, Any] = {
        "resourceType": "ServiceRequest",
        "id": str(referral.id),
        "status": status_map.get(referral.status, "draft"),
        "intent": "order",
        "priority": priority,
        "code": {"coding": [{"system": "https://recova.health/fhir/pathway", "code": referral.pathway, "display": referral.pathway}]},
        "subject": {"reference": patient_urn},
        "authoredOn": _iso(referral.created_at),
        "note": [{"text": referral.reason}],
    }
    if requester_urn:
        sr["requester"] = {"reference": requester_urn}
    if coverage_urn:
        sr["insurance"] = [{"reference": coverage_urn}]
    if reason_urn:
        sr["reasonReference"] = [{"reference": reason_urn}]
    if facility:
        sr["performer"] = [{"display": facility.name}]
    return sr


def build_care_plan_resource(
    referral: Referral,
    patient_urn: str,
    *,
    service_request_urn: str,
    author_urn: str | None = None,
) -> dict[str, Any]:
    active = referral.status not in {ReferralStatus.PROPOSED.value, ReferralStatus.REJECTED.value, ReferralStatus.CANCELLED.value}
    completed = referral.status == ReferralStatus.OUTCOME_VERIFIED.value
    cp: dict[str, Any] = {
        "resourceType": "CarePlan",
        "id": f"cp-{referral.id}",
        "status": "completed" if completed else ("active" if active else "draft"),
        "intent": "plan",
        "title": f"Recova {referral.track.upper()} Closed-Loop Plan ({referral.pathway})",
        "description": referral.reason,
        "subject": {"reference": patient_urn},
        "activity": [{"reference": {"reference": service_request_urn}}],
    }
    if author_urn:
        cp["author"] = {"reference": author_urn}
    return cp


def build_communication_resource(notif: Notification, patient_urn: str) -> dict[str, Any]:
    return {
        "resourceType": "Communication",
        "id": str(notif.id),
        "status": "completed" if notif.status in {"sent", "delivered"} else ("not-done" if notif.status in {"failed", "not_configured"} else "in-progress"),
        "category": [{"text": notif.category}],
        "medium": [{"text": notif.channel}],
        "subject": {"reference": patient_urn},
        "sent": _iso(notif.sent_at) if notif.sent_at else None,
        "payload": [{"contentString": f"{notif.subject}: {notif.body}"}],
    }


def build_patient_fhir_bundle(
    *,
    org: Organization,
    patient: Patient,
    consents: list[Consent],
    observations: list[Observation],
    plan: InsurancePlan | None = None,
    latest_run: PipelineRun | None = None,
    latest_scoring: ScoringResult | None = None,
    latest_review: ClinicalReview | None = None,
    practitioner: User | None = None,
    referrals: list[tuple[Referral, CareFacility | None]] | None = None,
    screenings: list[ScreeningRecord] | None = None,
    notifications: list[Notification] | None = None,
    bundle_type: str = "transaction",
) -> dict[str, Any]:
    now_iso = datetime.now(timezone.utc).isoformat()
    entries: list[dict[str, Any]] = []

    def add(res: dict[str, Any], method: str = "POST") -> str:
        full_url = _urn(res["resourceType"], res["id"])
        entry: dict[str, Any] = {"fullUrl": full_url, "resource": res}
        if bundle_type == "transaction":
            entry["request"] = {"method": method, "url": f"{res['resourceType']}/{res['id']}" if method == "PUT" else res["resourceType"]}
        entries.append(entry)
        return full_url

    org_urn = add(build_organization_resource(org), method="PUT")
    patient_urn = add(build_patient_resource(patient, org_urn), method="PUT")
    practitioner_urn = add(build_practitioner_resource(practitioner), method="PUT") if practitioner else None
    coverage_urn = add(build_coverage_resource(plan, patient_urn), method="PUT") if plan else None

    for c in consents:
        add(build_consent_resource(c, patient_urn, org_urn))

    for obs in observations[:50]:
        add(build_observation_resource(obs, patient_urn))

    for scr in (screenings or [])[:10]:
        if scr.phq9_item_responses:
            add(build_questionnaire_response(scr, patient_urn))

    score_obs_urn: str | None = None
    if latest_run is not None:
        add(build_encounter_resource(latest_run, patient_urn, org_urn))
    if latest_scoring is not None:
        signed_off = latest_review is not None and latest_review.decision != "reject"
        score_obs_urn = add(build_scoring_observation_resource(latest_scoring, patient_urn, signed_off=signed_off))

    for ref, facility in referrals or []:
        sr_urn = add(
            build_service_request_resource(
                ref,
                patient_urn,
                requester_urn=practitioner_urn,
                coverage_urn=coverage_urn,
                reason_urn=score_obs_urn,
                facility=facility,
            )
        )
        add(build_care_plan_resource(ref, patient_urn, service_request_urn=sr_urn, author_urn=practitioner_urn))

    for n in (notifications or [])[:20]:
        add(build_communication_resource(n, patient_urn))

    return {
        "resourceType": "Bundle",
        "id": f"recova-r4-{patient.id}",
        "meta": {
            "lastUpdated": now_iso,
            "profile": [
                "http://hl7.org/fhir/StructureDefinition/Bundle",
                "https://malaffi.ae/fhir/StructureDefinition/recova-closed-loop-bundle",
            ],
            "tag": [
                {
                    "system": "https://doh.gov.ae/fhir/coding/governance",
                    "code": "DECIDE-AI-SEPARATED",
                    "display": "Deterministic scoring separated from LLM synthesis",
                }
            ],
        },
        "type": bundle_type,
        "timestamp": now_iso,
        "entry": entries,
    }


_REQUIRED_FIELDS: dict[str, tuple[str, ...]] = {
    "Organization": ("id", "name"),
    "Patient": ("id", "name", "gender"),
    "Practitioner": ("id", "name"),
    "Consent": ("id", "status", "scope", "patient"),
    "Coverage": ("id", "status", "beneficiary", "payor"),
    "Observation": ("id", "status", "code", "subject"),
    "QuestionnaireResponse": ("id", "status", "subject"),
    "Encounter": ("id", "status", "class", "subject"),
    "ServiceRequest": ("id", "status", "intent", "subject"),
    "CarePlan": ("id", "status", "intent", "subject"),
    "Communication": ("id", "status"),
}


def _collect_refs(obj: Any, out: list[str]) -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "reference" and isinstance(v, str) and v.startswith("urn:uuid:"):
                out.append(v)
            else:
                _collect_refs(v, out)
    elif isinstance(obj, list):
        for item in obj:
            _collect_refs(item, out)


def validate_fhir_bundle(bundle: dict[str, Any]) -> dict[str, Any]:
    """Validate FHIR R4 Bundle structure, required resource fields, and urn:uuid reference integrity."""
    errors: list[str] = []
    warnings: list[str] = []

    if bundle.get("resourceType") != "Bundle":
        errors.append("Root resourceType must be 'Bundle'")
    if bundle.get("type") not in {"transaction", "collection", "document", "batch"}:
        errors.append(f"Invalid Bundle.type: {bundle.get('type')}")

    entries = bundle.get("entry")
    if not isinstance(entries, list) or not entries:
        errors.append("Bundle.entry must be a non-empty list")
        return {"valid": False, "errors": errors, "warnings": warnings, "resource_counts": {}}

    full_urls: set[str] = set()
    resource_counts: dict[str, int] = {}

    for i, entry in enumerate(entries):
        fu = entry.get("fullUrl")
        res = entry.get("resource")
        if not fu:
            errors.append(f"entry[{i}] missing fullUrl")
        elif fu in full_urls:
            errors.append(f"Duplicate fullUrl: {fu}")
        else:
            full_urls.add(fu)

        if not isinstance(res, dict):
            errors.append(f"entry[{i}] missing resource object")
            continue

        rtype = res.get("resourceType")
        if not rtype:
            errors.append(f"entry[{i}] resource missing resourceType")
            continue
        resource_counts[rtype] = resource_counts.get(rtype, 0) + 1

        req = _REQUIRED_FIELDS.get(rtype)
        if req is None:
            warnings.append(f"entry[{i}] unprofiled resourceType '{rtype}'")
        else:
            for f in req:
                if not res.get(f):
                    errors.append(f"{rtype}/{res.get('id', '?')} missing required field '{f}'")

        if bundle.get("type") == "transaction" and not entry.get("request", {}).get("method"):
            errors.append(f"entry[{i}] ({rtype}) missing request.method for transaction Bundle")

    refs: list[str] = []
    _collect_refs(entries, refs)
    for ref in refs:
        if ref not in full_urls:
            errors.append(f"Broken internal reference: {ref}")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "resource_counts": resource_counts,
        "total_entries": len(entries),
    }
