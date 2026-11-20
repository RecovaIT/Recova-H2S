"""Live i18n catalog & dynamic backend text translation API."""

from __future__ import annotations

import json
import re
from collections import OrderedDict
from typing import Literal

import httpx
from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.core.config import get_settings

router = APIRouter(prefix="/i18n", tags=["i18n"])

# Deterministic catalog for backend enums, statuses, notifications, roles, agents, and phrases
BACKEND_CATALOG_AR: dict[str, str] = {
    # Tracks & Programmes
    "core": "ريكوفا للتعافي",
    "loop": "ريكوفا لوب",
    "neuro": "ريكوفا للأعصاب",
    "worksafe": "ريكوفا لسلامة العمل",
    "Recova Core": "ريكوفا للتعافي",
    "Recova Loop": "ريكوفا لوب",
    "Recova Neuro": "ريكوفا للأعصاب",
    "Recova WorkSafe": "ريكوفا لسلامة العمل",
    # Risk tiers
    "GREEN": "أخضر (مستقر)",
    "AMBER": "كهرماني (إنذار مبكر)",
    "RED": "أحمر (يتطلب انتباهًا)",
    "EMERGENCY_BYPASS": "تجاوز الطوارئ (البوابة ٢)",
    "UNSCORED": "غير مقيم",
    "INDETERMINATE": "غير محدد",
    "green": "أخضر (مستقر)",
    "amber": "كهرماني (إنذار مبكر)",
    "red": "أحمر (يتطلب انتباهًا)",
    "emergency_bypass": "تجاوز الطوارئ (البوابة ٢)",
    "unscored": "غير مقيم",
    "indeterminate": "غير محدد",
    # Pipeline, review, referral, delivery & consent statuses
    "active": "نشط",
    "approved": "معتمد",
    "blocked": "محجوب",
    "booked": "محجوز",
    "cancelled": "ملغى",
    "completed": "مكتمل",
    "configured": "مُعدّ",
    "consultation_completed": "اكتملت الاستشارة",
    "draft": "مسودة",
    "escalated": "تم التصعيد",
    "established": "مستقر / معتمد",
    "failed": "فشل",
    "granted": "ممنوح",
    "in_app_available": "متاح داخل التطبيق",
    "in_progress": "قيد التنفيذ",
    "insufficient": "غير كافٍ",
    "missed": "فائت",
    "not_applicable": "غير منطبق",
    "not_configured": "غير مُعدّ",
    "open": "مفتوح",
    "outcome_verified": "تم التحقق من النتيجة",
    "patient_notified": "تم إشعار المريض",
    "pending": "قيد الانتظار",
    "pending_clinician_review": "بانتظار مراجعة الطبيب",
    "practice": "تدريبي",
    "processed": "تمت المعالجة",
    "proposed": "مقترح",
    "published": "منشور",
    "queued": "في قائمة الانتظار",
    "received": "تم الاستلام",
    "rejected": "مرفوض",
    "resolved": "تم الحل",
    "revoked": "مسحوب",
    "running": "قيد التشغيل",
    "sent": "تم الإرسال",
    "skipped": "تم التخطي",
    "unknown": "غير معروف",
    "verified": "موثّق",
    "withdrawn": "مسحوب",
    # Consent scopes
    "data_processing": "معالجة البيانات",
    "wearable_ingestion": "استقبال بيانات الأجهزة القابلة للارتداء",
    "external_llm": "الذكاء الاصطناعي الخارجي",
    "hie_sharing": "تبادل المعلومات الصحية",
    # Roles & Org types
    "Platform Admin": "مسؤول المنصة",
    "Org Admin": "مسؤول المنشأة",
    "Clinician": "طبيب سريري",
    "Nurse": "ممرض / ممرضة",
    "Care Coordinator": "منسق الرعاية",
    "Supervisor": "مشرف",
    "Authority User": "مستخدم الهيئة الصحية",
    "Patient": "مشارك / مريض",
    "Rehab Center": "مركز تأهيل",
    "Hospital": "مستشفى",
    "Clinic": "عيادة",
    "Employer": "جهة عمل",
    "Public Health": "الصحة العامة",
    "Primary Care": "الرعاية الأولية",
    # Agents
    "agent 1": "الوكيل ١",
    "agent 2": "الوكيل ٢",
    "agent 3": "الوكيل ٣",
    "agent 4": "الوكيل ٤",
    "agent 5": "الوكيل ٥",
    "agent 6": "الوكيل ٦",
    "intake_triage": "فرز الاستقبال",
    "consent_gate": "بوابة الموافقة",
    "safety_gate": "بوابة السلامة والطوارئ",
    "baseline_drift": "تحليل خط الأساس والانحراف",
    "deterministic_z_score": "حساب معامل Z الحتمي",
    "llm_synthesis": "التلخيص السريري بالذكاء الاصطناعي",
    "care_navigation": "توجيه الرعاية والإحالات",
    # Notifications & System Emails
    "Your Recova care plan was updated": "تم تحديث خطة رعايتك في ريكوفا",
    "Your care plan was updated": "تم تحديث خطة رعايتك",
    "Your Recova portal is ready": "بوابة ريكوفا الخاصة بك جاهزة",
    "Your Recova patient portal invitation": "دعوة بوابة المريض في ريكوفا",
    "You have been added to a Recova facility": "تمت إضافتك إلى منشأة في ريكوفا",
    "Your Recova password was changed": "تم تغيير كلمة مرور ريكوفا الخاصة بك",
    "Your Recova password was updated": "تم تحديث كلمة مرور ريكوفا الخاصة بك",
    "Your account password was updated. If this was not you, contact your facility immediately.": "تم تحديث كلمة مرور حسابك. إذا لم تكن أنت، تواصل مع منشأتك فورًا.",
    "Your password was changed while signed in. Contact your facility if this was not you.": "تم تغيير كلمة مرورك أثناء تسجيل الدخول. تواصل مع منشأتك إذا لم تقم بذلك.",
    "Urgent Health Alert": "تنبيه صحي عاجل",
    "Extreme Heat Advisory — Outdoor Shift Precautions": "تحذير الحرارة الشديدة — احتياطات المناوبة الخارجية",
    "Hydrate every 20 minutes and report dizziness immediately.": "اشرب الماء كل 20 دقيقة وأبلغ عن الدوار فورًا.",
    "Patient missed scheduled appointment; triggering navigator outreach...": "تغيّب المريض عن الموعد المحدد؛ جارٍ تفعيل تواصل منسق الرعاية...",
    # Seeded System Test-Case Fixtures (37 accounts / 4 programmes / 5 scenarios)
    "Judge Demo: Recova Recovery Centre": "عرض التحكيم: مركز ريكوفا للتعافي",
    "Judge Demo: Recova Loop Clinic": "عرض التحكيم: عيادة ريكوفا لوب",
    "Judge Demo: Recova Neuro Studio": "عرض التحكيم: استوديو ريكوفا للأعصاب",
    "Judge Demo: Recova WorkSafe Site": "عرض التحكيم: موقع ريكوفا لسلامة العمل",
    "Legacy Multi-Track Clinic": "عيادة المسارات المتعددة السابقة",
    "Judge Demo Solar Site": "موقع الطاقة الشمسية التجريبي",
    "Al Dhafra": "الظفرة",
    "Field Operations": "العمليات الميدانية",
    "Thiqa Comprehensive": "ثقة الشامل",
    "Abu Dhabi Core Referral Center": "مركز أبوظبي لإحالات التعافي",
    "Abu Dhabi Loop Referral Center": "مركز أبوظبي لإحالات لوب",
    "Abu Dhabi Neuro Referral Center": "مركز أبوظبي لإحالات الأعصاب",
    "Abu Dhabi WorkSafe Referral Center": "مركز أبوظبي لإحالات سلامة العمل",
    "Judge demo approved follow-up referral.": "إحالة متابعة معتمدة (بيانات اختبارية).",
    "Expanding rehabilitation center to include IFHAS metabolic screening.": "توسيع مركز التأهيل ليشمل فحص IFHAS الأيضي.",
    "Severe chest pain and feeling dizzy": "ألم شديد في الصدر مع شعور بالدوار",
    "stable": "مستقر",
    "gradual_decline": "تراجع تدريجي",
    "missing_data": "بيانات ناقصة",
    "emergency": "طوارئ",
    "absent_consent": "دون موافقة",
    "screening_coordinator": "منسق الفحوصات",
    "care_coordinator": "منسق الرعاية",
    "psychiatrist": "طبيب نفسي",
    "occ_health_director": "مدير الصحة المهنية",
    "org_admin": "مسؤول المنشأة",
    "clinician": "طبيب سريري",
    "supervisor": "مشرف",
    "authority_user": "مستخدم الهيئة الصحية",
    "patient": "مريض / مشارك",
    "CORE": "كور",
    "LOOP": "لوب",
    "NEURO": "نيورو",
    "WORKSAFE": "وورك سيف",
}

