import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import PatientsPage from "@/app/patients/page";
import ReferralsPage from "@/app/referrals/page";
import ReviewsPage from "@/app/reviews/page";
import AgentsPage from "@/app/agents/page";
import { patientsService } from "@/services/patients";
import { careService } from "@/services/care";
import { engineService } from "@/services/engine";
const { replace, state } = vi.hoisted(() => ({
  replace: vi.fn(),
  state: {
    session: null as null | { role: string },
    loading: false,
    hasPermission: () => false,
    hasTrack: () => false,
  },
}));
vi.mock("next/navigation", () => ({ useRouter: () => ({ replace }) }));
vi.mock("@/hooks/useAuth", () => ({ useAuth: () => state }));
vi.mock("@/services/patients", () => ({ patientsService: { list: vi.fn() } }));
vi.mock("@/services/care", () => ({
  careService: {
    listReferrals: vi.fn(),
    listInterventions: vi.fn(),
    listReviews: vi.fn(),
  },
}));
vi.mock("@/services/engine", () => ({
  engineService: { listRuns: vi.fn(), listEmergencies: vi.fn() },
}));
afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  state.session = null;
});
describe("Protected workspace loading", () => {
  it.each([
    ["patients", PatientsPage],
    ["referrals", ReferralsPage],
    ["reviews", ReviewsPage],
    ["agents", AgentsPage],
  ])(
    "does not request private %s data before authentication",
    async (_name, Page) => {
      render(<Page />);
      await waitFor(() => expect(replace).toHaveBeenCalledWith("/login"));
      expect(patientsService.list).not.toHaveBeenCalled();
      expect(careService.listReferrals).not.toHaveBeenCalled();
      expect(careService.listReviews).not.toHaveBeenCalled();
      expect(engineService.listRuns).not.toHaveBeenCalled();
    },
  );
  it("does not mount a patient workspace when the signed-in role lacks access", () => {
    state.session = { role: "supervisor" };
    render(<PatientsPage />);
    expect(screen.getByText("Access Restricted")).toBeInTheDocument();
    expect(patientsService.list).not.toHaveBeenCalled();
  });
});
