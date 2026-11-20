import { beforeEach, describe, expect, it, vi } from "vitest";
import BootstrapAlias from "@/app/bootstrap/page";
import RegistrationAlias from "@/app/register-organization/page";
const { redirect } = vi.hoisted(() => ({
  redirect: vi.fn(() => {
    throw new Error("NEXT_REDIRECT");
  }),
}));
vi.mock("next/navigation", () => ({ redirect }));
beforeEach(() => vi.clearAllMocks());
describe("Legacy public auth addresses", () => {
  it("routes the old bootstrap address to public signup", () => {
    expect(() => BootstrapAlias()).toThrow("NEXT_REDIRECT");
    expect(redirect).toHaveBeenCalledWith("/signup");
  });
  it("preserves a valid programme selection from the old signup address", async () => {
    await expect(
      RegistrationAlias({
        searchParams: Promise.resolve({ programme: "worksafe" }),
      }),
    ).rejects.toThrow("NEXT_REDIRECT");
    expect(redirect).toHaveBeenCalledWith("/signup?programme=worksafe");
  });
  it("does not turn arbitrary query values into redirect targets", async () => {
    await expect(
      RegistrationAlias({
        searchParams: Promise.resolve({
          programme: "https://external.example.com",
        }),
      }),
    ).rejects.toThrow("NEXT_REDIRECT");
    expect(redirect).toHaveBeenCalledWith("/signup");
  });
});
