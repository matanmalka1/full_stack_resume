import type { ApplicationDetail, PreparationState } from "@/api/contracts";
import { routePaths } from "@/app/routePaths";

/* The ordered stages of the CV wizard, and the only place their Hebrew names live.

   Intake leads. Pasting the posting and creating the Application is the wizard's first
   step, not merely how a reader arrives: the screen is one guided flow from a job ad to a
   ready CV, so the spine names where that flow begins. It once sat outside these stages
   because the Application screen was a record hub a saved job was reopened from long after
   preparation was done - counting intake then made that hub read as step 1 of a workflow
   it no longer took part in. The hub is a wizard step now, so its first stage is honest.

   Intake is a display position only, and never the target of a `PreparationState`: once an
   Application exists it is already past intake, so `stageForPreparationState` maps every
   backend state to a later stage and the create screen supplies the position explicitly.

   Validation is not a stage of its own either. It has no screen and no record of its own:
   both stages pointed at `/draft`, so the bar drew two chips for one screen. The
   distinction they carried - draft written vs. draft validated - is the preparation
   badge's, and it is on the screen itself. */
export const workflowStages = ["intake", "analysis", "draft", "ready"] as const;

export type WorkflowStage = (typeof workflowStages)[number];

/* The stage names, and the only place they are written. Each screen in the flow titles
   itself from this table rather than from a string of its own: a heading that names the
   step differently from the chip above it gives the reader's position two names, and the
   draft step had already been repaired that way once, one page at a time. Two stages
   still carried the fault - "ניתוח" against a "ניתוח והתאמה" heading and "מוכן" against
   "מוכן למסירה" - which is what a hand-kept second copy does. The fuller name is the one
   that survives, because it is the one that says what the step is. */
export const workflowStageLabels: Record<WorkflowStage, string> = {
  intake: "קליטת משרה",
  analysis: "ניתוח והתאמה",
  draft: "טיוטה ואימות",
  ready: "מוכן למסירה",
};

/* Where the backend's PreparationState sits in the landmark. Exhaustive over the
   generated union, so a state added to the projection fails the build here rather than
   leaving the landmark on whichever stage it happened to be showing.

   This is a display position, not a second workflow state machine. It decides nothing
   about what may happen next: that comes from `available_actions` and
   `recommended_action`. */
export const stageForPreparationState: Record<PreparationState, WorkflowStage> = {
  needs_analysis: "analysis",
  /* Creating the draft is the action that closes analysis. The document exists from the
     first analysis on, but until it has content there is no draft to be on, so marking the
     next stage here made the rail disagree with the open page's heading. */
  ready_to_draft: "analysis",
  draft_in_progress: "draft",
  approved: "draft",
  ready: "ready",
};

export type StageDestinations = Partial<Record<WorkflowStage, string>>;

/* Where each stage's work can be re-read, derived from the projection rather than listed
   by hand. A stage with nothing at the other end yet gets no entry, so the landmark offers
   a link only where there is something to open.

   Job Detail is not among them. It holds the job, not a stage of the CV, so the bar
   offers no way to it - the screens that need a way back to it have one in their own
   breadcrumbs and in the shell header.

   The editor is one destination for one stage: the draft, its check, its approval and its
   render are panels of that single screen, reachable whenever the document has content -
   from Ready too, because editing a Ready document is allowed and is the way back to it.
   Ready is offered only while the projection says the document is Ready. */
export const workflowDestinations = (
  applicationId: string,
  detail: ApplicationDetail | undefined,
): StageDestinations => {
  const hasContent =
    detail !== undefined &&
    detail.document_id != null &&
    detail.preparation_state !== "needs_analysis" &&
    detail.preparation_state !== "ready_to_draft";

  return {
    analysis: routePaths.application(applicationId),
    ...(hasContent ? { draft: routePaths.draft(applicationId) } : {}),
    ...(detail?.document_state === "ready" ? { ready: routePaths.ready(applicationId) } : {}),
  };
};
