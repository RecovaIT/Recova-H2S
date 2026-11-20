"""Gate 2: Emergency Red-Flag Bypass Agent.

Deterministic acute safety screening. The LLM can NEVER override or suppress
this gate. When any critical red flag is detected, routine scoring/LLM steps
are bypassed and an EmergencyEvent + STAT triage referral are created immediately.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.schemas import Gate2Evidence, Gate2Input, Gate2Output
from app.models.clinical import CheckIn, Observation, Patient, ScreeningRecord
from app.models.engine import EmergencyEvent

EMERGENCY_RULES_VERSION = "1.1.0"

_TEXT_RULES: list[tuple[str, str, re.Pattern[str]]] = [
    (
        "CRISIS_SUICIDAL_IDEATION",
        "Suicidal ideation or self-harm indicator in check-in text",
        re.compile(
            r"(suicid|kill myself|end my life|want to die|self[- ]?harm|overdos|don'?t want to live|"
            r"انتحار|أقتل نفسي|إنهاء حياتي|أريد أن أموت|إيذاء النفس)",
            re.IGNORECASE,
        ),
    ),
    (
        "CRISIS_SEVERE_WITHDRAWAL",
        "Severe acute withdrawal / delirium / seizure indicator",
        re.compile(
            r"(severe withdrawal|seizure|hallucinat|delirium tremens|can'?t stop shaking|convulsion|"
            r"انسحاب حاد|نوبة صرع|هلوسة|هذيان|تشنجات)",
            re.IGNORECASE,
        ),
    ),
    (
        "CRISIS_ACUTE_CARDIAC",
        "Acute cardiac / chest pain / syncope indicator",
        re.compile(
            r"(chest pain|crushing chest|heart attack|passed out|syncope|can'?t breathe|severe shortness of breath|"
            r"ألم في الصدر|ألم صدري|ضيق تنفس حاد|إغماء|نوبة قلبية)",
            re.IGNORECASE,
        ),
    ),
    (
        "CRISIS_HEATSTROKE",
        "Suspected acute exertional heatstroke indicator",
        re.compile(
            r"(heatstroke|heat stroke|collapsed in heat|stopped sweating.*confused|disoriented.*heat|"
            r"ضربة شمس|إغماء حراري|انهيار حراري)",
            re.IGNORECASE,
        ),
    ),
]

_SYMPTOM_CODES = {
    "suicidal_ideation": ("CRISIS_SUICIDAL_IDEATION", "Structured suicidal ideation symptom flagged"),
    "self_harm": ("CRISIS_SUICIDAL_IDEATION", "Structured self-harm symptom flagged"),
    "seizure": ("CRISIS_SEVERE_WITHDRAWAL", "Structured seizure symptom flagged"),
    "delirium": ("CRISIS_SEVERE_WITHDRAWAL", "Structured delirium/hallucination symptom flagged"),
    "severe_withdrawal": ("CRISIS_SEVERE_WITHDRAWAL", "Structured severe withdrawal symptom flagged"),
    "chest_pain": ("CRISIS_ACUTE_CARDIAC", "Structured chest pain symptom flagged"),
    "syncope": ("CRISIS_ACUTE_CARDIAC", "Structured syncope/collapse symptom flagged"),
    "heatstroke_confusion": ("CRISIS_HEATSTROKE", "Structured heatstroke neuro-confusion symptom flagged"),
}


def has_emergency_text(value: str) -> bool:
    return any(pattern.search(value) for _, _, pattern in _TEXT_RULES)


def run_gate2(
    db: Session,
    patient: Patient,
    track: str,
    as_of: datetime,
    *,
    run_id=None,
    create_event: bool = True,
) -> tuple[Gate2Input, Gate2Output]:
    obs_cutoff = as_of - timedelta(hours=24)
    checkin_cutoff = as_of - timedelta(hours=48)

    recent_obs = db.scalars(
        select(Observation)
        .where(
            Observation.organization_id == patient.organization_id,
            Observation.patient_id == patient.id,
            Observation.effective_at <= as_of,
            Observation.effective_at >= obs_cutoff,
            Observation.status != "entered_in_error",
        )
        .order_by(Observation.effective_at.desc())
    ).all()

    recent_checkins = db.scalars(
        select(CheckIn)
        .where(
            CheckIn.organization_id == patient.organization_id,
            CheckIn.patient_id == patient.id,
            CheckIn.effective_at <= as_of,
            CheckIn.effective_at >= checkin_cutoff,
        )
        .order_by(CheckIn.effective_at.desc())
    ).all()

    recent_screenings = db.scalars(
        select(ScreeningRecord)
        .where(
            ScreeningRecord.organization_id == patient.organization_id,
            ScreeningRecord.patient_id == patient.id,
            ScreeningRecord.screened_at <= as_of,
            ScreeningRecord.screened_at >= checkin_cutoff,
        )
        .order_by(ScreeningRecord.screened_at.desc())
    ).all()

    inp = Gate2Input(
        patient_id=patient.id,
        track=track,
        as_of=as_of,
        recent_observations_count=len(recent_obs),
        recent_checkins_count=len(recent_checkins),
    )

    evidence: list[Gate2Evidence] = []
    rule_codes: list[str] = []

    def add_ev(code: str, source: str, summary: str, value=None, observed_at=None) -> None:
        if code not in rule_codes:
            rule_codes.append(code)
        evidence.append(
            Gate2Evidence(
                rule_code=code,
                severity="critical",
                source=source,
                summary=summary,
                value=value,
                observed_at=observed_at,
            )
        )

    # 1. Check-in emergency checks
    for chk in recent_checkins:
        if chk.self_reported_crisis:
            add_ev(
                "CRISIS_SELF_REPORTED",
                f"check_in:{chk.id}",
                "Participant flagged acute crisis on check-in",
                value=True,
                observed_at=chk.effective_at,
            )
        for sym in chk.symptoms or []:
            sym_low = str(sym).strip().lower()
            if sym_low in _SYMPTOM_CODES:
                code, msg = _SYMPTOM_CODES[sym_low]
                add_ev(code, f"check_in:{chk.id}", msg, value=sym_low, observed_at=chk.effective_at)
        if chk.text:
            for code, msg, pat in _TEXT_RULES:
                m = pat.search(chk.text)
                if m:
                    add_ev(code, f"check_in:{chk.id}", f"{msg} (matched phrase)", value=m.group(0), observed_at=chk.effective_at)

    # 2. Acute vital sign / biomarker emergency thresholds
    for o in recent_obs:
        if o.value_num is None:
            continue
        v = o.value_num
        if o.metric_code == "core_temp_est_c" and v >= 40.0:
            add_ev("CRISIS_HEATSTROKE_TEMP", f"observation:{o.id}", f"Estimated core temperature critical ({v:.1f} C >= 40.0 C)", value=v, observed_at=o.effective_at)
        elif o.metric_code == "resting_hr" and (v >= 150.0 or v <= 35.0):
            add_ev("CRISIS_CRITICAL_HEART_RATE", f"observation:{o.id}", f"Critical resting heart rate ({v:.0f} bpm)", value=v, observed_at=o.effective_at)
        elif o.metric_code == "bp_systolic" and v >= 180.0:
            add_ev("CRISIS_HYPERTENSIVE_URGENCY", f"observation:{o.id}", f"Hypertensive crisis threshold (SBP {v:.0f} mmHg >= 180)", value=v, observed_at=o.effective_at)
        elif o.metric_code == "bp_diastolic" and v >= 120.0:
            add_ev("CRISIS_HYPERTENSIVE_URGENCY", f"observation:{o.id}", f"Hypertensive crisis threshold (DBP {v:.0f} mmHg >= 120)", value=v, observed_at=o.effective_at)
        elif o.metric_code == "phq9_score" and v >= 24.0:
            add_ev("CRISIS_SEVERE_DEPRESSION", f"observation:{o.id}", f"Critical PHQ-9 score ({v:.0f} >= 24)", value=v, observed_at=o.effective_at)

    # 3. PHQ-9 item 9 (thoughts of self-harm / suicide) >= 2 (more than half the days / nearly every day)
    for scr in recent_screenings:
        items = scr.phq9_item_responses or []
        if len(items) >= 9 and int(items[8]) >= 2:
            add_ev(
                "CRISIS_PHQ9_ITEM9",
                f"screening:{scr.id}",
                f"PHQ-9 Item 9 suicidal/self-harm thoughts elevated (score={items[8]}/3)",
                value=items[8],
                observed_at=scr.screened_at,
            )

    triggered = len(evidence) > 0
    event_id = None
    if triggered and create_event:
        ev = EmergencyEvent(
            organization_id=patient.organization_id,
            patient_id=patient.id,
            run_id=run_id,
            track=track,
            status="open",
            rule_codes=rule_codes,
            evidence=[e.model_dump(mode="json") for e in evidence],
            rules_version=EMERGENCY_RULES_VERSION,
        )
        db.add(ev)
        db.flush()
        event_id = ev.id

    out = Gate2Output(
        rules_version=EMERGENCY_RULES_VERSION,
        emergency_triggered=triggered,
        rule_codes=rule_codes,
        evidence=evidence,
        emergency_event_id=event_id,
    )
    return inp, out
