import { describe, expect, it } from "vitest";

import { actionDestination } from "./actionDestinations";

describe("Stage E action destinations", () => {
  it("routes validation from the Application projection", () => {
    expect(actionDestination("validate", "app 1")).toBe("/applications/app%201/validation");
  });

  it("routes approval from the Application projection", () => {
    expect(actionDestination("approve", "app 1")).toBe("/applications/app%201/approval");
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
