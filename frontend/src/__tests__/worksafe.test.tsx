import React from "react";
import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { AuthProvider } from "@/hooks/useAuth";
import { ToastProvider } from "@/components/ui/toast";
import { WorkSafeWorkspace } from "@/features/worksafe/WorkSafeWorkspace";

vi.mock("@/services/auth", () => ({
  authService: {
    status: vi.fn().mockResolvedValue({ needs_bootstrap: false }),
    me: vi.fn().mockResolvedValue({
      user: { id: "u2", email: "sup@recova.ae", full_name: "Supervisor Sam", is_active: true, is_platform_admin: false, preferred_language: "en", created_at: "2026-01-01" },
      active_organization: { id: "o1", name: "Yard", slug: "yard", org_type: "employer", enabled_tracks: ["worksafe"], is_active: true, settings: {}, created_at: "2026-01-01" },
      role: "supervisor",
      permissions: ["org:read", "workforce:read_aggregate"],
      tracks: ["worksafe"],
      memberships: [],
    }),
  },
}));

vi.mock("@/services/signals", () => ({
  signalsService: {
    listWorkplaces: vi.fn().mockResolvedValue([{ id: "w1", organization_id: "o1", name: "Mussafah Site", is_active: true }]),
    listDepartments: vi.fn().mockResolvedValue([{ id: "d1", organization_id: "o1", name: "Crew Alpha", min_group_size_for_reporting: 5, is_active: true }]),
    getWorkforceHeatmap: vi.fn().mockResolvedValue([
      {
        department_id: "d1",
        department_name: "Crew Alpha",
        worker_count: 2,
        k_anonymity_threshold: 5,
        suppressed_k_anonymity: true,
        risk_counts: null,
        latest_heat_index_c: 43.2,
        latest_ambient_temp_c: 40.0,
        open_interventions: 1,
      },
    ]),
    listWorkplaceAssessments: vi.fn().mockResolvedValue([]),
  },
}));

vi.mock("@/services/care", () => ({
  careService: {
    listInterventions: vi.fn().mockResolvedValue([]),
  },
}));

describe("WorkSafeWorkspace k-anonymity enforcement", () => {
  it("shows suppression notice when department worker count is below k threshold", async () => {
    render(
      <AuthProvider>
        <ToastProvider>
          <WorkSafeWorkspace />
        </ToastProvider>
      </AuthProvider>
    );

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Crew Alpha" })).toBeInTheDocument();
    });
    expect(screen.getByText(/Suppressed \(k < 5\)/i)).toBeInTheDocument();
    expect(screen.getByText(/43.2 °C/)).toBeInTheDocument();
  });
});
