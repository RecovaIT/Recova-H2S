# Recova-H2S Platform Engineering Rules & Standards

This document establishes the official engineering guidelines, architectural invariants, and clinical governance rules for the **Recova Anticipatory Health Platform** (Future Health Challenge 2026).

---

## 1. Zero Mock & Zero Static Data Standard

### Principle
In clinical and healthcare software, simulated or fabricated data presented to a user as real data is a critical safety hazard. Every interface in Recova must communicate directly with live backend endpoints and persist to the primary database.

### Mandatory Rules
1. **No Static Fallback Arrays:**  
   UI components must never contain hardcoded arrays of fake patients, dummy referrals, mock biomarker points, or placeholder statistics.
2. **Explicit Empty State Handling:**  
   When an API returns an empty set (`items: []` or `count: 0`), components must render an `<EmptyState />` flow with an explanation of what data is expected and an action button allowing the clinician or participant to initiate the real data flow.
3. **End-to-End Persistence:**  
   Every user form (check-ins, cognitive games, environmental assessments, referral status changes, clinical reviews) must call a backend endpoint that performs transactional validation and saves to PostgreSQL 16.
4. **Authentic Authentication:**  
   No hardcoded test passwords or bypasses in login forms. Real sessions are validated through HTTP-only session cookies and CSRF tokens.

---

## 2. DECIDE-AI Clinical Governance Standard

### Principle
Clinical decisions must be transparent, verifiable, and explainable under international DECIDE-AI guidelines. Deterministic mathematical computations must never be conflated with stochastic large language model outputs.

### Mandatory Rules
1. **Visible Separation of Math and AI:**  
   * **Box 1:** Agent 4 Deterministic Signal Matrix displaying baseline mean ($\mu$), sample standard deviation ($\sigma$), standard error ($\text{SE}$), longitudinal Z-scores, and alert corridor boundaries.
   * **Box 2:** Agent 5 Generative Clinical Synthesis draft summarizing clinical context.
2. **Honest Provider Fallback:**  
   When no LLM API key is configured or when synthesis is offline, the interface must explicitly declare `"AI Clinical Synthesis Provider Not Configured... Recova never fabricates synthetic AI text"`. Fabricating fake AI advice is strictly prohibited.
3. **Cryptographic Non-Repudiation:**  
   All clinical sign-offs (`approve_referral`, `modify_plan`, `request_lab`) must capture the clinician's medical license number, institutional role, UTC timestamp, and a computed SHA-256 signature hash stored immutably in `clinical_reviews` and `audit_events`.

---

## 3. Clinical Safety & Emergency Gate 2 Bypass

### Principle
Life safety supersedes routine administrative or clinical review queues.

### Mandatory Rules
1. **Sub-Second Escalation:**  
   Any patient input containing emergency crisis keywords (suicidal ideation, self-harm, severe substance withdrawal, acute chest pain) or acute vitals (core temperature $> 38.5^\circ\text{C}$ or dizziness under heat stress) must trigger the deterministic **Gate 2 Emergency Bypass**.
2. **Immediate Red Alert Banners:**  
   Emergency events immediately generate high-visibility alerts on clinician dashboards, bypassing routine non-urgent triage queues.

---

## 4. UAE Data Sovereignty & Field-Level Encryption

### Principle
Compliance with UAE Federal Health Data Law, DoH Abu Dhabi (Malaffi), and MoHAP regulations.

### Mandatory Rules
1. **Field-Level Encryption at Rest:**  
   Patient PII (Emirates ID, MRN, phone, email, emergency contacts) must be encrypted using application-layer Fernet (AES-128-CBC) before being written to PostgreSQL.
2. **Zero Plaintext Logging:**  
   Decrypted PII must never be exposed in terminal stdout/stderr, application server logs, or unauthenticated HTTP responses.
3. **Workforce Privacy ($k$-Anonymity):**  
   Supervisor workforce health views must aggregate department data and suppress reporting for departments with fewer than $k$ workers ($k \ge 5$) to prevent worker re-identification.

---

## 5. Bilingual & RTL Directional Integrity

### Principle
Healthcare software deployed in the UAE must provide native, respectful, and typographically correct Arabic support.

### Mandatory Rules
1. **Native RTL Wrapping:**  
   Arabic text must always be contained within elements specifying `dir="rtl"` with appropriate font styling and right alignment (`text-right font-sans`).
2. **Zero Inline JSX Splitting:**  
   Arabic sentences must never be chopped into fragments with embedded JSX expressions that invert punctuation or word sequence.

---

## 6. Multi-Tenancy & Access Control

### Principle
Tenant isolation is strictly maintained across all healthcare organizations.

### Mandatory Rules
1. **Tenant-Scoped Operations:**  
   Every query and mutation must enforce scoping to the authenticated user's `organization_id`.
2. **Role Verification:**  
   Fine-grained permissions must be validated on both frontend navigation guards and backend FastAPI route dependencies.
