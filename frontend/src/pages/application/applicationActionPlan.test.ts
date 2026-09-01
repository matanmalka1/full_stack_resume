import { describe, expect, it } from "vitest";

import type { ApplicationDetail, Reason } from "../../api/contracts";
import { applicationActionPlan } from "./applicationActionPlan";

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
    const plan = applicationActionPlan(staleDetail());

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
    const plan = applicationActionPlan(staleDetail({ available_actions: [] }));

    expect(plan.replaceDraft).toBeNull();
    expect(plan.archiveDraft).toBeNull();
  });

  /* And the converse. `available_actions` may well permit replacing a draft that is not
     stale, but this screen offers the pair as the way out of the alert above them: with
     nothing reported as out of date, a button to replace the draft is answering a question
     the reader has not been asked. */
  it("withholds both when the workflow permits them but nothing is stale", () => {
    const plan = applicationActionPlan(staleDetail({ stale_reasons: [] }));

    expect(plan.replaceDraft).toBeNull();
    expect(plan.archiveDraft).toBeNull();
  });

  /* Replacement builds a new draft, so it needs the two sources to build it from. Archive
     builds nothing and needs neither - it only has to name the draft it is setting aside.
     Asserted in one act because the difference between them is the point: the same missing
     ids stop one command and not the other. */
  it("needs an analysis and a selection plan to replace, but not to archive", () => {
    const withoutSources = applicationActionPlan(
      staleDetail({ active_analysis_id: null, active_selection_plan_id: null }),
    );

    expect(withoutSources.replaceDraft).toBeNull();
    expect(withoutSources.archiveDraft).toEqual({ workingDraftId: "draft-1" });

    const withoutPlan = applicationActionPlan(staleDetail({ active_selection_plan_id: null }));

    expect(withoutPlan.replaceDraft).toBeNull();
    expect(withoutPlan.archiveDraft).toEqual({ workingDraftId: "draft-1" });
  });

  /* Both commands are addressed to a draft, so neither survives its absence - however the
     projection came to report a stale reason with no active draft to attach it to. */
  it("withholds both when there is no active draft to address", () => {
    const plan = applicationActionPlan(staleDetail({ active_working_draft_id: null }));

    expect(plan.replaceDraft).toBeNull();
    expect(plan.archiveDraft).toBeNull();
  });

  /* The recommendation decides emphasis only, exactly as it does for every other action
     on this screen - never whether the command is offered. */
  it("emphasizes replacement only when the projection recommends it", () => {
    const plan = applicationActionPlan(staleDetail({ recommended_action: "replace_working_draft" }));

    expect(plan.replaceDraft?.emphasized).toBe(true);
    expect(plan.unbuiltRecommendation).toBeNull();
  });

  /* The regression this section exists to close: a recommended action this screen now
     builds must not be reported as one it does not. */
  it("does not report either command as unbuilt once it is offered here", () => {
    expect(
      applicationActionPlan(staleDetail({ recommended_action: "archive_working_draft" })).unbuiltRecommendation,
    ).toBeNull();
  });
});

describe("recommended action destinations", () => {
  it("routes rendering back to the editor that recovers the exact approved revision", () => {
    const plan = applicationActionPlan(
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
});
