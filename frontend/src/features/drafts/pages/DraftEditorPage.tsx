import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { applicationDetailQueryOptions, invalidateApplicationViews } from "@/api/applications";
import {
  workingDraftFactsQueryKey,
  workingDraftFactsQueryOptions,
  workingDraftQueryKey,
  workingDraftQueryOptions,
} from "@/api/drafts";
import { ErrorCallout } from "@/ui/ErrorCallout";
import { DraftReviewPanel } from "../components/DraftReviewPanel";
import { routePaths } from "@/app/routePaths";
import { useRequiredParam } from "@/app/useRequiredParam";
import { LiveRegion } from "@/ui/LiveRegion";
import { QueryState } from "@/ui/QueryState";
import { Skeleton } from "@/ui/Skeleton";
import { OperationOverlay, type PendingWork, isOperationLive, operationTypeLabels } from "@/features/operations";
import { applicationLabel } from "@/features/applications";
import { PreparationAlerts, WizardStepShell } from "@/features/preparation";
import { DraftApprovalBar } from "../components/DraftApprovalBar";
import { DraftApprovalDialog } from "../components/DraftApprovalDialog";
import { DraftConflictDialog } from "../components/DraftConflictDialog";
import { DraftEditorNotices } from "../components/DraftEditorNotices";
import { DraftEmptyState } from "../components/DraftEmptyState";
import { DraftFactPanel } from "../components/DraftFactPanel";
import { DraftHeaderCard } from "../components/DraftHeaderCard";
import { DraftHistoryControls } from "../components/DraftHistoryControls";
import { DraftOutlineEditor } from "../components/DraftOutlineEditor";
import { DraftPreview } from "../components/DraftPreview";
import { DraftRenderPanel } from "../components/DraftRenderPanel";
import { DraftValidationPanel } from "../components/DraftValidationPanel";
import { type DraftWorkspaceMode, DraftWorkspace } from "../components/DraftWorkspace";
import { useDraftDocument } from "../api/queries";
import { useDraftEditing } from "../hooks/useDraftEditing";
import { useRenderApprovedRevision } from "../hooks/useRenderApprovedRevision";
import { useDraftValidation } from "../hooks/useDraftValidation";

/* The workspace's own shape, held while the document behind it is read.

   It opens in `document` mode, so what is coming is the view switch on its own line and
   the rendered draft at full width beneath it - which is what this stands in for. Drawn
   this way the arrival is the placeholder filling in rather than a screen's worth of
   panels appearing at once against a line of muted text.

   Not an Operation card: nothing is running. The read is a read, and the only thing worth
   saying about it is where the document will be. */
const draftLoading = (
  <div className="flex flex-col gap-6">
    <LiveRegion>טוען את הטיוטה…</LiveRegion>
    <div className="flex justify-end">
      <Skeleton className="block h-10 w-72 max-w-full" />
    </div>
    <Skeleton className="block h-[32rem] w-full" />
  </div>
);

