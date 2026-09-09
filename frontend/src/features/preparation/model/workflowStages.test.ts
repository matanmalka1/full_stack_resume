import { describe, expect, it } from "vitest";

import type { ApplicationDetail } from "@/api/contracts";
import { stageForPreparationState, workflowDestinations } from "./workflowStages";

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

  /* Approval still has one explicit action left: rendering. The ready destination must
     not claim that an unrendered revision is ready. */
  it("keeps an approved revision in the draft stage until a rendered revision exists", () => {
    expect(stageForPreparationState.approved).toBe("draft");
    expect(
      workflowDestinations(
        "app-1",
        detail({ preparation_state: "approved", latest_approved_revision_id: "rev-a" }),
      ),
    ).toMatchObject({ draft: "/applications/app-1/draft" });
    expect(
      workflowDestinations(
        "app-1",
        detail({ preparation_state: "approved", latest_approved_revision_id: "rev-a" }),
      ),
    ).not.toHaveProperty("ready");
  });

  it("names only the rendered ready revision", () => {
    expect(
      workflowDestinations("app-1", detail({ latest_approved_revision_id: "rev-a", latest_ready_revision_id: "rev-b" }))
        .ready,
    ).toBe("/revisions/rev-b");
  });
});
