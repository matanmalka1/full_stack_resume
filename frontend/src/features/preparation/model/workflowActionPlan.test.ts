import { describe, expect, it } from "vitest";

import type { ApplicationDetail, Reason } from "@/api/contracts";
import { workflowActionPlan, hasWorkflowActionsContent } from "./workflowActionPlan";

/* §14. The two stale-draft commands are the only actions this screen sends that are
   addressed to a specific version of a specific record, and the only ones whose wrong
   answer destroys something no re-run reproduces. What they are offered on is therefore
   worth asserting on its own, without a DOM: the rules are about what the projection
   permits, and rendering a screen to read them back would be testing the buttons instead
   of the gate. */

const staleReason: Reason = {
  code: "DRAFT_SOURCES_MOVED",
  message: "the analysis in force is newer than the draft",
  entity_references: {},
  allowed_resolution_actions: ["replace_working_draft", "archive_working_draft"],
};

/* A draft exists and its sources moved: the state both commands answer. Each test below
   removes exactly one of the conditions from this. */
const staleDetail = (overrides: Partial<ApplicationDetail> = {}): ApplicationDetail =>
  ({
    recruitment_status: "saved",
    allowed_recruitment_transitions: [],
    recruitment_timeline: [],
    preparation_state: "ready_to_draft",
    working_draft_state: "editing",
    review_reasons: [],
    stale_reasons: [staleReason],
    warnings: [],
    active_job_snapshot_id: "snap-1",
    active_analysis_id: "analysis-1",
    active_selection_plan_id: "plan-1",
    active_working_draft_id: "draft-1",
    newer_draft_in_progress: false,
    available_actions: ["replace_working_draft", "archive_working_draft"],
    blocked_actions: [],
    recommended_action: null,
    application: {
      id: "app-1",
      company: "Acme",
      target_role: "Backend Engineer",
      current_status: "saved",
      notes: "",
      source: "manual",
      created_at: "2026-08-24T07:00:00Z",
      updated_at: "2026-08-24T07:00:00Z",
    },
    ...overrides,
  }) as ApplicationDetail;

describe("the way out of a stale draft (§14)", () => {
  /* Both conditions, and the ids each command must carry. The ids are asserted rather
     than merely the offer, because a command sent without them is refused by the server
     for a broken lineage - so a plan that offered the button while dropping one would
     produce a button that cannot work. */
  it("offers both commands with the exact ids when the draft is stale and the workflow permits it", () => {
    const plan = workflowActionPlan(staleDetail());

    expect(plan.replaceDraft).toEqual({
      analysisId: "analysis-1",
      emphasized: false,
      selectionPlanId: "plan-1",
      workingDraftId: "draft-1",
    });
    expect(plan.archiveDraft).toEqual({ workingDraftId: "draft-1" });
  });

  /* The projection stays the authority on whether the workflow permits a command. A draft
     can be stale in a state that still forbids replacing it, and staleness alone must not
     talk this screen into sending one. */
  it("withholds both when the draft is stale but the workflow does not permit them", () => {
    const plan = workflowActionPlan(staleDetail({ available_actions: [] }));

    expect(plan.replaceDraft).toBeNull();
    expect(plan.archiveDraft).toBeNull();
  });

  /* And the converse. `available_actions` may well permit replacing a draft that is not
     stale, but this screen offers the pair as the way out of the alert above them: with
     nothing reported as out of date, a button to replace the draft is answering a question
     the reader has not been asked. */
  it("withholds both when the workflow permits them but nothing is stale", () => {
    const plan = workflowActionPlan(staleDetail({ stale_reasons: [] }));

    expect(plan.replaceDraft).toBeNull();
    expect(plan.archiveDraft).toBeNull();
  });

  /* The other state in which the rebuild is what this screen is answering. Editing a claim
     detaches it from its canonical fact, which fails validation without producing a stale
     reason; the only other repair offered there is an AI regeneration that can fail, so a
     replacement withheld here leaves a draft that can neither be approved nor rebuilt.
     Archive stays withheld: nothing is out of date, and discarding is not a repair. */
  it("offers the rebuild - and only the rebuild - when validation failed without a stale reason", () => {
    const plan = workflowActionPlan(staleDetail({ stale_reasons: [], working_draft_state: "validation_failed" }));

    expect(plan.replaceDraft).toEqual({
      analysisId: "analysis-1",
      emphasized: false,
      selectionPlanId: "plan-1",
      workingDraftId: "draft-1",
    });
    expect(plan.archiveDraft).toBeNull();
  });

  /* Replacement builds a new draft, so it needs the two sources to build it from. Archive
     builds nothing and needs neither - it only has to name the draft it is setting aside.
     Asserted in one act because the difference between them is the point: the same missing
     ids stop one command and not the other. */
  it("needs an analysis and a selection plan to replace, but not to archive", () => {
    const withoutSources = workflowActionPlan(
      staleDetail({ active_analysis_id: null, active_selection_plan_id: null }),
    );

    expect(withoutSources.replaceDraft).toBeNull();
    expect(withoutSources.archiveDraft).toEqual({ workingDraftId: "draft-1" });

    const withoutPlan = workflowActionPlan(staleDetail({ active_selection_plan_id: null }));

    expect(withoutPlan.replaceDraft).toBeNull();
    expect(withoutPlan.archiveDraft).toEqual({ workingDraftId: "draft-1" });
  });

  /* Both commands are addressed to a draft, so neither survives its absence - however the
     projection came to report a stale reason with no active draft to attach it to. */
  it("withholds both when there is no active draft to address", () => {
    const plan = workflowActionPlan(staleDetail({ active_working_draft_id: null }));

    expect(plan.replaceDraft).toBeNull();
    expect(plan.archiveDraft).toBeNull();
  });

  /* The recommendation decides emphasis only, exactly as it does for every other action
     on this screen - never whether the command is offered. */
  it("emphasizes replacement only when the projection recommends it", () => {
    const plan = workflowActionPlan(staleDetail({ recommended_action: "replace_working_draft" }));

    expect(plan.replaceDraft?.emphasized).toBe(true);
    expect(plan.unbuiltRecommendation).toBeNull();
  });

  /* The regression this section exists to close: a recommended action this screen now
     builds must not be reported as one it does not. */
  it("does not report either command as unbuilt once it is offered here", () => {
    expect(
      workflowActionPlan(staleDetail({ recommended_action: "archive_working_draft" })).unbuiltRecommendation,
    ).toBeNull();
  });
});

