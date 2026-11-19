import { api } from "@/lib/api";
import type {
  Consent,
  ConsentScope,
  Enrollment,
  FamilyHealthPassport,
  Page,
  PatientDetail,
  PatientSummary,
  Track,
} from "@/types/recova";

export interface PatientCreatePayload {
  participant_type: "patient" | "employee";
  mrn: string;
  given_name: string;
  family_name: string;
  date_of_birth?: string | null;
  sex?: "male" | "female" | "other" | "unknown";
  preferred_language?: "en" | "ar";
  national_id?: string | null;
  phone?: string | null;
  email?: string | null;
  emergency_contact?: Record<string, unknown> | null;
  education_level?: "none" | "primary" | "secondary" | "tertiary" | "postgraduate" | null;
  primary_language_matches_assessment?: boolean;
  hearing_status?: "normal" | "mild_loss" | "moderate_loss" | "severe_loss" | "aided";
  vision_status?: "normal" | "corrected" | "mild_impairment" | "severe_impairment";
  clinical_history?: Record<string, unknown>;
  insurance_plan_id?: string | null;
  insurance_member_id?: string | null;
  department_id?: string | null;
  job_role?: string | null;
  tracks: Track[];
}

export interface ConsentCreatePayload {
  patient_id: string;
  scope: ConsentScope;
  method: "written" | "verbal_witnessed" | "electronic" | "guardian";
  granted_by_name?: string;
  evidence_reference?: string;
  notes?: string;
}

export const patientsService = {
  list(params?: {
    page?: number;
    page_size?: number;
    q?: string;
    track?: string;
    risk_tier?: string;
    department_id?: string;
    active_only?: boolean;
  }): Promise<Page<PatientSummary>> {
    return api.get("/patients", params);
  },

  create(payload: PatientCreatePayload): Promise<PatientDetail> {
    return api.post("/patients", payload);
  },

  get(patientId: string): Promise<PatientDetail> {
    return api.get(`/patients/${patientId}`);
  },

  update(patientId: string, payload: Partial<PatientCreatePayload> & { is_active?: boolean }): Promise<PatientDetail> {
    return api.patch(`/patients/${patientId}`, payload);
  },

  enroll(patientId: string, track: Track, context: Record<string, unknown> = {}): Promise<Enrollment> {
    return api.post(`/patients/${patientId}/enrollments`, { track, context });
  },

  getPassport(patientId: string): Promise<FamilyHealthPassport> {
    return api.get(`/patients/${patientId}/passport`);
  },

  listConsents(patientId: string): Promise<Consent[]> {
    return api.get(`/consents/patient/${patientId}`);
  },

  grantConsent(payload: ConsentCreatePayload): Promise<Consent> {
    return api.post("/consents", payload);
  },

  revokeConsent(consentId: string, reason?: string): Promise<Consent> {
    return api.post(`/consents/${consentId}/revoke`, undefined, reason ? { reason } : undefined);
  },

  issuePortalInvitation(
    patientId: string,
    recipientEmail: string
  ): Promise<{
    invitation_id: string;
    patient_id: string;
    organization_id: string;
    organization_name?: string | null;
    primary_programme?: string | null;
    recipient_email: string;
    expires_at: string;
    invitation_token: string;
  }> {
    return api.post(`/patients/${patientId}/portal-invitations`, { recipient_email: recipientEmail });
  },
};
