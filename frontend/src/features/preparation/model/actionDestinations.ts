import { routePaths } from "@/app/routePaths";

/* Which backend action names this frontend has actually built a screen for.

   It is a route table keyed by the backend's own action vocabulary, not a second
   workflow state machine: it decides nothing about availability, which stays the §9
   projection's answer through `available_actions`. It exists so that "this action now
   has a screen" is one fact in one place - the context screen links to it and the review
   reason stops promising it is coming - rather than two that drift apart.

   An action absent from the table has no screen yet, which is the honest default. */

const destinations: Record<string, (applicationId: string) => string> = {
  /* Job Detail summarizes preparation but does not execute it. Board recommendations and
     alerts therefore address the preparation screen that owns these controls. */
  analyze: routePaths.preparation,
  apply_analysis_decisions: routePaths.preparation,
  create_selection_plan: routePaths.preparation,
  create_draft: routePaths.preparation,
  archive_working_draft: routePaths.preparation,
  replace_working_draft: routePaths.preparation,
  /* The Draft Editor is where the patch is issued, so the three commands it carries all
     lead to it. `apply_selection_change` and the removal path are controls on that
     screen rather than screens of their own: they act on the claim the user is looking
     at, and a separate destination would ask them to find it twice. */
  update_working_draft: routePaths.draft,
  /* Validation and approval are states of the draft editor, not screens beside it.
     Both act on the exact draft the editor is holding, so they resolve to that one
     destination: the panel that reports the result and the dialog that approves it are
     already there when the user arrives. */
  validate: routePaths.draft,
  approve: routePaths.draft,
  /* After approval the editor recovers the exact latest approved revision from the
     projection and renders its explicit render panel, including after a reload. */
  render: routePaths.draft,
};

export const actionDestination = (action: string, applicationId: string): string | null =>
  destinations[action]?.(applicationId) ?? null;

/* Which of the screens above the reader is on. An alert region is rendered on more than
   one of them, and whether it offers a way to the control that resolves a reason depends
   on whether that control is already where the reader is standing - a question only the
   screen can answer, so it says which one it is rather than each caller re-deriving it. */
export type PreparationScreen = "preparation" | "draft";

export const screenPath = (screen: PreparationScreen, applicationId: string): string =>
  screen === "draft" ? routePaths.draft(applicationId) : routePaths.preparation(applicationId);
