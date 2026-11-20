---
description: Zero mock data, end-to-end backend integration, DECIDE-AI governance, and clinical safety rules for Recova-H2S
globs: "frontend/src/**/*, backend/app/**/*"
---

# Codebase Rules: No Mock Data & End-to-End Integrity

1. **NO MOCK OR STATIC DATA IN UI COMPONENTS:**
   - Every page and component must fetch live data via the appropriate service from `/api/v1/*`.
   - Never inject mock JSON files, sample objects, or static fallback constants into frontend state.
   - When no records exist from an endpoint, render a clean, honest `<EmptyState />` component explaining how the user can generate real data.

2. **END-TO-END MUTATIONS & PERSISTENCE:**
   - Every user action (logins, check-ins, cognitive taps, readiness assessments, referral status updates, clinical reviews) must invoke a FastAPI endpoint that persists to the PostgreSQL database.
   - Always handle network and validation errors gracefully with user-facing toasts or alerts.

3. **DECIDE-AI SEPARATION:**
   - Keep Agent 4 deterministic math in Box 1 and Agent 5 AI synthesis in Box 2. Never mix them.
   - Never fabricate synthetic text when the LLM provider is unconfigured.

4. **CLINICAL EMERGENCY GATE 2 BYPASS:**
   - Deterministic crisis keywords and emergency vitals must immediately trigger Gate 2 bypass.

5. **FIELD-LEVEL ENCRYPTION & SOVEREIGNTY:**
   - Encrypt all sensitive PII with Fernet before database writes.
   - Do not log unencrypted patient data.

6. **BILINGUAL ARABIC & ENGLISH SUPPORT:**
   - Always wrap Arabic text in `<div dir="rtl" className="text-right font-sans ...">`.
