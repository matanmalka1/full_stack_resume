import { describe, expect, it } from "vitest";

import type { Classification } from "@/api/analyses";
import { changedKeys, matchingOrigin, matchingSubmission } from "./matchingConfiguration";

const current = {
  emphasis: "account-growth",
  language: "he",
  profile: "account-manager",
  track: "sales",
} as const;

const classification = (overrides: Partial<Classification> = {}): Classification =>
  ({ ...current, decided: [], ...overrides }) as Classification;

describe("the matching configuration form", () => {
  it("submits only the values that changed", () => {
    const next = { ...current, emphasis: "new-business" } as const;

    expect(changedKeys(current, next)).toEqual(["emphasis"]);
    expect(matchingSubmission(current, next)).toEqual({
      emphasis_override: "new-business",
      language_override: null,
      profile_override: null,
      track_override: null,
    });
  });

  it("names a value the reader decided apart from one the analysis proposed", () => {
    expect(matchingOrigin("track", classification())).toBe("analysis");
    expect(matchingOrigin("track", classification({ decided: ["track"] }))).toBe("decided");
    /* An Emphasis decision is recorded on the analysis like any other. */
    expect(matchingOrigin("emphasis", classification({ decided: ["emphasis"] }))).toBe("decided");
    expect(matchingOrigin("emphasis", classification())).toBe("analysis");
  });
});
