import { describe, expect, it } from "vitest";

import type { ApplicationDetail } from "@/api/contracts";
import { HASH, detail as baseDetail } from "@/test/fixtures";
import { workflowActionPlan } from "./workflowActionPlan";

const detail = (overrides: Partial<ApplicationDetail> = {}): ApplicationDetail =>
  baseDetail({ available_actions: [], recommended_action: null, ...overrides });

/* §14 `build_from_analysis`: the one action on this screen that discards written work, and
   the reason it is explicit rather than something a newer analysis does by itself. */
describe("rebuilding from a newer analysis", () => {
  it("names the newer analysis and the exact document it re-pins", () => {
    const plan = workflowActionPlan(
      detail({
        latest_analysis_id: "analysis-2",
        document_analysis_id: "analysis-1",
        available_actions: ["build_from_analysis", "edit"],
      }),
    );

    expect(plan.buildFromAnalysis).toEqual({
      analysisId: "analysis-2",
      discardsContent: true,
      documentHash: HASH,
      emphasized: false,
    });
  });

  /* The projection stays the authority: a newer analysis alone does not talk this screen
     into offering the rebuild. */
  it("is withheld unless the projection offers it", () => {
    expect(workflowActionPlan(detail({ latest_analysis_id: "analysis-2" })).buildFromAnalysis).toBeNull();
  });

  it("loses nothing written while the document has no content", () => {
    const plan = workflowActionPlan(
      detail({
        preparation_state: "ready_to_draft",
        latest_analysis_id: "analysis-2",
        available_actions: ["build_from_analysis", "create_draft"],
        recommended_action: "create_draft",
      }),
    );

    expect(plan.buildFromAnalysis?.discardsContent).toBe(false);
    expect(plan.createDraft).toEqual({ documentHash: HASH, emphasized: true });
  });
});

describe("recommended action destinations", () => {
  it("handles the fact selection on the preparation screen", () => {
    const plan = workflowActionPlan(
      detail({
        preparation_state: "ready_to_draft",
        available_actions: ["update_selection", "propose_selection", "create_draft"],
        recommended_action: "update_selection",
      }),
    );

    expect(plan.selection).toEqual({ emphasized: true });
    expect(plan.unbuiltRecommendation).toBeNull();
  });

  /* The claim-level commands are controls in the editor, so a recommendation naming one of
     them is not unbuilt: a screen exists and the reason callouts beside this one link to it. */
  it("does not call a claim-level recommendation unbuilt", () => {
    for (const recommended of ["confirm_and_use_fact", "regenerate_claim", "regenerate_section"]) {
      const plan = workflowActionPlan(
        detail({ available_actions: ["edit", recommended], recommended_action: recommended }),
      );

      expect(plan.unbuiltRecommendation).toBeNull();
      expect(plan.draftScreen?.href).toBe("/applications/app-1/draft");
    }
  });

  it("routes rendering to the editor, where the approved document is rendered", () => {
    const plan = workflowActionPlan(
      detail({
        preparation_state: "approved",
        available_actions: ["analyze", "edit", "render"],
        recommended_action: "render",
      }),
    );

    expect(plan.draftScreen).toEqual({
      action: "render",
      emphasized: true,
      href: "/applications/app-1/draft",
      label: "יצירת קובץ קורות החיים",
    });
    expect(plan.unbuiltRecommendation).toBeNull();
  });

  /* The reason for the single-document model: Ready is not a dead end. The ready step is
     what the workflow is waiting on, and the editor stays offered as the way back. */
  it("offers the Ready document first and the editor as the way back to it", () => {
    const plan = workflowActionPlan(
      detail({
        preparation_state: "ready",
        available_actions: ["edit", "submit", "download_pdf"],
        recommended_action: "submit",
      }),
    );

    expect(plan.ready).toEqual({ emphasized: true, href: "/applications/app-1/ready" });
    expect(plan.draftScreen).toEqual({
      action: "edit",
      emphasized: false,
      href: "/applications/app-1/draft",
      label: "חזרה לעריכת הטיוטה",
    });
    expect(plan.createDraft).toBeNull();
    expect(plan.unbuiltRecommendation).toBeNull();
  });

  it("offers no ready step for a document that is not Ready", () => {
    expect(workflowActionPlan(detail({ available_actions: ["edit", "approve"] })).ready).toBeNull();
  });
});
