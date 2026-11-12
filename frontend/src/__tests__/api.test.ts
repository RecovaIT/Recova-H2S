import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { api, ApiError, clearCsrfToken, setCsrfToken } from "@/lib/api";

describe("Recova API client", () => {
  beforeEach(() => {
    clearCsrfToken();
    document.cookie = "recova_csrf=; expires=Thu, 01 Jan 1970 00:00:00 GMT";
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("includes credentials and attaches X-CSRF-Token on mutating requests only", async () => {
    setCsrfToken("csrf-secret-123");
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { "content-type": "application/json" },
      })
    );
    vi.stubGlobal("fetch", fetchMock);

    await api.get("/auth/status");
    const getCall = fetchMock.mock.calls[0][1] as RequestInit;
    expect(getCall.credentials).toBe("include");
    expect((getCall.headers as Headers).get("X-CSRF-Token")).toBeNull();

    await api.post("/check-ins", { patient_id: "p1", track: "core" });
    const postCall = fetchMock.mock.calls[1][1] as RequestInit;
    expect(postCall.credentials).toBe("include");
    expect((postCall.headers as Headers).get("X-CSRF-Token")).toBe("csrf-secret-123");
  });

  it("parses structured backend AppError JSON responses cleanly", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          error: {
            code: "consent_missing",
            message: "Mandatory data_processing consent is not active",
            details: { scope: "data_processing" },
          },
          request_id: "req-999",
        }),
        {
          status: 403,
          headers: { "content-type": "application/json" },
        }
      )
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(api.post("/pipeline/runs", {})).rejects.toMatchObject({
      name: "ApiError",
      status: 403,
      code: "consent_missing",
      message: "Mandatory data_processing consent is not active",
      requestId: "req-999",
    });

    try {
      await api.post("/pipeline/runs", {});
    } catch (e) {
      expect(e).toBeInstanceOf(ApiError);
    }
  });
});
