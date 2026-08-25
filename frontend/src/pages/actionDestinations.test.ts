import { describe, expect, it } from "vitest";

import { actionDestination } from "./actionDestinations";

describe("Stage E action destinations", () => {
  /* Both act on the draft the workspace is holding, so both resolve to it: the panel
     that reports the validation result and the dialog that approves it are already on
     that screen. */
  it("routes validation to the draft workspace", () => {
    expect(actionDestination("validate", "app 1")).toBe("/applications/app%201/draft");
  });

  it("routes approval to the draft workspace", () => {
    expect(actionDestination("approve", "app 1")).toBe("/applications/app%201/draft");
  });

  it("keeps review on its established destination", () => {
    expect(actionDestination("apply_analysis_decisions", "app-1")).toBe("/applications/app-1/review");
  });

  it("keeps draft editing on its established destination", () => {
    expect(actionDestination("update_working_draft", "app-1")).toBe("/applications/app-1/draft");
  });

  it("does not invent a destination for an unknown backend action", () => {
    expect(actionDestination("future_action", "app-1")).toBeNull();
  });
});
