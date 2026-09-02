import { appRoutes } from "../../app/appRoutes";

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
  analyze: appRoutes.preparation,
  apply_analysis_decisions: appRoutes.preparation,
  create_draft: appRoutes.preparation,
  archive_working_draft: appRoutes.preparation,
  replace_working_draft: appRoutes.preparation,
  /* The Draft Editor is where the patch is issued, so the three commands it carries all
     lead to it. `apply_selection_change` and the removal path are controls on that
     screen rather than screens of their own: they act on the claim the user is looking
     at, and a separate destination would ask them to find it twice. */
  update_working_draft: appRoutes.draft,
  /* Validation and approval are states of the draft editor, not screens beside it.
     Both act on the exact draft the editor is holding, so they resolve to that one
     destination: the panel that reports the result and the dialog that approves it are
     already there when the user arrives. */
  validate: appRoutes.draft,
  approve: appRoutes.draft,
  /* After approval the editor recovers the exact latest approved revision from the
     projection and renders its explicit render panel, including after a reload. */
  render: appRoutes.draft,
};

export const actionDestination = (action: string, applicationId: string): string | null =>
  destinations[action]?.(applicationId) ?? null;

export const actionIsOnPreparationScreen = (action: string, applicationId: string): boolean =>
  actionDestination(action, applicationId) === appRoutes.preparation(applicationId);
