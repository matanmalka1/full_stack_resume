import type { ApplicationDetail, ApplicationListItem } from "@/api/contracts";
import { routePaths } from "@/app/routePaths";

/* Which backend action names this frontend has actually built a screen for.

   It is a route table keyed by the backend's own action vocabulary, not a second
   workflow state machine: it decides nothing about availability, which stays the §9
   projection's answer through `available_actions`. It exists so that "this action now
   has a screen" is one fact in one place - the context screen links to it and the review
   reason stops promising it is coming - rather than two that drift apart.

   An action absent from the table has no screen yet, which is the honest default. */

const destinations: Record<string, (applicationId: string) => string> = {
  /* The Application screen is where preparation is executed - it is the preparation
     screen, not a summary beside one. It carried a second URL ending in `/preparation`
     for exactly these links; one address answers them now. */
  analyze: routePaths.application,
  apply_analysis_decisions: routePaths.application,
  create_selection_plan: routePaths.application,
  create_draft: routePaths.application,
  archive_working_draft: routePaths.application,
  replace_working_draft: routePaths.application,
  /* The Draft Editor is where the patch is issued, so the commands it carries all lead
     to it. `apply_selection_change`, the regeneration commands and the fact resolution
     are controls on that screen rather than screens of their own: they act on the claim
     the user is looking at, and a separate destination would ask them to find it twice.
     `confirm_and_use_fact` in particular is the terminal state of an ordinary editing
     mistake - a claim that lost its fact link - and its control is `ClaimFactResolution`,
     which is already on that screen beside the claim it repairs. */
  update_working_draft: routePaths.draft,
  apply_selection_change: routePaths.draft,
  confirm_and_use_fact: routePaths.draft,
  regenerate_claim: routePaths.draft,
  regenerate_section: routePaths.draft,
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

/* Re-enter the guided flow at the work the server currently recommends. The fallback is
   deliberately about records that already exist, not about deciding what work is allowed:
   a draft opens in its editor and a rendered revision opens as the finished document.
   Availability and recommendation remain projection-owned. */
type ResumeProjection = Pick<
  ApplicationListItem,
  "id" | "latest_ready_revision_id" | "preparation_state" | "recommended_action"
>;

const resumeDestination = (application: ResumeProjection): string => {
  const recommended =
    application.recommended_action === null
      ? null
      : actionDestination(application.recommended_action, application.id);

  if (recommended !== null) {
    return recommended;
  }

  if (application.preparation_state === "ready" && application.latest_ready_revision_id != null) {
    return routePaths.revision(application.latest_ready_revision_id);
  }

  if (
    application.preparation_state === "draft_in_progress" ||
    application.preparation_state === "ready_for_approval" ||
    application.preparation_state === "approved"
  ) {
    return routePaths.draft(application.id);
  }

  return routePaths.application(application.id);
};

export const preparationResumeDestination = (application: ApplicationListItem): string =>
  resumeDestination(application);

/* Duplicate detection intentionally returns identity evidence only. Its resume route can
   read the full projection before choosing a screen, so the duplicate contract does not
   grow a second, soon-stale copy of workflow state merely to build a link. */
export const preparationResumeDestinationFromDetail = (
  applicationId: string,
  detail: ApplicationDetail,
): string =>
  resumeDestination({
    id: applicationId,
    latest_ready_revision_id: detail.latest_ready_revision_id,
    preparation_state: detail.preparation_state,
    recommended_action: detail.recommended_action,
  });

/* Which of the screens above the reader is on. An alert region is rendered on more than
   one of them, and whether it offers a way to the control that resolves a reason depends
   on whether that control is already where the reader is standing - a question only the
   screen can answer, so it says which one it is rather than each caller re-deriving it. */
export type PreparationScreen = "preparation" | "draft";

export const screenPath = (screen: PreparationScreen, applicationId: string): string =>
  screen === "draft" ? routePaths.draft(applicationId) : routePaths.application(applicationId);
