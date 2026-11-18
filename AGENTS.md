# Recova Platform Engineering Rules & Standards (AGENTS.md)

> **MANDATORY POLICY FOR ALL AGENTS AND DEVELOPERS**  
> These rules govern the entire Recova-H2S codebase. They must be followed strictly on every file edit, component creation, endpoint implementation, and architectural decision.

---

## 1. Zero Mock & Zero Static Data Policy (Strict End-to-End)

* **No Hardcoded Arrays or Fallback Objects:**  
  Components, tables, dropdowns, cards, and charts must **NEVER** use mock fallback datasets, hardcoded dummy arrays, or simulated sample objects.
* **100% End-to-End Live Connectivity:**  
  Every piece of data displayed in the UI must originate from the live FastAPI backend (`/api/v1/*`), backed by PostgreSQL 16. Every user action (check-in, cognitive trial, readiness rating, referral approval, organization creation) must persist to the database.
* **Honest Empty States over Fake Data:**  
  When an endpoint returns no records (`items.length === 0`), components must render an explicit, clear `<EmptyState />` or loading skeleton with actionable instructions on how to generate real data. Never fall back to fake "demo" records.
* **No Hardcoded Demo Credentials:**  
  Forms must never pre-fill fake test credentials or hide real authentication requirements.

---

## 2. DECIDE-AI Governance & Deterministic/AI Separation

* **Strict Visual & Architectural Separation:**  
  Deterministic mathematical computations (Agent 4) must be displayed in a completely separate visual box from generative LLM synthesis (Agent 5).
  * **Box 1 (Agent 4):** Deterministic Signal Matrix (baseline $\mu$, standard deviation $\sigma$, standard error $\text{SE}$, longitudinal Z-scores, NOAA heat index equations, practice-effect regressions).
  * **Box 2 (Agent 5):** AI Clinical Synthesis draft with bilingual English/Arabic toggles.
* **Zero AI Fabrication (Honest Provider Status):**  
  If the LLM provider is not configured (`LLM_PROVIDER=none` or empty API key), the system must display an honest notice:  
  `"AI Clinical Synthesis Provider Not Configured... Recova never fabricates synthetic AI text"`.  
  Never simulate fake generative clinical summaries.

---

## 3. Clinical Safety & Emergency Gate 2 Bypass

* **Immediate Deterministic Escalation:**  
  Safety-critical inputs (crisis phrases, self-harm signals, severe acute withdrawal, heat illness with core temperature $> 38.5^\circ\text{C}$ or dizziness) must trigger the deterministic **Gate 2 Emergency Bypass**.
* **Zero Latency & Unskippable Alerting:**  
  Emergency events bypass routine asynchronous review queues and immediately surface red emergency alert banners to attending clinicians.

---

## 4. Cryptographic Non-Repudiation & Audit Trail

* **Immutable Decision Signing:**  
  Every clinical governance action (Approve Referral, Modify Plan, Request Lab or Toxicology Screen) must record:
  1. Reviewer's Medical License Number
  2. Institutional Clinical Role
  3. ISO 8601 UTC Timestamp
  4. SHA-256 Cryptographic Signature Hash computed over the decision payload
* **Audit Event Persistence:**  
  All governance events, role switches, and patient data accesses must generate an immutable record in the `audit_events` table.

---

## 5. UAE Data Sovereignty, Privacy & Field-Level Encryption

* **Regulatory Compliance:**  
  Compliant with UAE Federal Health Data Law, DoH Abu Dhabi, and MoHAP regulations.
* **Application-Layer Fernet Encryption at Rest:**  
  All Personally Identifiable Information (PII) including Emirates National ID, Medical Record Number (MRN), phone number, email, and emergency contact details must be encrypted using Fernet (AES-128-CBC) before being written to PostgreSQL.
* **Zero Plaintext Logging:**  
  Decrypted patient PII must never be written to terminal outputs, system logs, or unauthenticated API endpoints.
* **$k$-Anonymity in Workforce Health (WorkSafe):**  
  Supervisors must never see individual worker biometric scores. Departments with fewer than $k$ workers ($k \ge 5$) must be suppressed to prevent identity disclosure.

---

## 6. Bilingual & Directional Integrity (Arabic RTL & English LTR)

* **Native Arabic Support:**  
  All clinical syntheses, check-in instructions, and patient-facing workflows must support Arabic natively.
* **Strict RTL Container Attributes:**  
  Any Arabic text must be wrapped inside a container with `dir="rtl"` and semantic right alignment (`text-right font-sans`).
* **Zero Fragmented JSX Templates:**  
  Arabic text must never be interleaved with broken inline JSX template expressions that scramble punctuation or word order.

---

## 7. Multi-Tenancy & Strict RBAC Enforcement

* **Tenant Isolation:**  
  Every API route, database query, and state update must be scoped to the authenticated user's `organization_id`. Cross-tenant data leakage is strictly prohibited.
* **Role-Based Access Control:**  
  Permissions (`patients:read`, `reviews:sign`, `pipeline:run`, `workforce:manage`, etc.) must be verified on both frontend navigation guards and backend route dependencies.

---

## 8. Code Quality, Testing & Zero Regressions

* **TypeScript Strictness:**  
  Zero TypeScript compiler errors (`npm run typecheck` must pass with 0 errors).
* **Automated Verification Suites:**  
  Every change must maintain 100% pass rates across Vitest frontend unit tests and Pytest backend integration suites.
