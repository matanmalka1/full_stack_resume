import { describe, expect, it } from "vitest";

import type { ApplicationDetail } from "@/api/contracts";
import { stageForPreparationState, workflowDestinations } from "./workflowStages";

const detail = (overrides: Partial<ApplicationDetail>) => overrides as ApplicationDetail;

describe("workflowDestinations", () => {
  it("keeps ready-to-draft on analysis until the document has content", () => {
    expect(stageForPreparationState.ready_to_draft).toBe("analysis");
    expect(
      workflowDestinations("app-1", detail({ document_id: "doc-1", preparation_state: "ready_to_draft" })),
    ).toEqual({ analysis: "/applications/app-1" });
  });

  it("offers the editor once the document has content", () => {
    expect(workflowDestinations("app-1", detail({}))).toEqual({
      analysis: "/applications/app-1",
    });
    expect(
      workflowDestinations("app-1", detail({ document_id: "doc-1", preparation_state: "draft_in_progress" })),
    ).toMatchObject({ draft: "/applications/app-1/draft" });
    /* Checking is not a stage, so it is not a destination either: it is a panel of the
       editor, and the editor is the draft stage's own screen. */
    expect(
      workflowDestinations("app-1", detail({ document_id: "doc-1", preparation_state: "draft_in_progress" })),
    ).not.toHaveProperty("validation");
  });

  /* Approval still has one explicit action left: rendering. The ready destination must
     not claim that an unrendered document is ready. */
  it("keeps an approved document in the draft stage until it is rendered", () => {
    const approved = detail({ document_id: "doc-1", preparation_state: "approved" });

    expect(stageForPreparationState.approved).toBe("draft");
    expect(workflowDestinations("app-1", approved)).toMatchObject({ draft: "/applications/app-1/draft" });
    expect(workflowDestinations("app-1", approved)).not.toHaveProperty("ready");
  });

  /* The reason the model changed: Ready is not the end of the road. The editor stays a
     destination beside it, so the rail offers the way back to the draft. */
  it("offers both the ready document and the way back to its draft", () => {
    expect(workflowDestinations("app-1", detail({ document_id: "doc-1", preparation_state: "ready" }))).toEqual({
      analysis: "/applications/app-1",
      draft: "/applications/app-1/draft",
      ready: "/applications/app-1/ready",
    });
  });
});
