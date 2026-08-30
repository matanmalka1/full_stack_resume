import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiProblem, apiRequest } from "./client";

afterEach(() => vi.unstubAllGlobals());

describe("apiRequest error boundary", () => {
  it("preserves backend Problem Details", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            type: "about:blank#state_conflict",
            title: "Conflict",
            status: 409,
            code: "STATE_CONFLICT",
            detail: "The state moved.",
          }),
          { status: 409, headers: { "Content-Type": "application/problem+json" } },
        ),
      ),
    );

    await expect(apiRequest("/api/v1/example")).rejects.toMatchObject({
      problem: { code: "STATE_CONFLICT", status: 409 },
    });
  });

  it("normalizes network failures without exposing browser exception text", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("secret transport detail")));

    try {
      await apiRequest("/api/v1/example");
      throw new Error("Expected the request to fail");
    } catch (error) {
      expect(error).toBeInstanceOf(ApiProblem);
      expect(error).toMatchObject({
        problem: { code: "NETWORK_UNAVAILABLE", status: 0 },
      });
      expect(String(error)).not.toContain("secret transport detail");
    }
  });

  it("normalizes malformed successful JSON", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response("not-json", { status: 200, headers: { "Content-Type": "application/json" } }),
      ),
    );

    await expect(apiRequest("/api/v1/example")).rejects.toMatchObject({
      problem: { code: "INVALID_SERVER_RESPONSE", status: 0 },
    });
  });
});