describe("recommended action destinations", () => {
  it("does not reserve an empty action surface for a review decision handled by its own panel", () => {
    const plan = workflowActionPlan(
      staleDetail({
        preparation_state: "needs_review",
        working_draft_state: "none",
        stale_reasons: [],
        active_working_draft_id: null,
        available_actions: ["apply_analysis_decisions"],
        recommended_action: "apply_analysis_decisions",
      }),
    );

    expect(plan.reviewHandledHere).toBe(true);
    expect(hasWorkflowActionsContent(plan)).toBe(false);
  });

  it("handles fact selection on the preparation screen even when no plan exists yet", () => {
    const plan = workflowActionPlan(
      staleDetail({
        preparation_state: "needs_review",
        working_draft_state: "none",
        stale_reasons: [],
        active_selection_plan_id: null,
        active_working_draft_id: null,
        available_actions: ["create_selection_plan"],
        recommended_action: "create_selection_plan",
      }),
    );

    expect(plan.createSelectionPlan).toEqual({
      analysisId: "analysis-1",
      emphasized: true,
      selectionPlanId: null,
    });
    expect(plan.unbuiltRecommendation).toBeNull();
  });

  /* The claim-level commands are controls in the editor, so a recommendation naming one of
     them is not unbuilt: this screen has nothing to offer for it, but a screen exists and
     the reason callouts beside this one link to it. Reporting it as having no screen told
     the reader the app could not do what it had just told them to do. */
  it("does not call a claim-level recommendation unbuilt", () => {
    for (const recommended of [
      "confirm_and_use_fact",
      "apply_selection_change",
      "regenerate_claim",
      "regenerate_section",
    ]) {
      const plan = workflowActionPlan(
        staleDetail({
          preparation_state: "needs_review",
          working_draft_state: "validation_failed",
          stale_reasons: [],
          available_actions: ["update_working_draft", recommended],
          recommended_action: recommended,
        }),
      );

      expect(plan.unbuiltRecommendation).toBeNull();
      expect(plan.draftScreen?.href).toBe("/applications/app-1/draft");
    }
  });

  it("routes rendering back to the editor that recovers the exact approved revision", () => {
    const plan = workflowActionPlan(
      staleDetail({
        preparation_state: "approved",
        working_draft_state: "none",
        stale_reasons: [],
        active_working_draft_id: null,
        latest_approved_revision_id: "revision-1",
        available_actions: ["analyze", "render"],
        recommended_action: "render",
      }),
    );

    expect(plan.draftScreen).toEqual({
      emphasized: true,
      href: "/applications/app-1/draft",
      label: "יצירת קובץ קורות החיים",
    });
    expect(plan.unbuiltRecommendation).toBeNull();
  });

  it("makes the current Ready revision the only preparation action when no newer draft exists", () => {
    const plan = workflowActionPlan(
      staleDetail({
        preparation_state: "ready",
        working_draft_state: "none",
        stale_reasons: [],
        active_working_draft_id: null,
        latest_ready_revision_id: "revision-1",
        available_actions: ["create_draft", "render"],
        recommended_action: "create_draft",
      }),
    );

    expect(plan.createDraft).toBeNull();
    expect(plan.draftScreen).toBeNull();
    expect(plan.readyRevision).toEqual({ emphasized: true, href: "/revisions/revision-1" });
    expect(plan.unbuiltRecommendation).toBeNull();
  });

  it("names the distinct newer draft while preserving the usable Ready revision", () => {
    const plan = workflowActionPlan(
      staleDetail({
        preparation_state: "ready",
        working_draft_state: "validated",
        stale_reasons: [],
        active_working_draft_id: "draft-2",
        latest_ready_revision_id: "revision-1",
        newer_draft_in_progress: true,
        available_actions: ["approve"],
        recommended_action: "approve",
      }),
    );

    expect(plan.draftScreen).toEqual({
      emphasized: false,
      href: "/applications/app-1/draft",
      label: "המשך עבודה על הטיוטה החדשה",
    });
    expect(plan.readyRevision).toEqual({ emphasized: true, href: "/revisions/revision-1" });
  });
});
