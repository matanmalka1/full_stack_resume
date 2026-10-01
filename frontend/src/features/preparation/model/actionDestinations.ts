import type { ApplicationDetail, ApplicationListItem, OperationType } from "@/api/contracts";
import { routePaths } from "@/navigation/routePaths";

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
  /* `MatchingConfigurationEditor` is a control inside `PreparationView`, which this screen
     renders, so the action resolves to the screen already holding it. */
  edit_matching_configuration: routePaths.application,
  /* Re-pinning the document to a newer analysis sits beside the analysis it is decided
     against. */
  build_from_analysis: routePaths.application,
  create_draft: routePaths.application,
  /* The Draft Editor is where the patch is issued, so the commands it carries all lead
     to it. The regeneration commands and the fact resolution are controls on that screen
     rather than screens of their own: they act on the claim the user is looking at, and a
     separate destination would ask them to find it twice. `confirm_and_use_fact` in
     particular is the terminal state of an ordinary editing mistake - a claim that lost its
     fact link - and its control is `ClaimFactResolution`, which is already on that screen
     beside the claim it repairs. */
  edit: routePaths.draft,
  confirm_and_use_fact: routePaths.draft,
  regenerate_claim: routePaths.draft,
  regenerate_section: routePaths.draft,
  /* Checking, approval and render are states of the draft editor, not screens beside it.
     All three act on the document the editor is holding, so they resolve to that one
     destination: the panel that reports the check, the dialog that approves and the panel
     that renders are already there when the user arrives. */
  check: routePaths.draft,
  approve: routePaths.draft,
  render: routePaths.draft,
  /* What is done with a Ready document - taking its file and recording that it was sent -
     is the ready step's. */
  submit: routePaths.ready,
  download_pdf: routePaths.ready,
};

export const actionDestination = (action: string, applicationId: string): string | null =>
  destinations[action]?.(applicationId) ?? null;

/* Re-enter the guided flow at the work the server currently recommends. The fallback is
   deliberately about what the document already is, not about deciding what work is
   allowed: a document with content opens in its editor and a Ready one opens as the
   finished document. Availability and recommendation remain projection-owned. */
type ResumeProjection = Pick<
  ApplicationListItem,
  "id" | "preparation_state" | "recommended_action" | "active_operation"
>;

const operationActions: Record<OperationType, string> = {
  analyze_job: "analyze",
  create_draft: "create_draft",
  regenerate_section: "regenerate_section",
  regenerate_claim: "regenerate_claim",
  render_document: "render",
};

const resumeDestination = (application: ResumeProjection): string => {
  /* Running work owns the entry point even when the document is Ready. This chooses its
     host screen, without creating work or changing permissions. */
  const operation = application.active_operation;
  if (operation != null && operation.application_id === application.id) {
    const destination = actionDestination(operationActions[operation.operation_type], application.id);
    if (destination !== null) return destination;
  }
  const recommended =
    application.recommended_action == null ? null : actionDestination(application.recommended_action, application.id);

  if (recommended !== null) {
    return recommended;
  }

  if (application.preparation_state === "ready") {
    return routePaths.ready(application.id);
  }

  if (application.preparation_state === "draft_in_progress" || application.preparation_state === "approved") {
    return routePaths.draft(application.id);
  }

  return routePaths.application(application.id);
};

export const preparationResumeDestination = (application: ApplicationListItem): string =>
  resumeDestination(application);

/* Duplicate detection intentionally returns identity evidence only. Its resume route can
   read the full projection before choosing a screen, so the duplicate contract does not
   grow a second, soon-stale copy of workflow state merely to build a link. */
export const preparationResumeDestinationFromDetail = (applicationId: string, detail: ApplicationDetail): string =>
  resumeDestination({
    id: applicationId,
    active_operation: detail.active_operation,
    preparation_state: detail.preparation_state,
    recommended_action: detail.recommended_action,
  });

/* Which of the screens above the reader is on. An alert region is rendered on more than
   one of them, and whether it offers a way to the control that resolves a reason depends
   on whether that control is already where the reader is standing - a question only the
   screen can answer, so it says which one it is rather than each caller re-deriving it. */
export type PreparationScreen = "preparation" | "draft" | "ready";

export const screenPath = (screen: PreparationScreen, applicationId: string): string =>
  screen === "draft"
    ? routePaths.draft(applicationId)
    : screen === "ready"
      ? routePaths.ready(applicationId)
      : routePaths.application(applicationId);
