import type { ApplicationDetail } from "../../api/contracts";
import { actionDestination } from "./actionDestinations";

/* What the preparation screen may offer, derived from the §9 projection alone.

   This is the reading of the projection, separated from the rendering of it. It decides
   nothing the backend has not already decided - every field below is `available_actions`,
   `recommended_action`, or an id the projection carries - which is precisely why it is
   worth testing without a DOM: the rules it encodes are about what the workflow permits,
   and they were previously spread through a 312-line component where the only way to ask
   whether approval outranks validation was to render a screen and read its buttons. */
export interface ApplicationActionPlan {
  /* `analyze` is offered as re-analysis once an analysis is already in force. */
  analyze: { emphasized: boolean; reanalysis: boolean } | null;
  /* The generate command, with the two ids it must carry. */
  createDraft: { analysisId: string; emphasized: boolean; selectionPlanId: string } | null;
  /* §14: generate writes over the one active WorkingDraft. With one in hand, discarding it
     is a choice `replace_working_draft` carries rather than one `create_draft` makes
     silently, so generate is withheld and the two explicit commands below take over. */
  draftWouldReplace: boolean;
  /* §14: the two ways out of a stale draft, and the only actions on this screen addressed
     to a specific version of one. Both carry `active_working_draft_id`; the version itself
     is not in the projection and is read separately by whoever sends the command.

     Offered on two conditions, not one. `available_actions` is the authority on whether
     the workflow permits the command at all, and `stale_reasons` is why this screen puts
     it in front of the reader: replacing a draft that is not stale is a command the
     workflow may well allow, but it is not what this screen is answering. */
  archiveDraft: { workingDraftId: string } | null;
  replaceDraft: { analysisId: string; emphasized: boolean; selectionPlanId: string; workingDraftId: string } | null;
  /* `update_working_draft`, `validate` and `approve` all resolve to the draft editor:
     validation is a panel there and approval a dialog opened from it. Offered side by side
     they read as three destinations that all arrive at one URL, so they collapse to one
     control wearing the furthest-along name - that being the one the workflow is waiting
     on. The recommendation decides emphasis only; it never picks a different URL. */
  draftScreen: { emphasized: boolean; href: string; label: string } | null;
  readyRevision: { emphasized: boolean; href: string } | null;
  /* The review decision's control is a panel on this same screen, so it is handled here
     more completely than a link ever handled it - and must not be reported as unbuilt. */
  reviewHandledHere: boolean;
  /* A recommended action with no control here and no destination anywhere. It is a claim
     about existence, not availability, so it asks the same route table the reason callouts
     ask: gating it on availability would let this say a screen does not exist while a
     callout beside it links to that very screen. */
  unbuiltRecommendation: string | null;
}

export const applicationActionPlan = (detail: ApplicationDetail): ApplicationActionPlan => {
  const applicationId = detail.application.id;
  const recommended = detail.recommended_action ?? null;
  const available = (action: string): boolean => detail.available_actions.includes(action);
  const analysisId = detail.active_analysis_id ?? null;
  const selectionPlanId = detail.active_selection_plan_id ?? null;
  const draftWouldReplace = detail.working_draft_state !== "none";

  const canAnalyze = available("analyze");
  const analyze = canAnalyze ? { emphasized: recommended === "analyze", reanalysis: recommended !== "analyze" } : null;

  const createDraft =
    available("create_draft") && analysisId !== null && selectionPlanId !== null && !draftWouldReplace
      ? { analysisId, emphasized: recommended === "create_draft", selectionPlanId }
      : null;

  const destinationFor = (action: string): string | null =>
    available(action) ? actionDestination(action, applicationId) : null;
  const editHref = destinationFor("update_working_draft");
  const validationHref = destinationFor("validate");
  const approvalHref = destinationFor("approve");
  /* Furthest along wins the label: if approval is offered the draft is validated and
     approving is what the workflow is waiting on, and so down the chain. */
  const draftScreenTarget =
    approvalHref !== null
      ? { href: approvalHref, label: "אישור הגרסה" }
      : validationHref !== null
        ? { href: validationHref, label: "אימות הטיוטה" }
        : editHref !== null
          ? { href: editHref, label: "עריכת הטיוטה" }
          : null;
  const draftScreen =
    draftScreenTarget === null
      ? null
      : {
          ...draftScreenTarget,
          emphasized: recommended === "approve" || recommended === "validate" || recommended === "update_working_draft",
        };

  const readyRevision =
    detail.latest_ready_revision_id == null
      ? null
      : {
          emphasized: detail.preparation_state === "ready",
          href: `/revisions/${encodeURIComponent(detail.latest_ready_revision_id)}`,
        };

  const workingDraftId = detail.active_working_draft_id ?? null;
  const stale = detail.stale_reasons.length > 0;
  const replaceDraft =
    stale &&
    available("replace_working_draft") &&
    workingDraftId !== null &&
    analysisId !== null &&
    selectionPlanId !== null
      ? { analysisId, emphasized: recommended === "replace_working_draft", selectionPlanId, workingDraftId }
      : null;
  const archiveDraft =
    stale && available("archive_working_draft") && workingDraftId !== null ? { workingDraftId } : null;

  const reviewHandledHere = available("apply_analysis_decisions");
  const handledHere = new Set(
    [
      analyze === null ? null : "analyze",
      createDraft === null ? null : "create_draft",
      replaceDraft === null ? null : "replace_working_draft",
      archiveDraft === null ? null : "archive_working_draft",
      reviewHandledHere ? "apply_analysis_decisions" : null,
      editHref === null ? null : "update_working_draft",
      validationHref === null ? null : "validate",
      approvalHref === null ? null : "approve",
    ].filter((action): action is string => action !== null),
  );

  const unbuiltRecommendation =
    recommended !== null && !handledHere.has(recommended) && actionDestination(recommended, applicationId) === null
      ? recommended
      : null;

  return {
    analyze,
    archiveDraft,
    createDraft,
    draftWouldReplace,
    replaceDraft,
    draftScreen,
    readyRevision,
    reviewHandledHere,
    unbuiltRecommendation,
  };
};
