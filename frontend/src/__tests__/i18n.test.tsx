import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { LanguageProvider } from "@/hooks/useLanguage";
import { ToastProvider } from "@/components/ui/toast";
import { AppShell } from "@/components/AppShell";
import { LandingNavigation } from "@/components/marketing/LandingNavigation";
import { ProgrammeExplorer } from "@/components/marketing/ProgrammeExplorer";
import { watchIncomingPayload } from "@/lib/i18n-engine";

vi.mock("next/navigation", () => ({
  usePathname: () => "/dashboard",
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), prefetch: vi.fn() }),
}));

vi.mock("@/hooks/useAuth", () => ({
  useAuth: () => ({
    session: {
      user: {
        id: "u1",
        email: "clinician@recova.ae",
        full_name: "Dr. Layla Al Mansoori",
        is_platform_admin: false,
      },
      role: "clinician",
      active_organization: {
        id: "org1",
        name: "Al Amal Center",
        slug: "al-amal",
        primary_programme: "core",
        enabled_tracks: ["core"],
      },
      organizations: [
        {
          id: "org1",
          name: "Al Amal Center",
          slug: "al-amal",
          primary_programme: "core",
          enabled_tracks: ["core"],
        },
      ],
      memberships: [],
      permissions: ["org:read", "notifications:read"],
    },
    hasPermission: () => true,
    hasTrack: () => true,
    switchOrganization: vi.fn(),
    logout: vi.fn(),
  }),
}));

vi.mock("@/hooks/useRealtimeEvents", () => ({
  useRealtimeEvents: () => ({ connected: true }),
}));

vi.mock("@/services/care", () => ({
  careService: {
    listNotifications: vi.fn().mockResolvedValue({ items: [], total: 0 }),
    markNotificationRead: vi.fn(),
  },
}));

vi.mock("@/services/engine", () => ({
  engineService: {
    listEmergencies: vi.fn().mockResolvedValue([]),
  },
}));

describe("Root-level i18n dictionary, navbars, patterns, and live watcher", () => {
  afterEach(() => {
    window.localStorage.clear();
    document.documentElement.lang = "en";
    document.documentElement.dir = "ltr";
    vi.restoreAllMocks();
  });

  it("translates LandingNavigation navbar completely and toggles back to English", async () => {
    const user = userEvent.setup();
    render(
      <LanguageProvider>
        <LandingNavigation />
      </LanguageProvider>
    );

    expect(screen.getByText("Health intelligence, connected.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "The platform" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Toggle language" }));

    expect(document.documentElement.lang).toBe("ar");
    expect(document.documentElement.dir).toBe("rtl");
    expect(screen.getByText("ذكاء صحي متصل.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "المنصة" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "البرامج" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "فتح القائمة" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Toggle language" }));

    expect(document.documentElement.lang).toBe("en");
    expect(document.documentElement.dir).toBe("ltr");
    expect(screen.getByText("Health intelligence, connected.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "The platform" })).toBeInTheDocument();
  });

  it("translates AppShell, AppSidebar (collapsed + <option>), patterns, and live-arriving DOM/API data", async () => {
    const user = userEvent.setup();
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.includes("/i18n/translate")) {
        return new Response(
          JSON.stringify({
            target_lang: "ar",
            translations: {
              "Custom clinical ward outreach requested": "تم طلب تواصل سريري مخصص مع الجناح",
            },
          }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        );
      }
      return new Response(JSON.stringify({ catalog: {} }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    });

    const { container } = render(
      <ToastProvider>
        <LanguageProvider>
          <AppShell title="Care overview" subtitle="Your connected care workspace">
            <div>
              <h2>Population health</h2>
              <p>Active participants</p>
              <p>Overdue by 2d 4h</p>
              <p>Risk Tier: AMBER</p>
              <select aria-label="Role">
                <option value="clinician">Clinician</option>
              </select>
              <span data-no-translate="true">MRN-1001</span>
              <input placeholder="Search" />
              <div id="live-slot">Custom clinical ward outreach requested</div>
            </div>
          </AppShell>
        </LanguageProvider>
      </ToastProvider>
    );

    expect(await screen.findByRole("heading", { name: "Care overview" })).toBeInTheDocument();
    expect(document.documentElement.dir).toBe("ltr");

    // Pre-warm incoming backend payload before user switches language
    watchIncomingPayload({ note: "Custom clinical ward outreach requested", mrn: "MRN-1001" });

    await user.click(screen.getByRole("button", { name: "Toggle language" }));

    expect(document.documentElement.lang).toBe("ar");
    expect(document.documentElement.dir).toBe("rtl");
    expect(screen.getByRole("heading", { name: "نظرة عامة على الرعاية" })).toBeInTheDocument();
    expect(screen.getByText("مساحة الرعاية المتصلة الخاصة بك")).toBeInTheDocument();
    expect(screen.getByText("صحة السكان")).toBeInTheDocument();
    expect(screen.getByText("المشاركون النشطون")).toBeInTheDocument();
    expect(screen.getByText("متأخر بمقدار 2ي 4س")).toBeInTheDocument();
    expect(screen.getByText(/مستوى الخطر: كهرماني/)).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "طبيب سريري" })).toBeInTheDocument();
    expect(screen.getByPlaceholderText("بحث")).toBeInTheDocument();
    expect(screen.getByText("MRN-1001")).toBeInTheDocument();

    // Unseen incoming backend string resolved asynchronously via /i18n/translate watcher
    await waitFor(() => {
      expect(screen.getByText("تم طلب تواصل سريري مخصص مع الجناح")).toBeInTheDocument();
    });
    expect(fetchSpy).toHaveBeenCalled();

    // Dynamically inserted element AFTER switch is caught automatically by MutationObserver
    const dynamicEl = document.createElement("p");
    dynamicEl.textContent = "Approved";
    container.appendChild(dynamicEl);
    await waitFor(() => {
      expect(dynamicEl.textContent).toBe("معتمد");
    });

    await user.click(screen.getByRole("button", { name: "Toggle language" }));
    expect(document.documentElement.lang).toBe("en");
    expect(document.documentElement.dir).toBe("ltr");
    expect(screen.getByRole("heading", { name: "Care overview" })).toBeInTheDocument();
    expect(screen.getByText("Overdue by 2d 4h")).toBeInTheDocument();
    expect(dynamicEl.textContent).toBe("Approved");
  });

  it("switches ProgrammeExplorer engine selector tabs and copy between English and Arabic", async () => {
    const user = userEvent.setup();
    render(
      <LanguageProvider>
        <LandingNavigation />
        <ProgrammeExplorer />
      </LanguageProvider>
    );

    expect(screen.getByRole("tab", { name: /Recova Core/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Choose Recova Core/i })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Toggle language" }));

    expect(document.documentElement.lang).toBe("ar");
    expect(document.documentElement.dir).toBe("rtl");
    expect(screen.getByRole("tab", { name: /ريكوفا للتعافي/i })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /ريكوفا لوب/i })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /ريكوفا للأعصاب/i })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /ريكوفا لسلامة العمل/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /اختر ريكوفا للتعافي/i })).toBeInTheDocument();

    await user.click(screen.getByRole("tab", { name: /ريكوفا لوب/i }));
    expect(screen.getByRole("link", { name: /اختر ريكوفا لوب/i })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Toggle language" }));
    expect(screen.getByRole("link", { name: /Choose Recova Loop/i })).toBeInTheDocument();
  });
});
