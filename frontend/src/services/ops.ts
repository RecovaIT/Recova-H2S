import { api } from "@/lib/api";
import type {
  AuditEvent,
  BenchmarkRun,
  BenchmarkRunDetail,
  CareFacility,
  InsurancePlan,
  IntegrationConfig,
  JobRecord,
  Organization,
  OverviewReport,
  Page,
  ReferralPathway,
  RolePermissionView,
  Track,
  UserWithMemberships,
} from "@/types/recova";

export const opsService = {
  getOverview(): Promise<OverviewReport> {
    return api.get("/reports/overview");
  },

  listOrganizations(): Promise<Organization[]> {
    return api.get("/organizations");
  },

  createOrganization(payload: {
    name: string;
    slug: string;
    org_type: string;
    enabled_tracks: Track[];
    country?: string;
    emirate?: string;
  }): Promise<Organization> {
    return api.post("/organizations", payload);
  },

  updateOrganization(
    orgId: string,
    payload: {
      name?: string;
      org_type?: string;
      enabled_tracks?: Track[];
      country?: string;
      emirate?: string;
      data_retention_days?: number;
      settings?: Record<string, unknown>;
    }
  ): Promise<Organization> {
    return api.patch(`/organizations/${orgId}`, payload);
  },

  getPermissionsCatalog(): Promise<{ permissions: string[] }> {
    return api.get("/organizations/permissions/catalog");
  },

  listRolePermissions(): Promise<RolePermissionView[]> {
    return api.get("/organizations/permissions/roles");
  },

  setRoleOverride(payload: {
    role: string;
    permission: string;
    effect: "grant" | "revoke";
  }): Promise<Record<string, unknown>> {
    return api.post("/organizations/permissions/overrides", payload);
  },

  deleteRoleOverride(role: string, permission: string): Promise<{ message: string }> {
    return api.delete("/organizations/permissions/overrides", { role, permission });
  },

  listUsers(): Promise<UserWithMemberships[]> {
    return api.get("/users");
  },

  createUser(payload: {
    email: string;
    full_name: string;
    role: string;
    password?: string;
    preferred_language?: "en" | "ar";
    license_number?: string;
  }): Promise<{ user: UserWithMemberships; activation_token?: string }> {
    return api.post("/users", payload);
  },

  updateUser(
    userId: string,
    payload: { full_name?: string; is_active?: boolean; license_number?: string }
  ): Promise<Record<string, unknown>> {
    return api.patch(`/users/${userId}`, payload);
  },

  updateMembership(
    membershipId: string,
    payload: { role?: string; is_active?: boolean; department_ids?: string[] }
  ): Promise<Record<string, unknown>> {
    return api.patch(`/users/memberships/${membershipId}`, payload);
  },

  listAuditLogs(params?: {
    page?: number;
    page_size?: number;
    action?: string;
    resource_type?: string;
    outcome?: string;
  }): Promise<Page<AuditEvent>> {
    return api.get("/audit-logs", params);
  },

  listJobs(params?: { page?: number; page_size?: number }): Promise<Page<JobRecord>> {
    return api.get("/audit-logs/jobs", params);
  },

  getBenchmarkSuite(): Promise<{
    suite_name: string;
    suite_version: string;
    total_cases: number;
    cases: Array<Record<string, unknown>>;
  }> {
    return api.get("/benchmarks/suite");
  },

  listBenchmarkRuns(): Promise<BenchmarkRun[]> {
    return api.get("/benchmarks/runs");
  },

  runBenchmarks(tracks: Track[], runAsync = false): Promise<BenchmarkRunDetail> {
    return api.post("/benchmarks/runs", { tracks, run_async: runAsync });
  },

  getBenchmarkRun(runId: string): Promise<BenchmarkRunDetail> {
    return api.get(`/benchmarks/runs/${runId}`);
  },

  exportPatientFhir(
    patientId: string,
    bundleType: "collection" | "transaction" = "collection"
  ): Promise<{ bundle: Record<string, unknown>; validation: Record<string, unknown> }> {
    return api.get(`/fhir/patients/${patientId}/bundle`, { bundle_type: bundleType });
  },

  pushToMalaffi(patientId: string): Promise<Record<string, unknown>> {
    return api.post(`/fhir/patients/${patientId}/push-malaffi`);
  },

  listInsurancePlans(): Promise<InsurancePlan[]> {
    return api.get("/settings/insurance-plans");
  },

  createInsurancePlan(payload: {
    code: string;
    name: string;
    payer_name?: string;
    network_tier?: string;
    covered_pathways: ReferralPathway[];
    requires_preauthorization: boolean;
  }): Promise<InsurancePlan> {
    return api.post("/settings/insurance-plans", payload);
  },

  listCareFacilities(): Promise<CareFacility[]> {
    return api.get("/settings/care-facilities");
  },

  createCareFacility(payload: {
    name: string;
    facility_type:
      | "primary_care"
      | "specialist"
      | "teleconsult"
      | "rehab"
      | "emergency"
      | "occupational_health"
      | "therapist";
    pathways: ReferralPathway[];
    specialties: string[];
    accepted_plan_ids: string[];
    address?: string;
    contact_phone?: string;
    contact_email?: string;
    typical_wait_days?: number;
  }): Promise<CareFacility> {
    return api.post("/settings/care-facilities", payload);
  },

  listIntegrations(): Promise<IntegrationConfig[]> {
    return api.get("/settings/integrations");
  },

  upsertIntegration(
    name: string,
    payload: { enabled: boolean; settings: Record<string, unknown>; secrets?: Record<string, string> }
  ): Promise<IntegrationConfig> {
    return api.put(`/settings/integrations/${name}`, payload);
  },

  testIntegration(name: string): Promise<Record<string, unknown>> {
    return api.post(`/settings/integrations/${name}/test`);
  },
};
