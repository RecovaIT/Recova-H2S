# Shared Six-Agent Workflow & Deterministic Scoring Engine

Recova executes one unified gated six-agent pipeline (`backend/app/agents/orchestrator.py`) for every track (`core`, `loop`, `neuro`, `worksafe`). Each stage has explicit Pydantic I/O schemas (`app/agents/schemas.py`), execution timing, error handling, and persistent `AgentStepResult` audit records.

```text
  Incoming Signals (Wearables / Check-ins / IFHAS Labs / Cognitive Trials / WorkSafe)
       │
       ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ Gate 1: Consent, Governance & Guardrail Agent (`gate1_consent.py`)      │
│  • Checks active `data_processing` consent & active patient flag        │
│  • Validates track data streams & surfaces LOINC/unit quality flags      │
│  • Missing optional streams: continues + penalizes confidence index     │
│  • Missing mandatory consent: blocks routine pipeline (`blocked`);      │
│    Gate 2 still screens vital-interest emergencies if enabled           │
└──────────────────────────┬──────────────────────┬───────────────────────┘
                           │ Consent Valid        │ Revoked / Missing
                           ▼                      ▼
                  Pipeline Continues      Run stops (`blocked`), Gate 2 check-in
                                          audit preserved
       │
       ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ Gate 2: Emergency Red-Flag Bypass Agent (`gate2_emergency.py`)          │
│  • Deterministic rules (`EMERGENCY_RULES_VERSION = "1.1.0"`):          │
│    - Suicidal ideation / self-harm (EN + AR patterns, PHQ-9 Item 9)     │
│    - Severe withdrawal / seizures / delirium                            │
│    - Acute cardiac / chest pain / syncope / critical vital cutoffs      │
│    - Suspected heatstroke (core temp >= 40.0 C, confusion/heat patterns)│
│  • LLM CANNOT override or suppress this gate.                           │
└──────────────────────────┬──────────────────────┬───────────────────────┘
                           │ No Red Flags         │ Emergency Triggered
                           ▼                      ▼
┌──────────────────────────────────────┐   ┌──────────────────────────────┐
│ Agent 3: Longitudinal Signal         │   │ EMERGENCY BYPASS             │
│          & Context Aggregator        │   │ • Stops Agents 3–5           │
│ • Collects baseline & current windows│   │ • Sets `EMERGENCY_BYPASS`    │
│ • Normalizes units & confounders     │   │ • Creates `EmergencyEvent`   │
└──────────────────────────┬───────────┘   │ • Creates STAT triage ref    │
                           ▼               │ • Dispatches real alerts     │
┌──────────────────────────────────────┐   └──────────────────────────────┘
│ Agent 4: Deterministic Baseline &    │
│          Drift Scoring Engine        │
│ (`ALGORITHM_VERSION = "1.2.0"`)      │
│ • Personal baseline (3–5 windows)    │
│ • Zero-variance SD floor guard       │
│ • Confounder SE expansion (<= 1.75x) │
│ • Practice effect (Neuro <= 12%)     │
│ • Z-score & Risk Tier (`GREEN` /     │
│   `AMBER` / `RED` / `INDETERMINATE`) │
└──────────────────────────┬───────────┘
                           ▼
┌──────────────────────────────────────┐
│ Agent 5: Clinical Synthesis Agent    │
│ • Checks `llm_synthesis` consent     │
│ • Sends ONLY de-identified metrics   │
│ • Validated `SynthesisDraftSchema`   │
│ • Honest `provider_not_configured`   │
│   if no LLM credentials set          │
└──────────────────────────┬───────────┘
                           ▼
┌──────────────────────────────────────┐
│ Agent 6: Closed-Loop Care &          │
│          Referral Orchestrator       │
│ • Maps Track + Tier -> Pathway & SLA │
│ • Checks patient `InsurancePlan`     │
│ • Matches `CareFacility` network     │
│ • Never auto-verifies clinical close │
└──────────────────────────────────────┘
```

## 1. Agent 4 Mathematical Specification (`app/engine/scoring.py`)

Agent 4 runs purely in Python (`ALGORITHM_VERSION = "1.2.0"`). Every input, intermediate variance, confounder multiplier, and algorithm version is persisted in `scoring_results`.

### Personal Baseline Establishment
- Uses the patient's initial **$n \in [3, 5]$ stable observation windows** per metric (or previously persisted `PersonalBaseline`).
- If fewer than 3 baseline windows exist (`n < 3`), Agent 4 **never fabricates $Z = 0$**:
  - `baseline_status` is set to `"insufficient"`.
  - Metrics without reference cutoffs return `INDETERMINATE`.
  - Single-visit screening/OSH metrics with `use_reference_fallback=True` (such as Loop `hba1c`, `bp_systolic`, `phq9_score` or WorkSafe `core_temp_est_c`, `heat_index_c`) report explicit clinical reference alerts (`GREEN` / `AMBER` / `RED`) alongside `baseline_status="insufficient"`.

