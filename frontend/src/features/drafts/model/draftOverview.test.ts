import { describe, expect, it } from "vitest";

import type { ApplicationDetail, DraftClaim, DraftFact } from "@/api/contracts";
import { cvDocument, detail as projection } from "@/test/fixtures";
import { draftSteps, summarizeContent, summarizeSelection } from "./draftOverview";
import type { EditableDocument } from "./drafts.types";

const line = (claim_id: string, claim_type: DraftClaim["claim_type"], fact_ids: string[] = []): DraftClaim => ({
  claim_id,
  claim_type,
  fact_ids,
  style: "bullet",
  text: claim_id,
});

const fact = (fact_id: string, overrides: Partial<DraftFact> = {}): DraftFact => ({
  fact_id,
  linked_claim_ids: [],
  outcome: "selected",
  reason: null,
  section: "Experience",
  text: fact_id,
  ...overrides,
});

const documentWith = (claims: DraftClaim[], facts: DraftFact[] = [], headline = line("h", "headline")) =>
  cvDocument({
    facts,
    outline: { headline, contacts: [], sections: [{ name: "Experience", claims }] },
  }) as EditableDocument;

describe("summarizeContent", () => {
  it("folds claim types into where each body line came from", () => {
    const summary = summarizeContent(
      documentWith([
        line("a", "canonical", ["f"]),
        line("b", "derived", ["f"]),
        line("c", "composite", ["f", "g"]),
        line("d", "reviewed", ["f"]),
        line("e", "pending"),
      ]),
    );

    expect(summary).toMatchObject({ verbatim: 1, reworded: 3, unsupported: 1 });
    expect(summary.unsupportedClaims.map((claim) => claim.claim_id)).toEqual(["e"]);
  });

  it("lists an unsupported headline as blocking without counting it as a body line", () => {
    const summary = summarizeContent(documentWith([line("a", "canonical", ["f"])], [], line("h", "pending")));

    expect(summary.unsupported).toBe(0);
    expect(summary.unsupportedClaims.map((claim) => claim.claim_id)).toEqual(["h"]);
  });
});

describe("summarizeSelection", () => {
  it("counts only what the selection ranked, and offers only omitted facts nothing rests on", () => {
    const summary = summarizeSelection(
      documentWith(
        [],
        [
          fact("selected"),
          fact("pinned", { outcome: "pinned" }),
          fact("rescued", { outcome: "rescued" }),
          fact("budget", { outcome: "omitted", reason: "below_section_budget" }),
          fact("budget-2", { outcome: "omitted", reason: "below_section_budget" }),
          fact("user", { outcome: "omitted", reason: "excluded_by_user" }),
          fact("still-linked", { outcome: "omitted", linked_claim_ids: ["c"] }),
          fact("contact", { outcome: null }),
        ],
      ),
    );

    expect(summary.included).toBe(3);
    expect(summary.pinned).toBe(1);
    expect(summary.omitted.map((item) => item.fact_id)).toEqual(["budget", "budget-2", "user"]);
  });
});

describe("draftSteps", () => {
  const steps = (overrides: Partial<ApplicationDetail>, claims: DraftClaim[] = [line("a", "canonical", ["f"])]) =>
    draftSteps(projection(overrides), summarizeContent(documentWith(claims))).map((step) => step.status);

  it("starts at the check when every line is backed and nothing was checked", () => {
    expect(steps({ content_check: "none", preparation_state: "draft_in_progress", review_reasons: [] })).toEqual([
      "done",
      "current",
      "upcoming",
    ]);
  });

  it("holds at the content while a line has nothing behind it, even after a passing check", () => {
    expect(
      steps({ content_check: "passed", preparation_state: "draft_in_progress", review_reasons: [] }, [
        line("e", "pending"),
      ]),
    ).toEqual(["blocked", "upcoming", "upcoming"]);
  });

  it("moves to approval once the check passed on backed content", () => {
    expect(steps({ content_check: "passed", preparation_state: "draft_in_progress", review_reasons: [] })).toEqual([
      "done",
      "done",
      "current",
    ]);
  });

  it("reports every step done once the projection says the document is approved", () => {
    expect(steps({ content_check: "passed", preparation_state: "approved", review_reasons: [] })).toEqual([
      "done",
      "done",
      "done",
    ]);
  });
});
