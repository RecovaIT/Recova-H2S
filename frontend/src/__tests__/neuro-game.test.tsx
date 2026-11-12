import React from "react";
import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { AuthProvider } from "@/hooks/useAuth";
import { ToastProvider } from "@/components/ui/toast";
import { NeuroActivityGame } from "@/features/neuro/NeuroActivityGame";

vi.mock("@/services/auth", () => ({
  authService: {
    status: vi.fn().mockResolvedValue({ needs_bootstrap: false }),
    me: vi.fn().mockResolvedValue({
      user: { id: "u1", email: "doc@recova.ae", full_name: "Dr. A", is_active: true, is_platform_admin: false, preferred_language: "en", created_at: "2026-01-01" },
      active_organization: { id: "o1", name: "Hub", slug: "hub", org_type: "hospital", enabled_tracks: ["neuro"], is_active: true, settings: {}, created_at: "2026-01-01" },
      role: "clinician",
      permissions: ["pipeline:read", "cognitive:administer", "observations:read"],
      tracks: ["neuro"],
      memberships: [],
    }),
  },
}));

vi.mock("@/services/patients", () => ({
  patientsService: {
    list: vi.fn().mockResolvedValue({
      items: [
        {
          id: "p-neuro-1",
          organization_id: "o1",
          participant_type: "patient",
          mrn: "NEURO-101",
          given_name: "Fatima",
          family_name: "Al Mansoori",
          preferred_language: "en",
          is_active: true,
          created_at: "2026-01-01",
          enrollments: [{ id: "e1", patient_id: "p-neuro-1", track: "neuro", status: "active", enrolled_at: "2026-01-01", context: {} }],
        },
      ],
      total: 1,
      page: 1,
      page_size: 100,
      pages: 1,
    }),
    get: vi.fn().mockResolvedValue({
      id: "p-neuro-1",
      organization_id: "o1",
      participant_type: "patient",
      mrn: "NEURO-101",
      given_name: "Fatima",
      family_name: "Al Mansoori",
      preferred_language: "en",
      education_level: "secondary",
      hearing_status: "normal",
      vision_status: "normal",
      clinical_history: {},
      is_active: true,
      created_at: "2026-01-01",
      enrollments: [],
    }),
  },
}));

vi.mock("@/services/signals", () => ({
  signalsService: {
    listCognitiveAssessments: vi.fn().mockResolvedValue([]),
    listObservations: vi.fn().mockResolvedValue({ items: [], total: 0, page: 1, page_size: 100, pages: 0 }),
  },
}));

vi.mock("@/services/engine", () => ({
  engineService: {
    listBaselines: vi.fn().mockResolvedValue([]),
    listRuns: vi.fn().mockResolvedValue({ items: [], total: 0, page: 1, page_size: 1, pages: 0 }),
  },
}));

describe("NeuroActivityGame", () => {
  it("renders non-diagnostic disclaimer and cognitive start button", async () => {
    render(
      <AuthProvider>
        <ToastProvider>
          <NeuroActivityGame />
        </ToastProvider>
      </AuthProvider>
    );

    await waitFor(() => {
      expect(screen.getByText(/Non-Diagnostic Early Brain Health/i)).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /Start Cognitive Assessment Session/i })).toBeInTheDocument();
    });
  });
});