_LOWER_CATALOG_AR: dict[str, str] = {k.lower(): v for k, v in BACKEND_CATALOG_AR.items()}

_NON_TRANSLATABLE_RE = re.compile(
    r"^(?:"
    r"[\d\s.,:%+\-–—/()\[\]°C]+|"
    r"MRN[- ]?[A-Za-z0-9-]+|"
    r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}|"
    r"https?://\S+|"
    r"[a-fA-F0-9]{16,}|"
    r"sk-\S+|"
    r"[\u0600-\u06FF\s\d.,!?()-]+"
    r")$"
)

_DURATION_PART_RE = re.compile(r"(\d+)([dhm])")

_TRANSLATION_CACHE: OrderedDict[str, str] = OrderedDict()
_MAX_CACHE_ENTRIES = 2000


class TranslateBatchRequest(BaseModel):
    target_lang: Literal["ar"] = "ar"
    texts: list[str] = Field(default_factory=list, max_length=50)


class TranslateBatchResponse(BaseModel):
    target_lang: Literal["ar"]
    translations: dict[str, str]
    llm_assisted: bool = False


def _format_duration_ar(text: str) -> str:
    def _sub(match: re.Match[str]) -> str:
        num, unit = match.group(1), match.group(2)
        unit_ar = {"d": "ي", "h": "س", "m": "د"}.get(unit, unit)
        return f"{num}{unit_ar}"

    return _DURATION_PART_RE.sub(_sub, text)


