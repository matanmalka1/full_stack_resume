import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback } from "react";
import { Link, useParams } from "react-router-dom";

import { applicationDetailQueryKey, applicationDetailQueryOptions } from "../api/applications";
import { ApiProblem } from "../api/client";
import type { DraftClaim, WorkingDraftUpdate } from "../api/contracts";
import {
  type DraftRead,
  workingDraftFactsQueryKey,
  workingDraftFactsQueryOptions,
  workingDraftQueryKey,
  workingDraftQueryOptions,
} from "../api/drafts";
import { useWorkflowStage } from "../app/WorkflowLandmark";
import { buttonClasses } from "../ui/Button";
import { Callout } from "../ui/Callout";
import { Card } from "../ui/Card";
import { LtrText } from "../ui/LtrText";
import { PageHeading } from "../ui/PageHeading";
import { StatusBadge } from "../ui/StatusBadge";
import { TechnicalDetails } from "../ui/TechnicalDetails";
import { DraftClaimCard } from "./DraftClaimCard";
import { DraftConflictDialog } from "./DraftConflictDialog";
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

  /* Which command removes a line is `removability`'s answer, not a guess made here. The
     patch takes the unauthorized ones; the deterministic exclusion arrives with the
     selection controls. */
  const removeClaim = (claim: DraftClaim) => {
    if (draft !== undefined && removability(claim, draft, facts).route === "patch") {
      autosave.queueRemoval(claim.claim_id);
    }
  };

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
                  onRemove={removeClaim}
                />
                {draft.outline.contacts.map((contact) => (
                  <DraftClaimCard
                    claim={contact}
                    draft={draft}
                    facts={facts}
                    key={contact.claim_id}
                    onBlur={autosave.flush}
                    onEdit={editClaim}
                    onRemove={removeClaim}
                  />
                ))}
              </ul>

              {draft.outline.sections.map((section) => (
                <div className="flex flex-col gap-3" key={section.name}>
                  <h3 className="text-body font-semibold text-cv-text" dir="auto">
                    {section.name}
                  </h3>
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
                          onRemove={removeClaim}
                        />
                      ))}
                    </ul>
                  )}
                </div>
              ))}
            </section>

            <div>
              <Link className={buttonClasses("secondary")} to={applicationHref}>
                חזרה למועמדות
              </Link>
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
