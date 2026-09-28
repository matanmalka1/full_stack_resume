import { describe, expect, it } from "vitest";

import type { Classification } from "@/api/analyses";
import type { ApplicationDetail } from "@/api/contracts";
import { changedKeys, createsAnalysis, matchingOrigin, matchingSubmission } from "./matchingConfiguration";

const current = {
  emphasis: "account-growth",
  language: "he",
  profile: "account-manager",
  track: "sales",
} as const;

const classification = (overrides: Partial<Classification> = {}): Classification =>
  ({ ...current, decided: [], ...overrides }) as Classification;

const detail = (analysisEmphasis: string): ApplicationDetail =>
  ({ latest_analysis: { analysis: { emphasis: analysisEmphasis } } }) as unknown as ApplicationDetail;

describe("the matching configuration form", () => {
  it("submits only the values that changed, and says whether a new analysis follows", () => {
    const next = { ...current, emphasis: "new-business" } as const;

    expect(changedKeys(current, next)).toEqual(["emphasis"]);
    expect(matchingSubmission(current, next)).toEqual({
      emphasis_override: "new-business",
      language_override: null,
      profile_override: null,
      track_override: null,
    });
    expect(createsAnalysis(["emphasis"])).toBe(false);
    expect(createsAnalysis(["emphasis", "profile"])).toBe(true);
  });

  it("names a value the reader decided apart from one the analysis proposed", () => {
    expect(matchingOrigin("track", classification(), detail("account-growth"))).toBe("analysis");
    expect(matchingOrigin("track", classification({ decided: ["track"] }), detail("account-growth"))).toBe("decided");
    /* Emphasis is effective at plan level: differing from the analysis' own value means
       it was chosen, even with no override recorded on the analysis. */
    expect(matchingOrigin("emphasis", classification(), detail("new-business"))).toBe("decided");
    expect(matchingOrigin("emphasis", classification(), detail("account-growth"))).toBe("analysis");
  });
});
