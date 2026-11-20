"""LLM provider abstraction for Agent 5 (Clinical Synthesis & Explainability).

Supports OpenAI, Azure OpenAI, Google Gemini, and Anthropic via direct HTTPS APIs.
Strict clinical safety invariants:
- Only de-identified/pseudonymized deterministic metrics and flags are sent.
- Outputs are validated against `SynthesisDraftSchema`.
- The LLM NEVER sets risk tiers, diagnoses patients, or approves referrals.
- If no provider is configured, returns `provider_not_configured` without fabricating text.
- Post-call consistency check: rejects any draft that contradicts the deterministic trace
  (per task brief 2.3).
"""

from __future__ import annotations

import hashlib
import json
import re
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


# ---------- Post-call consistency check (task brief 2.3) ----------

_TIER_PATTERNS = [
    # High-confidence: "risk tier is RED", "overall tier: AMBER", "overall risk tier = GREEN"
    re.compile(
        r"\b(?:overall\s+(?:risk\s+)?tier|risk\s+tier)\s*(?:is|of|[:=])?\s*(GREEN|AMBER|RED)\b",
        re.IGNORECASE,
    ),
    # High-confidence: "classified as RED", "flagged as AMBER", "assigned RED"
    re.compile(
        r"\b(?:classified|flagged|assigned|labeled)\s+as\s+(GREEN|AMBER|RED)\b",
        re.IGNORECASE,
    ),
]

_Z_PATTERNS = [
    # "Z-score of -2.3", "Z-score: -2.3", "Z-score -2.3"
    re.compile(r"\bZ[-\s]?score\s*(?:of|=|:|is)?\s*(-?\d+(?:\.\d+)?)", re.IGNORECASE),
    # "Z = -2.3", "Z=-2.3"
    re.compile(r"\bZ\s*=\s*(-?\d+(?:\.\d+)?)", re.IGNORECASE),
    # "-2.3 SE", "-2.3 standard errors"
    re.compile(r"(-?\d+(?:\.\d+)?)\s*(?:standard\s+errors?|SE\b)"),
]


def _collect_engine_zs(deidentified: dict[str, Any]) -> set[float]:
    """Collect all valid Z-scores from the engine payload (primary + per-metric)."""
    zs: set[float] = set()
    primary = deidentified.get("primary_z_score")
    if primary is not None:
        try:
            zs.add(round(float(primary), 2))
        except (TypeError, ValueError):
            pass
    for m in deidentified.get("metric_details") or []:
        if isinstance(m, dict):
            z = m.get("z_score")
            if z is not None:
                try:
                    zs.add(round(float(z), 2))
                except (TypeError, ValueError):
                    pass
    return zs


def _check_consistency(draft: SynthesisDraftSchema, deidentified: dict[str, Any]) -> str | None:
    """Reject if the LLM draft contradicts the deterministic engine trace.

    Checks:
      1. Tier: any explicit risk-tier assertion must match `deterministic_risk_tier`.
      2. Z-score: any stated Z must match one of the engine's Z values (primary or per-metric).
      3. Per-metric tier labels in `contributing_signals` must match `metric_details[*].risk_tier`.

    Returns None if consistent, else a human-readable error string.
    """
    engine_tier = deidentified.get("deterministic_risk_tier")
    # Emergency cases never reach Agent 5, but be defensive if they do.
    if engine_tier in (None, "EMERGENCY_BYPASS", "INDETERMINATE"):
        return None

    text = " ".join([draft.summary_en, " ".join(draft.contributing_signals)])

    # ---- Check 1: tier assertions ----
    if engine_tier in ("GREEN", "AMBER", "RED"):
        for pat in _TIER_PATTERNS:
            for match in pat.finditer(text):
                stated = match.group(1).upper()
                if stated != engine_tier:
                    return (
                        f"draft asserts tier '{stated}' but engine computed "
                        f"'{engine_tier}'"
                    )

    # ---- Check 2: Z-score assertions ----
    valid_zs = _collect_engine_zs(deidentified)
    if valid_zs:
        for pat in _Z_PATTERNS:
            for match in pat.finditer(text):
                try:
                    stated_z = round(float(match.group(1)), 2)
                except (TypeError, ValueError):
                    continue
                if stated_z not in valid_zs:
                    return (
                        f"draft states Z={stated_z} which is not one of the "
                        f"engine values {sorted(valid_zs)}"
                    )

    # ---- Check 3: per-metric tier labels in contributing_signals ----
    metric_tiers: dict[str, str] = {}
    for m in deidentified.get("metric_details") or []:
        if isinstance(m, dict) and m.get("metric_code") and m.get("risk_tier"):
            metric_tiers[str(m["metric_code"])] = str(m["risk_tier"]).upper()

    if metric_tiers:
        for sig in draft.contributing_signals:
            m = re.match(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*[:=]", sig)
            if not m:
                continue
            code = m.group(1)
            tier_m = re.search(r"\b(GREEN|AMBER|RED)\b", sig)
            if tier_m and code in metric_tiers:
                stated = tier_m.group(1).upper()
                if stated != metric_tiers[code]:
                    return (
                        f"signal '{code}' labeled '{stated}' but engine assigned "
                        f"'{metric_tiers[code]}'"
                    )

    return None


# ---------- Provider call adapters ----------

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


# ---------- Public entry point ----------

def generate_clinical_synthesis(
    deidentified_context: dict[str, Any],
    *,
    org_override: dict[str, str] | None = None,
    settings: Settings | None = None,
) -> SynthesisCallResult:
    """Invoke the configured LLM provider on de-identified Agent 4 context and validate schema + consistency."""
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

    # ---- Schema validation ----
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

    # ---- Consistency validation (task brief 2.3) ----
    consistency_error = _check_consistency(draft, deidentified_context)
    if consistency_error:
        return SynthesisCallResult(
            status=SynthesisStatus.VALIDATION_FAILED,
            provider=provider,
            model=used_model,
            prompt_hash=prompt_hash,
            error=f"Consistency check failed: {consistency_error}",
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