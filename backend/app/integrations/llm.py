"""LLM provider abstraction for Agent 5 (Clinical Synthesis & Explainability).

Supports OpenAI, Azure OpenAI, Google Gemini, and Anthropic via direct HTTPS APIs.
Strict clinical safety invariants:
- Only de-identified/pseudonymized deterministic metrics and flags are sent.
- Outputs are validated against `SynthesisDraftSchema`.
- The LLM NEVER sets risk tiers, diagnoses patients, or approves referrals.
- If no provider is configured, returns `provider_not_configured` without fabricating text.
"""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any

import httpx
from pydantic import BaseModel, Field, ValidationError

from app.core.config import Settings, get_settings
from app.models.enums import SynthesisStatus

PROMPT_VERSION = "1.0.0"


class SynthesisDraftSchema(BaseModel):
    summary_en: str = Field(min_length=20, max_length=4000)
    summary_ar: str = Field(min_length=20, max_length=4000)
    contributing_signals: list[str] = Field(default_factory=list, max_length=20)
    missing_data_limitations: list[str] = Field(default_factory=list, max_length=20)
    confounder_notes: list[str] = Field(default_factory=list, max_length=20)
    recommended_follow_up_actions: list[str] = Field(default_factory=list, max_length=10)
    clinical_disclaimer: str = Field(min_length=10, max_length=500)


class SynthesisCallResult(BaseModel):
    status: SynthesisStatus
    provider: str | None = None
    model: str | None = None
    prompt_version: str = PROMPT_VERSION
    prompt_hash: str | None = None
    draft: SynthesisDraftSchema | None = None
    error: str | None = None
    latency_ms: int | None = None


_SYSTEM_PROMPT = """You are a clinical decision-support explanation writer (DECIDE-AI compliant) inside the Recova platform.
You receive ONLY deterministic statistical outputs computed by Agent 4 (Python math engine).

STRICT RULES:
1. NEVER invent, alter, or override the deterministic risk_tier or Z-scores.
2. NEVER state a definitive medical diagnosis; frame everything as a clinician review draft.
3. NEVER approve or authorize referrals autonomously; recommend actions for clinician review.
4. Explicitly explain missing data limitations and confounders when present.
5. Output ONLY a single valid JSON object matching this exact schema:
{
  "summary_en": "Clear, concise English clinical review draft grounded strictly in the input metrics.",
  "summary_ar": "Accurate Modern Standard Arabic clinical review draft matching summary_en.",
  "contributing_signals": ["metric_code: concise explanation of deterministic Z-score and direction"],
  "missing_data_limitations": ["concise explanation of any missing data streams and confidence impact"],
  "confounder_notes": ["concise explanation of applied confounders"],
  "recommended_follow_up_actions": ["concrete non-binding review/follow-up options for clinician sign-off"],
  "clinical_disclaimer": "Draft clinical synthesis for licensed clinician review; deterministic scoring is advisory and not an autonomous diagnosis."
}"""


def _extract_json(text: str) -> dict[str, Any]:
    s = text.strip()
    if s.startswith("```"):
        lines = s.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        s = "\n".join(lines).strip()
    start = s.find("{")
    end = s.rfind("}")
    if start != -1 and end != -1 and end > start:
        s = s[start : end + 1]
    return json.loads(s)


def _call_openai(cfg: dict[str, str], payload_json: str, timeout: float) -> tuple[str, str]:
    model = cfg.get("model") or "gpt-4o-mini"
    base = (cfg.get("base_url") or "https://api.openai.com/v1").rstrip("/")
    r = httpx.post(
        f"{base}/chat/completions",
        headers={"Authorization": f"Bearer {cfg['api_key']}", "Content-Type": "application/json"},
        json={
            "model": model,
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": payload_json},
            ],
        },
        timeout=timeout,
    )
    r.raise_for_status()
    data = r.json()
    return data["choices"][0]["message"]["content"], model


def _call_azure_openai(cfg: dict[str, str], payload_json: str, timeout: float) -> tuple[str, str]:
    dep = cfg["azure_deployment"]
    ver = cfg.get("azure_api_version") or "2024-06-01"
    base = cfg["base_url"].rstrip("/")
    r = httpx.post(
        f"{base}/openai/deployments/{dep}/chat/completions?api-version={ver}",
        headers={"api-key": cfg["api_key"], "Content-Type": "application/json"},
        json={
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": payload_json},
            ],
        },
        timeout=timeout,
    )
    r.raise_for_status()
    data = r.json()
    return data["choices"][0]["message"]["content"], dep


