import { describe, expect, it } from "vitest";

import { isDueToday, isNextActionOverdue } from "./applicationListPresentation";

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
