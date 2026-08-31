import { afterEach, describe, expect, it, vi } from "vitest";

import { captureClaimFact, confirmAndUseFact, transitionFact } from "./facts";

const json = (value: unknown, status = 200) =>
  new Response(JSON.stringify(value), {
    status,
    headers: { "Content-Type": "application/json" },
  });

afterEach(() => vi.unstubAllGlobals());

describe("fact lifecycle transport", () => {
  it("captures exact claim context with explicit provenance", async () => {
    const fetchMock = vi.fn().mockResolvedValue(json({ fact: { fact_id: "fact-1" } }, 201));
    vi.stubGlobal("fetch", fetchMock);

    await captureClaimFact({
      application_id: "app-1",
      claim_id: "claim-1",
      source: "development.md",
      meaning: "Owned migration",
      english: "Owned migration",
      tags: ["ownership"],
      provenance: "Confirmed from performance review",
      reason: "captured from the contextual draft claim flow",
    });

    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/v1/facts/from-claim");
    expect(JSON.parse(String(fetchMock.mock.calls[0]?.[1]?.body))).toMatchObject({
      application_id: "app-1",
      claim_id: "claim-1",
      provenance: "Confirmed from performance review",
    });
  });

  it("requires the explicit confirmation flag for lifecycle changes", async () => {
    const fetchMock = vi.fn().mockImplementation(() =>
      Promise.resolve(json({ fact: { fact_id: "fact-1" } })),
    );
    vi.stubGlobal("fetch", fetchMock);

    await transitionFact("fact-1", "confirm", {
      confirm: true,
      reason: "explicit Web confirmation",
    });
    await confirmAndUseFact("fact-1", {
      application_id: "app-1",
      job_analysis_id: "analysis-1",
      profile: "development",
      section: "Experience",
      reason: "confirmed from the contextual draft claim flow",
    });

    expect(JSON.parse(String(fetchMock.mock.calls[0]?.[1]?.body))).toEqual({
      confirm: true,
      reason: "explicit Web confirmation",
    });
    expect(fetchMock.mock.calls[1]?.[0]).toBe("/api/v1/facts/fact-1/confirm-and-use");
  });
});