### Mean, Sample Standard Deviation & Zero-Variance Guard
Given baseline window values $x_1, \dots, x_n$:
$$\bar{x} = \frac{1}{n}\sum_{i=1}^n x_i, \qquad s_{\text{raw}} = \sqrt{\frac{\sum_{i=1}^n (x_i - \bar{x})^2}{\max(n - 1, 1)}}$$
$$s_{\text{used}} = \max(s_{\text{raw}}, \sigma_{\text{floor}})$$
$$\text{SE}_{\text{raw}} = \frac{s_{\text{used}}}{\sqrt{n}}$$

Each metric in `METRIC_CATALOG` defines a documented `default_sd_floor` ($\sigma_{\text{floor}}$, e.g., `0.25h` for `sleep_hours`, `3.0ms` for `hrv_rmssd`, `2.0bpm` for `resting_hr`, `25.0ms` for `cog_reaction_time_ms`) to prevent division by zero or brittle spikes on identical readings.

### Confounder SE Expansion (Capped at $1.75\times$)
Depending on track and participant profile:
- **Neuro (`cog_*` metrics):**
  - `hearing_status`: `mild_loss` ($\times 1.25$), `moderate_loss`/`severe_loss` ($\times 1.35$) on auditory/sequence/recall metrics.
  - `vision_status`: `mild_impairment` ($\times 1.25$), `severe_impairment` ($\times 1.35$) on visual/sequence/rule-switch/reaction-time metrics.
  - `primary_language_matches_assessment == False`: $\times 1.15$ on recall/rule-switching.
  - `education_level` in `{"none", "primary"}`: $\times 1.10$.
  - `poor_sleep_confounder`: $\times 1.15$.
- **Core (`sleep_hours`, `hrv_rmssd`):** `shift_work`: $\times 1.15$.
- The combined multiplier is capped at `1.75` (`SE_adjusted = SE_raw * mult`) so confounders attenuate moderate noise without masking severe collapse.

### Practice Effect Adjustment (Neuro)
For cognitive metrics with `apply_practice_effect=True` and `session_index > 1`:
$$p = \min\left(0.04 \cdot \ln(\text{session\_index}),\, 0.12\right)$$
Expectations adjust upward (+$p \cdot \bar{x}$) for accuracy metrics and downward (-$p \cdot \bar{x}$) for reaction latency (`cog_reaction_time_ms`), creating `practice_gain_offset`.

### Longitudinal Drift $Z$-Score & Risk Classification
$$Z = \frac{X_{\text{current}} - (\bar{x} + \text{practice\_gain\_offset})}{\max(\text{SE}_{\text{adjusted}},\, 10^{-9})}$$

Directionality guard prevents clinically favorable improvement (e.g., longer sleep when `lower_is_worse`) from raising an alarm:
- If `drift_direction == "improving"`: classifies as `GREEN` (unless an adverse clinical reference threshold is crossed).
- Otherwise classifies $|Z|$:
  - **GREEN:** $|Z| < 1.0$
  - **AMBER:** $1.0 \le |Z| < 1.96$
  - **RED:** $|Z| \ge 1.96$

Missing expected track streams reduce `confidence_index` (starting from 100%, subtracting track `stream_missing_penalty` per absent stream) while allowing graceful degradation on partial telemetry.

## 2. Routing Rules in Agent 6 (`app/agents/agent6_referral.py`)

| Track | Risk Tier | Pathway | Priority | Default SLA |
| --- | --- | --- | --- | --- |
| `core` | `RED` | `async_teleconsult` | `urgent` | 24 hours |
| `core` | `AMBER` | `outpatient_therapist` | `routine` | 72 hours |
| `loop` | `RED` | `specialist` | `urgent` | 48 hours |
| `loop` | `AMBER` | `primary_care` | `routine` | 168 hours |
| `neuro` | `RED` | `specialist` | `urgent` | 72 hours |
| `neuro` | `AMBER` | `primary_care` | `routine` | 336 hours |
| `worksafe` | `RED` | `occupational_health` | `urgent` | 4 hours |
| `worksafe` | `AMBER` | `occupational_health` | `routine` | 24 hours |
| *any* | `EMERGENCY_BYPASS` | `emergency_triage` | `stat` | Acute escalation |
