"""Import all models so Alembic autogenerate and relationship resolution see them."""

from app.models.base import Base
from app.models.identity import Membership, Organization, PasswordResetToken, RolePermissionOverride, User, UserSession
from app.models.clinical import (
    CheckIn,
    CognitiveAssessment,
    Consent,
    Department,
    Observation,
    Patient,
    ScreeningRecord,
    TrackEnrollment,
    WearableIngestionBatch,
    Workplace,
    WorkplaceAssessment,
)
from app.models.engine import AgentStepResult, ClinicalSynthesis, EmergencyEvent, PersonalBaseline, PipelineRun, ScoringResult
from app.models.care import (
    CareFacility,
    ClinicalReview,
    InsurancePlan,
    Intervention,
    Notification,
    OutcomeVerification,
    Referral,
    ReferralEvent,
)
from app.models.ops import AuditEvent, BenchmarkCaseResult, BenchmarkRun, IntegrationConfig, Job

__all__ = [
    "Base", "Membership", "Organization", "PasswordResetToken", "RolePermissionOverride", "User", "UserSession",
    "CheckIn", "CognitiveAssessment", "Consent", "Department", "Observation", "Patient", "ScreeningRecord",
    "TrackEnrollment", "WearableIngestionBatch", "Workplace", "WorkplaceAssessment", "AgentStepResult",
    "ClinicalSynthesis", "EmergencyEvent", "PersonalBaseline", "PipelineRun", "ScoringResult", "CareFacility",
    "ClinicalReview", "InsurancePlan", "Intervention", "Notification", "OutcomeVerification", "Referral",
    "ReferralEvent", "AuditEvent", "BenchmarkCaseResult", "BenchmarkRun", "IntegrationConfig", "Job",
]
