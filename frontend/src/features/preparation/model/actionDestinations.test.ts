import { describe, expect, it } from "vitest";

import type { ApplicationListItem } from "@/api/contracts";
import { preparationResumeDestination } from "./actionDestinations";

const item = (overrides: Partial<ApplicationListItem>): ApplicationListItem =>
  ({
    id: "app-1",
    preparation_state: "needs_analysis",
    recommended_action: null,
    ...overrides,
  }) as ApplicationListItem;

describe("preparationResumeDestination", () => {
  it("follows the action recommended by the server projection", () => {
    expect(
      preparationResumeDestination(item({ preparation_state: "ready_for_approval", recommended_action: "approve" })),
    ).toBe("/applications/app-1/draft");
  });

  it("reopens an existing draft when no recommendation is present", () => {
    expect(preparationResumeDestination(item({ preparation_state: "draft_in_progress" }))).toBe(
      "/applications/app-1/draft",
    );
  });

  it("opens the exact rendered revision for a completed flow", () => {
    expect(
      preparationResumeDestination(
        item({ preparation_state: "ready", latest_ready_revision_id: "revision / 1" }),
      ),
    ).toBe("/revisions/revision%20%2F%201");
  });

  it("falls back to analysis when no later record exists", () => {
    expect(preparationResumeDestination(item({ preparation_state: "ready_to_draft" }))).toBe(
      "/applications/app-1",
    );
  });
});