/* A.4 frame 3: read the draft, check what stands behind each line, validate, sign, and
   render - on the one screen that holds the draft all five act on.

   Reading is what it is for. The user arrives to see what was written and signs; a line
   that needs changing is edited where it sits. Server state is the three hooks below;
   what is left here is the four decisions this screen makes for itself and how the parts
   are placed. */
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
    draft,
    draftError,
    etag,
    facts,
    operation,
    settled,
    watch,
    workingDraftId,
  } = useDraftDocument(applicationId);

  /* The daily workspace opens with editing and the rendered document together. A focused
     full-width preview remains available, especially on narrow screens. */
  const [mode, setMode] = useState<DraftWorkspaceMode>("read");
  const [approvalOpen, setApprovalOpen] = useState(false);
  /* The revision this editor just approved. Held here rather than read from the projection
     so the render step names the exact revision the approval returned. */
  const [approvedRevisionId, setApprovedRevisionId] = useState<string | null>(null);

  /* Approval deactivates the WorkingDraft atomically. Prefer the exact command response;
     after a reload, the projection may recover the same pending render step only when
     there is no newer active draft and the latest approved revision is the current
     preparation milestone. */
  const renderRevisionId =
    approvedRevisionId ??
    (workingDraftId === null && detail?.preparation_state === "approved"
      ? (detail.latest_approved_revision_id ?? null)
      : null);

  const renderFinished =
    operation?.operation_type === "render_revision" && operation.status === "succeeded" && renderRevisionId !== null;

  /* A regeneration activates a new version of the same WorkingDraft. The Operation
     query reaches terminal state before the application projection necessarily polls
     again, so refresh the document reads directly from the output boundary. Otherwise
     the next regeneration can send the previous edit version and fail SOURCE_CHANGED. */
  useEffect(() => {
    if (
      operation?.status !== "succeeded" ||
      workingDraftId === null ||
      !operation.outputs.some(
        (output) => output.active && output.output_type === "working_draft" && output.output_id === workingDraftId,
      )
    ) {
      return;
    }
    void Promise.all([
      queryClient.invalidateQueries({ queryKey: workingDraftQueryKey(workingDraftId) }),
      queryClient.invalidateQueries({ queryKey: workingDraftFactsQueryKey(workingDraftId) }),
    ]);
  }, [operation?.status, operation?.outputs, queryClient, workingDraftId]);

  useEffect(() => {
    if (renderFinished) {
      navigate(routePaths.revision(renderRevisionId), { replace: true });
    }
  }, [navigate, renderFinished, renderRevisionId]);

  /* The generate this screen was opened by has succeeded and activated its draft, and the
     projection naming that draft is a poll behind. Read from the run's own outputs rather
     than from a list of the Operation types that write drafts, so a new one that produces
     the same output is covered without being registered here.

     Without it the screen answered the gap with `DraftEmptyState` - "אין כרגע טיוטה פעילה"
     over a link back - which is the pre-generate state, shown for a poll to a reader who
     had just watched the draft being written, and taken away again by the projection that
     arrived next. */
  const draftArriving =
    workingDraftId === null &&
    operation?.status === "succeeded" &&
    operation.outputs.some((output) => output.active && output.output_type === "working_draft");

  /* Both windows where this screen's work is finished but the screen is not stopping here:
     it is loading the draft that was just written, or leaving for the ready step. Either
     way the run's overlay stays open and says what is happening, instead of closing on
     "הושלמה" for the tick before the next thing replaces it. */
  const continuation = renderFinished
    ? "הקבצים נוצרו. מעבר לגרסה המוכנה…"
    : draftArriving
      ? "הטיוטה נוצרה. טוענים את העורך…"
      : undefined;

  /* The render command is the editor's, so the one overlay below reports it from the
     press - see `useRenderApprovedRevision`. */
  const renderState = useRenderApprovedRevision({
    approvedRevisionId: renderRevisionId,
    autoStart: approvedRevisionId !== null,
    onQueued: watch,
    rendering: operation?.operation_type === "render_revision",
  });
  const pending: PendingWork | undefined = renderState.pending
    ? {
        heading: <>הרצת {operationTypeLabels.render_revision}</>,
        note: "הגרסה אושרה. יצירת ה־HTML וה־PDF מתחילה.",
      }
    : undefined;
  /* One answer, shared with the overlay, to whether the draft may be changed now. A
     hidden overlay does not make it so: a regeneration rewriting the draft, or one that
     finished and has not been read back, would have any edit addressed to the version it
     replaces - refused as a conflict at best. */
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
    facts,
    onOperationQueued: watch,
    operationLive,
    workingDraftId,
  });
  const validation = useDraftValidation(
    applicationId,
    draft,
    operationLive ||
      editing.dirty ||
      resolving ||
      resolutionError != null ||
      applicationError != null ||
      draftError != null ||
      detail?.working_draft_state === "stale",
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
      if (
        current.active_analysis_id !== detail?.active_analysis_id ||
        current.active_selection_plan_id !== detail?.active_selection_plan_id ||
        current.active_working_draft_id !== workingDraftId
      ) {
        throw new Error("הקשר המועמדות השתנה. המצב רוענן; יש לבדוק את ההחלטות והטיוטה לפני ניסיון נוסף.");
      }
      if (workingDraftId !== null) await queryClient.fetchQuery(workingDraftQueryOptions(workingDraftId));
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
      // refreshing its consequences or choosing a version for validation.
      const settled = await editing.settle();
      await invalidateApplicationViews(queryClient, applicationId);
      const currentDetail = await queryClient.fetchQuery({
        ...applicationDetailQueryOptions(applicationId),
        staleTime: 0,
      });
      const id = currentDetail.active_working_draft_id;
      if (id === null || id !== workingDraftId) return;
      // Do not join a read started before the confirmation committed.
      await Promise.all([
        queryClient.cancelQueries({ queryKey: workingDraftQueryKey(id) }),
        queryClient.cancelQueries({ queryKey: workingDraftFactsQueryKey(id) }),
      ]);
      await Promise.all([
        queryClient.fetchQuery({ ...workingDraftQueryOptions(id), staleTime: 0 }),
        queryClient.fetchQuery({ ...workingDraftFactsQueryOptions(id), staleTime: 0 }),
      ]);
      // A stale context may refuse saving. Still show that context, keep the local
      // buffer, and report the unfinished follow-up rather than undoing confirmation.
      if (!settled)
        throw new Error("מצב הטיוטה רוענן, אך יש לפתור את שגיאת השמירה או הקונפליקט. העריכות המקומיות נשמרו.");
      if (currentDetail.working_draft_state === "stale" || !currentDetail.available_actions.includes("validate"))
        return;
      // Settle once more after the reads, then validate the exact version read back.
      if (!(await editing.settle())) throw new Error("יש לשמור את העריכות לפני בדיקת הקובץ.");
      const latest = await queryClient.fetchQuery({ ...workingDraftQueryOptions(id), staleTime: 0 });
      await validation.validateExact(latest.draft);
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
    const target = document.getElementById(`draft-claim-${claimTarget.claimId}`);
    target?.scrollIntoView?.({ block: "center" });
    target?.focus();
  }, [claimTarget]);

  /* A validation becoming stale is the reason to offer validation again, not a reason
     to disable it. Other stale causes describe an obsolete draft context and still stop
     the finish flow until the projection's resolution is applied. */
  const hasContextStaleness =
    detail?.working_draft_state === "stale" ||
    (detail?.stale_reasons ?? []).some((reason) => reason.code !== "DRAFT_EDITED_AFTER_VALIDATION");

  const approvalUnavailable =
    operationLive ||
    editing.dirty ||
    resolving ||
    resolutionError != null ||
    applicationError != null ||
    draftError != null ||
    detail === undefined ||
    detail.review_reasons.length > 0 ||
    hasContextStaleness;

  // A blocker closes this explicit choice permanently; clearing it never reopens approval.
  if (approvalOpen && approvalUnavailable) setApprovalOpen(false);

  /* One press starts the finish flow. Validation remains its own exact backend boundary;
     once it passes, the event that requested it opens the explicit approval dialog instead
     of making the user press the footer action again. The hook retains and displays any
     validation failure, so the rejected promise needs no second error state here. */
  const validateAndOpenApproval = async () => {
    if (draft === undefined || approvalUnavailable) return;
    try {
      const run = await validation.validateExact(draft);
      if (run.passed) setApprovalOpen(true);
    } catch {
      // useDraftValidation exposes the mutation error beside the preview.
    }
  };

  return (
    /* No description: `DraftHeaderCard` below names the company and the target role
       together, and the heading repeated the role on its own a line above it. The step's
       name is the shell's, from the same table the spine marks it with - it used to be
       "קריאה, אימות ואישור", three words the rail does not use, so the reader's position
       had two names depending on which of the two they read. */
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
        /* The one step whose body is a document beside the evidence for each of its lines.
         Two readable columns need the wide frame the other steps do not. */
        measure="wide"
        stage="draft"
      >
        <QueryState
          error={applicationError}
          fallbackTitle="לא ניתן לטעון את מצב המועמדות"
          loading={detail === undefined}
          loadingLabel="טוען את מצב המועמדות…"
        />
        {draftError === null || draftError === undefined ? null : (
          <QueryState error={draftError} fallbackTitle="לא ניתן לטעון את הטיוטה" />
        )}

        {detail === undefined ? null : (
          <>
            <DraftHeaderCard
              detail={detail}
              dirty={editing.dirty}
              draft={draft}
              saveState={workingDraftId === null ? null : editing.saveState}
            />

            {/* Live work, over the draft it is rewriting rather than on a screen the user
              has to leave the text for; once it is over, a chip here reopens its report.
              One overlay for every run this screen watches, the render's wait included. */}
            <OperationOverlay
              awaitingRecord={awaitingRecord}
              continuation={continuation}
              onQueued={watch}
              operation={operation}
              pending={pending}
              settled={settled}
            />

            {/* The projection's own blockers, reported by the one region that reports them.
              A claim with no fact behind it raises PENDING_FACT_REQUIRES_RESOLUTION there,
              and it is shown here as the reason it already is rather than as an approval
              rule this screen invented. This screen used to map the same two arrays into
              bare titles of its own - no server message, no control - which named what
              refuses approval without naming anything the reader could do about it. */}
            <PreparationAlerts detail={detail} screen="draft" showReviewReasons={false} />
            {resolutionError === null ? null : (
              <ErrorCallout
                error={resolutionError}
                fallbackTitle="לא ניתן להמשיך לפני שמירת העריכות"
                fallbackDetail="יש לפתור את שגיאת השמירה או הקונפליקט, ולבדוק את ההקשר המעודכן לפני ניסיון נוסף. הטקסט המקומי נשמר בעורך."
              />
            )}

            {workingDraftId === null && renderRevisionId === null && !draftArriving ? (
              <DraftEmptyState applicationId={applicationId} />
            ) : null}
          </>
        )}

        {renderRevisionId !== null ? (
          /* The render is reported once, by the overlay above: while it is, the panel
             steps aside, so the approved box and its "create the files" CTA never appear
             beside the operation already creating them. */
          <DraftRenderPanel state={renderState} />
        ) : null}

        {renderRevisionId === null && draft === undefined && workingDraftId !== null && draftError === null ? (
          <QueryState loading loadingState={draftLoading} />
        ) : null}

        {renderRevisionId !== null || draft === undefined ? null : (
          <>
            {detail === undefined ? null : (
              <DraftReviewPanel
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
              />
            )}
            <DraftWorkspace
              editor={
                <>
                  <DraftHistoryControls
                    canRedo={!operationLive && editing.history.canRedo}
                    canUndo={!operationLive && editing.history.canUndo}
                    onRedo={editing.history.redo}
                    onUndo={editing.history.undo}
                  />
                  <DraftOutlineEditor
                    actions={editing.claimActions}
                    draft={editing.visibleDraft ?? draft}
                    factContext={{
                      beforeResolve,
                      afterResolve: afterFactResolved,
                      onResolvingChange: setResolving,
                      analysisId: detail?.active_analysis_id ?? null,
                      applicationId,
                      language: facts?.language ?? detail?.application.language ?? "en",
                      profile: detail?.application.profile ?? null,
                    }}
                    facts={facts}
                    onMoveClaim={editing.history.moveClaim}
                    onMoveSection={editing.history.moveSection}
                    onRegenerateSection={editing.regenerateSection}
                  />

                  <DraftEditorNotices
                    aiUnavailable={editing.aiUnavailable}
                    dirty={editing.dirty}
                    regenerationError={editing.regenerationError}
                    selectionError={editing.selectionError}
                  />

                  <DraftFactPanel
                    busy={operationLive || editing.selectionPending}
                    facts={facts}
                    onInclude={editing.includeFact}
                  />
                </>
              }
              mode={mode}
              onModeChange={changeMode}
              preview={
                /* The right pane is the document and everything said about it: the live
                 preview and the validation result for the exact version shown. The
                 decision those two gate is pinned to the screen instead, in one place
                 across both modes. */
                <>
                  <DraftPreview draft={draft} />
                  <DraftValidationPanel validation={validation} />
                </>
              }
            />

            <DraftApprovalBar
              applicationHref={applicationHref}
              exactPassingRunId={validation.exactPassingRunId}
              onApprove={() => {
                if (!approvalUnavailable && validation.exactPassingRunId !== null) setApprovalOpen(true);
              }}
              onValidate={() => {
                void validateAndOpenApproval();
              }}
              unavailable={approvalUnavailable}
              reviewBlocked={(detail?.review_reasons ?? []).length > 0}
              stale={validation.stale}
              validationPending={validation.isPending}
              validationResult={
                validation.error !== null && validation.error !== undefined
                  ? "לא ניתן להשלים את בדיקת הקובץ. פרטי השגיאה מופיעים לצד הטיוטה."
                  : validation.lastRun === undefined
                    ? undefined
                    : validation.lastRun.passed && validation.exactPassingRunId !== null
                      ? approvalUnavailable
                        ? "הבדיקה עברה על הגרסה המוצגת. יש לפתור את החסמים לפני הכנת ה־PDF."
                        : "הבדיקה הושלמה בהצלחה. אפשר לאשר ולהכין את ה־PDF."
                      : validation.lastRun.passed
                        ? "הבדיקה הושלמה, אך הטיוטה השתנתה מאז. יש לבדוק את הגרסה החדשה."
                        : "הבדיקה הושלמה ונדרשים תיקונים. הפרטים מופיעים לצד הטיוטה."
              }
            />

            <DraftApprovalDialog
              applicationId={applicationId}
              detail={detail}
              draft={draft}
              onApproved={(revisionId) => {
                setApprovalOpen(false);
                setApprovedRevisionId(revisionId);
              }}
              onClose={() => setApprovalOpen(false)}
              onStale={() => {
                setApprovalOpen(false);
                validation.reportStaleRefusal();
              }}
              open={approvalOpen && !approvalUnavailable}
              validationRunId={validation.exactPassingRunId}
            />

            <DraftConflictDialog
              current={draft}
              onDiscardLocal={editing.conflict.discardLocal}
              onReapplyLocal={editing.conflict.reapplyLocal}
              open={editing.conflict.open}
              pending={editing.conflict.pending}
              pendingAdditions={editing.conflict.pendingAdditions}
              pendingRemovals={editing.conflict.pendingRemovals}
              pendingSectionOrder={editing.conflict.pendingSectionOrder}
              pendingClaimOrders={editing.conflict.pendingClaimOrders}
            />
          </>
        )}
      </WizardStepShell>
    </div>
  );
};
