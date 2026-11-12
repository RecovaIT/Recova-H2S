"""Tests for LLM synthesis validation and fallback behavior (Agent 5)."""

from __future__ import annotations

import json

import httpx

from app.integrations.llm import generate_clinical_synthesis
from app.models.enums import SynthesisStatus


def test_llm_unconfigured_returns_honest_status():
    res = generate_clinical_synthesis({"track": "core", "deterministic_risk_tier": "RED"})
    assert res.status == SynthesisStatus.PROVIDER_NOT_CONFIGURED
    assert res.draft is None


def test_llm_valid_and_invalid_schema_handling(monkeypatch):
    class FakeResp:
        def __init__(self, payload: dict):
            self._payload = payload

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return self._payload

    valid_json = {
        "summary_en": "Deterministic Z-score indicates significant sleep reduction (-2.3 SE) relative to personal baseline.",
        "summary_ar": "يشير مؤشر الانحراف المعياري المحدد إلى انخفاض ملحوظ في ساعات النوم بمقدار -2.3 خطأ معياري.",
        "contributing_signals": ["sleep_hours: Z = -2.30 (RED)"],
        "missing_data_limitations": [],
        "confounder_notes": [],
        "recommended_follow_up_actions": ["Review sleep trend and consider tele-consultation within 24 hours."],
        "clinical_disclaimer": "Draft clinical synthesis for licensed clinician review only.",
    }

    monkeypatch.setattr(
        httpx,
        "post",
        lambda *a, **kw: FakeResp({"choices": [{"message": {"content": json.dumps(valid_json)}}]}),
    )

    res = generate_clinical_synthesis(
        {"track": "core", "deterministic_risk_tier": "RED"},
        org_override={"provider": "openai", "api_key": "sk-test-dummy", "model": "gpt-4o-mini"},
    )
    assert res.status == SynthesisStatus.COMPLETED
    assert res.draft is not None
    assert "sleep" in res.draft.summary_en.lower()

    # Invalid schema from LLM must fail validation instead of passing through
    monkeypatch.setattr(
        httpx,
        "post",
        lambda *a, **kw: FakeResp({"choices": [{"message": {"content": '{"summary_en": "too short"}'}}]}),
    )
    bad = generate_clinical_synthesis(
        {"track": "core", "deterministic_risk_tier": "RED"},
        org_override={"provider": "openai", "api_key": "sk-test-dummy"},
    )
    assert bad.status == SynthesisStatus.VALIDATION_FAILED
    assert bad.draft is None
