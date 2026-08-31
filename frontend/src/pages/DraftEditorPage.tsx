import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, RefreshCw } from "lucide-react";
import { useCallback, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { applicationDetailQueryKey, applicationDetailQueryOptions } from "../api/applications";
import { type QueuedOperation, operationQueryKey } from "../api/operations";
import type { DraftClaim, DraftFact, WorkingDraftUpdate } from "../api/contracts";
import {
  type DraftRead,
  applySelectionChange,
  regenerateClaim,
  regenerateSection,
  selectionOverlay,
  workingDraftFactsQueryKey,
  workingDraftFactsQueryOptions,
  workingDraftQueryKey,
  workingDraftQueryOptions,
} from "../api/drafts";
import { aiRegenerationAvailable, settingsQueryOptions } from "../api/settings";
import { ErrorCallout } from "../app/ErrorCallout";
import { useWorkflowStage } from "../app/WorkflowLandmark";
import { Button, buttonClasses } from "../ui/Button";
import { Callout } from "../ui/Callout";
import { cx } from "../ui/cx";
import { Card } from "../ui/Card";
import { LtrText } from "../ui/LtrText";
import { PageHeading } from "../ui/PageHeading";
import { StatusBadge } from "../ui/StatusBadge";
import { TechnicalDetails } from "../ui/TechnicalDetails";
import { ViewSwitch } from "../ui/ViewSwitch";
import { ActiveOperationPanel } from "./ActiveOperationPanel";
import { DraftApprovalDialog } from "./DraftApprovalDialog";
import { ClaimFactResolution } from "./ClaimFactResolution";
import { DraftClaimCard } from "./DraftClaimCard";
import { DraftConflictDialog } from "./DraftConflictDialog";
import { DraftFactPanel } from "./DraftFactPanel";
import { FactLifecyclePanel } from "./FactLifecyclePanel";
import { DraftPreview } from "./DraftPreview";
import { DraftRenderPanel } from "./DraftRenderPanel";
import { DraftSaveState } from "./DraftSaveState";
import { DraftValidationPanel } from "./DraftValidationPanel";
import { removability } from "./claimRemoval";
import { useDraftAutosave } from "./useDraftAutosave";
import { useWatchedOperation } from "./useWatchedOperation";
import { actionLabel, workingDraftStateLabels, workingDraftStateTones } from "./applicationLabels";

/* A.4 frame 3: the editor pane. It reads the §9 projection for which draft is active and
   what is blocking, and the draft itself for the structure it edits. It derives no second
   workflow state machine (A.1): the blockers below are the projection's own review
   reasons, and approval is refused by the backend, not by a rule invented here. */
export const DraftEditorPage = () => {
  const { applicationId } = useParams();

  if (applicationId === undefined) {
    throw new Error("DraftEditorPage rendered without an applicationId route parameter");
  }

  const applicationQuery = useQuery(applicationDetailQueryOptions(applicationId));
  const settingsQuery = useQuery({ ...settingsQueryOptions, enabled: false });
  const regenerationAvailable = aiRegenerationAvailable(settingsQuery.data?.settings);
  const detail = applicationQuery.data;
  useWorkflowStage(detail === undefined ? "unknown" : detail.preparation_state);
  /* The same watch the Application screen keeps, on the other screen that queues durable
     work against one Application. Regeneration is reported here, beside the draft it is
     rewriting. */
  const { operation: watched, watch } = useWatchedOperation(applicationId, detail);

  const workingDraftId = detail?.active_working_draft_id ?? null;
  const draftQuery = useQuery({
    ...workingDraftQueryOptions(workingDraftId ?? ""),
    enabled: workingDraftId !== null,
  });
  const factsQuery = useQuery({
    ...workingDraftFactsQueryOptions(workingDraftId ?? ""),
    enabled: workingDraftId !== null,
  });

  const draft = draftQuery.data?.draft;
  const facts = factsQuery.data;
  const applicationHref = `/applications/${encodeURIComponent(applicationId)}`;
  const queryClient = useQueryClient();
  /* A.4's responsive fallback. Both panes stay mounted and one is hidden, rather than one
     being unmounted: switching views must not discard text the user has typed, and an
     unmounted editor would take its visible text with it. */
  const [view, setView] = useState<"editor" | "preview">("editor");
  /* The three screens that used to follow the editor are states of this one editor.
     None of them changes what is sent: the validation panel runs the same command, the
     dialog is A.4 frame 5's own approval dialog, and the render panel keeps rendering an
     explicit action on the exact revision the approval returned. */
  const [approvalOpen, setApprovalOpen] = useState(false);
  const [validationStale, setValidationStale] = useState(false);
  const [exactPassingRunId, setExactPassingRunId] = useState<string | null>(null);
  /* The revision this editor just approved. Held here rather than read from the
     projection so the render step names the exact revision the approval returned. */
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

  /* A save changes the draft, so the read that produced it is stale by definition. The
     new token is installed directly - it is the one the response returned for the version
     that now exists - and the reads are invalidated so the outline, the pending claims,
     and the projection's blockers all come back describing the same version. */
  const onSaved = useCallback(
    (_update: WorkingDraftUpdate, etag: string | null) => {
      if (workingDraftId === null) {
        return;
      }
      queryClient.setQueryData<DraftRead>(workingDraftQueryKey(workingDraftId), (previous) =>
        previous === undefined ? previous : { ...previous, etag },
      );
      void queryClient.invalidateQueries({
        queryKey: workingDraftQueryKey(workingDraftId),
      });
      void queryClient.invalidateQueries({
        queryKey: workingDraftFactsQueryKey(workingDraftId),
      });
      void queryClient.invalidateQueries({
        queryKey: applicationDetailQueryKey(applicationId),
      });
    },
    [applicationId, queryClient, workingDraftId],
  );

  /* Stable, because the panel reports through it from an effect: a fresh function each
     render would make that effect re-run on every render of this screen. */
  const onExactPassingRun = useCallback((runId: string | null) => {
    setExactPassingRunId(runId);
    /* A fresh exact passing run is the answer to the staleness the approval reported. */
    if (runId !== null) {
      setValidationStale(false);
    }
  }, []);

  const autosave = useDraftAutosave({
    etag: draftQuery.data?.etag ?? null,
    onSaved,
    workingDraftId,
  });

  /* The fact links are the claim's own. An edit changes wording, not what backs it -
     relinking is a separate decision, and sending a different set here would silently
     re-authorize a line the user only rephrased. */
  const editClaim = (claim: DraftClaim, text: string) =>
    autosave.queueEdit({
      claim_id: claim.claim_id,
      fact_ids: claim.fact_ids,
      text,
    });

  /* §14: the overlay is absolute, so every change starts from what the accounting
     currently reports and adds one decision to it. Sending only what moved would drop
     every pin and exclusion the user made before. */
  const selection = useMutation({
    mutationFn: async (change: { pinned?: string[]; excluded?: string[] }) => {
      if (draft === undefined || facts === undefined) {
        throw new Error("a selection change was offered before the draft and its facts arrived");
      }
      const overlay = selectionOverlay(facts);
      return applySelectionChange(draft.id, draft.edit_version, {
        pinned_fact_ids: [...new Set([...overlay.pinned_fact_ids, ...(change.pinned ?? [])])],
        excluded_fact_ids: [...new Set([...overlay.excluded_fact_ids, ...(change.excluded ?? [])])],
      });
    },
    onSuccess: () => {
      /* The plan and the document changed together, and the ETag with them. Nothing from
         the response is seeded: the refreshed reads report the version that now exists. */
      onSaved({} as WorkingDraftUpdate, null);
    },
  });

  /* Which command removes a line is `removability`'s answer, not a guess made here: the
     patch takes the unauthorized claims, and a fact-authorized one is removed by
     excluding the facts behind it. */
  const removeClaim = (claim: DraftClaim) => {
    if (draft === undefined) {
      return;
    }
    const route = removability(claim, draft, facts).route;

    if (route === "patch") {
      autosave.queueRemoval(claim.claim_id);
    }
    if (route === "selection") {
      selection.mutate({ excluded: claim.fact_ids });
    }
  };

  /* Including an omitted fact is a pin: in a budgeted deterministic selection, holding it
     is the only way to say "keep this one". */
  const includeFact = (fact: DraftFact) => selection.mutate({ pinned: [fact.fact_id] });

  /* §14 regeneration is an Operation, and it is reported in place rather than followed to
     a screen of its own.

     It used to navigate. That made the one action that acts on a single line of the draft
     the only action that took the draft off the screen: the user regenerated a claim, was
     handed a progress line with no text beside it, and came back through a link that led
     to the Application screen rather than to the editor they had left. The Application
     screen already reports its own work this way, and this is the same watch - the
     projection opens it, the Operation's own query closes it, and the accepted `202`
     seeds the first state so the panel appears with the press rather than a poll later.

     `/operations/:id` stays reachable: the panel links to it, and it is where a direct
     link or a reload of a queued Operation lands. */
  const followQueued = ({ operation }: QueuedOperation) => {
    queryClient.setQueryData(operationQueryKey(operation.id), operation);
    watch(operation.id);
  };

  const regeneration = useMutation({
    mutationFn: async (target: { claimId?: string; section?: string }) => {
      if (draft === undefined) {
        throw new Error("a regeneration was offered before the draft arrived");
      }
      /* One key per target and version: a resent regeneration of the same line at the
         same version is the same command, and a different version is a different one. */
      const key = `${draft.id}:${draft.edit_version}:${target.claimId ?? target.section ?? ""}`;

      return target.claimId === undefined
        ? regenerateSection(draft, target.section ?? "", key)
        : regenerateClaim(draft, target.claimId, key);
    },
    onSuccess: followQueued,
  });

  /* The version and hash sent are the ones the read returned, so an unsaved edit would
     be regenerated away from. Autosave settles first, and until it does the control says
     so rather than freezing a version the user has already moved past. */
  const unsaved =
    autosave.status === "saving" ||
    autosave.status === "conflict" ||
    autosave.pending.length > 0 ||
    autosave.pendingRemovals.length > 0;

  return (
    <Card aria-labelledby="route-heading">
      <PageHeading
        description={
          detail === undefined
            ? "טוען את מצב המועמדות…"
            : `תפקיד היעד: ${detail.application.target_role}`
        }
        eyebrow="סביבת עריכה"
        id="route-heading"
      >
        עריכה, אימות ואישור
      </PageHeading>

      <div className="mt-6 flex flex-col gap-6">
        {applicationQuery.error === null ? null : (
          <ErrorCallout
            error={applicationQuery.error}
            fallbackDetail="הפנייה לשרת נכשלה. אפשר לרענן את העמוד ולנסות שוב."
            fallbackTitle="לא ניתן לטעון את מצב המועמדות"
          />
        )}
        {draftQuery.error === null ? null : (
          <ErrorCallout
            error={draftQuery.error}
            fallbackDetail="הפנייה לשרת נכשלה. אפשר לרענן את העמוד ולנסות שוב."
            fallbackTitle="לא ניתן לטעון את הטיוטה"
          />
        )}

        {detail !== undefined && workingDraftId === null && renderRevisionId === null ? (
          <Callout
            action={
              <Link className={buttonClasses("primary")} to={applicationHref}>
                חזרה למועמדות
              </Link>
            }
            title="אין כרגע טיוטה פעילה למועמדות הזו"
            tone="neutral"
          >
            מסך המועמדות מציג את המצב המדויק ואת הפעולה שיוצרת טיוטה.
          </Callout>
        ) : null}

        {detail === undefined ? null : (
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-surface border border-cv-border bg-cv-surface-muted px-4 py-3 shadow-inner">
            <StatusBadge tone={workingDraftStateTones[detail.working_draft_state]}>
              {workingDraftStateLabels[detail.working_draft_state]}
            </StatusBadge>
            {workingDraftId === null ? null : <DraftSaveState state={autosave} />}
          </div>
        )}

        {/* Live work, reported beside the draft it is rewriting rather than on a screen
            the user has to leave the text for. */}
        {watched === undefined ? null : <ActiveOperationPanel onQueued={watch} operation={watched} />}

        {/* The projection's own blockers. A claim with no fact behind it raises
            PENDING_FACT_REQUIRES_RESOLUTION there, and it is shown here as the reason it
            already is rather than as an approval rule this screen invented. */}
        {(detail?.review_reasons ?? []).map((reason) => (
          <Callout key={reason.code} title="נדרשת החלטה לפני אישור הגרסה" tone="blocker">
            <p dir="auto">{reason.message}</p>
            {reason.allowed_resolution_actions.length === 0 ? null : (
              <p className="mt-2">
                הפעולות שפותרות אותה:{" "}
                {reason.allowed_resolution_actions.map(actionLabel).join(" · ")}.
              </p>
            )}
            <TechnicalDetails className="mt-3">
              <LtrText>{reason.code}</LtrText>
            </TechnicalDetails>
          </Callout>
        ))}

        {(detail?.stale_reasons ?? []).map((reason) => (
          <Callout key={reason.code} title="הטיוטה אינה מעודכנת מול המקורות שלה" tone="warning">
            <p dir="auto">{reason.message}</p>
          </Callout>
        ))}

        {renderRevisionId !== null ? (
          <DraftRenderPanel approvedRevisionId={renderRevisionId} onQueued={watch} />
        ) : draft === undefined ? (
          workingDraftId === null || draftQuery.error !== null ? null : (
            <p className="text-body text-cv-text-muted">טוען את הטיוטה…</p>
          )
        ) : (
          <div className="flex flex-col gap-6">
            <div className="lg:hidden">
              <ViewSwitch
                label="מעבר בין העריכה לתצוגה ולאישור"
                onChange={setView}
                /* The second pane is no longer only a preview: it carries the validation
                   result and the approval too, so at narrow widths it is named for what
                   it holds rather than leaving those controls behind a label that does
                   not mention them. */
                options={[
                  { label: "עריכה", value: "editor" },
                  { label: "תצוגה ואישור", value: "preview" },
                ]}
                value={view}
              />
            </div>

            <div className="flex flex-col gap-6 lg:flex-row lg:items-start lg:gap-8 xl:gap-10">
              <div
                className={cx(
                  "flex min-w-0 flex-col gap-6 lg:flex-1 lg:basis-7/12",
                  view === "editor" ? undefined : "hidden lg:flex",
                )}
              >
                <section aria-labelledby="draft-structure-heading" className="flex flex-col gap-4">
                  <h2
                    className="text-heading-sm font-bold text-cv-text"
                    id="draft-structure-heading"
                  >
                    מבנה המסמך
                  </h2>

                  <ul className="flex flex-col gap-3">
                    <DraftClaimCard
                      claim={draft.outline.headline}
                      draft={draft}
                      facts={facts}
                      onBlur={autosave.flush}
                      onEdit={editClaim}
                      onRegenerate={(claim) => regeneration.mutate({ claimId: claim.claim_id })}
                      onRemove={removeClaim}
                      unsaved={unsaved || regeneration.isPending || !regenerationAvailable}
                    />
                    {draft.outline.contacts.map((contact) => (
                      <DraftClaimCard
                        claim={contact}
                        draft={draft}
                        facts={facts}
                        key={contact.claim_id}
                        onBlur={autosave.flush}
                        onEdit={editClaim}
                        onRegenerate={(claim) => regeneration.mutate({ claimId: claim.claim_id })}
                        onRemove={removeClaim}
                        unsaved={unsaved || regeneration.isPending || !regenerationAvailable}
                      />
                    ))}
                  </ul>

                  {draft.outline.sections.map((section) => (
                    <div
                      className="flex flex-col gap-3 border-t border-cv-border pt-6"
                      key={section.name}
                    >
                      <div className="flex flex-wrap items-center justify-between gap-3">
                        <h3 className="text-heading-sm font-bold text-cv-text" dir="auto">
                          {section.name}
                        </h3>
                        <Button
                          disabled={unsaved || regeneration.isPending || !regenerationAvailable}
                          onClick={() => regeneration.mutate({ section: section.name })}
                          variant="secondary"
                        >
                          <RefreshCw aria-hidden="true" className="size-4" />
                          יצירה מחדש של הפרק
                        </Button>
                      </div>
                      {section.claims.length === 0 ? (
                        <p className="text-support leading-6 text-cv-text-muted">
                          אין כרגע שורות בסעיף הזה.
                        </p>
                      ) : (
                        <ul className="flex flex-col gap-3">
                          {section.claims.map((claim) => (
                            <DraftClaimCard
                              claim={claim}
                              draft={draft}
                              factResolution={
                                <ClaimFactResolution
                                  analysisId={detail?.active_analysis_id ?? null}
                                  applicationId={applicationId}
                                  claim={claim}
                                  draft={draft}
                                  language={facts?.language ?? detail?.application.language ?? "en"}
                                  profile={detail?.application.profile ?? null}
                                  section={section.name}
                                />
                              }
                              facts={facts}
                              key={claim.claim_id}
                              onBlur={autosave.flush}
                              onEdit={editClaim}
                              onRegenerate={(claim) =>
                                regeneration.mutate({ claimId: claim.claim_id })
                              }
                              onRemove={removeClaim}
                              unsaved={unsaved || regeneration.isPending || !regenerationAvailable}
                            />
                          ))}
                        </ul>
                      )}
                    </div>
                  ))}
                </section>

                {regenerationAvailable ? null : (
                  <Callout title="יצירה מחדש באמצעות AI אינה זמינה" tone="neutral">
                    יש להגדיר ספק ולהפעיל AI במסך ההגדרות. לא יתבצע מעבר דטרמיניסטי שקט.
                    <div className="mt-3">
                      <Link className={buttonClasses("secondary")} to="/settings">מעבר להגדרות</Link>
                    </div>
                  </Callout>
                )}

                {regeneration.error === null ? null : (
                  <ErrorCallout
                    error={regeneration.error}
                    fallbackDetail="לא ניתן היה להפעיל יצירה מחדש. הטיוטה נשמרה כפי שהיא."
                    fallbackTitle="היצירה מחדש לא הופעלה"
                  />
                )}

                {unsaved ? (
                  <p className="text-support leading-6 text-cv-text-muted">
                    יצירה מחדש מוקפאת על הגרסה השמורה של הטיוטה, ולכן היא זמינה רק אחרי שהשמירה
                    הסתיימה.
                  </p>
                ) : null}

                {selection.error === null ? null : (
                  <ErrorCallout
                    error={selection.error}
                    fallbackDetail="לא ניתן היה לשנות את בחירת העובדות. הטיוטה נשמרה כפי שהיא."
                    fallbackTitle="שינוי הבחירה לא בוצע"
                  />
                )}

                <DraftFactPanel busy={selection.isPending} facts={facts} onInclude={includeFact} />

                <FactLifecyclePanel
                  profile={detail?.application.profile ?? null}
                  sections={draft.outline.sections.map((section) => section.name)}
                />

                <div>
                  <Link className={buttonClasses("secondary")} to={applicationHref}>
                    <ArrowRight aria-hidden="true" className="size-4" />
                    חזרה למועמדות
                  </Link>
                </div>
              </div>

              {/* The right pane is the document and everything said about it: the live
                  preview, the validation result for the exact version shown, and the
                  approval that follows from it. Those last two were screens; reaching
                  them meant leaving the text they describe. */}
              <div
                className={cx(
                  "flex min-w-0 flex-col gap-5 lg:sticky lg:top-20 lg:flex-1 lg:basis-5/12",
                  view === "preview" ? undefined : "hidden lg:flex",
                )}
              >
                <DraftPreview draft={draft} />

                <DraftValidationPanel
                  applicationId={applicationId}
                  draft={draft}
                  onExactPassingRun={onExactPassingRun}
                  stale={validationStale}
                />

                <div className="flex flex-wrap items-center justify-between gap-3 rounded-surface border border-cv-border bg-cv-surface p-4 shadow-surface">
                  <p className="text-support leading-6 text-cv-text-muted">
                    {exactPassingRunId === null
                      ? "האישור נפתח אחרי אימות שעבר על הגרסה המוצגת."
                      : "האימות עבר על הגרסה המוצגת."}
                  </p>
                  <Button
                    disabled={exactPassingRunId === null}
                    onClick={() => setApprovalOpen(true)}
                  >
                    אישור הגרסה
                  </Button>
                </div>
              </div>
            </div>

            <TechnicalDetails>
              <LtrText>{`${draft.id} · v${draft.edit_version}`}</LtrText>
            </TechnicalDetails>

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
                setValidationStale(true);
              }}
              open={approvalOpen}
              validationRunId={exactPassingRunId}
            />

            <DraftConflictDialog
              current={draft}
              onDiscardLocal={autosave.discardLocal}
              onReapplyLocal={autosave.reapplyLocal}
              open={autosave.status === "conflict"}
              pending={autosave.pending}
              pendingRemovals={autosave.pendingRemovals}
            />
          </div>
        )}
      </div>
    </Card>
  );
};
