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

export const workflowStageLabels: Record<WorkflowStage, string> = {
  intake: "קליטת משרה",
  analysis: "ניתוח",
  draft: "טיוטה ואימות",
  ready: "מוכן",
};

/* What each stage produces, in one line. The labels above are single nouns, and a noun
   alone does not tell a reader what a stage is for or what has to be true before "מוכן".

   These describe the stage, not what may happen next: which action is possible is
   `available_actions` and `recommended_action`, and the landmark decides none of it. */
export const workflowStageHints: Record<WorkflowStage, string> = {
  intake: "הדבקת מודעת המשרה ויצירת המועמדות",
  analysis: "התאמת המשרה לעובדות הקנוניות",
  draft: "ניסוח, אימות מול העובדות ואישור הגרסה",
  ready: "גרסה מאושרת ומרונדרת, מוכנה לשליחה",
};

/* Where the backend's PreparationState sits in the landmark. Exhaustive over the
   generated union, so a state added to the projection fails the build here rather than
   leaving the landmark on whichever stage it happened to be showing.

   This is a display position, not a second workflow state machine. It decides nothing
   about what may happen next: that comes from `available_actions` and
   `recommended_action`. */
export const stageForPreparationState: Record<PreparationState, WorkflowStage> = {
  needs_analysis: "analysis",
  needs_review: "analysis",
  ready_to_draft: "draft",
  draft_in_progress: "draft",
  ready_for_approval: "draft",
  approved: "ready",
  ready: "ready",
};

export type StageDestinations = Partial<Record<WorkflowStage, string>>;

/* Where each stage's work can be re-read, derived from the projection rather than listed
   by hand. A stage whose record does not exist yet gets no entry, so the landmark offers
   a link only where there is something at the other end.

   Job Detail is not among them. It holds the job, not a stage of the CV, so the bar
   offers no way to it - the screens that need a way back to it have one in their own
   breadcrumbs and in the shell header.

   The editor is one destination for one stage: the draft, its validation, and its
   approval are panels of that single screen. Ready names the revision the Application
   currently stands on - `latest_ready_revision_id` first, because a rendered revision is
   the one the reader means by "מוכן", and the approved revision only while no render
   exists yet. */
export const workflowDestinations = (
  applicationId: string,
  detail: ApplicationDetail | undefined,
): StageDestinations => {
  const readyRevisionId = detail?.latest_ready_revision_id ?? detail?.latest_approved_revision_id ?? null;
  const editable = detail?.active_working_draft_id != null;

  return {
    analysis: routePaths.preparation(applicationId),
    ...(editable ? { draft: routePaths.draft(applicationId) } : {}),
    ...(readyRevisionId == null ? {} : { ready: routePaths.revision(readyRevisionId) }),
  };
};
