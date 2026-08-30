import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo } from "react";
import { Link } from "react-router-dom";

import {
  applicationDetailQueryKey,
  startAnalysis,
  startDraftGeneration,
} from "../api/applications";
import type { ApplicationDetail } from "../api/contracts";
import { executionProvider, settingsQueryOptions } from "../api/settings";
import { type QueuedOperation, operationQueryKey } from "../api/operations";
import { ErrorCallout } from "../app/ErrorCallout";
import { ActionBar } from "../ui/ActionBar";
import { Button, buttonClasses } from "../ui/Button";
import { Callout } from "../ui/Callout";
import { actionDestination } from "./actionDestinations";
import { actionLabel } from "./applicationLabels";

interface ApplicationActionsProps {
  detail: ApplicationDetail;
  /* What this component just queued. The projection reports an Operation only on its next
     read, so without this the panel would appear a poll later than the press that caused
     it - and a command that failed before the worker picked it up might never be reported
     at all. The accepted `202` is the earliest and most certain answer, so it is handed
     straight to the screen that shows it. */
  onQueued: (operationId: string) => void;
}

/* A.1: the actions come from the projection. This screen implements `analyze` and the
   no-review `create_draft` continuation; any other action the backend recommends is named
   and reported as not yet built, because inventing a destination for it would be exactly
   the second workflow state machine the information architecture forbids. */
export const ApplicationActions = ({ detail, onQueued }: ApplicationActionsProps) => {
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
     both follow it the same way - and neither navigates.

     Queueing used to send the user to the Operation's own screen, which made every action
     a round trip out of the context they were working in and back again. The projection
     carries `active_operation` in full and starts polling the moment it appears, so the
     Application screen reports the work in place. What the accepted `202` still buys is
     the first state: seeding it means the panel appears immediately instead of after the
     next poll, and the Operation screen a direct link reaches is already warm. */
  const followQueued = ({ operation }: QueuedOperation) => {
    queryClient.setQueryData(operationQueryKey(operation.id), operation);
    onQueued(operation.id);
    void queryClient.invalidateQueries({ queryKey: applicationDetailQueryKey(detail.application.id) });
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

  /* The review decision has no button here and no destination anywhere: its control is a
     panel on this same screen, directly under the analysis it decides about. It is still
     "handled" - more completely than a link ever handled it - so it is registered below
     rather than reported as an action whose screen was never built. */
  const reviewHandledHere = detail.available_actions.includes("apply_analysis_decisions");

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
  /* Rendering happens in the draft editor, on the revision the approval there
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
  if (reviewHandledHere) {
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
  /* `update_working_draft`, `validate` and `approve` all resolve to the draft editor:
     validation is a panel on that screen and approval is a dialog opened from it, so all
     three are the same link wearing three labels. Offered side by side they read as three
     destinations and ask the reader to choose between them, when every choice arrives at
     the same place - and on this screen the row had four buttons, three of which went to
     one URL.

     So they collapse to one control. Which of the three names it is the projection's
     recommendation, not this screen's guess; with none of them recommended the furthest
     along is the honest label, because that is the one the workflow is waiting on. The
     approval dialog behind it carries the acknowledgement and the immutability warning,
     which is why nothing here needs to restate them: this button navigates, it does not
     commit. */
  /* Furthest along wins the label: if approval is offered the draft is validated and
     approving is what the workflow is waiting on, and so down the chain. The projection's
     recommendation decides emphasis only - it never picks a different destination, since
     there is only one. */
  const draftScreen =
    approvalHref !== null
      ? { href: approvalHref, label: "אישור הגרסה" }
      : validationHref !== null
        ? { href: validationHref, label: "אימות הטיוטה" }
        : editHref !== null
          ? { href: editHref, label: "עריכת הטיוטה" }
          : null;
  const draftScreenButton = routeButton(
    "draft-screen",
    draftScreen?.href ?? null,
    draftScreen?.label ?? "",
    recommended === "approve" || recommended === "validate" || recommended === "update_working_draft",
  );
  const readyButton = routeButton("ready", readyHref, "צפייה בגרסה המוכנה", detail.preparation_state === "ready");

  return (
    <div className="flex flex-col gap-4">
      {error === null ? null : (
        <ErrorCallout
          error={error}
          fallbackDetail="לא ניתן להפעיל את הפעולה. מצב המועמדות לא השתנה ואפשר לנסות שוב."
          fallbackTitle="הפעולה לא בוצעה"
        />
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
          is active, so the consequence is stated rather than confirmed away.

          It is stated where the consequence exists. With no draft to mark stale, the
          sentence was warning about an effect on a record that is not there - one of three
          paragraphs of caveat standing between the reader and the button they came to
          press, and the only one of them attached to the secondary action. */}
      {canAnalyze && !analyzeRecommended && draftWouldReplace ? (
        <p className="text-support leading-6 text-cv-text-muted">
          ניתוח מחדש יוצר ניתוח חדש ונפרד לאותו תצלום משרה. הטיוטה הפעילה נשמרת כפי שהיא, אך תסומן
          כלא מעודכנת מולו.
        </p>
      ) : null}

      {/* The sources are named, not resolved: the draft is built from the analysis and
          the plan the screen is showing, and neither is changed by building from it.

          The clause reassuring the reader that no active draft is being overwritten went
          with the stage that already says so - `canDraft` requires `working_draft_state`
          to be `none`, which is the same fact. It returns below, where it stops being
          true. */}
      {canDraft ? (
        <p className="text-support leading-6 text-cv-text-muted">
          הטיוטה נוצרת מהניתוח ומתוכנית הבחירה הפעילים של המועמדות. שניהם רשומות שאינן משתנות.
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
          draftButton,
          draftScreenButton,
          readyButton,
        ].filter((button) => button !== null);

        if (inWorkflowOrder.length === 0) {
          return null;
        }

        const recommendedKey = new Map<string, boolean>([
          ["analyze", analyzeRecommended],
          ["draft", draftRecommended],
          [
            "draft-screen",
            editRecommended || recommended === "validate" || recommended === "approve",
          ],
          ["ready", detail.preparation_state === "ready"],
        ]);
        const emphasized =
          inWorkflowOrder.find((button) => recommendedKey.get(String(button.key)) === true) ??
          inWorkflowOrder[inWorkflowOrder.length - 1];
        const rest = inWorkflowOrder.filter((button) => button !== emphasized);

        return (
          <ActionBar
            /* The offered actions continue the next-step sentence above them rather than
               closing the page, so they start where that sentence starts. Whether there
               is one of them or several, they are the reader's way on from that line and
               belong beside it, not at the far edge of the card. */
            align="start"
            primary={emphasized}
            secondary={rest.length === 0 ? undefined : rest}
          />
        );
      })()}
    </div>
  );
};
