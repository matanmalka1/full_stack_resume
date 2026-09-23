import { describe, expect, it } from "vitest";

import { isDueToday, isNextActionOverdue, preparationProgress } from "./applicationListPresentation";

/* The row's step bar reads its order from the label map. This pins that order to the
   one the specification lists (§4), so reordering the labels cannot silently reorder
   the bar. */
describe("preparation progress", () => {
  it("places each CV state in the specification's order", () => {
    const specOrder = [
      "needs_analysis",
      "needs_review",
      "ready_to_draft",
      "draft_in_progress",
      "ready_for_approval",
      "approved",
      "ready",
    ] as const;

    specOrder.forEach((state, index) => {
      expect(preparationProgress(state)).toEqual({ step: index + 1, total: specOrder.length });
    });
  });
});

describe("next-action calendar dates", () => {
  const localToday = new Date(2026, 8, 2, 23, 30);

  it("compares date-only reminders with the reader's local calendar day", () => {
    expect(isNextActionOverdue("2026-09-01", localToday)).toBe(true);
    expect(isNextActionOverdue("2026-09-02", localToday)).toBe(false);
    expect(isDueToday("2026-09-02", localToday)).toBe(true);
    expect(isDueToday("2026-09-03", localToday)).toBe(false);
  });

  it("rejects malformed and impossible reminder dates consistently", () => {
    for (const value of [null, "", "2026-02-29", "2026-09-02T00:00:00Z", "not-a-date"]) {
      expect(isNextActionOverdue(value, localToday)).toBe(false);
      expect(isDueToday(value, localToday)).toBe(false);
    }
  });
});