def _call_anthropic(cfg: dict[str, str], payload_json: str, timeout: float) -> tuple[str, str]:
    model = cfg.get("model") or "claude-3-5-sonnet-latest"
    base = (cfg.get("base_url") or "https://api.anthropic.com").rstrip("/")
    r = httpx.post(
        f"{base}/v1/messages",
        headers={
            "x-api-key": cfg["api_key"],
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "max_tokens": 1200,
            "temperature": 0.1,
            "system": _SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": payload_json}],
        },
        timeout=timeout,
    )
    r.raise_for_status()
    data = r.json()
    text = "".join(block.get("text", "") for block in data.get("content", []) if block.get("type") == "text")
    return text, model


def _call_gemini(cfg: dict[str, str], payload_json: str, timeout: float) -> tuple[str, str]:
    model = cfg.get("model") or "gemini-2.0-flash"
    base = (cfg.get("base_url") or "https://generativelanguage.googleapis.com/v1beta").rstrip("/")
    r = httpx.post(
        f"{base}/models/{model}:generateContent",
        params={"key": cfg["api_key"]},
        headers={"Content-Type": "application/json"},
        json={
            "systemInstruction": {"parts": [{"text": _SYSTEM_PROMPT}]},
            "contents": [{"role": "user", "parts": [{"text": payload_json}]}],
            "generationConfig": {"temperature": 0.1, "responseMimeType": "application/json"},
        },
        timeout=timeout,
    )
    r.raise_for_status()
    data = r.json()
    text = data["candidates"][0]["content"]["parts"][0]["text"]
    return text, model


def generate_clinical_synthesis(
    deidentified_context: dict[str, Any],
    *,
    org_override: dict[str, str] | None = None,
    settings: Settings | None = None,
) -> SynthesisCallResult:
    """Invoke the configured LLM provider on de-identified Agent 4 context and validate schema."""
    s = settings or get_settings()
    provider = (org_override or {}).get("provider") or s.llm_provider
    api_key = (org_override or {}).get("api_key") or s.llm_api_key
    model = (org_override or {}).get("model") or s.llm_model
    base_url = (org_override or {}).get("base_url") or s.llm_base_url
    azure_dep = (org_override or {}).get("azure_deployment") or s.llm_azure_deployment
    azure_ver = (org_override or {}).get("azure_api_version") or s.llm_azure_api_version

    if provider == "none" or not api_key:
        return SynthesisCallResult(
            status=SynthesisStatus.PROVIDER_NOT_CONFIGURED,
            provider=provider,
            error="No LLM provider credentials are configured; deterministic scoring remains available.",
        )
    if provider == "azure_openai" and (not base_url or not azure_dep):
        return SynthesisCallResult(
            status=SynthesisStatus.PROVIDER_NOT_CONFIGURED,
            provider=provider,
            error="Azure OpenAI requires base_url and azure_deployment.",
        )

    payload_json = json.dumps(deidentified_context, sort_keys=True, default=str)
    prompt_hash = hashlib.sha256((_SYSTEM_PROMPT + payload_json).encode()).hexdigest()
    cfg = {
        "api_key": api_key,
        "model": model,
        "base_url": base_url,
        "azure_deployment": azure_dep,
        "azure_api_version": azure_ver,
    }

    t0 = time.perf_counter()
    try:
        if provider == "openai":
            raw_text, used_model = _call_openai(cfg, payload_json, s.llm_timeout_seconds)
        elif provider == "azure_openai":
            raw_text, used_model = _call_azure_openai(cfg, payload_json, s.llm_timeout_seconds)
        elif provider == "anthropic":
            raw_text, used_model = _call_anthropic(cfg, payload_json, s.llm_timeout_seconds)
        elif provider == "gemini":
            raw_text, used_model = _call_gemini(cfg, payload_json, s.llm_timeout_seconds)
        else:
            return SynthesisCallResult(
                status=SynthesisStatus.PROVIDER_NOT_CONFIGURED,
                provider=provider,
                prompt_hash=prompt_hash,
                error=f"Unsupported LLM provider '{provider}'",
            )
    except Exception as exc:  # noqa: BLE001
        return SynthesisCallResult(
            status=SynthesisStatus.PROVIDER_ERROR,
            provider=provider,
            model=model or None,
            prompt_hash=prompt_hash,
            error=f"LLM provider request failed: {type(exc).__name__}: {exc}",
            latency_ms=int((time.perf_counter() - t0) * 1000),
        )

    latency = int((time.perf_counter() - t0) * 1000)
    try:
        parsed = _extract_json(raw_text)
        draft = SynthesisDraftSchema.model_validate(parsed)
    except (json.JSONDecodeError, ValidationError, TypeError) as exc:
        return SynthesisCallResult(
            status=SynthesisStatus.VALIDATION_FAILED,
            provider=provider,
            model=used_model,
            prompt_hash=prompt_hash,
            error=f"LLM output failed schema validation: {exc}",
            latency_ms=latency,
        )

    return SynthesisCallResult(
        status=SynthesisStatus.COMPLETED,
        provider=provider,
        model=used_model,
        prompt_hash=prompt_hash,
        draft=draft,
        latency_ms=latency,
    )
