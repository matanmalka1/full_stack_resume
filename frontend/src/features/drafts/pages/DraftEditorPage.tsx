import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { applicationDetailQueryOptions, invalidateApplicationViews } from "@/api/applications";
import { documentQueryKey, documentQueryOptions } from "@/api/documents";
import { ErrorCallout } from "@/ui/ErrorCallout";
import { routePaths } from "@/app/routePaths";
import { useRequiredParam } from "@/app/useRequiredParam";
import { LiveRegion } from "@/ui/LiveRegion";
import { QueryState } from "@/ui/QueryState";
import { Skeleton } from "@/ui/Skeleton";
import { OperationOverlay, type PendingWork, isOperationLive, operationTypeLabels } from "@/features/operations";
import { applicationLabel } from "@/features/applications";
import { PreparationAlerts, WizardStepShell } from "@/features/preparation";
import { DraftApprovalBar } from "../components/DraftApprovalBar";
import { DraftAttentionPanel } from "../components/DraftAttentionPanel";
import { DraftApprovalDialog } from "../components/DraftApprovalDialog";
import { DraftConflictDialog } from "../components/DraftConflictDialog";
import { DraftContentSummary } from "../components/DraftContentSummary";
import { DraftEditorNotices } from "../components/DraftEditorNotices";
import { DraftEmptyState } from "../components/DraftEmptyState";
import { DraftHistoryControls } from "../components/DraftHistoryControls";
import { DraftOutlineEditor } from "../components/DraftOutlineEditor";
import { DraftPreview } from "../components/DraftPreview";
import { DraftProgress } from "../components/DraftProgress";
import { DraftRenderPanel } from "../components/DraftRenderPanel";
import { DraftValidationPanel } from "../components/DraftValidationPanel";
import { type DraftWorkspaceMode, DraftWorkspace, DraftWorkspaceSwitch } from "../components/DraftWorkspace";
import { useDraftDocument } from "../api/queries";
import { useDocumentCheck } from "../hooks/useDocumentCheck";
import { useDraftEditing } from "../hooks/useDraftEditing";
import { useRenderDocument } from "../hooks/useRenderDocument";
import { summarizeContent, summarizeSelection } from "../model/draftOverview";
import { isEditable } from "../model/drafts.types";

/* The workspace's own shape, held while the document behind it is read. */
const draftLoading = (
  <div className="flex flex-col gap-6">
    <LiveRegion>טוען את הטיוטה…</LiveRegion>
    <div className="flex justify-end">
      <Skeleton className="block h-10 w-72 max-w-full" />
    </div>
    <Skeleton className="block h-[32rem] w-full" />
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
  "propose_selection",
  "render_document",
]);

/* A.4 frame 3: read the document, check what stands behind each line, check, approve, and
   render - on the one screen that holds the document all five act on.

   There is one mutable document per Application. Approval and Ready are states of it the
   projection reports (`document_state`), not records this screen moves between, so the
   editor stays open in every one of them: editing an approved or Ready document is
   allowed, and returns it to draft on the next read. That is also the way back from the
   ready step. */
