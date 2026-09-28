import type { ApplicationDetail } from "@/api/contracts";
import { routePaths } from "@/app/routePaths";
import { actionDestination } from "./actionDestinations";

/* What the preparation screen may offer, derived from the §9 projection alone.

   This is the reading of the projection, separated from the rendering of it. It decides
   nothing the backend has not already decided - every field below is `available_actions`,
   `recommended_action`, or an id/hash the projection carries - which is precisely why it
   is worth testing without a DOM: the rules it encodes are about what the workflow
   permits, and asking whether approval outranks checking should not need a screen. */
export interface WorkflowActionPlan {
  /* `analyze` is offered as re-analysis once an analysis is already in force. */
  analyze: { emphasized: boolean; reanalysis: boolean } | null;
  /* The fact selection screen: the document's own selection, which exists from the first
     analysis on. */
  selection: { emphasized: boolean } | null;
  /* The generate command, addressed to the document at the hash the projection reports. */
  createDraft: { documentHash: string; emphasized: boolean } | null;
  /* §14 `build_from_analysis`: a newer analysis exists than the one the document is pinned
     to. Explicit, because it replaces the selection and clears content and every stamp -
     `discardsContent` says whether that loses written work, which is what decides whether
     the press asks first. */
  buildFromAnalysis: {
    analysisId: string;
    discardsContent: boolean;
    documentHash: string;
    emphasized: boolean;
  } | null;
  /* `edit`, `check`, `approve`, and `render` all resolve to the draft editor: the check is
     a panel there, approval a dialog, render a panel. Offered side by side they read as
     destinations that all arrive at one URL, so they collapse to one control wearing the
     furthest-along name. The recommendation decides emphasis only. */
  draftScreen: { emphasized: boolean; href: string; label: string } | null;
  /* The ready step, offered only while the projection says the document is Ready. */
  ready: { emphasized: boolean; href: string } | null;
  /* A recommended action with no control here and no destination anywhere. It is a claim
     about existence, not availability, so it asks the same route table the reason callouts
     ask. */
  unbuiltRecommendation: string | null;
}

/* Whether `WorkflowActions` has anything to put inside its surface. Some actions are
   deliberately handled elsewhere on the preparation screen: the fact selection in its own
   panel and re-analysis beside the diagnostics. Treating those as content here leaves an
   emphasized but empty card behind. */
export const hasWorkflowActionsContent = (plan: WorkflowActionPlan): boolean =>
  (plan.analyze !== null && !plan.analyze.reanalysis) ||
  plan.createDraft !== null ||
  plan.buildFromAnalysis !== null ||
  plan.draftScreen !== null ||
  plan.ready !== null ||
  plan.unbuiltRecommendation !== null;

export const workflowActionPlan = (detail: ApplicationDetail): WorkflowActionPlan => {
  const applicationId = detail.application.id;
  const recommended = detail.recommended_action ?? null;
  const available = (action: string): boolean => detail.available_actions.includes(action);
  const documentHash = detail.document_hash ?? null;
  const hasContent =
    detail.document_id != null &&
    detail.preparation_state !== "needs_analysis" &&
    detail.preparation_state !== "ready_to_draft";

  const analyze = available("analyze")
    ? { emphasized: recommended === "analyze", reanalysis: recommended !== "analyze" }
    : null;

  const selection =
    documentHash !== null && (available("update_selection") || available("propose_selection"))
      ? { emphasized: recommended === "update_selection" || recommended === "propose_selection" }
      : null;

  const createDraft =
    available("create_draft") && documentHash !== null
      ? { documentHash, emphasized: recommended === "create_draft" }
      : null;

  const newerAnalysisId = detail.latest_analysis_id ?? null;
  const buildFromAnalysis =
    available("build_from_analysis") && documentHash !== null && newerAnalysisId !== null
      ? {
          analysisId: newerAnalysisId,
          discardsContent: hasContent,
          documentHash,
          emphasized: recommended === "build_from_analysis",
        }
      : null;

  const destinationFor = (action: string): string | null =>
    available(action) ? actionDestination(action, applicationId) : null;
  const editHref = destinationFor("edit");
  const checkHref = destinationFor("check");
  const approvalHref = destinationFor("approve");
  const renderHref = destinationFor("render");
  const readyNow = detail.document_state === "ready";
  /* Furthest along wins the label: if rendering is offered the document is approved and
     the files are what the workflow is waiting on; before that, approval. A Ready document
     stays editable, so the editor is still offered beside it - as the way back, not as
     what the workflow is waiting on. */
  const draftScreenTarget =
    renderHref !== null
      ? { href: renderHref, label: "יצירת קובץ קורות החיים" }
      : approvalHref !== null
        ? { href: approvalHref, label: "אישור הגרסה" }
        : checkHref !== null
          ? { href: checkHref, label: "בדיקת הטיוטה" }
          : editHref !== null
            ? { href: editHref, label: readyNow ? "חזרה לעריכת הטיוטה" : "עריכת הטיוטה" }
            : null;
  const draftScreen =
    draftScreenTarget === null
      ? null
      : {
          ...draftScreenTarget,
          emphasized:
            recommended === "render" || recommended === "approve" || recommended === "check" || recommended === "edit",
        };

  const ready = readyNow
    ? { emphasized: detail.preparation_state === "ready", href: routePaths.ready(applicationId) }
    : null;

  const handledHere = new Set(
    [
      analyze === null ? null : "analyze",
      selection === null ? null : "update_selection",
      selection === null ? null : "propose_selection",
      createDraft === null ? null : "create_draft",
      buildFromAnalysis === null ? null : "build_from_analysis",
      editHref === null ? null : "edit",
      checkHref === null ? null : "check",
      approvalHref === null ? null : "approve",
      renderHref === null ? null : "render",
    ].filter((action): action is string => action !== null),
  );

  const unbuiltRecommendation =
    recommended !== null && !handledHere.has(recommended) && actionDestination(recommended, applicationId) === null
      ? recommended
      : null;

  return {
    analyze,
    buildFromAnalysis,
    createDraft,
    draftScreen,
    ready,
    selection,
    unbuiltRecommendation,
  };
};
