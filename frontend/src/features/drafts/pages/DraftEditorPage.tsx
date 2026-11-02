import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import { applicationDetailQueryOptions, invalidateApplicationViews } from "@/api/applications";
import {
  documentQueryKey,
  documentQueryOptions,
  invalidateDocumentViews,
  outlineClaims,
  setDocumentTemplate,
} from "@/api/documents";
import type { TemplateName } from "@/api/templates";
import { CommitBar } from "@/ui/CommitBar";
import { ErrorCallout } from "@/ui/ErrorCallout";
import { routePaths } from "@/navigation/routePaths";
import { useRequiredParam } from "@/navigation/useRequiredParam";
import { LiveRegion } from "@/ui/LiveRegion";
import { QueryState } from "@/ui/QueryState";
import { Skeleton } from "@/ui/Skeleton";
import { useIsPhone } from "@/ui/useIsPhone";
import { OperationOverlay, type PendingWork, isOperationLive, operationTypeLabels } from "@/features/operations";
import { PreparationAlerts } from "@/features/preparation";
import { type DraftApprovalState, DraftApprovalNote, DraftApproveButton } from "../components/DraftApproval";
import { DraftAttentionPanel } from "../components/DraftAttentionPanel";
import { DraftApprovalDialog } from "../components/DraftApprovalDialog";
import { DraftConflictDialog } from "../components/DraftConflictDialog";
import { DraftEditorNotices } from "../components/DraftEditorNotices";
import { DraftEmptyState } from "../components/DraftEmptyState";
import { DraftFitCard } from "../components/DraftFitCard";
import { DraftHeader } from "../components/DraftHeader";
import { DraftHistoryControls } from "../components/DraftHistoryControls";
import { DraftOutlineEditor } from "../components/DraftOutlineEditor";
import { DraftPreview } from "../components/DraftPreview";
import { DraftPreviewToggle } from "../components/DraftPreviewToggle";
import { DraftRenderPanel } from "../components/DraftRenderPanel";
import { DraftRequirementsPanel } from "../components/DraftRequirementsPanel";
import { DraftSaveState } from "../components/DraftSaveState";
import { DraftSectionNav } from "../components/DraftSectionNav";
import { DraftTemplateControl } from "../components/DraftTemplateControl";
import { DraftValidationPanel } from "../components/DraftValidationPanel";
import { type DraftWorkspaceMode, DraftWorkspace } from "../components/DraftWorkspace";
import { RegenerationDiffPanel } from "../components/RegenerationDiffPanel";
import { useDraftDocument } from "../api/queries";
import { useDocumentCheck } from "../hooks/useDocumentCheck";
import { useDraftEditing } from "../hooks/useDraftEditing";
import { useRegenerationDiff } from "../hooks/useRegenerationDiff";
import { useRenderDocument } from "../hooks/useRenderDocument";
import { claimRequirements, draftFit } from "../model/draftFit";
import { unsupportedClaims } from "../model/draftOverview";
import { defaultPart, draftParts, partOfClaim } from "../model/draftParts";
import { isEditable } from "../model/drafts.types";
import { revertEdit } from "../model/regenerationDiff";

/* The workspace's own shape, held while the document behind it is read. */
const draftLoading = (
  <div className="flex flex-col gap-3.5 lg:grid lg:grid-cols-[minmax(0,10.625rem)_minmax(0,1fr)_minmax(0,16.25rem)] lg:gap-5">
    <LiveRegion>טוען את הטיוטה…</LiveRegion>
    <Skeleton className="block h-44 w-full max-lg:h-11" />
    <Skeleton className="block h-96 w-full" />
    <Skeleton className="block h-36 w-full max-lg:hidden" />
  </div>
);

/* Operation types whose success rewrites the document this screen holds. Read back from
   the document itself when one finishes, because the Operation reaches terminal state
   before the projection necessarily polls again - and the next command must carry the
   hash the finished run produced, not the one before it. */