def _translate_deterministic_ar(raw: str) -> str | None:
    norm = " ".join(raw.split())
    if not norm or _NON_TRANSLATABLE_RE.match(norm):
        return None
    if norm in BACKEND_CATALOG_AR:
        return BACKEND_CATALOG_AR[norm]
    if norm.lower() in _LOWER_CATALOG_AR:
        return _LOWER_CATALOG_AR[norm.lower()]
    if norm in _TRANSLATION_CACHE:
        _TRANSLATION_CACHE.move_to_end(norm)
        return _TRANSLATION_CACHE[norm]

    m_overdue = re.match(r"^Overdue by (.+)$", norm)
    if m_overdue:
        return f"متأخر بمقدار {_format_duration_ar(m_overdue.group(1))}"

    m_rem = re.match(r"^(.+) remaining$", norm)
    if m_rem:
        return f"متبقي {_format_duration_ar(m_rem.group(1))}"

    m_risk = re.match(r"^Risk Tier:\s*(.+)$", norm, re.I)
    if m_risk:
        tier = _translate_deterministic_ar(m_risk.group(1)) or m_risk.group(1)
        return f"مستوى الخطر: {tier}"

    m_consent = re.match(r"^Consent granted:\s*(.+)$", norm, re.I)
    if m_consent:
        scope = _translate_deterministic_ar(m_consent.group(1)) or m_consent.group(1)
        return f"تم منح الموافقة: {scope}"

    m_stage = re.match(r"^Stage\s+(\d+)\s*[:·-]\s*(.+)$", norm, re.I)
    if m_stage:
        rest = _translate_deterministic_ar(m_stage.group(2)) or m_stage.group(2)
        return f"المرحلة {m_stage.group(1)} · {rest}"

    m_active = re.match(r"^(\d+)\s+active$", norm, re.I)
    if m_active:
        return f"{m_active.group(1)} نشط"

    return None


