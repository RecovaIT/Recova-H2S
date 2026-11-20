import { api } from "@/lib/api";
import type {
  AuditEvent,
  AuthorityNotice,
  AuthorityReport,
  AuthorityScope,
  BenchmarkRun,
  BenchmarkRunDetail,
  CareFacility,
  InsurancePlan,
  IntegrationConfig,
  JobRecord,
  LlmKeyStatus,
  Organization,
  OverviewReport,
  Page,
  PlatformOverviewReport,
  ProgrammeRequest,
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
    primary_programme?: Track;
    enabled_tracks: Track[];
    country?: string;
    emirate?: string;
  }): Promise<Organization> {
    return api.post("/organizations", payload);
  },

  selectPrimaryProgramme(
    orgId: string,
    payload: { primary_programme: Track; reason?: string; restrict_to_primary?: boolean }
  ): Promise<Organization> {
    return api.post(`/organizations/${orgId}/select-primary-programme`, payload);
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
      send_activation_email?: boolean;
    preferred_language?: "en" | "ar";
    license_number?: string;
    }): Promise<{ user: UserWithMemberships; activation?: {status:string;id?:string} | null }> {
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

  getLlmKeyStatus(provider = "gemini"): Promise<LlmKeyStatus> {
    return api.get("/settings/integrations/llm/key-status", { provider });
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

  getPlatformOverview(): Promise<PlatformOverviewReport> {
    return api.get("/reports/platform-overview");
  },

  listProgrammeRequests(): Promise<ProgrammeRequest[]> {
    return api.get("/organizations/programme-requests");
  },

  createProgrammeRequest(payload: {
    requested_programme: Track;
    justification: string;
  }): Promise<ProgrammeRequest> {
    return api.post("/organizations/programme-requests", payload);
  },

  reviewProgrammeRequest(
    requestId: string,
    payload: { decision: "approved" | "rejected"; review_note?: string }
  ): Promise<ProgrammeRequest> {
    return api.post(`/organizations/programme-requests/${requestId}/review`, payload);
  },

  listAuthorityScopes(): Promise<AuthorityScope[]> {
    return api.get("/authority/scopes");
  },

  createAuthorityScope(payload: {
    user_id: string;
    organization_id?: string | null;
    assigned_emirates: string[];
    assigned_facility_ids?: string[];
    can_publish?: boolean;
    can_view_reports?: boolean;
    min_suppression_k?: number;
  }): Promise<AuthorityScope> {
    return api.post("/authority/scopes", payload);
  },

  revokeAuthorityScope(scopeId: string): Promise<{ revoked: boolean; id: string }> {
    return api.delete(`/authority/scopes/${scopeId}`);
  },

  listAuthorityNotices(): Promise<AuthorityNotice[]> {
    return api.get("/authority/notices");
  },

  previewAuthorityNotice(payload: {
    title: string;
    message: string;
    plain_language_action?: string;
    severity: "info" | "advisory" | "urgent";
    scope_emirate?: string;
    facility_ids?: string[];
    eligible_programmes: string[];
  }): Promise<{ organization_count: number; recipient_count: number; organizations: Array<{ id: string; name: string; emirate?: string | null }> }> {
    return api.post("/authority/notices/preview", payload);
  },

  createAuthorityNotice(payload: {
    title: string;
    message: string;
    plain_language_action?: string;
    severity: "info" | "advisory" | "urgent";
    scope_emirate?: string;
    facility_ids?: string[];
    eligible_programmes: string[];
    acknowledgement_required?: boolean;
    idempotency_key?: string;
  }): Promise<AuthorityNotice> {
    return api.post("/authority/notices", payload);
  },

  updateAuthorityNotice(
    noticeId: string,
    payload: Partial<{
      title: string;
      message: string;
      plain_language_action: string;
      severity: "info" | "advisory" | "urgent";
      scope_emirate: string;
      eligible_programmes: string[];
    }>
  ): Promise<AuthorityNotice> {
    return api.patch(`/authority/notices/${noticeId}`, payload);
  },

  publishAuthorityNotice(noticeId: string): Promise<AuthorityNotice> {
    return api.post(`/authority/notices/${noticeId}/publish`);
  },

  withdrawAuthorityNotice(noticeId: string): Promise<AuthorityNotice> {
    return api.post(`/authority/notices/${noticeId}/withdraw`);
  },

  getAuthorityReports(): Promise<AuthorityReport> {
    return api.get("/authority/reports");
  },

  listVisibleNotices(): Promise<AuthorityNotice[]> {
    return api.get("/notices");
  },

  markNoticeRead(noticeId: string): Promise<{ notice_id: string; state: string; read_at: string }> {
    return api.post(`/notices/${noticeId}/read`);
  },

  acknowledgeNotice(noticeId: string): Promise<{ notice_id: string; acknowledged: boolean; acknowledged_at: string }> {
    return api.post(`/notices/${noticeId}/acknowledgements`);
  },
};
