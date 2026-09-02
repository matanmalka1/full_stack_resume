import { describe, expect, it } from "vitest";

import type { ApplicationDetail } from "../api/contracts";
import { workflowDestinations } from "./WorkflowLandmark";

const detail = (overrides: Partial<ApplicationDetail>) => overrides as ApplicationDetail;

describe("workflowDestinations", () => {
  it("offers the editor only once a working draft exists", () => {
    expect(workflowDestinations("app-1", detail({}))).toEqual({
      analysis: "/applications/app-1/preparation",
    });
    expect(workflowDestinations("app-1", detail({ active_working_draft_id: "draft-1" }))).toMatchObject({
      draft: "/applications/app-1/draft",
    });
    /* Validation is not a stage, so it is not a destination either: it is a panel of the
       editor, and the editor is the draft stage's own screen. */
    expect(workflowDestinations("app-1", detail({ active_working_draft_id: "draft-1" }))).not.toHaveProperty(
      "validation",
    );
  });

  /* A rendered revision is what "מוכן" means to the reader; the approved one answers only
     while no render exists yet. */
  it("names the ready revision, preferring the rendered one", () => {
    expect(workflowDestinations("app-1", detail({ latest_approved_revision_id: "rev-a" })).ready).toBe(
      "/revisions/rev-a",
    );
    expect(
      workflowDestinations("app-1", detail({ latest_approved_revision_id: "rev-a", latest_ready_revision_id: "rev-b" }))
        .ready,
    ).toBe("/revisions/rev-b");
  });
});
