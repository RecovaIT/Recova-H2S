"""Tests for LLM synthesis validation, fallback behavior, and consistency check (Agent 5)."""

from __future__ import annotations

import json

import httpx

from app.integrations.llm import generate_clinical_synthesis
from app.models.enums import SynthesisStatus


class _FakeResp:
    """Minimal httpx.post return shape for monkeypatching."""

    def __init__(self, payload: dict):
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


def _ok_payload(content: dict) -> _FakeResp:
    return _FakeResp({"choices": [{"message": {"content": json.dumps(content)}}]})


_VALID_DRAFT = {
    "summary_en": "Deterministic Z-score of -2.30 indicates significant sleep reduction relative to personal baseline.",
    "summary_ar": "يشير مؤشر الانحراف المعياري المحدد -2.30 إلى انخفاض ملحوظ في ساعات النوم مقارنة بالخط الأساسي.",
    "contributing_signals": ["sleep_hours: Z = -2.30 (RED)"],
    "missing_data_limitations": [],
    "confounder_notes": [],
    "recommended_follow_up_actions": ["Review sleep trend and consider tele-consultation within 24 hours."],
    "clinical_disclaimer": "Draft clinical synthesis for licensed clinician review only.",
}


# ---------- Existing tests (preserved) ----------

def test_llm_unconfigured_returns_honest_status():
    res = generate_clinical_synthesis({"track": "core", "deterministic_risk_tier": "RED"})
    assert res.status == SynthesisStatus.PROVIDER_NOT_CONFIGURED
    assert res.draft is None


def test_llm_valid_and_invalid_schema_handling(monkeypatch):
    # Valid schema (no primary_z in payload → Z check skipped, tier check passes)
    monkeypatch.setattr(httpx, "post", lambda *a, **kw: _ok_payload(_VALID_DRAFT))
    res = generate_clinical_synthesis(
        {"track": "core", "deterministic_risk_tier": "RED"},
        org_override={"provider": "openai", "api_key": "sk-test-dummy", "model": "gpt-4o-mini"},
    )
    assert res.status == SynthesisStatus.COMPLETED
    assert res.draft is not None
    assert "sleep" in res.draft.summary_en.lower()

    # Invalid schema must fail before consistency check runs
    monkeypatch.setattr(
        httpx, "post", lambda *a, **kw: _ok_payload({"summary_en": "too short"})
    )
    bad = generate_clinical_synthesis(
        {"track": "core", "deterministic_risk_tier": "RED"},
        org_override={"provider": "openai", "api_key": "sk-test-dummy"},
    )
    assert bad.status == SynthesisStatus.VALIDATION_FAILED
    assert bad.draft is None


# ---------- New consistency-check tests (task brief 2.3) ----------

def test_consistency_accepts_valid_output_with_matching_tier_and_z(monkeypatch):
    """Draft asserts the SAME tier and Z as the engine → accepted."""
    draft = {
        **_VALID_DRAFT,
        "summary_en": "Deterministic Z-score of -2.30 indicates significant sleep drift. "
                      "Risk tier is RED; recommend urgent tele-consultation.",
    }
    monkeypatch.setattr(httpx, "post", lambda *a, **kw: _ok_payload(draft))

    res = generate_clinical_synthesis(
        {
            "track": "core",
            "deterministic_risk_tier": "RED",
            "primary_z_score": -2.30,
        },
        org_override={"provider": "openai", "api_key": "sk-test-dummy"},
    )
    assert res.status == SynthesisStatus.COMPLETED, res.error
    assert res.draft is not None


def test_consistency_rejects_tier_contradiction(monkeypatch):
    """Draft asserts a DIFFERENT tier than the engine → rejected."""
    draft = {
        **_VALID_DRAFT,
        "summary_en": "The patient appears stable. Risk tier is GREEN; "
                      "continue routine monitoring without escalation.",
        "summary_ar": "يبدو المريض مستقراً. مستوى الخطورة GREEN؛ استمر في المتابعة الروتينية دون تصعيد.",
        "contributing_signals": ["sleep_hours: Z = -2.30 (RED)"],
    }
    monkeypatch.setattr(httpx, "post", lambda *a, **kw: _ok_payload(draft))

    res = generate_clinical_synthesis(
        {
            "track": "core",
            "deterministic_risk_tier": "RED",
            "primary_z_score": -2.30,
        },
        org_override={"provider": "openai", "api_key": "sk-test-dummy"},
    )
    assert res.status == SynthesisStatus.VALIDATION_FAILED
    assert res.draft is None
    assert "Consistency check failed" in (res.error or "")
    assert "tier" in (res.error or "").lower()


def test_consistency_rejects_z_mismatch(monkeypatch):
    """Draft states a Z-score that does not exist in the engine trace → rejected."""
    draft = {
        **_VALID_DRAFT,
        "summary_en": "Deterministic Z-score of -4.50 indicates severe decline. "
                      "Risk tier is RED; escalate immediately.",
        "summary_ar": "يشير الانحراف -4.50 إلى تراجع شديد. مستوى الخطورة RED.",
        "contributing_signals": ["sleep_hours: Z = -4.50 (RED)"],
    }
    monkeypatch.setattr(httpx, "post", lambda *a, **kw: _ok_payload(draft))

    res = generate_clinical_synthesis(
        {
            "track": "core",
            "deterministic_risk_tier": "RED",
            "primary_z_score": -2.30,
        },
        org_override={"provider": "openai", "api_key": "sk-test-dummy"},
    )
    assert res.status == SynthesisStatus.VALIDATION_FAILED
    assert res.draft is None
    assert "Consistency check failed" in (res.error or "")
    assert "Z=" in (res.error or "") or "Z-score" in (res.error or "").lower() or "-4.50" in (res.error or "")