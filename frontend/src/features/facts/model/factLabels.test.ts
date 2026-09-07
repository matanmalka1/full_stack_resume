import { describe, expect, it } from "vitest";

import type { Fact } from "@/api/contracts";
import { factLabel, factLabelInLanguage, factSourceLabel, factStatusLabel, isCrossTrackFact } from "./factLabels";

const fact = (overrides: Partial<Fact> = {}): Fact => ({
  confirmed_at: null,
  effective_dates: null,
  fact_id: "fact.a",
  link_target: null,
  meaning: "Led a B2B sales team",
  provenance: "Confirmed by candidate",
  renderings: { en: "Led a B2B sales team of six" },
  replaces: null,
  resume_style: "bullet",
  source: "sales.md",
  status: "canonical",
  tags: ["sales"],
  ...overrides,
});

describe("how a fact is named on screen", () => {
  /* Two chains, deliberately different. The interface is Hebrew, so a fact listed in it
     leads with its Hebrew rendering; a fact read inside a draft leads with the draft's
     own language and falls through to English, never to Hebrew, because a Hebrew line in
     an English CV would be the wrong wording rather than a missing one. Unifying these
     is the regression this test exists to catch. */
  it("leads with Hebrew in the interface and with the reading language in a draft", () => {
    const bilingual = fact({ renderings: { en: "Led a team", he: "הובלתי צוות" } });

    expect(factLabel(bilingual)).toBe("הובלתי צוות");
    expect(factLabelInLanguage(bilingual, "en")).toBe("Led a team");
  });

  it("falls through to English, and never to Hebrew, for a language the fact was not written in", () => {
    const bilingual = fact({ renderings: { en: "Led a team", he: "הובלתי צוות" } });

    expect(factLabelInLanguage(bilingual, "fr")).toBe("Led a team");
  });

  /* A fact always carries a meaning, so nothing ever renders as an empty label. */
  it("falls back to the stored meaning when the fact carries no rendering at all", () => {
    const bare = fact({ renderings: {} });

    expect(factLabel(bare)).toBe("Led a B2B sales team");
    expect(factLabelInLanguage(bare, "he")).toBe("Led a B2B sales team");
  });
});

describe("the fact vocabulary", () => {
  it("translates the statuses and sources the contract declares", () => {
    expect(factStatusLabel("pending")).toBe("ממתינה לאישור");
    expect(factStatusLabel("canonical")).toBe("מקור אמת");
    expect(factSourceLabel("development.md")).toBe("ניסיון בפיתוח");
  });

  /* Status and source arrive as open strings. A value the backend adds before this
     interface knows it must read as itself rather than as an empty slot. */
  it("shows an unknown status or source as itself rather than as nothing", () => {
    expect(factStatusLabel("superseded")).toBe("superseded");
    expect(factSourceLabel("volunteering.md")).toBe("volunteering.md");
  });
});

describe("attaching a fact across career tracks", () => {
  it("names the mismatch when the fact belongs to the other track", () => {
    expect(isCrossTrackFact("development.md", "sales.md")).toBe(true);
  });

  it("stays quiet when the fact is already on the active track", () => {
    expect(isCrossTrackFact("sales.md", "sales.md")).toBe(false);
  });

  /* Shared and situational facts are written to be reused across tracks, so attaching
     one is ordinary rather than something to warn about. */
  it("treats the track-neutral sources as belonging everywhere", () => {
    expect(isCrossTrackFact("common.md", "sales.md")).toBe(false);
    expect(isCrossTrackFact("situational_skills.md", "development.md")).toBe(false);
  });

  /* With no active Profile there is no track to be crossing, and a warning would be
     naming a conflict that does not exist. */
  it("raises nothing when there is no active Profile to compare against", () => {
    expect(isCrossTrackFact("development.md", null)).toBe(false);
  });
});