const DOCUMENT_WRITING_OPERATIONS = new Set([
  "create_draft",
  "regenerate_section",
  "regenerate_claim",
  "render_document",
]);

/* A.4 frame 3: read the document, check what stands behind each line, check, approve, and
   render - on the one screen that holds the document all five act on.

   There is one mutable document per Application. Approval and Ready are states of it the
   projection reports (`preparation_state`), not records this screen moves between, so the
   editor stays open in every one of them: editing an approved or Ready document is
   allowed, and returns it to draft on the next read. That is also the way back from the
   ready step. */
export const DraftEditorPage = () => {
  const applicationId = useRequiredParam("applicationId");
  const isPhone = useIsPhone();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const requestedClaim = searchParams.get("claim");
  const queryClient = useQueryClient();
  const [resolutionError, setResolutionError] = useState<unknown>(null);
  const [resolving, setResolving] = useState(false);
  const [claimTarget, setClaimTarget] = useState<{ claimId: string } | null>(null);
  const {
    applicationError,
    awaitingRecord,
    detail,
    document,
    draft,
    draftError,
    etag,
    hasDocument,
    operation,
    settled,
    watch,
  } = useDraftDocument(applicationId);

  const [mode, setMode] = useState<DraftWorkspaceMode>("read");
  const [approvalOpen, setApprovalOpen] = useState(false);
  /* Set by this screen's own approval, so the render it starts is the automatic
     continuation of a press - never something a visit to an approved document starts. */
  const [approvedHere, setApprovedHere] = useState(false);
  /* The render this screen queued. Only its success moves the reader on: a render that
     finished before they came back to edit must not bounce them out of the editor. */
  const [renderQueuedHere, setRenderQueuedHere] = useState<string | null>(null);

  const preparationState = detail?.preparation_state ?? "needs_analysis";
  const renderStage = preparationState === "approved" || preparationState === "ready";

  const renderFinished =
    operation?.operation_type === "render_document" &&
    operation.status === "succeeded" &&
    operation.id === renderQueuedHere &&
    preparationState === "ready";

  useEffect(() => {
    if (
      operation?.status !== "succeeded" ||
      operation.application_id !== applicationId ||
      !DOCUMENT_WRITING_OPERATIONS.has(operation.operation_type)
    ) {
      return;
    }
    void queryClient.invalidateQueries({ queryKey: documentQueryKey(applicationId) });
  }, [applicationId, operation?.application_id, operation?.operation_type, operation?.status, queryClient]);

  useEffect(() => {
    if (renderFinished) {
      navigate(routePaths.ready(applicationId), { replace: true });
    }
  }, [applicationId, navigate, renderFinished]);

  /* The generate this screen was opened by has succeeded, and the document read naming its
     content is a poll behind. Without this the screen answered the gap with the empty
     state - the pre-generate screen, shown for a poll to a reader who had just watched the
     draft being written. */
  const draftArriving =
    draft === undefined && operation?.operation_type === "create_draft" && operation.status === "succeeded";

  const continuation = renderFinished
    ? "הקבצים נוצרו. מעבר לקורות החיים המוכנים…"
    : draftArriving
      ? "הטיוטה נוצרה. טוענים את העורך…"
      : undefined;

  const renderState = useRenderDocument({
    autoStart: approvedHere,
    detail,
    onQueued: (operationId) => {
      setRenderQueuedHere(operationId);
      watch(operationId);
    },
    rendering: operation?.operation_type === "render_document" && !operation.is_terminal,
  });
  const pending: PendingWork | undefined = renderState.pending
    ? {
        heading: <>הרצת {operationTypeLabels.render_document}</>,
        note: "הגרסה אושרה. יצירת ה־HTML וה־PDF מתחילה.",
      }
    : undefined;
  /* One answer, shared with the overlay, to whether the document may be changed now. A
     hidden overlay does not make it so: a run rewriting the document, or one that finished
     and has not been read back, would have any edit addressed to the document it replaces. */
  const operationLive = isOperationLive({
    awaitingRecord,
    continuation,
    operation,
    pending: pending !== undefined,
    settled,
  });

  /* The lines a regeneration is about to overwrite are captured at the press and bound to
     the run the server accepted, so its success can be shown before and after. */
  const regenerationDiff = useRegenerationDiff({ draft, operation });
  const editing = useDraftEditing({
    applicationId,
    draft,
    etag,
    onOperationQueued: (operationId) => {
      regenerationDiff.bind(operationId);
      watch(operationId);
    },
    operationLive,
  });
  const claimActions = {
    ...editing.claimActions,
    onRegenerate: (claim: Parameters<typeof editing.claimActions.onRegenerate>[0]) => {
      regenerationDiff.capture({ kind: "claim", claimId: claim.claim_id });
      editing.claimActions.onRegenerate(claim);
    },
    onReview: (claim: Parameters<typeof editing.claimActions.onReview>[0]) => {
      regenerationDiff.capture({ kind: "claim", claimId: claim.claim_id });
      editing.claimActions.onReview(claim);
    },
  };
  const regenerateSection = (section: string) => {
    regenerationDiff.capture({ kind: "section", section });
    editing.regenerateSection(section);
  };
  /* What makes the document on screen something neither a check nor an approval can speak
     for: live work on it, unsaved edits, a resolution in flight or failed, an unresolved read.
     Approval adds its own two conditions below. */
  const documentUnsettled =
    operationLive ||
    editing.dirty ||
    resolving ||
    resolutionError != null ||
    applicationError != null ||
    draftError != null;
  const check = useDocumentCheck(applicationId, draft, documentUnsettled);

  /* Hiding the rows must not strand text still sitting in the buffer, so the document
     view settles it first. */
  const changeMode = (next: DraftWorkspaceMode) => {
    if (next === "document") editing.flush();
    setMode(next);
  };

  const beforeResolve = async () => {
    setResolutionError(null);
    setApprovalOpen(false);
    try {
      if (!(await editing.settle())) {
        throw new Error("העריכות לא נשמרו. יש לפתור את שגיאת השמירה או הקונפליקט ולנסות שוב; הטקסט המקומי נשמר בעורך.");
      }
      await invalidateApplicationViews(queryClient, applicationId);
      const current = await queryClient.fetchQuery(applicationDetailQueryOptions(applicationId));
      if (current.document_analysis_id !== detail?.document_analysis_id) {
        throw new Error("המסמך נבנה מחדש מניתוח אחר. המצב רוענן; יש לבדוק את הטיוטה לפני ניסיון נוסף.");
      }
      await queryClient.fetchQuery({ ...documentQueryOptions(applicationId), staleTime: 0 });
      // Refreshing may have taken time; do not change context over newly buffered edits.
      if (!(await editing.settle())) throw new Error("יש להשלים את שמירת העריכות לפני המשך.");
    } catch (error) {
      setResolutionError(error);
      throw error;
    }
  };

  const afterFactResolved = async () => {
    setResolutionError(null);
    try {
      // Confirmation has committed. Preserve edits made during that request before
      // refreshing its consequences or choosing a document to check.
      const editsSaved = await editing.settle();
      await invalidateApplicationViews(queryClient, applicationId);
      const currentDetail = await queryClient.fetchQuery({
        ...applicationDetailQueryOptions(applicationId),
        staleTime: 0,
      });
      if (currentDetail.document_id == null) return;
      // Do not join a read started before the confirmation committed.
      await queryClient.cancelQueries({ queryKey: documentQueryKey(applicationId) });
      await queryClient.fetchQuery({ ...documentQueryOptions(applicationId), staleTime: 0 });
      if (!editsSaved)
        throw new Error("מצב הטיוטה רוענן, אך יש לפתור את שגיאת השמירה או הקונפליקט. העריכות המקומיות נשמרו.");
      if (!currentDetail.available_actions.includes("check")) return;
      // Settle once more after the reads, then check the exact document read back.
      if (!(await editing.settle())) throw new Error("יש לשמור את העריכות לפני בדיקת הקובץ.");
      const latest = await queryClient.fetchQuery({ ...documentQueryOptions(applicationId), staleTime: 0 });
      if (isEditable(latest.document)) await check.checkExact(latest.document);
    } catch (error) {
      setResolutionError(error);
      throw error;
    }
  };

  /* The template is part of the document hash, so it is chosen like any command over
     the document: unsaved edits first, then against the hash just read, then the
     document read back so the next autosave carries the new token. */
  const chooseTemplate = async (template: TemplateName | null) => {
    if (!(await editing.settle())) {
      throw new Error("העריכות לא נשמרו. יש לפתור את שגיאת השמירה או הקונפליקט ולנסות שוב.");
    }
    const latest = await queryClient.fetchQuery({ ...documentQueryOptions(applicationId), staleTime: 0 });
    await setDocumentTemplate(applicationId, latest.document.document_hash, template);
    await invalidateDocumentViews(queryClient, applicationId);
    await queryClient.fetchQuery({ ...documentQueryOptions(applicationId), staleTime: 0 });
  };

  const navigateSaved = async (href: string) => {
    setResolutionError(null);
    setResolving(true);
    try {
      await beforeResolve();
      navigate(href);
    } catch (error) {
      setResolutionError(error);
    } finally {
      setResolving(false);
    }
  };

  useEffect(() => {
    if (claimTarget === null) return;
    const target = window.document.getElementById(`draft-claim-${claimTarget.claimId}`);
    target?.scrollIntoView?.({ block: "center" });
    target?.focus();
  }, [claimTarget]);

  const focusDocumentId = draft?.id;
  useEffect(() => {
    if (requestedClaim === null || focusDocumentId === undefined) return;
    // A same-page link can close a native modal in this commit. Focus after its
    // close algorithm has released the inert page and restored its old focus.
    const frame = window.requestAnimationFrame(() => {
      const target = window.document.getElementById(`draft-claim-${requestedClaim}`);
      target?.scrollIntoView?.({ block: "center" });
      target?.focus();
    });
    return () => window.cancelAnimationFrame(frame);
  }, [requestedClaim, focusDocumentId]);

  const approvalUnavailable = documentUnsettled || detail === undefined || detail.review_reasons.length > 0;

  // A blocker closes this explicit choice permanently; clearing it never reopens approval.
  if (approvalOpen && approvalUnavailable) setApprovalOpen(false);

  /* One press starts the finish flow. The check remains its own exact backend boundary;
     once it passes, the event that requested it opens the explicit approval dialog. A
     check that already passed against this exact document is not run again. */
  const checkAndOpenApproval = async () => {
    if (draft === undefined || approvalUnavailable) return;
    if (check.passing) {
      setApprovalOpen(true);
      return;
    }
    try {
      const result = await check.checkExact(draft);
      if (result.passed) setApprovalOpen(true);
    } catch {
      // useDocumentCheck exposes the mutation error beside the draft.
    }
  };

  const noContent = detail !== undefined && (!hasDocument || (document !== undefined && draft === undefined));

  /* The lines nothing authorizes, read from the document's own outline. */
  const unsupported = useMemo(() => (draft === undefined ? [] : unsupportedClaims(draft)), [draft]);
  /* A refused review is history once no line it refused still reads as it was refused -
     edited, undone, or removed. Its status row would otherwise stay red over a document
     that no longer holds the wording, until some later run happened to replace it. */
  const reviewSettled = useMemo(() => {
    if (draft === undefined || operation?.status !== "failed" || operation.failure_reason?.code !== "claim_review") {
      return false;
    }
    const current = new Map(outlineClaims(draft.outline).map((claim) => [claim.claim_id, claim.text]));
    return operation.failure_reason.claims.every((refused) => current.get(refused.claim_id) !== refused.text);
  }, [draft, operation]);
  /* The posting's requirements against the facts, from the analysis the projection
     already carries - no read of its own. */
  const fit = useMemo(() => (detail === undefined ? null : draftFit(detail)), [detail]);
  const requirements = useMemo(() => (detail === undefined ? new Map() : claimRequirements(detail)), [detail]);

  /* The part of the CV on screen. Chosen once when the draft arrives - the line a link
     asked for, else the first part holding a line to decide - and after that only by the
     reader: resolving that line must not move the screen to another part under them. */
  const parts = useMemo(() => (draft === undefined ? [] : draftParts(draft)), [draft]);
  const [chosenPart, setChosenPart] = useState<string | null>(null);
  if (chosenPart === null && draft !== undefined) {
    setChosenPart((requestedClaim === null ? undefined : partOfClaim(draft, requestedClaim)) ?? defaultPart(parts));
  }
  const activePart = parts.some((part) => part.id === chosenPart) ? (chosenPart ?? "") : defaultPart(parts);

  const showClaim = (claimId: string) => {
    if (draft === undefined) return;
    setMode("read");
    setChosenPart(partOfClaim(draft, claimId) ?? activePart);
    // A fresh request also supports jumping to the same claim again.
    setClaimTarget({ claimId });
  };

  const approval: DraftApprovalState = {
    passing: check.passing,
    onApprove: () => {
      if (!approvalUnavailable && check.passing) setApprovalOpen(true);
    },
    onValidate: () => {
      void checkAndOpenApproval();
    },
    reviewBlocked: (detail?.review_reasons ?? []).length > 0,
    stale: check.stale,
    unavailable: approvalUnavailable,
    validationPending: check.isPending,
    validationResult:
      check.error !== null && check.error !== undefined
        ? "לא ניתן להשלים את בדיקת הקובץ. פרטי השגיאה מופיעים בתצוגה המקדימה."
        : check.lastCheck === undefined
          ? undefined
          : check.lastCheck.passed
            ? approvalUnavailable
              ? "הבדיקה עברה על הגרסה המוצגת. יש לפתור את החסמים לפני הכנת ה־PDF."
              : "הבדיקה הושלמה בהצלחה. אפשר לאשר ולהכין את ה־PDF."
            : "הבדיקה הושלמה ונדרשים תיקונים. הפרטים מופיעים כאן, לצד הטיוטה.",
  };
  /* Approval is the step's command until the document is approved; from then on the
     render panel carries the step's next act. */
  const approvable = draft !== undefined && !renderStage;
  /* What the check found, beside the lines while it asks for something - a failure, an
     outdated result or a refused approval. A passing report has nothing to ask, and stays
     with the rendered document behind the preview button. */
  const checkNeedsReader =
    check.stale ||
    check.contentCheck === "failed" ||
    check.contentCheck === "outdated" ||
    (check.error !== null && check.error !== undefined);

  return (
    <div
      className="contents"
      onClickCapture={(event) => {
        const anchor = (event.target as Element).closest("a");
        const href = anchor?.getAttribute("href");
        if (href?.startsWith("/") && !href.startsWith("//")) {
          event.preventDefault();
          event.stopPropagation();
          if (!resolving) void navigateSaved(href);
        }
      }}
    >
      {/* The page's own frame rather than the wizard's: the design draws this step with
          no stage bar, its heading row carrying the way back, the preview and the
          approval. */}
      <section
        aria-labelledby="route-heading"
        className="page-frame flex flex-col gap-5 max-lg:min-h-[calc(100dvh-2.5rem)] max-lg:gap-3.5"
      >
        <DraftHeader
          actions={
            draft === undefined ? undefined : (
              <>
                <DraftPreviewToggle mode={mode} onModeChange={changeMode} />
                {approvable && !isPhone ? <DraftApproveButton state={approval} /> : null}
              </>
            )
          }
          applicationId={applicationId}
          detail={detail}
        />

        <QueryState
          error={applicationError}
          errorTitle="לא ניתן לטעון את מצב המועמדות"
          loading={detail === undefined}
          loadingLabel="טוען את מצב המועמדות…"
        />
        {draftError === null || draftError === undefined ? null : (
          <QueryState error={draftError} errorTitle="לא ניתן לטעון את הטיוטה" />
        )}

        {detail === undefined ? null : (
          <>
            <OperationOverlay
              awaitingRecord={awaitingRecord}
              continuation={continuation}
              /* The render is this step's own last act, so it is reported in the step,
                 where its banner used to stand - once, not as that banner plus a corner
                 panel saying the same. Held inline through the continuation to Ready so
                 the report does not jump to the corner for its last moment. */
              inline={renderState.inFlight || renderFinished}
              inlineNote="הגרסה אושרה. כשקובצי ה־HTML וה־PDF יהיו מוכנים, המסך יעבור לקורות החיים המוכנים למסירה."
              onQueued={watch}
              operation={reviewSettled ? undefined : operation}
              pending={pending}
              settled={settled}
            />

            {/* The projection's own blockers and warnings, reported by the one region that
                reports them - including a document built on an older analysis, which this
                screen answers by linking back to where it is rebuilt. */}
            <PreparationAlerts detail={detail} screen="draft" showReviewReasons={false} />
            {resolutionError === null ? null : (
              <ErrorCallout
                error={resolutionError}
                title="לא ניתן להמשיך לפני שמירת העריכות"
                fallbackDetail="העריכות נשארו בעורך. יש לפתור את בעיית השמירה ולנסות שוב."
              />
            )}

            {noContent && !draftArriving ? <DraftEmptyState applicationId={applicationId} /> : null}
          </>
        )}

        {renderStage && draft !== undefined ? (
          /* The render is reported once, by the overlay above: while it is, the panel steps
             aside, so the "create the files" CTA never appears beside the operation already
             creating them. */
          <DraftRenderPanel
            applicationId={applicationId}
            lastRenderError={detail?.last_render_error}
            state={renderState}
          />
        ) : null}

        {draft === undefined && hasDocument && document === undefined && draftError === null ? (
          <QueryState loading loadingState={draftLoading} />
        ) : null}

        {draft === undefined ? null : (
          <>
            {detail === undefined ? null : (
              <DraftAttentionPanel
                detail={detail}
                draft={draft}
                onShowClaim={showClaim}
                unsupportedClaims={unsupported}
              />
            )}
            <DraftWorkspace
              editor={
                /* Three columns on a wide screen, as the design draws them: the parts of
                   the CV, the open part, and what is kept beside it - the fit, the save
                   state, and what the approval is waiting on. On a phone one column, in
                   the design's order: the fit, the parts as tabs, the open part, then the
                   rest. The side column dissolves there so its blocks can take their own
                   places in that order. */
                <div className="flex flex-col gap-3.5 lg:grid lg:grid-cols-[minmax(0,10.625rem)_minmax(0,1fr)_minmax(0,16.25rem)] lg:items-start lg:gap-5">
                  <div className="max-lg:order-2">
                    <DraftSectionNav active={activePart} onSelect={setChosenPart} parts={parts} />
                  </div>

                  <div className="flex min-w-0 flex-col gap-3.5 max-lg:order-3">
                    <DraftEditorNotices
                      aiUnavailable={editing.aiUnavailable}
                      dirty={editing.dirty}
                      regenerationError={editing.regenerationError}
                    />

                    <RegenerationDiffPanel
                      changes={regenerationDiff.changes}
                      locked={operationLive}
                      onDismiss={regenerationDiff.dismiss}
                      onRevert={(change) => {
                        const edit = revertEdit(change, (editing.visibleDraft ?? draft).outline);
                        if (edit === null) return;
                        editing.claimActions.onEdit(edit.claim, edit.text);
                        editing.claimActions.onCommit();
                      }}
                      outline={(editing.visibleDraft ?? draft).outline}
                      target={regenerationDiff.target}
                    />

                    <DraftOutlineEditor
                      actions={claimActions}
                      active={activePart}
                      draft={editing.visibleDraft ?? draft}
                      factContext={{
                        beforeResolve,
                        afterResolve: afterFactResolved,
                        onResolvingChange: setResolving,
                        analysisId: draft.analysis_id,
                        applicationId,
                        language: draft.language,
                        profile: detail?.application.profile ?? null,
                      }}
                      facts={draft}
                      onMoveClaim={editing.history.moveClaim}
                      onRegenerateSection={regenerateSection}
                      requirements={requirements}
                    />
                  </div>

                  <div className="flex min-w-0 flex-col gap-3.5 max-lg:contents">
                    {fit === null ? null : (
                      <div className="max-lg:order-1">
                        <DraftFitCard fit={fit} />
                      </div>
                    )}
                    {/* Each requirement against the lines on screen, under the fit it
                        details; on a phone after the rest, folded until opened. */}
                    {detail === undefined ? null : (
                      <div className="max-lg:order-7">
                        <DraftRequirementsPanel detail={detail} outline={(editing.visibleDraft ?? draft).outline} />
                      </div>
                    )}
                    <div className="max-lg:order-4">
                      <DraftSaveState
                        dirty={editing.dirty}
                        state={editing.saveState}
                        trailing={
                          <DraftHistoryControls
                            canRedo={!operationLive && editing.history.canRedo}
                            canUndo={!operationLive && editing.history.canUndo}
                            onRedo={editing.history.redo}
                            onUndo={editing.history.undo}
                          />
                        }
                      />
                    </div>
                    {approvable ? <DraftApprovalNote className="max-lg:order-5" state={approval} /> : null}
                    {mode === "read" && checkNeedsReader ? (
                      <div className="max-lg:order-6">
                        <DraftValidationPanel check={check} />
                      </div>
                    ) : null}
                  </div>
                </div>
              }
              mode={mode}
              preview={
                <>
                  <DraftTemplateControl
                    disabled={operationLive || resolving}
                    draft={draft}
                    onApply={chooseTemplate}
                    stamped={renderStage}
                  />
                  <DraftPreview draft={draft} />
                  {mode === "document" ? <DraftValidationPanel check={check} /> : null}
                </>
              }
            />

            {/* A phone's command is the bar pinned to the screen's bottom edge. The spacer
                before it takes what a short part leaves of the screen, so the bar stands at
                the bottom edge even then; the bar itself stays a child of the frame, which
                is what gives `sticky` the room to pin it over a long one. */}
            {approvable && isPhone ? (
              <>
                <div aria-hidden="true" className="-mt-3.5 flex-1" />
                <CommitBar primary={<DraftApproveButton size="large" state={approval} />} />
              </>
            ) : null}

            <DraftApprovalDialog
              applicationId={applicationId}
              detail={detail}
              draft={draft}
              onApproved={() => {
                setApprovalOpen(false);
                setApprovedHere(true);
              }}
              onCheckFailed={() => setApprovalOpen(false)}
              onClose={() => setApprovalOpen(false)}
              onStale={() => {
                setApprovalOpen(false);
                check.reportStaleRefusal();
              }}
              open={approvalOpen && !approvalUnavailable}
            />

            <DraftConflictDialog
              current={draft}
              onDiscardLocal={editing.conflict.discardLocal}
              onReapplyLocal={editing.conflict.reapplyLocal}
              open={editing.conflict.open}
              pending={editing.conflict.pending}
              pendingAdditions={editing.conflict.pendingAdditions}
              pendingRemovals={editing.conflict.pendingRemovals}
              pendingClaimOrders={editing.conflict.pendingClaimOrders}
            />
          </>
        )}
      </section>
    </div>
  );
};
