import { describe, expect, it } from "vitest";

import type { ApplicationListItem } from "@/api/contracts";
import {
  attentionHubItems,
  formatApplicationDate,
  formatRelativeUpdate,
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

describe("action hub items", () => {
  const application = (id: string, overrides: Partial<ApplicationListItem> = {}): ApplicationListItem =>
    ({
      id,
      company: id,
      target_role: "Engineer",
      preparation_state: "draft_in_progress",
      review_reasons: [],
      warnings: [],
      recommended_action: null,
      ...overrides,
    }) as ApplicationListItem;

  const reason = {
    code: "PENDING_FACT_REQUIRES_RESOLUTION",
    message: "m",
    entity_references: {},
    allowed_resolution_actions: [],
  };
  const warning = { code: "DOCUMENT_ON_OLDER_ANALYSIS", message: "m", entity_references: {} };

  /* One row per Application a review reason blocks, each the way to the step that
     resolves it. A warning disables nothing and a Ready CV waits on nothing the board
     can clear, so neither is listed. */
  it("lists only what a review reason blocks", () => {
    const items = attentionHubItems([
      application("ready", { preparation_state: "ready" }),
      application("warned", { warnings: [warning] }),
      application("blocked", { review_reasons: [reason], warnings: [warning] }),
      application("quiet"),
    ]);

    expect(items.map((item) => [item.application.id, item.to])).toEqual([["blocked", "/applications/blocked/draft"]]);
  });
});
