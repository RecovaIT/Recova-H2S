import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import SettingsPage from "@/app/settings/page";
import { ToastProvider } from "@/components/ui/toast";
import { LanguageProvider } from "@/hooks/useLanguage";
import { opsService } from "@/services/ops";

vi.mock("next/navigation", () => ({
  usePathname: () => "/settings",
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), prefetch: vi.fn() }),
}));

vi.mock("@/hooks/useRealtimeEvents", () => ({
  useRealtimeEvents: () => ({ connected: true }),
}));

vi.mock("@/services/care", () => ({
  careService: {
    listNotifications: vi.fn().mockResolvedValue({ items: [], total: 0 }),
  },
}));

vi.mock("@/services/engine", () => ({
  engineService: {
    listEmergencies: vi.fn().mockResolvedValue([]),
  },
}));

vi.mock("@/hooks/useAuth", () => ({
  useAuth: () => ({
    loading: false,
    needsBootstrap: false,
    session: {
      user: {
        id: "u1",
        email: "admin@demo.recova.ae",
        full_name: "Facility Admin",
        is_platform_admin: false,
      },
      role: "org_admin",
      active_organization: {
        id: "org1",
        name: "Recova Demo Org",
        slug: "recova-demo",
        primary_programme: "core",
        enabled_tracks: ["core"],
      },
      memberships: [],
      permissions: ["org:read", "org:manage", "settings:read", "settings:manage"],
    },
    hasPermission: () => true,
    hasTrack: () => true,
    refreshSession: vi.fn().mockResolvedValue(undefined),
    switchOrganization: vi.fn(),
    logout: vi.fn(),
  }),
}));

vi.mock("@/services/ops", () => ({
  opsService: {
    listIntegrations: vi.fn(),
    listInsurancePlans: vi.fn(),
    listCareFacilities: vi.fn(),
    listProgrammeRequests: vi.fn(),
    getLlmKeyStatus: vi.fn(),
    upsertIntegration: vi.fn(),
    testIntegration: vi.fn(),
  },
}));

describe("Settings LLM defaults & automatic backend key lookup", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(opsService.listIntegrations).mockResolvedValue([
      {
        integration: "llm",
        status: "configured",
        enabled: true,
        settings: {},
        has_secrets: true,
        env_configured: true,
      },
    ]);
    vi.mocked(opsService.listInsurancePlans).mockResolvedValue([]);
    vi.mocked(opsService.listCareFacilities).mockResolvedValue([]);
    vi.mocked(opsService.listProgrammeRequests).mockResolvedValue([]);
    vi.mocked(opsService.upsertIntegration).mockResolvedValue({
      integration: "llm",
      status: "configured",
      enabled: true,
      settings: { provider: "openai", model: "gpt-4o-mini" },
      has_secrets: true,
      env_configured: false,
    });
  });

  it("defaults to Gemini, hides API Key input when backend VPS env key is active, and restores manual input when none found", async () => {
    const user = userEvent.setup();
    vi.mocked(opsService.getLlmKeyStatus).mockImplementation(async (provider = "gemini") => {
      if (provider === "gemini") {
        return {
          provider: "gemini",
          key_available: true,
          source: "backend_env",
          masked_key: "AIza••••••••9876",
          default_model: "gemini-2.0-flash",
          default_base_url: null,
        };
      }
      return {
        provider,
        key_available: false,
        source: "none",
        masked_key: null,
        default_model: "gpt-4o-mini",
        default_base_url: null,
      };
    });

    render(
      <ToastProvider>
        <LanguageProvider>
          <SettingsPage />
        </LanguageProvider>
      </ToastProvider>
    );

    const providerSelect = await screen.findByLabelText("Provider");
    expect(providerSelect).toHaveValue("gemini");
    expect(screen.getByLabelText("Model")).toHaveValue("gemini-2.0-flash");

    await waitFor(() => {
      expect(opsService.getLlmKeyStatus).toHaveBeenCalledWith("gemini");
    });

    // When routed via backend VPS env, the manual API key input is removed from DOM for security
    expect(await screen.findByText(/API Key Connected Automatically from Backend \(VPS\)/i)).toBeInTheDocument();
    expect(screen.getByText(/AIza••••••••9876/)).toBeInTheDocument();
    expect(screen.queryByLabelText(/API Key/i)).not.toBeInTheDocument();

    // Switch to OpenAI (no backend env key) -> renders the initial manual API Key input field
    await user.selectOptions(providerSelect, "openai");
    await waitFor(() => {
      expect(opsService.getLlmKeyStatus).toHaveBeenCalledWith("openai");
    });
    const apiKeyInput = await screen.findByLabelText(/API Key/i);
    expect(apiKeyInput).toHaveValue("");
    expect(screen.getByText(/No API key found in backend \(VPS\) env/i)).toBeInTheDocument();

    await user.type(apiKeyInput, "sk-manual-key-123");
    await user.click(screen.getByRole("button", { name: "Save LLM Integration" }));
    await waitFor(() => {
      expect(opsService.upsertIntegration).toHaveBeenCalledWith(
        "llm",
        expect.objectContaining({
          settings: expect.objectContaining({ provider: "openai", model: "gpt-4o-mini", use_backend_env: false }),
          secrets: { api_key: "sk-manual-key-123" },
        })
      );
    });

    // Switch to Anthropic where backend request itself fails -> still falls back cleanly to manual input
    vi.mocked(opsService.getLlmKeyStatus).mockRejectedValueOnce(new Error("502 Bad Gateway"));
    await user.selectOptions(providerSelect, "anthropic");
    await waitFor(() => {
      expect(opsService.getLlmKeyStatus).toHaveBeenCalledWith("anthropic");
    });
    expect(await screen.findByLabelText(/API Key/i)).toBeInTheDocument();
  });
});
