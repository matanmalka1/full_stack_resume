import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { applicationDetailQueryKey, applicationDetailQueryOptions } from "../api/applications";
import { ApiProblem } from "../api/client";
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
import { DraftClaimCard } from "./DraftClaimCard";
import { DraftConflictDialog } from "./DraftConflictDialog";
import { DraftFactPanel } from "./DraftFactPanel";
import { DraftPreview } from "./DraftPreview";
import { DraftSaveState } from "./DraftSaveState";
import { removability } from "./claimRemoval";
import { useDraftAutosave } from "./useDraftAutosave";
import { actionLabel, workingDraftStateLabels, workingDraftStateTones } from "./applicationLabels";

const problemMessage = (error: unknown, fallback: string): string =>
  error instanceof ApiProblem ? error.problem.detail : fallback;

const ErrorCallout = ({ error, title }: { error: unknown; title: string }) => (
  <Callout
    role="alert"
    title={error instanceof ApiProblem ? error.problem.title : title}
    tone="blocker"
  >
    {problemMessage(error, "הפנייה לשרת נכשלה. אפשר לרענן את העמוד ולנסות שוב.")}
    {error instanceof ApiProblem ? (
      <TechnicalDetails className="mt-3">
        <LtrText>{error.problem.code}</LtrText>
      </TechnicalDetails>
    ) : null}
  </Callout>
);

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
  const navigate = useNavigate();
  /* A.4's responsive fallback. Both panes stay mounted and one is hidden, rather than one
     being unmounted: switching views must not discard text the user has typed, and an
     unmounted editor would take its visible text with it. */
  const [view, setView] = useState<"editor" | "preview">("editor");

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

  /* §14 regeneration is an Operation, so it leaves this screen for the one that owns
     Operation progress, failure, and retry. The accepted representation is seeded there
     rather than fetched again, exactly as analyze and generate do. */
  const followQueued = ({ operation, operationPath }: QueuedOperation) => {
    queryClient.setQueryData(operationQueryKey(operation.id), operation);
    void navigate(operationPath);
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
        id="route-heading"
      >
        עריכת הטיוטה
      </PageHeading>

      <div className="mt-6 flex flex-col gap-6">
        {applicationQuery.error === null ? null : (
          <ErrorCallout error={applicationQuery.error} title="לא ניתן לטעון את מצב המועמדות" />
        )}
        {draftQuery.error === null ? null : (
          <ErrorCallout error={draftQuery.error} title="לא ניתן לטעון את הטיוטה" />
        )}

        {detail !== undefined && workingDraftId === null ? (
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
          <div className="flex flex-wrap items-center gap-3">
            <StatusBadge tone={workingDraftStateTones[detail.working_draft_state]}>
              {workingDraftStateLabels[detail.working_draft_state]}
            </StatusBadge>
            <DraftSaveState state={autosave} />
          </div>
        )}

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

        {draft === undefined ? (
          workingDraftId === null || draftQuery.error !== null ? null : (
            <p className="text-body text-cv-text-muted">טוען את הטיוטה…</p>
          )
        ) : (
          <div className="flex flex-col gap-6">
            <div className="lg:hidden">
              <ViewSwitch
                label="מעבר בין העריכה לתצוגה"
                onChange={setView}
                options={[
                  { label: "עריכה", value: "editor" },
                  { label: "תצוגה", value: "preview" },
                ]}
                value={view}
              />
            </div>

            <div className="flex flex-col gap-6 lg:flex-row lg:items-start lg:gap-8">
              <div
                className={cx(
                  "flex flex-col gap-6 lg:flex-1 lg:basis-3/5",
                  view === "editor" ? undefined : "hidden lg:flex",
                )}
              >
                <section aria-labelledby="draft-structure-heading" className="flex flex-col gap-4">
                  <h2
                    className="text-heading-sm font-semibold text-cv-text"
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
                    <div className="flex flex-col gap-3" key={section.name}>
                      <div className="flex flex-wrap items-center justify-between gap-3">
                        <h3 className="text-body font-semibold text-cv-text" dir="auto">
                          {section.name}
                        </h3>
                        <Button
                          disabled={unsaved || regeneration.isPending || !regenerationAvailable}
                          onClick={() => regeneration.mutate({ section: section.name })}
                          variant="secondary"
                        >
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
                  <Callout role="alert" title="היצירה מחדש לא הופעלה" tone="blocker">
                    {problemMessage(
                      regeneration.error,
                      "לא ניתן היה להפעיל יצירה מחדש. הטיוטה נשמרה כפי שהיא.",
                    )}
                    {regeneration.error instanceof ApiProblem ? (
                      <TechnicalDetails className="mt-3">
                        <LtrText>{regeneration.error.problem.code}</LtrText>
                      </TechnicalDetails>
                    ) : null}
                  </Callout>
                )}

                {unsaved ? (
                  <p className="text-support leading-6 text-cv-text-muted">
                    יצירה מחדש מוקפאת על הגרסה השמורה של הטיוטה, ולכן היא זמינה רק אחרי שהשמירה
                    הסתיימה.
                  </p>
                ) : null}

                {selection.error === null ? null : (
                  <Callout role="alert" title="שינוי הבחירה לא בוצע" tone="blocker">
                    {problemMessage(
                      selection.error,
                      "לא ניתן היה לשנות את בחירת העובדות. הטיוטה נשמרה כפי שהיא.",
                    )}
                    {selection.error instanceof ApiProblem ? (
                      <TechnicalDetails className="mt-3">
                        <LtrText>{selection.error.problem.code}</LtrText>
                      </TechnicalDetails>
                    ) : null}
                  </Callout>
                )}

                <DraftFactPanel busy={selection.isPending} facts={facts} onInclude={includeFact} />

                <div>
                  <Link className={buttonClasses("secondary")} to={applicationHref}>
                    חזרה למועמדות
                  </Link>
                </div>
              </div>

              <div
                className={cx(
                  "lg:flex-1 lg:basis-2/5",
                  view === "preview" ? undefined : "hidden lg:block",
                )}
              >
                <DraftPreview draft={draft} />
              </div>
            </div>

            <TechnicalDetails>
              <LtrText>{`${draft.id} · v${draft.edit_version}`}</LtrText>
            </TechnicalDetails>

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
