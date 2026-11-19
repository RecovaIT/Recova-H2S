import React, { useState } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AuthProvider, useAuth } from "@/hooks/useAuth";
import LoginPage from "@/app/login/page";
import { OrganizationOnboardingCard } from "@/components/OrganizationOnboardingCard";
import { AuthGuard } from "@/components/AuthGuard";
import { authService } from "@/services/auth";

const replaceMock = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: replaceMock, push: vi.fn() }),
}));

vi.mock("@/services/auth", () => ({
  authService: {
    status: vi.fn(),
    me: vi.fn(),
    login: vi.fn(),
    bootstrap: vi.fn(),
    registerOrganization: vi.fn(),
    switchOrganization: vi.fn(),
    logout: vi.fn(),
  },
}));

describe("LoginPage & Tenant Onboarding", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(authService.status).mockResolvedValue({ needs_bootstrap: false });
    vi.mocked(authService.me).mockRejectedValue(new Error("Unauthenticated"));
  });

  it("renders Add New Organisation button linking to /register-organization when logged out", async () => {
    render(
      <AuthProvider>
        <LoginPage />
      </AuthProvider>
    );

    await waitFor(() => {
      const addOrgLink = screen.getByRole("link", { name: /add new organisation/i });
      expect(addOrgLink).toBeInTheDocument();
      expect(addOrgLink).toHaveAttribute("href", "/register-organization");
    });
  });

  it("opens the privacy-protected WorkSafe workspace for supervisors",async()=>{
    vi.mocked(authService.me).mockResolvedValue({user:{id:"sup",email:"sup@example.com",full_name:"Supervisor",is_active:true,is_platform_admin:false,preferred_language:"en",created_at:"2026-11-19"},active_organization:{id:"yard",name:"Yard",slug:"yard",org_type:"employer",enabled_tracks:["worksafe"],is_active:true,settings:{},created_at:"2026-11-19"},role:"supervisor",permissions:["org:read","workforce:read_aggregate"],tracks:["worksafe"],memberships:[]});
    render(<AuthProvider><LoginPage/></AuthProvider>);
    await waitFor(()=>expect(replaceMock).toHaveBeenCalledWith("/worksafe"));
  });

  it("submits OrganizationOnboardingCard in register mode and redirects to /dashboard", async () => {
    const user = userEvent.setup({ delay: null });
    vi.mocked(authService.registerOrganization).mockResolvedValue({
      user: {
        id: "u1",
        email: "admin@dubai-care.ae",
        full_name: "Dr. Tariq Saeed",
        is_active: true,
        is_platform_admin: false,
        preferred_language: "en",
        created_at: "2026-11-12T00:00:00Z",
      },
      active_organization: {
        id: "org-new",
        name: "Dubai Care Clinic",
        slug: "dubai-care-clinic",
        org_type: "clinic",
        enabled_tracks: ["core", "loop", "neuro", "worksafe"],
        is_active: true,
        settings: {},
        created_at: "2026-11-12T00:00:00Z",
      },
      role: "org_admin",
      permissions: ["org:read"],
      tracks: ["core", "loop", "neuro", "worksafe"],
      memberships: [],
    });

    render(
      <AuthProvider>
        <OrganizationOnboardingCard mode="register" />
      </AuthProvider>
    );

    await user.type(screen.getByLabelText(/organisation name/i), "Dubai Care Clinic");
    expect(screen.getByLabelText(/tenant slug/i)).toHaveValue("dubai-care-clinic");
    await user.selectOptions(screen.getByLabelText(/organisation type/i), "clinic");
    await user.type(screen.getByLabelText(/full name/i), "Dr. Tariq Saeed");
    await user.type(screen.getByLabelText(/admin email/i), "admin@dubai-care.ae");
    await user.type(screen.getByLabelText(/^password/i), "DubaiClinicPass123!");
    await user.click(screen.getByRole("button", { name: /continue/i }));
    await user.click(screen.getByRole("button", { name: /recova loop/i }));
    await user.click(screen.getByRole("button", { name: /continue/i }));
    await user.click(screen.getByRole("button", { name: /continue/i }));
    expect(screen.getByRole("checkbox", { name: /I confirm the shared/i })).not.toBeChecked();
    await user.click(screen.getByRole("checkbox", { name: /I confirm the shared/i }));
    await user.click(screen.getByRole("button", { name: /continue/i }));
    expect(authService.registerOrganization).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: /create organisation & sign in/i }));

    await waitFor(() => {
      expect(authService.registerOrganization).toHaveBeenCalledWith(
        expect.objectContaining({
          organization_name: "Dubai Care Clinic",
          primary_programme: "loop",
          enabled_tracks: ["loop"],
          organization_slug: "dubai-care-clinic",
          org_type: "clinic",
          admin_email: "admin@dubai-care.ae",
        })
      );
      expect(replaceMock).toHaveBeenCalledWith("/dashboard");
    });
  }, 15000);

  it("remounts AuthGuard children when active organisation switches", async () => {
    const user = userEvent.setup({ delay: null });
    const baseUser = {
      id: "u1",
      email: "admin@hub.ae",
      full_name: "Admin",
      is_active: true,
      is_platform_admin: true,
      preferred_language: "en",
      created_at: "2026-11-12T00:00:00Z",
    };
    const orgA = {
      id: "org-a",
      name: "Org A",
      slug: "org-a",
      org_type: "hospital",
      enabled_tracks: ["core"],
      is_active: true,
      settings: {},
      created_at: "2026-11-12T00:00:00Z",
    };
    const orgB = {
      id: "org-b",
      name: "Org B",
      slug: "org-b",
      org_type: "clinic",
      enabled_tracks: ["core"],
      is_active: true,
      settings: {},
      created_at: "2026-11-12T00:00:00Z",
    };

    vi.mocked(authService.me).mockResolvedValue({
      user: baseUser,
      active_organization: orgA,
      role: "platform_admin",
      permissions: ["org:read"],
      tracks: ["core"],
      memberships: [],
    });
    vi.mocked(authService.switchOrganization).mockResolvedValue({
      user: baseUser,
      active_organization: orgB,
      role: "platform_admin",
      permissions: ["org:read"],
      tracks: ["core"],
      memberships: [],
    });

    function TenantProbe() {
      const { session, switchOrganization } = useAuth();
      const [staleInput, setStaleInput] = useState("org-a-draft");
      return (
        <div>
          <span data-testid="active-org">{session?.active_organization?.slug}</span>
          <input aria-label="Draft" value={staleInput} onChange={(e) => setStaleInput(e.target.value)} />
          <button type="button" onClick={() => void switchOrganization("org-b")}>
            Switch to B
          </button>
        </div>
      );
    }

    render(
      <AuthProvider>
        <AuthGuard requiredPermission="org:read">
          <TenantProbe />
        </AuthGuard>
      </AuthProvider>
    );

    await waitFor(() => expect(screen.getByTestId("active-org")).toHaveTextContent("org-a"));
    const input = screen.getByLabelText("Draft");
    await user.clear(input);
    await user.type(input, "modified-in-a");
    expect(input).toHaveValue("modified-in-a");

    await user.click(screen.getByRole("button", { name: /switch to b/i }));
    await waitFor(() => expect(screen.getByTestId("active-org")).toHaveTextContent("org-b"));
    expect(screen.getByLabelText("Draft")).toHaveValue("org-a-draft");
  });
});