async def _llm_translate_batch(texts: list[str]) -> dict[str, str]:
    s = get_settings()
    env_cfg = s.resolve_llm_env(None)
    provider = env_cfg.get("provider") or "none"
    api_key = env_cfg.get("api_key") or ""
    if provider == "none" or not api_key or not texts:
        return {}

    prompt = (
        "Translate each English healthcare UI or operational notification string into clear, accurate Modern Standard Arabic. "
        "NEVER alter or translate patient IDs, MRNs (e.g. MRN-10042), codes (PHQ-9, HbA1c, HRV, WBGT, LOINC, FHIR R4, Recova), "
        "emails, URLs, numeric values, Z-scores, or units. "
        "Return ONLY a JSON object mapping each exact English input string to its Arabic translation.\n"
        f"Inputs: {json.dumps(texts, ensure_ascii=False)}"
    )

    try:
        async with httpx.AsyncClient(timeout=min(s.llm_timeout_seconds, 12.0)) as client:
            raw_content = ""
            if provider == "openai":
                base = (env_cfg.get("base_url") or "https://api.openai.com/v1").rstrip("/")
                resp = await client.post(
                    f"{base}/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={
                        "model": env_cfg.get("model") or "gpt-4o-mini",
                        "temperature": 0.1,
                        "response_format": {"type": "json_object"},
                        "messages": [{"role": "user", "content": prompt}],
                    },
                )
                resp.raise_for_status()
                raw_content = resp.json()["choices"][0]["message"]["content"]
            elif provider == "azure_openai":
                base = env_cfg.get("base_url", "").rstrip("/")
                dep = env_cfg.get("azure_deployment", "")
                ver = env_cfg.get("azure_api_version") or s.llm_azure_api_version
                if not base or not dep:
                    return {}
                resp = await client.post(
                    f"{base}/openai/deployments/{dep}/chat/completions",
                    params={"api-version": ver},
                    headers={"api-key": api_key},
                    json={
                        "temperature": 0.1,
                        "response_format": {"type": "json_object"},
                        "messages": [{"role": "user", "content": prompt}],
                    },
                )
                resp.raise_for_status()
                raw_content = resp.json()["choices"][0]["message"]["content"]
            elif provider == "gemini":
                model = env_cfg.get("model") or "gemini-2.0-flash"
                resp = await client.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                    params={"key": api_key},
                    json={
                        "contents": [{"parts": [{"text": prompt}]}],
                        "generationConfig": {"responseMimeType": "application/json", "temperature": 0.1},
                    },
                )
                resp.raise_for_status()
                raw_content = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
            elif provider == "anthropic":
                resp = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": api_key,
                        "anthropic-version": "2023-06-01",
                    },
                    json={
                        "model": env_cfg.get("model") or "claude-3-5-haiku-latest",
                        "max_tokens": 2048,
                        "temperature": 0.1,
                        "messages": [{"role": "user", "content": prompt}],
                    },
                )
                resp.raise_for_status()
                raw_content = resp.json()["content"][0]["text"]

            parsed = json.loads(raw_content)
            if isinstance(parsed, dict):
                return {
                    str(k): str(v)
                    for k, v in parsed.items()
                    if isinstance(k, str) and isinstance(v, str) and v.strip()
                }
    except Exception:
        return {}
    return {}


@router.get("/catalog")
def get_i18n_catalog(lang: str = "ar"):
    """Return pre-warmed backend UI, enum, status, agent, and notice translations."""
    if lang != "ar":
        return {"lang": lang, "version": "2.0", "catalog": {}}
    return {
        "lang": "ar",
        "version": "2.0",
        "catalog": BACKEND_CATALOG_AR,
    }


@router.post("/translate", response_model=TranslateBatchResponse)
async def translate_batch(req: TranslateBatchRequest):
    """Translate dynamic incoming backend/UI strings deterministically and (when configured) via LLM."""
    translations: dict[str, str] = {}
    unseen: list[str] = []

    for raw in req.texts:
        norm = " ".join(raw.split())
        if not norm or len(norm) > 500 or _NON_TRANSLATABLE_RE.match(norm):
            continue
        direct = _translate_deterministic_ar(norm)
        if direct:
            translations[norm] = direct
        elif norm not in unseen:
            unseen.append(norm)

    llm_assisted = False
    if unseen and get_settings().llm_configured:
        llm_results = await _llm_translate_batch(unseen[:25])
        if llm_results:
            llm_assisted = True
            for src, dst in llm_results.items():
                norm_src = " ".join(src.split())
                translations[norm_src] = dst
                _TRANSLATION_CACHE[norm_src] = dst
                _TRANSLATION_CACHE.move_to_end(norm_src)
                if len(_TRANSLATION_CACHE) > _MAX_CACHE_ENTRIES:
                    _TRANSLATION_CACHE.popitem(last=False)

    return TranslateBatchResponse(
        target_lang=req.target_lang,
        translations=translations,
        llm_assisted=llm_assisted,
    )
