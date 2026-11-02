import { describe, expect, it } from "vitest";

import type { ApplicationListItem } from "@/api/contracts";
import {
  attentionHubItems,
  formatApplicationDate,
  formatRelativeUpdate,
  isDueToday,
  isNextActionOverdue,
  isDueThisWeek,
  preparationProgress,
} from "./applicationListPresentation";

describe("relative update dates", () => {
  const now = new Date(2026, 8, 9, 10, 0);
  const daysAgo = (days: number, hour = 12) => new Date(2026, 8, 9 - days, hour).toISOString();

  it("names today by the hour and the rest of the week by the reader's local calendar day", () => {
    expect(formatRelativeUpdate(new Date(2026, 8, 9, 9, 30).toISOString(), now)).toBe("עכשיו");
    expect(formatRelativeUpdate(daysAgo(0, 1), now)).toBe("לפני 9 שע׳");
    expect(formatRelativeUpdate(daysAgo(1, 23), now)).toBe("אתמול");
    expect(formatRelativeUpdate(daysAgo(2), now)).toBe("לפני יומיים");
    expect(formatRelativeUpdate(daysAgo(6), now)).toBe("לפני 6 ימים");
  });

  it("falls back to the absolute date beyond a week, in the future, and keeps unparseable values", () => {
    expect(formatRelativeUpdate(daysAgo(7), now)).toBe(`ב־${formatApplicationDate(daysAgo(7))}`);
    expect(formatRelativeUpdate(daysAgo(-1), now)).toBe(`ב־${formatApplicationDate(daysAgo(-1))}`);
    expect(formatRelativeUpdate("not-a-date", now)).toBe("not-a-date");
  });
});

/* The card's step bar reads its order from the label map. This pins that order to the
   one the specification lists (§4), so reordering the labels cannot silently reorder
   the bar. */
describe("preparation progress", () => {
  it("places each CV state in the specification's order", () => {
    const specOrder = ["needs_analysis", "ready_to_draft", "draft_in_progress", "approved", "ready"] as const;

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
    expect(isDueThisWeek("2026-09-02", localToday)).toBe(false);
    expect(isDueThisWeek("2026-09-03", localToday)).toBe(true);
    expect(isDueThisWeek("2026-09-08", localToday)).toBe(true);
    expect(isDueThisWeek("2026-09-09", localToday)).toBe(false);
  });

  it("rejects malformed and impossible reminder dates consistently", () => {
    for (const value of [null, "", "2026-02-29", "2026-09-02T00:00:00Z", "not-a-date"]) {
      expect(isNextActionOverdue(value, localToday)).toBe(false);
      expect(isDueToday(value, localToday)).toBe(false);
      expect(isDueThisWeek(value, localToday)).toBe(false);
    }
  });
});

describe("action hub items", () => {
  const today = new Date(2026, 8, 2, 12, 0);
  const application = (id: string, overrides: Partial<ApplicationListItem> = {}): ApplicationListItem =>
    ({
      id,
      company: id,
      target_role: "Engineer",
      recruitment_status: "applied",
      preparation_state: "draft_in_progress",
      review_reasons: [],
      warnings: [],
      recommended_action: null,
      is_closed: false,
      ...overrides,
    }) as ApplicationListItem;

  /* One row per Application, the most pressing source winning, in the order overdue,
     today, a projected reason, this week, Ready. Closed and quiet Applications ask for
     nothing. */
  it("orders what waits by urgency and gives each row the way to where it is done", () => {
    const items = attentionHubItems(
      [
        application("ready", { preparation_state: "ready" }),
        application("week", { next_action: "Call back", next_action_date: "2026-09-05" }),
        application("reason", {
          warnings: [{ code: "ANALYSIS_LOW_CONFIDENCE", message: "low", entity_references: {} }],
        }),
        application("today", { next_action: "Interview", next_action_date: "2026-09-02" }),
        application("late", {
          next_action: "Send portfolio",
          next_action_date: "2026-08-30",
          warnings: [{ code: "ANALYSIS_LOW_CONFIDENCE", message: "low", entity_references: {} }],
        }),
        application("closed", { is_closed: true, next_action: "Old", next_action_date: "2026-08-01" }),
        application("quiet"),
      ],
      today,
    );

    expect(items.map((item) => [item.application.id, item.type, item.label, item.to])).toEqual([
      ["late", "overdue", "באיחור", "/applications/late"],
      ["today", "due_today", "היום", "/applications/today"],
      ["reason", "attention", "דורש טיפול", "/applications/reason/draft"],
      ["week", "due_this_week", "השבוע", "/applications/week"],
      ["ready", "ready", "מוכן", "/applications/ready/ready"],
    ]);
    expect(items[0]?.title).toBe("Send portfolio");
  });
});
