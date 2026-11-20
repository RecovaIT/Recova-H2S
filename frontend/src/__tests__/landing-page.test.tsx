import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import HomePage from "@/app/page";

const { auth, replace } = vi.hoisted(() => ({
  auth: { session: null as null | { role: string }, needsBootstrap: true },
  replace: vi.fn(),
}));
vi.mock("@/hooks/useAuth", () => ({ useAuth: () => auth }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ replace }) }));
vi.mock("next/image", () => ({
  default: (props: { src: string; alt: string }) =>
    React.createElement("img", { src: props.src, alt: props.alt }),
}));

beforeEach(() => {
  cleanup();
  auth.session = null;
  vi.clearAllMocks();
});

describe("Public Recova landing page", () => {
  it("explains the platform without redirecting a visitor even before operator setup", () => {
    render(<HomePage />);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(
      /Care, onestep ahead/,
    );
    expect(screen.getByRole("tab", { name: /Recova Core/ })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(
      screen.getByRole("heading", { name: /shared public-health layer/ }),
    ).toBeInTheDocument();
    expect(replace).not.toHaveBeenCalled();
    expect(
      screen.getByRole("link", { name: "Find your programme" }),
    ).toHaveAttribute("href", "#programmes");
  });
  it("lets visitors explore programmes using clicks and the keyboard", async () => {
    const user = userEvent.setup();
    render(<HomePage />);
    await user.click(screen.getByRole("tab", { name: /Recova Loop/ }));
    expect(
      screen.getByRole("heading", {
        name: "Turn a screening result into a next step.",
      }),
    ).toBeInTheDocument();
    await user.keyboard("{End}");
    expect(screen.getByRole("tab", { name: /Recova WorkSafe/ })).toHaveFocus();
    expect(
      screen.getByRole("heading", { name: /Put people at the centre/ }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Choose Recova WorkSafe" }),
    ).toHaveAttribute("href", "/register-organization?programme=worksafe");
  });
  it("opens and dismisses the mobile menu with Escape and restores focus", async () => {
    const user = userEvent.setup();
    render(<HomePage />);
    await user.click(screen.getByRole("button", { name: "Open menu" }));
    expect(
      screen.getByRole("navigation", { name: "Mobile navigation" }),
    ).toBeInTheDocument();
    await user.tab();
    await user.keyboard("{Escape}");
    expect(
      screen.queryByRole("navigation", { name: "Mobile navigation" }),
    ).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Open menu" })).toHaveFocus();
  });
  it.each([
    ["patient", "/portal"],
    ["supervisor", "/worksafe"],
    ["authority_user", "/authority"],
    ["clinician", "/dashboard"],
  ])(
    "keeps the landing page public and links a signed-in %s to the right workspace",
    (role, href) => {
      auth.session = { role };
      render(<HomePage />);
      expect(
        screen.getByRole("link", { name: "Open workspace" }),
      ).toHaveAttribute("href", href);
      expect(replace).not.toHaveBeenCalled();
    },
  );
});
