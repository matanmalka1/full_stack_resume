import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useMemo } from "react";
import { Link, useNavigate } from "react-router-dom";

import { startAnalysis, startDraftGeneration } from "../api/applications";
import { ApiProblem } from "../api/client";
import type { ApplicationDetail } from "../api/contracts";
import { type QueuedOperation, operationQueryKey } from "../api/operations";
import { ActionBar } from "../ui/ActionBar";
import { Button, buttonClasses } from "../ui/Button";
import { Callout } from "../ui/Callout";
import { LtrText } from "../ui/LtrText";
import { TechnicalDetails } from "../ui/TechnicalDetails";
import { actionDestination } from "./actionDestinations";
import { actionLabel } from "./applicationLabels";

interface ApplicationActionsProps {
  detail: ApplicationDetail;
}

const mutationMessage = (error: unknown): string =>
  error instanceof ApiProblem
    ? error.problem.detail
    : "לא ניתן להפעיל את הפעולה. מצב המועמדות לא השתנה ואפשר לנסות שוב.";

/* A.1: the actions come from the projection. This screen implements `analyze` and the
   no-review `create_draft` continuation; any other action the backend recommends is named
   and reported as not yet built, because inventing a destination for it would be exactly
   the second workflow state machine the information architecture forbids. */
export const ApplicationActions = ({ detail }: ApplicationActionsProps) => {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const snapshotId = detail.active_job_snapshot_id;
  const analysisId = detail.active_analysis_id ?? null;
  const selectionPlanId = detail.active_selection_plan_id ?? null;
  /* One key per snapshot: an answer that never arrived can be sent again without
     queueing a second analysis of the same posting. */
  const analyzeKey = useMemo(() => crypto.randomUUID(), [snapshotId]);
  /* One key per source pair, for the same reason: a resent generate for the same analysis
     and plan is the same command, and a different pair is a different one. */
  const draftKey = useMemo(() => crypto.randomUUID(), [analysisId, selectionPlanId]);

  /* Both commands queue durable work and answer `202` with the Operation they queued, so
     both follow it the same way: seed the accepted representation as the Operation
     screen's first state rather than fetching it a second time, then navigate. */
  const followQueued = ({ operation, operationPath }: QueuedOperation) => {
    queryClient.setQueryData(operationQueryKey(operation.id), operation);
    void navigate(operationPath);
  };

  const analyze = useMutation({
    mutationFn: () => startAnalysis(detail.application.id, snapshotId, analyzeKey),
    onSuccess: followQueued,
  });

  const draft = useMutation({
    mutationFn: async () => {
      /* Availability is the projection's answer, but the IDs are this call's arguments:
         a generate without both of them is not a command this screen may send. */
      if (analysisId === null || selectionPlanId === null) {
        throw new Error("create_draft was offered without an active analysis and selection plan");
      }
      return startDraftGeneration(detail.application.id, analysisId, selectionPlanId, draftKey);
    },
    onSuccess: followQueued,
  });

  const recommended = detail.recommended_action ?? null;
  const canAnalyze = detail.available_actions.includes("analyze");
  const analyzeRecommended = recommended === "analyze";

  /* §14: generate writes over the one active WorkingDraft. With no draft there is nothing
     to discard. With one, discarding it is a choice - `replace_working_draft` carries the
     exact version and the Keep decision - and this screen has neither, so it does not
     offer a button that would silently overwrite the user's working copy. */
  const draftAvailable =
    detail.available_actions.includes("create_draft") &&
    analysisId !== null &&
    selectionPlanId !== null;
  const draftWouldReplace = detail.working_draft_state !== "none";
  const canDraft = draftAvailable && !draftWouldReplace;
  const draftRecommended = recommended === "create_draft";

  /* An action this screen can take the user to is as "built" as one it performs: the
     review decision is committed on its own screen, not here. */
  const reviewHref = detail.available_actions.includes("apply_analysis_decisions")
    ? actionDestination("apply_analysis_decisions", detail.application.id)
    : null;
  const reviewRecommended = recommended === "apply_analysis_decisions";

  /* The same, for the draft the user is holding. The editor is the screen for every
     command addressed at an existing draft, so availability of the autosave patch is what
     says there is something there to edit. */
  const editHref = detail.available_actions.includes("update_working_draft")
    ? actionDestination("update_working_draft", detail.application.id)
    : null;
  const editRecommended = recommended === "update_working_draft";

  const handledHere = new Set<string>();
  if (canAnalyze) {
    handledHere.add("analyze");
  }
  if (canDraft) {
    handledHere.add("create_draft");
  }
  if (reviewHref !== null) {
    handledHere.add("apply_analysis_decisions");
  }
  if (editHref !== null) {
    handledHere.add("update_working_draft");
  }

  /* "Its screen is not built" is a claim about existence, not about availability, so it
     is answered by the same route table the reason callouts ask. Gating it on
     availability instead would let this block say a screen does not exist while a
     review reason beside it links to that very screen. */
  const unbuilt =
    recommended !== null &&
    !handledHere.has(recommended) &&
    actionDestination(recommended, detail.application.id) === null
      ? recommended
      : null;
  const error = analyze.error ?? draft.error;

  const analyzeButton = canAnalyze ? (
    <Button
      disabled={analyze.isPending}
      onClick={() => analyze.mutate()}
      variant={analyzeRecommended ? "primary" : "secondary"}
    >
      {analyze.isPending
        ? "מפעיל ניתוח…"
        : analyzeRecommended
          ? "ניתוח המשרה"
          : "ניתוח מחדש של המשרה"}
    </Button>
  ) : null;

  const reviewButton =
    reviewHref === null ? null : (
      <Link className={buttonClasses(reviewRecommended ? "primary" : "secondary")} to={reviewHref}>
        החלטות הסקירה
      </Link>
    );

  const editButton =
    editHref === null ? null : (
      <Link className={buttonClasses(editRecommended ? "primary" : "secondary")} to={editHref}>
        עריכת הטיוטה
      </Link>
    );

  const draftButton = canDraft ? (
    <Button
      disabled={draft.isPending}
      onClick={() => draft.mutate()}
      variant={draftRecommended ? "primary" : "secondary"}
    >
      {draft.isPending ? "יוצר טיוטה…" : "יצירת טיוטה"}
    </Button>
  ) : null;

  return (
    <div className="flex flex-col gap-4">
      {error === null ? null : (
        <Callout role="alert" title="הפעולה לא בוצעה" tone="blocker">
          {mutationMessage(error)}
          {error instanceof ApiProblem ? (
            <TechnicalDetails className="mt-3">
              <LtrText>{error.problem.code}</LtrText>
            </TechnicalDetails>
          ) : null}
        </Callout>
      )}

      {unbuilt === null ? null : (
        <Callout title={`הפעולה המומלצת כעת היא ${actionLabel(unbuilt)}`} tone="neutral">
          {unbuilt === "create_draft" && draftWouldReplace
            ? "יצירת טיוטה חדשה כותבת על הטיוטה הפעילה, ולכן היא דורשת החלטה מפורשת על שמירת הטיוטה הקיימת. מסך ההחלפה מגיע בפרוסה הבאה, ועד אז הטיוטה הפעילה נשמרת כפי שהיא."
            : "המסך שלה עדיין לא נבנה והוא מגיע בפרוסה הבאה. מצב המועמדות שלמעלה הוא המקור המדויק, ושום פעולה אינה מופעלת מעצמה."}
        </Callout>
      )}

      {/* Re-analysis destroys nothing: the existing JobAnalysis and any active draft are
          immutable records that stay exactly as they are. What changes is which analysis
          is active, so the consequence is stated rather than confirmed away. */}
      {canAnalyze && !analyzeRecommended ? (
        <p className="text-support leading-6 text-cv-text-muted">
          ניתוח מחדש יוצר ניתוח חדש ונפרד לאותו תצלום משרה. הטיוטה הפעילה נשמרת כפי שהיא,
          אך תסומן כלא מעודכנת מולו.
        </p>
      ) : null}

      {/* The sources are named, not resolved: the draft is built from the analysis and the
          plan the screen is showing, and neither of them is changed by building from it. */}
      {canDraft ? (
        <p className="text-support leading-6 text-cv-text-muted">
          הטיוטה נוצרת מהניתוח ומתוכנית הבחירה הפעילים של המועמדות. שניהם רשומות שאינן
          משתנות, ואין כעת טיוטה פעילה שהיצירה כותבת עליה.
        </p>
      ) : null}

      {(() => {
        /* One emphasized primary (A.1). Review outranks the draft while a decision is
           still owed, editing an existing draft outranks building another one, and
           analyze stays the fallback when nothing else is offered. */
        const ordered = [reviewButton, editButton, draftButton, analyzeButton].filter(
          (button) => button !== null,
        );
        return ordered.length === 0 ? null : (
          <ActionBar
            primary={ordered[0]}
            secondary={ordered.length === 1 ? undefined : ordered.slice(1)}
          />
        );
      })()}
    </div>
  );
};
