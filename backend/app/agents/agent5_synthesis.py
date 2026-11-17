"""Agent 5: Clinical Synthesis & Explainability Agent (LLM-backed, strictly non-autonomous)."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.schemas import Agent5Input, Agent5Output
from app.core.security import decrypt_str
from app.engine.scoring import DeterministicScoreBundle
from app.integrations.llm import PROMPT_VERSION, generate_clinical_synthesis
from app.models.clinical import Patient
from app.models.engine import ClinicalSynthesis
from app.models.enums import ConsentScope, SynthesisStatus
from app.models.ops import IntegrationConfig


def _load_org_llm_override(db: Session, organization_id: uuid.UUID) -> dict[str, str] | None:
    cfg = db.scalar(
        select(IntegrationConfig).where(
            IntegrationConfig.organization_id == organization_id,
            IntegrationConfig.integration == "llm",
            IntegrationConfig.enabled.is_(True),
        )
    )
    if cfg is None:
        return None
    secrets: dict = {}
    if cfg.secrets_encrypted:
        import json

        raw = decrypt_str(cfg.secrets_encrypted)
        if raw:
            secrets = json.loads(raw)
    merged = {**(cfg.settings or {}), **secrets}
    return {k: str(v) for k, v in merged.items() if v is not None}


def run_agent5(
    db: Session,
    patient: Patient,
    run_id: uuid.UUID,
    bundle: DeterministicScoreBundle,
    *,
    active_scopes: set[str],
    revoked_scopes: set[str],
) -> tuple[Agent5Input, Agent5Output, ClinicalSynthesis]:
    # External synthesis requires explicit processing and synthesis grants.
    llm_explicitly_revoked = ConsentScope.LLM_SYNTHESIS.value in revoked_scopes
    llm_consent_granted = not llm_explicitly_revoked and {ConsentScope.DATA_PROCESSING.value, ConsentScope.LLM_SYNTHESIS.value}.issubset(active_scopes)

    inp = Agent5Input(
        track=bundle.track,
        risk_tier=bundle.risk_tier.value,
        confidence_index=bundle.confidence_index,
        primary_metric_code=bundle.primary_metric_code,
        primary_z=bundle.primary_z,
        llm_consent_granted=llm_consent_granted,
    )

    if not llm_consent_granted:
        syn = ClinicalSynthesis(
            organization_id=patient.organization_id,
            run_id=run_id,
            status=SynthesisStatus.CONSENT_NOT_GRANTED.value,
            prompt_version=PROMPT_VERSION,
            error="Patient consent for LLM clinical synthesis was revoked or not granted.",
        )
        db.add(syn)
        db.flush()
        out = Agent5Output(
            synthesis_id=syn.id,
            status=syn.status,
            prompt_version=PROMPT_VERSION,
            error=syn.error,
        )
        return inp, out, syn

    # Strict de-identification: NO patient name, MRN, DOB, national ID, phone, email, or notes sent to LLM.
    deidentified = {
        "track": bundle.track,
        "algorithm_version": bundle.algorithm_version,
        "deterministic_risk_tier": bundle.risk_tier.value,
        "confidence_index_pct": bundle.confidence_index,
        "composite_drift_index": bundle.composite_index,
        "primary_metric_code": bundle.primary_metric_code,
        "primary_z_score": bundle.primary_z,
        "missing_streams": bundle.missing_streams,
        "confounders_applied": bundle.confounders_applied,
        "metric_details": [
            {
                "metric_code": m.metric_code,
                "label": m.label,
                "unit": m.unit,
                "baseline_status": m.baseline_status,
                "baseline_mean": m.baseline_mean,
                "current_observation": m.current_observation,
                "adjusted_se": m.adjusted_se,
                "practice_gain_offset": m.practice_gain_offset,
                "z_score": m.z_score,
                "drift_direction": m.drift_direction,
                "risk_tier": m.risk_tier,
                "reference_alert": m.reference_alert,
            }
            for m in bundle.metric_results
        ],
    }

    org_override = _load_org_llm_override(db, patient.organization_id)
    res = generate_clinical_synthesis(deidentified, org_override=org_override)

    syn = ClinicalSynthesis(
        organization_id=patient.organization_id,
        run_id=run_id,
        status=res.status.value,
        provider=res.provider,
        model=res.model,
        prompt_version=res.prompt_version,
        prompt_hash=res.prompt_hash,
        summary_en=res.draft.summary_en if res.draft else None,
        summary_ar=res.draft.summary_ar if res.draft else None,
        structured=res.draft.model_dump() if res.draft else None,
        error=res.error,
        latency_ms=res.latency_ms,
    )
    db.add(syn)
    db.flush()

    out = Agent5Output(
        synthesis_id=syn.id,
        status=syn.status,
        provider=syn.provider,
        model=syn.model,
        prompt_version=syn.prompt_version,
        summary_en=syn.summary_en,
        summary_ar=syn.summary_ar,
        error=syn.error,
    )
    return inp, out, syn
