import { describe, expect, it } from "vitest";

import type { ApplicationListItem } from "@/api/contracts";
import { applicationAttention, preparationProgress } from "./resumePresentation";

/* The step bar reads its order from the label map. This pins that order to the one the
   specification lists (§4), so reordering the labels cannot silently reorder the bar. */
describe("preparation progress", () => {
  it("places each CV state in the specification's order", () => {
    const specOrder = ["needs_analysis", "ready_to_draft", "draft_in_progress", "approved", "ready"] as const;

    specOrder.forEach((state, index) => {
      expect(preparationProgress(state)).toEqual({ step: index + 1, total: specOrder.length });
    });
  });
});

describe("application attention", () => {
  const application = (overrides: Partial<ApplicationListItem> = {}): ApplicationListItem =>
    ({ id: "a", review_reasons: [], warnings: [], ...overrides }) as ApplicationListItem;

  const reason = {
    code: "PENDING_FACT_REQUIRES_RESOLUTION",
    message: "m",
    entity_references: {},
    allowed_resolution_actions: [],
  };
  const warning = { code: "DOCUMENT_ON_OLDER_ANALYSIS", message: "m", entity_references: {} };

  /* A warning disables nothing, so only a review reason asks for the reader. */
  it("answers only for a review reason", () => {
    expect(applicationAttention(application({ warnings: [warning] }))).toBeNull();
    expect(applicationAttention(application({ review_reasons: [reason] }))).not.toBeNull();
  });
});
