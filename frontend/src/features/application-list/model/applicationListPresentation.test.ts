import { describe, expect, it } from "vitest";

import {
  formatApplicationDate,
  formatRelativeUpdate,
  isDueToday,
  isNextActionOverdue,
  preparationProgress,
} from "./applicationListPresentation";

describe("relative update dates", () => {
  const now = new Date(2026, 8, 9, 10, 0);
  const daysAgo = (days: number, hour = 12) => new Date(2026, 8, 9 - days, hour).toISOString();

  it("names the last week by the reader's local calendar day", () => {
    expect(formatRelativeUpdate(daysAgo(0, 1), now)).toBe("היום");
    expect(formatRelativeUpdate(daysAgo(1, 23), now)).toBe("אתמול");
    expect(formatRelativeUpdate(daysAgo(2), now)).toBe("לפני יומיים");
    expect(formatRelativeUpdate(daysAgo(6), now)).toBe("לפני 6 ימים");
  });

  it("falls back to the absolute date beyond a week, in the future, and keeps unparseable values", () => {
    expect(formatRelativeUpdate(daysAgo(7), now)).toBe(formatApplicationDate(daysAgo(7)));
    expect(formatRelativeUpdate(daysAgo(-1), now)).toBe(formatApplicationDate(daysAgo(-1)));
    expect(formatRelativeUpdate("not-a-date", now)).toBe("not-a-date");
  });
});

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
