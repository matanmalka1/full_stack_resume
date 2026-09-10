import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { isTerminalOperation } from "@/api/operations";
import { routePaths } from "@/app/routePaths";
import { useRequiredParam } from "@/app/useRequiredParam";
import { QueryState } from "@/ui/QueryState";
import { ActiveOperationPanel } from "@/features/operations";
import { applicationLabel } from "@/features/applications";
import { PreparationAlerts, WizardStepShell } from "@/features/preparation";
import { FactLifecyclePanel } from "@/features/facts";
import { DraftApprovalBar } from "../components/DraftApprovalBar";
import { DraftApprovalDialog } from "../components/DraftApprovalDialog";
import { DraftConflictDialog } from "../components/DraftConflictDialog";
import { DraftEditorNotices } from "../components/DraftEditorNotices";
import { DraftEmptyState } from "../components/DraftEmptyState";
import { DraftFactPanel } from "../components/DraftFactPanel";
import { DraftHeaderCard } from "../components/DraftHeaderCard";
import { DraftOutlineEditor } from "../components/DraftOutlineEditor";
import { DraftPreview } from "../components/DraftPreview";
import { DraftRenderPanel } from "../components/DraftRenderPanel";
import { DraftValidationPanel } from "../components/DraftValidationPanel";
import { type DraftWorkspaceMode, DraftWorkspace } from "../components/DraftWorkspace";
import { useDraftDocument } from "../api/queries";
import { useDraftEditing } from "../hooks/useDraftEditing";
import { useDraftValidation } from "../hooks/useDraftValidation";

/* A.4 frame 3: read the draft, check what stands behind each line, validate, sign, and
   render - on the one screen that holds the draft all five act on.

   Reading is what it is for. The user arrives to see what was written and signs; a line
   that needs changing is edited where it sits. Server state is the three hooks below;
   what is left here is the four decisions this screen makes for itself and how the parts
   are placed. */
export const DraftEditorPage = () => {
  const applicationId = useRequiredParam("applicationId");
  const navigate = useNavigate();
  const { applicationError, detail, draft, draftError, etag, facts, operation, watch, workingDraftId } =
    useDraftDocument(applicationId);
  const editing = useDraftEditing({
    applicationId,
    draft,
    etag,
    facts,
    onOperationQueued: watch,
    workingDraftId,
  });
  const validation = useDraftValidation(applicationId, draft);

  /* Open on the document the user is deciding about. Claim provenance and editing are
     one deliberate switch away instead of making every fact and advanced control part
     of the first reading surface. */
  const [mode, setMode] = useState<DraftWorkspaceMode>("document");
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

  useEffect(() => {
    if (
      operation?.operation_type === "render_revision" &&
      operation.status === "succeeded" &&
      renderRevisionId !== null
    ) {
      navigate(routePaths.revision(renderRevisionId), { replace: true });
    }
  }, [navigate, operation, renderRevisionId]);

  /* Hiding the rows must not strand text still sitting in the buffer, so the document
     view settles it first. */
  const changeMode = (next: DraftWorkspaceMode) => {
    if (next === "document") editing.flush();
    setMode(next);
  };

  const applicationHref = routePaths.application(applicationId);

  return (
    /* No description: `DraftHeaderCard` below names the company and the target role
       together, and the heading repeated the role on its own a line above it. The step's
       name is the shell's, from the same table the spine marks it with - it used to be
       "קריאה, אימות ואישור", three words the rail does not use, so the reader's position
       had two names depending on which of the two they read. */
    <WizardStepShell
      applicationId={applicationId}
      detail={detail}
      eyebrow={
        detail === undefined ? undefined : (
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

          {/* Live work, reported beside the draft it is rewriting rather than on a screen
              the user has to leave the text for. */}
          {operation === undefined ? null : <ActiveOperationPanel onQueued={watch} operation={operation} />}

          {/* The projection's own blockers, reported by the one region that reports them.
              A claim with no fact behind it raises PENDING_FACT_REQUIRES_RESOLUTION there,
              and it is shown here as the reason it already is rather than as an approval
              rule this screen invented. This screen used to map the same two arrays into
              bare titles of its own - no server message, no control - which named what
              refuses approval without naming anything the reader could do about it. */}
          <PreparationAlerts detail={detail} screen="draft" />

          {workingDraftId === null && renderRevisionId === null ? (
            <DraftEmptyState applicationId={applicationId} />
          ) : null}
        </>
      )}

      {renderRevisionId !== null ? (
        <DraftRenderPanel
          approvedRevisionId={renderRevisionId}
          autoStart={approvedRevisionId !== null}
          onQueued={watch}
          /* The live render is reported once, by `ActiveOperationPanel` above. This tells
             the render panel to stand down while that is true, so the approved box and its
             "create the files" CTA never appear beside the operation already creating
             them. */
          rendering={operation?.operation_type === "render_revision" && !isTerminalOperation(operation)}
        />
      ) : null}

      {renderRevisionId === null && draft === undefined && workingDraftId !== null && draftError === null ? (
        <QueryState loading loadingLabel="טוען את הטיוטה…" />
      ) : null}

      {renderRevisionId !== null || draft === undefined ? null : (
        <>
          <DraftWorkspace
            editor={
              <>
                <DraftOutlineEditor
                  actions={editing.claimActions}
                  draft={draft}
                  factContext={{
                    analysisId: detail?.active_analysis_id ?? null,
                    applicationId,
                    language: facts?.language ?? detail?.application.language ?? "en",
                    profile: detail?.application.profile ?? null,
                  }}
                  facts={facts}
                  onRegenerateSection={editing.regenerateSection}
                />

                <DraftEditorNotices
                  aiUnavailable={editing.aiUnavailable}
                  dirty={editing.dirty}
                  regenerationError={editing.regenerationError}
                  selectionError={editing.selectionError}
                />

                <DraftFactPanel busy={editing.selectionPending} facts={facts} onInclude={editing.includeFact} />

                <FactLifecyclePanel
                  profile={detail?.application.profile ?? null}
                  sections={draft.outline.sections.map((section) => section.name)}
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
            onApprove={() => setApprovalOpen(true)}
            reviewBlocked={(detail?.review_reasons ?? []).length > 0}
            stale={validation.stale}
            validationResult={
              validation.error !== null && validation.error !== undefined
                ? "לא ניתן להשלים את האימות. פרטי השגיאה מופיעים לצד הטיוטה."
                : validation.lastRun === undefined
                ? undefined
                : validation.lastRun.passed && validation.exactPassingRunId !== null
                  ? "האימות הושלם בהצלחה. הטיוטה מוכנה לאישור."
                  : validation.lastRun.passed
                    ? "האימות הושלם, אך הטיוטה השתנתה מאז. יש להריץ אימות חדש."
                    : "האימות הושלם והטיוטה לא עברה. פרטי הכשל מופיעים לצד הטיוטה."
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
            open={approvalOpen}
            validationRunId={validation.exactPassingRunId}
          />

          <DraftConflictDialog
            current={draft}
            onDiscardLocal={editing.conflict.discardLocal}
            onReapplyLocal={editing.conflict.reapplyLocal}
            open={editing.conflict.open}
            pending={editing.conflict.pending}
            pendingRemovals={editing.conflict.pendingRemovals}
          />
        </>
      )}
    </WizardStepShell>
  );
};
