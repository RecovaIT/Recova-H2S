import { api } from "@/lib/api";
import type {
  EmergencyEvent,
  Page,
  PersonalBaseline,
  PipelineRun,
  PipelineRunDetail,
  ScoringResult,
  Track,
} from "@/types/recova";

export const engineService = {
  listBaselines(patientId: string): Promise<PersonalBaseline[]> {
    return api.get(`/baselines/patient/${patientId}`);
  },

  resetBaseline(patientId: string, metricCode?: string, reason?: string): Promise<{ reset_count: number }> {
    return api.post(`/baselines/patient/${patientId}/reset`, undefined, {
      metric_code: metricCode,
      reason,
    });
  },

  listScoringResults(patientId: string, track?: string): Promise<ScoringResult[]> {
    return api.get(`/scoring/patient/${patientId}`, track ? { track } : undefined);
  },

  getScoringConfig(): Promise<Record<string, unknown>> {
    return api.get("/scoring/config");
  },

  listRuns(params?: {
    page?: number;
    page_size?: number;
    patient_id?: string;
    track?: string;
    status?: string;
  }): Promise<Page<PipelineRun>> {
    return api.get("/pipeline/runs", params);
  },

  getRun(runId: string): Promise<PipelineRunDetail> {
    return api.get(`/pipeline/runs/${runId}`);
  },

  triggerRun(payload: {
    patient_id: string;
    track: Track;
    trigger?: "manual" | "checkin" | "wearable" | "screening" | "assessment";
    run_async?: boolean;
  }): Promise<PipelineRunDetail> {
    return api.post("/pipeline/runs", payload);
  },

  listAgentsCatalog(): Promise<Array<{ agent_key: string; agent_name: string; step_order: number }>> {
    return api.get("/agents/catalog");
  },

  listEmergencies(status?: string): Promise<EmergencyEvent[]> {
    return api.get("/agents/emergencies", status ? { status } : undefined);
  },

  resolveEmergency(
    eventId: string,
    action: "acknowledge" | "resolve",
    notes?: string
  ): Promise<EmergencyEvent> {
    return api.post(`/agents/emergencies/${eventId}/resolve`, { action, notes });
  },
};