export const DraftEditorPage = () => {
  const applicationId = useRequiredParam("applicationId");
  const navigate = useNavigate();
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

  const documentState = detail?.document_state ?? "none";
  const renderStage = documentState === "approved" || documentState === "ready";

  const renderFinished =
    operation?.operation_type === "render_document" &&
    operation.status === "succeeded" &&
    operation.id === renderQueuedHere &&
    documentState === "ready";

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

  const editing = useDraftEditing({
    applicationId,
    draft,
    etag,
    onOperationQueued: watch,
    operationLive,
  });
  const check = useDocumentCheck(
    applicationId,
    draft,
    operationLive ||
      editing.dirty ||
      resolving ||
      resolutionError != null ||
      applicationError != null ||
      draftError != null,
  );

  /* Hiding the rows must not strand text still sitting in the buffer, so the document
     view settles it first. */
  const changeMode = (next: DraftWorkspaceMode) => {
    if (next === "document") editing.flush();
    setMode(next);
  };

  const applicationHref = routePaths.application(applicationId);

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

  const approvalUnavailable =
    operationLive ||
    editing.dirty ||
    resolving ||
    resolutionError != null ||
    applicationError != null ||
    draftError != null ||
    detail === undefined ||
    detail.review_reasons.length > 0;

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
      // useDocumentCheck exposes the mutation error beside the preview.
    }
  };

  const noContent = detail !== undefined && (!hasDocument || (document !== undefined && draft === undefined));

  /* What the document is made of, read from its own outline and fact accounting: shared
     by the progress strip, the list of what blocks approval, and the account of how the
     content was built, so the three never count differently. */
  const content = useMemo(() => (draft === undefined ? undefined : summarizeContent(draft)), [draft]);
  const selection = useMemo(() => (draft === undefined ? undefined : summarizeSelection(draft)), [draft]);

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
      <WizardStepShell
        applicationId={applicationId}
        detail={detail}
        eyebrow={
          detail === undefined ? (
            <Skeleton className="inline-block w-56 max-w-full align-middle" />
          ) : (
            <span dir="auto">{applicationLabel(detail.application.company, detail.application.target_role)}</span>
          )
        }
        measure="wide"
        stage="draft"
      >
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
            {draft === undefined || content === undefined ? null : (
              <DraftProgress
                actions={<DraftWorkspaceSwitch mode={mode} onModeChange={changeMode} />}
                content={content}
                detail={detail}
                dirty={editing.dirty}
                draft={draft}
                saveState={editing.saveState}
              />
            )}

            <OperationOverlay
              awaitingRecord={awaitingRecord}
              continuation={continuation}
              onQueued={watch}
              operation={operation}
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

        {draft === undefined || content === undefined || selection === undefined ? null : (
          <>
            {detail === undefined ? null : (
              <DraftAttentionPanel
                detail={detail}
                draft={draft}
                onNavigate={(href) => {
                  if (!resolving) void navigateSaved(href);
                }}
                onShowClaim={(claimId) => {
                  setMode("read");
                  // A fresh request also supports jumping to the same claim again.
                  setClaimTarget({ claimId });
                }}
                unsupportedClaims={content.unsupportedClaims}
              />
            )}
            <DraftWorkspace
              editor={
                <>
                  <DraftContentSummary
                    busy={operationLive || editing.selectionPending}
                    content={content}
                    draft={draft}
                    onInclude={editing.includeFact}
                    selection={selection}
                  />

                  <DraftEditorNotices
                    aiUnavailable={editing.aiUnavailable}
                    dirty={editing.dirty}
                    regenerationError={editing.regenerationError}
                    selectionError={editing.selectionError}
                  />

                  <DraftOutlineEditor
                    actions={editing.claimActions}
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
                    history={
                      <DraftHistoryControls
                        canRedo={!operationLive && editing.history.canRedo}
                        canUndo={!operationLive && editing.history.canUndo}
                        onRedo={editing.history.redo}
                        onUndo={editing.history.undo}
                      />
                    }
                    onMoveClaim={editing.history.moveClaim}
                    onRegenerateSection={editing.regenerateSection}
                  />
                </>
              }
              mode={mode}
              preview={
                <>
                  <DraftPreview draft={draft} />
                  <DraftValidationPanel check={check} />
                </>
              }
            />

            {renderStage ? null : (
              <DraftApprovalBar
                applicationHref={applicationHref}
                passing={check.passing}
                onApprove={() => {
                  if (!approvalUnavailable && check.passing) setApprovalOpen(true);
                }}
                onValidate={() => {
                  void checkAndOpenApproval();
                }}
                unavailable={approvalUnavailable}
                reviewBlocked={(detail?.review_reasons ?? []).length > 0}
                stale={check.stale}
                validationPending={check.isPending}
                validationResult={
                  check.error !== null && check.error !== undefined
                    ? "לא ניתן להשלים את בדיקת הקובץ. פרטי השגיאה מופיעים לצד הטיוטה."
                    : check.lastCheck === undefined
                      ? undefined
                      : check.lastCheck.passed
                        ? approvalUnavailable
                          ? "הבדיקה עברה על הגרסה המוצגת. יש לפתור את החסמים לפני הכנת ה־PDF."
                          : "הבדיקה הושלמה בהצלחה. אפשר לאשר ולהכין את ה־PDF."
                        : "הבדיקה הושלמה ונדרשים תיקונים. הפרטים מופיעים לצד הטיוטה."
                }
              />
            )}

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
      </WizardStepShell>
    </div>
  );
};
