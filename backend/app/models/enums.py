"""Shared enumerations used by models, schemas and the engine (stored as strings)."""

from __future__ import annotations

from enum import StrEnum


class ParticipantType(StrEnum):
    PATIENT = "patient"
    EMPLOYEE = "employee"


class ConsentScope(StrEnum):
    DATA_PROCESSING = "data_processing"          # mandatory for routine pipeline processing
    WEARABLE_INGESTION = "wearable_ingestion"
    LLM_SYNTHESIS = "llm_synthesis"              # de-identified data sent to configured LLM provider
    FAMILY_NOTIFICATION = "family_notification"  # family / sponsor alerts
    HIE_SHARING = "hie_sharing"                  # FHIR export / Malaffi / Sahatna exchange
    SUPERVISOR_IDENTIFIABLE = "supervisor_identifiable"  # WorkSafe: identifiable data to supervisor
    OPTIONAL_CHANNELS = "optional_channels"      # optional external notification / public-health channels


class NoticeRecipientState(StrEnum):
    AVAILABLE = "available"
    READ = "read"
    ACKNOWLEDGED = "acknowledged"


class ConsentStatus(StrEnum):
    GRANTED = "granted"
    REVOKED = "revoked"


class ObservationSource(StrEnum):
    MANUAL = "manual"
    WEARABLE = "wearable"
    DEVICE = "device"
    CHECKIN = "checkin"
    SCREENING = "screening"
    ASSESSMENT = "assessment"
    WORKPLACE = "workplace"
    IMPORT = "import"


class RiskTier(StrEnum):
    GREEN = "GREEN"
    AMBER = "AMBER"
    RED = "RED"
    EMERGENCY_BYPASS = "EMERGENCY_BYPASS"
    INDETERMINATE = "INDETERMINATE"  # insufficient baseline / no scorable metrics


class RunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    EMERGENCY_BYPASS = "emergency_bypass"
    BLOCKED = "blocked"   # consent / governance gate refused routine processing
    FAILED = "failed"


class StepStatus(StrEnum):
    WAITING = "waiting"
    RUNNING = "running"
    COMPLETED = "completed"
    FLAGGED = "flagged"
    FAILED = "failed"
    BYPASSED = "bypassed"
    SKIPPED = "skipped"   # not executed because an earlier gate blocked processing


class SynthesisStatus(StrEnum):
    COMPLETED = "completed"
    PROVIDER_NOT_CONFIGURED = "provider_not_configured"
    CONSENT_NOT_GRANTED = "consent_not_granted"
    PROVIDER_ERROR = "provider_error"
    VALIDATION_FAILED = "validation_failed"


class ReviewDecision(StrEnum):
    APPROVE_REFERRAL = "approve_referral"
    MODIFY_PLAN = "modify_plan"
    REQUEST_LAB = "request_lab"          # lab / toxicology screen
    NO_ACTION = "no_action"
    REJECT = "reject"


class ReferralPathway(StrEnum):
    ASYNC_TELECONSULT = "async_teleconsult"
    OUTPATIENT_THERAPIST = "outpatient_therapist"
    PRIMARY_CARE = "primary_care"
    SPECIALIST = "specialist"
    FAMILY_ALERT = "family_alert"
    EMERGENCY_TRIAGE = "emergency_triage"
    ROUTINE_MONITORING = "routine_monitoring"
    OCCUPATIONAL_HEALTH = "occupational_health"


class ReferralStatus(StrEnum):
    PROPOSED = "proposed"                    # created by Agent 6, awaiting clinician sign-off
    APPROVED = "approved"                    # clinician signed off
    PATIENT_NOTIFIED = "patient_notified"    # at least one notification confirmed sent/delivered
    BOOKED = "booked"
    CONSULTATION_COMPLETED = "consultation_completed"
    OUTCOME_VERIFIED = "outcome_verified"
    MISSED = "missed"
    ESCALATED = "escalated"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class ReferralPriority(StrEnum):
    STAT = "stat"
    URGENT = "urgent"
    ROUTINE = "routine"


class SlaStatus(StrEnum):
    ON_TRACK = "on_track"
    AT_RISK = "at_risk"
    BREACHED = "breached"
    MET = "met"
    NOT_APPLICABLE = "not_applicable"


class NotificationChannel(StrEnum):
    IN_APP = "in_app"
    EMAIL = "email"
    SMS = "sms"
    WHATSAPP = "whatsapp"
    SAHATNA = "sahatna"


class NotificationStatus(StrEnum):
    QUEUED = "queued"
    SENT = "sent"              # accepted by provider / written to in-app inbox
    DELIVERED = "delivered"    # provider confirmed delivery (or recipient read in-app)
    FAILED = "failed"
    NOT_CONFIGURED = "not_configured"


class InterventionType(StrEnum):
    REST_BREAK = "rest_break"
    HYDRATION = "hydration"
    SHIFT_ROTATION = "shift_rotation"
    COACHING = "coaching"
    LAB_REQUEST = "lab_request"
    FOLLOW_UP_CALL = "follow_up_call"
    OTHER = "other"


class InterventionStatus(StrEnum):
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"        # will be retried if attempts remain
    DEAD = "dead"            # exhausted retries


class EmergencyStatus(StrEnum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


class IntegrationStatus(StrEnum):
    NOT_CONFIGURED = "not_configured"
    CONFIGURED = "configured"      # credentials present, not yet verified
    VERIFIED = "verified"          # connection test succeeded
    ERROR = "error"
    DISABLED = "disabled"
