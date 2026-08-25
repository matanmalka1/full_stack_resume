import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo } from "react";
import { Link, useNavigate } from "react-router-dom";

import { startAnalysis, startDraftGeneration } from "../api/applications";
import { ApiProblem } from "../api/client";
import type { ApplicationDetail } from "../api/contracts";
import { executionProvider, settingsQueryOptions } from "../api/settings";
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
  /* App owns the live settings read. This subscription consumes that cache without
     opening one request per action panel; isolated renders retain the safe deterministic
     default until a shell-provided value exists. */
  const settingsQuery = useQuery({ ...settingsQueryOptions, enabled: false });
  const settings = settingsQuery.data?.settings;
  const provider = executionProvider(settings);
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
    mutationFn: () => startAnalysis(detail.application.id, snapshotId, analyzeKey, provider),
    onSuccess: followQueued,
  });

  const draft = useMutation({
    mutationFn: async () => {
      /* Availability is the projection's answer, but the IDs are this call's arguments:
         a generate without both of them is not a command this screen may send. */
      if (analysisId === null || selectionPlanId === null) {
        throw new Error("create_draft was offered without an active analysis and selection plan");
      }
      return startDraftGeneration(detail.application.id, analysisId, selectionPlanId, draftKey, { provider });
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
  const validationHref = detail.available_actions.includes("validate")
    ? actionDestination("validate", detail.application.id)
    : null;
  const approvalHref = detail.available_actions.includes("approve")
    ? actionDestination("approve", detail.application.id)
    : null;
  /* Rendering happens in the draft workspace, on the revision the approval there
     produced. There is no render screen to link to, so the projection's `render` is
     reported by name below rather than given a destination this table does not have. */
  const readyHref = detail.latest_ready_revision_id == null
    ? null
    : `/approved-revisions/${encodeURIComponent(detail.latest_ready_revision_id)}/ready`;

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
  if (validationHref !== null) handledHere.add("validate");
  if (approvalHref !== null) handledHere.add("approve");

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
  const error = settingsQuery.error ?? analyze.error ?? draft.error;

  /* Keyed because the bar renders them from an array: with more than one secondary
     action, React needs each to be identifiable across renders. */
  const analyzeButton = canAnalyze ? (
    <Button
      disabled={settings === undefined || analyze.isPending}
      key="analyze"
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
      <Link
        className={buttonClasses(reviewRecommended ? "primary" : "secondary")}
        key="review"
        to={reviewHref}
      >
        החלטות הסקירה
      </Link>
    );

  const editButton =
    editHref === null ? null : (
      <Link
        className={buttonClasses(editRecommended ? "primary" : "secondary")}
        key="edit"
        to={editHref}
      >
        עריכת הטיוטה
      </Link>
    );

  const draftButton = canDraft ? (
    <Button
      disabled={settings === undefined || draft.isPending}
      key="draft"
      onClick={() => draft.mutate()}
      variant={draftRecommended ? "primary" : "secondary"}
    >
      {draft.isPending ? "יוצר טיוטה…" : "יצירת טיוטה"}
    </Button>
  ) : null;
  const routeButton = (key: string, href: string | null, label: string, emphasized: boolean) =>
    href === null ? null : <Link className={buttonClasses(emphasized ? "primary" : "secondary")} key={key} to={href}>{label}</Link>;
  const validationButton = routeButton("validate", validationHref, "אימות הטיוטה", recommended === "validate");
  const approvalButton = routeButton("approve", approvalHref, "אישור הגרסה", recommended === "approve");
  const readyButton = routeButton("ready", readyHref, "צפייה בגרסה המוכנה", detail.preparation_state === "ready");

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
          ניתוח מחדש יוצר ניתוח חדש ונפרד לאותו תצלום משרה. הטיוטה הפעילה נשמרת כפי שהיא, אך תסומן
          כלא מעודכנת מולו.
        </p>
      ) : null}

      {/* The sources are named, not resolved: the draft is built from the analysis and the
          plan the screen is showing, and neither of them is changed by building from it. */}
      {canDraft ? (
        <p className="text-support leading-6 text-cv-text-muted">
          הטיוטה נוצרת מהניתוח ומתוכנית הבחירה הפעילים של המועמדות. שניהם רשומות שאינן משתנות, ואין
          כעת טיוטה פעילה שהיצירה כותבת עליה.
        </p>
      ) : null}

      {(() => {
        /* Workflow order, and the same order every visit: analyze, review, draft, edit,
           validate, approve, ready. The bar used to be sorted by how far along each
           action was, which moved a button to the front of the row on the visit it
           became available - so the control under the pointer was not the one that had
           been there a moment earlier.

           One emphasized primary (A.1), which stays the projection's own
           `recommended_action`: the order below decides position, never emphasis. With
           nothing recommended, the furthest-along offered action leads, because that is
           the one the workflow is actually waiting on. */
        const inWorkflowOrder = [
          analyzeButton,
          reviewButton,
          draftButton,
          editButton,
          validationButton,
          approvalButton,
          readyButton,
        ].filter((button) => button !== null);

        if (inWorkflowOrder.length === 0) {
          return null;
        }

        const recommendedKey = new Map<string, boolean>([
          ["analyze", analyzeRecommended],
          ["review", reviewRecommended],
          ["draft", draftRecommended],
          ["edit", editRecommended],
          ["validate", recommended === "validate"],
          ["approve", recommended === "approve"],
          ["ready", detail.preparation_state === "ready"],
        ]);
        const emphasized =
          inWorkflowOrder.find((button) => recommendedKey.get(String(button.key)) === true) ??
          inWorkflowOrder[inWorkflowOrder.length - 1];
        const rest = inWorkflowOrder.filter((button) => button !== emphasized);

        return (
          <ActionBar
            primary={emphasized}
            secondary={rest.length === 0 ? undefined : rest}
          />
        );
      })()}
    </div>
  );
};
