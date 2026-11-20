import { api } from "@/lib/api";
import type {
  ClinicalReview,
  Intervention,
  NotificationChannel,
  NotificationItem,
  OutcomeVerification,
  Page,
  Referral,
  ReferralDetail,
  ReferralPathway,
  ReviewDecision,
  Track,
} from "@/types/recova";

export const careService = {
  listReviews(params?: {
    page?: number;
    page_size?: number;
    patient_id?: string;
    run_id?: string;
  }): Promise<Page<ClinicalReview>> {
    return api.get("/clinical-reviews", params);
  },

  createReview(payload: {
    run_id: string;
    decision: ReviewDecision;
    agrees_with_tier?: boolean;
    clinician_notes?: string;
    modified_plan?: Record<string, unknown>;
    lab_request?: Record<string, unknown>;
    referral_id?: string;
    notify_patient_channel?: NotificationChannel;
  }): Promise<ClinicalReview> {
    return api.post("/clinical-reviews", payload);
  },

  listReferrals(params?: {
    page?: number;
    page_size?: number;
    track?: string;
    status?: string;
    patient_id?: string;
    sla_status?: string;
  }): Promise<Page<Referral>> {
    return api.get("/referrals", params);
  },

  createReferral(payload: {
    patient_id: string;
    track: Track;
    pathway: ReferralPathway;
    priority: "stat" | "urgent" | "routine";
    reason: string;
    facility_id?: string;
  }): Promise<Referral> {
    return api.post("/referrals", payload);
  },

  getReferral(referralId: string): Promise<ReferralDetail> {
    return api.get(`/referrals/${referralId}`);
  },

  evaluateSlas(): Promise<Record<string, unknown>> {
    return api.post("/referrals/evaluate-slas");
  },

  notifyReferral(
    referralId: string,
    channel: NotificationChannel,
    message?: string
  ): Promise<{ referral: Referral; notification: NotificationItem }> {
    return api.post(`/referrals/${referralId}/notify`, { channel, message });
  },

  bookReferral(
    referralId: string,
    payload: {
      appointment_at: string;
      appointment_reference?: string;
      facility_id?: string;
      notes?: string;
    }
  ): Promise<Referral> {
    return api.post(`/referrals/${referralId}/book`, payload);
  },

  cancelReferral(referralId: string, reason: string): Promise<Referral> {
    return api.post(`/referrals/${referralId}/cancel`, { reason });
  },

  completeConsultation(referralId: string, notes?: string): Promise<Referral> {
    return api.post(`/referrals/${referralId}/complete-consultation`, { notes });
  },

  markMissed(referralId: string, notes?: string): Promise<Referral> {
    return api.post(`/referrals/${referralId}/missed`, undefined, notes ? { notes } : undefined);
  },

  verifyOutcome(
    referralId: string,
    payload: {
      outcome: "improved" | "stable" | "deteriorated" | "relapsed" | "lost_to_follow_up" | "referred_onward";
      verification_method: "clinic_visit" | "teleconsult" | "phone" | "record_review" | "lab_result";
      notes?: string;
      follow_up_run_id?: string;
    }
  ): Promise<OutcomeVerification> {
    return api.post(`/outcomes/referral/${referralId}/verify`, payload);
  },

  listInterventions(params?: { track?: string; department_id?: string }): Promise<Intervention[]> {
    return api.get("/interventions", params);
  },

  createIntervention(payload: {
    track: Track;
    patient_id?: string;
    department_id?: string;
    referral_id?: string;
    intervention_type:
      | "rest_break"
      | "hydration"
      | "shift_rotation"
      | "coaching"
      | "lab_request"
      | "follow_up_call"
      | "other";
    title: string;
    details?: string;
    due_at?: string;
  }): Promise<Intervention> {
    return api.post("/interventions", payload);
  },

  updateIntervention(
    interventionId: string,
    payload: { status: "planned" | "in_progress" | "completed" | "cancelled"; details?: string }
  ): Promise<Intervention> {
    return api.patch(`/interventions/${interventionId}`, payload);
  },

  listNotifications(params?: { page?: number; page_size?: number }): Promise<Page<NotificationItem>> {
    return api.get("/notifications", params);
  },

  markNotificationRead(notificationId: string): Promise<NotificationItem> {
    return api.post(`/notifications/${notificationId}/read`);
  },
};
