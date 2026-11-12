import { api } from "@/lib/api";
import type {
  CheckIn,
  CognitiveAssessment,
  CognitiveTrialInput,
  Department,
  HeatmapRow,
  MetricCatalogEntry,
  Observation,
  Page,
  ScreeningRecord,
  Track,
  Workplace,
  WorkplaceAssessment,
} from "@/types/recova";

export const signalsService = {
  catalog(): Promise<MetricCatalogEntry[]> {
    return api.get("/observations/catalog");
  },

  listObservations(
    patientId: string,
    params?: { page?: number; page_size?: number; metric_code?: string; track?: string }
  ): Promise<Page<Observation>> {
    return api.get(`/observations/patient/${patientId}`, params);
  },

  recordObservation(payload: {
    patient_id: string;
    track?: Track;
    metric_code: string;
    value_num?: number;
    value_text?: string;
    unit?: string;
    effective_at: string;
    source?: string;
    device_id?: string;
    provenance?: Record<string, unknown>;
  }): Promise<Observation> {
    return api.post("/observations", payload);
  },

  ingestWearables(payload: {
    patient_id: string;
    track: Track;
    source_system: "apple_health" | "garmin" | "fitbit" | "sahatna" | "csv" | "manual_device";
    device_id?: string;
    observations: Array<{
      metric_code: string;
      value_num: number;
      unit?: string;
      effective_at: string;
    }>;
    trigger_pipeline: boolean;
  }): Promise<{ batch: Record<string, unknown>; run_id: string | null }> {
    return api.post("/wearables/ingest", payload);
  },

  listCheckIns(patientId: string): Promise<CheckIn[]> {
    return api.get(`/check-ins/patient/${patientId}`);
  },

  createCheckIn(payload: {
    patient_id: string;
    track: Track;
    kind: "text" | "voice" | "readiness";
    mood_score?: number;
    craving_score?: number;
    stress_score?: number;
    sleep_quality?: number;
    sleep_hours_reported?: number;
    text?: string;
    transcript_source?: "browser_speech" | "typed" | "imported";
    symptoms?: string[];
    self_reported_crisis?: boolean;
    trigger_pipeline?: boolean;
  }): Promise<{ check_in: CheckIn; run_id: string | null }> {
    return api.post("/check-ins", payload);
  },

  listScreenings(patientId: string): Promise<ScreeningRecord[]> {
    return api.get(`/screenings/patient/${patientId}`);
  },

  createScreening(payload: {
    patient_id: string;
    programme?: string;
    screening_site?: string;
    hba1c?: number;
    bp_systolic?: number;
    bp_diastolic?: number;
    phq9_item_responses?: number[];
    phq9_score?: number;
    total_cholesterol?: number;
    ldl_cholesterol?: number;
    hdl_cholesterol?: number;
    triglycerides?: number;
    steps?: number;
    notes?: string;
    trigger_pipeline?: boolean;
  }): Promise<{ screening: ScreeningRecord; run_id: string | null }> {
    return api.post("/screenings", payload);
  },

  listCognitiveAssessments(patientId: string): Promise<CognitiveAssessment[]> {
    return api.get(`/cognitive-assessments/patient/${patientId}`);
  },

  createCognitiveAssessment(payload: {
    patient_id: string;
    started_at?: string;
    completed_at?: string;
    assessment_language: "en" | "ar";
    environment?: Record<string, unknown>;
    raw_trials: CognitiveTrialInput[];
    trigger_pipeline?: boolean;
  }): Promise<{ assessment: CognitiveAssessment; run_id: string | null }> {
    return api.post("/cognitive-assessments", payload);
  },

  listWorkplaces(): Promise<Workplace[]> {
    return api.get("/workforce/workplaces");
  },

  createWorkplace(payload: {
    name: string;
    location?: string;
    environment_type?: "outdoor" | "indoor" | "mixed";
  }): Promise<Workplace> {
    return api.post("/workforce/workplaces", payload);
  },

  listDepartments(): Promise<Department[]> {
    return api.get("/workforce/departments");
  },

  createDepartment(payload: {
    name: string;
    workplace_id?: string;
    min_group_size_for_reporting: number;
  }): Promise<Department> {
    return api.post("/workforce/departments", payload);
  },

  listWorkplaceAssessments(departmentId?: string): Promise<WorkplaceAssessment[]> {
    return api.get("/workforce/assessments", departmentId ? { department_id: departmentId } : undefined);
  },

  createWorkplaceAssessment(payload: {
    department_id?: string;
    workplace_id?: string;
    ambient_temp_c?: number;
    relative_humidity_pct?: number;
    wbgt_c?: number;
    noise_db?: number;
    lighting_lux?: number;
    source?: "manual" | "sensor" | "weather_api";
  }): Promise<WorkplaceAssessment> {
    return api.post("/workforce/assessments", payload);
  },

  submitWorkerReadiness(payload: {
    patient_id: string;
    readiness_score: number;
    fatigue_feeling: "fresh" | "mild_fatigue" | "exhausted" | "dizzy_heat_illness";
    hydrated: boolean;
    shift_duration_hours?: number;
    core_temp_est_c?: number;
    hr_recovery_minutes?: number;
    sleep_debt_hours?: number;
    hrv_rmssd?: number;
    voice_note?: string;
    trigger_pipeline?: boolean;
  }): Promise<{ check_in: CheckIn; run_id: string | null }> {
    return api.post("/workforce/readiness", payload);
  },

  getWorkforceHeatmap(): Promise<HeatmapRow[]> {
    return api.get("/workforce/heatmap");
  },

  getIdentifiableWorkerRisks(): Promise<Array<Record<string, unknown>>> {
    return api.get("/workforce/identifiable-risks");
  },
};
