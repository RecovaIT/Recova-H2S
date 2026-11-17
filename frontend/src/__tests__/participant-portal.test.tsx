import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ParticipantPortal from "@/app/portal/page";
import { api } from "@/lib/api";

vi.mock("next/navigation", () => ({ useRouter: () => ({ replace: vi.fn() }) }));
vi.mock("@/hooks/useAuth", () => ({ useAuth: () => ({ session: { role: "patient" }, loading: false, logout: vi.fn() }) }));
vi.mock("@/lib/api", () => ({ api: { get: vi.fn(), post: vi.fn() } }));

const participant = {
  name: "Amara", track: "core", facility: "Synthetic Recovery Centre", synthetic: true,
  scenario: "Stable recovery", consents: ["data_processing", "wearable_ingestion"],
  observations: [], checkins: [], care: [], notices: [], acknowledged: [], referrals: [],
};

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(api.get).mockResolvedValue(participant);
  vi.mocked(api.post).mockResolvedValue({ emergency: false });
});
afterEach(cleanup);

describe("Participant programme journeys", () => {
  it.each([
    ["core", "Recovery", "One day at a time."],
    ["loop", "Health Loop", "Your next step to better health."],
    ["neuro", "Brain Health", "A little practice. A clearer picture."],
    ["worksafe", "WorkSafe", "Start your shift with you."],
  ])("shows the %s enrolled experience", async (track, name, heading) => {
    vi.mocked(api.get).mockResolvedValue({ ...participant, track });
    render(<ParticipantPortal />);
    expect(await screen.findByRole("heading", { name: heading })).toBeInTheDocument();
    expect(screen.getByText(`Your ${name} space`)).toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: "Patient navigation" })).toBeInTheDocument();
  });

  it("submits a scoped reflection and confirms receipt", async () => {
    const user = userEvent.setup();
    render(<ParticipantPortal />);
    await screen.findByRole("heading", { name: "Hello, Amara" });
    await user.click(screen.getByRole("button", { name: "Check in" }));
    await user.type(screen.getByPlaceholderText("Share what feels important to you…"), "A settled day");
    await user.click(screen.getByRole("button", { name: "Send to my care team" }));
    await waitFor(() => expect(api.post).toHaveBeenCalledWith("/portal/check-ins", expect.objectContaining({ text: "A settled day", mood: 6, stress: 3 })));
    expect(await screen.findByRole("button", { name: "Check-in received" })).toBeDisabled();
    const payload = vi.mocked(api.post).mock.calls[0][1] as Record<string, unknown>;
    expect(payload).not.toHaveProperty("patient_id");
  });

  it("keeps submission unavailable while care-data permission is absent", async () => {
    vi.mocked(api.get).mockResolvedValue({ ...participant, consents: [] });
    const user = userEvent.setup();
    render(<ParticipantPortal />);
    await screen.findByText("Your permission comes first");
    await user.click(screen.getByRole("button", { name: "Check in" }));
    expect(screen.getByRole("button", { name: "Send to my care team" })).toBeDisabled();
  });

  it("records a wearable privacy change through the scoped API", async () => {
    const user = userEvent.setup();
    render(<ParticipantPortal />);
    await screen.findByRole("heading", { name: "Hello, Amara" });
    await user.click(screen.getByRole("button", { name: "Your profile and privacy" }));
    await user.click(screen.getByRole("switch", { name: "Wearable readings" }));
    await waitFor(() => expect(api.post).toHaveBeenCalledWith("/portal/consents", { scope: "wearable_ingestion", granted: false }));
  });
});
