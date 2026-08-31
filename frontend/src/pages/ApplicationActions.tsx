import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type ReactElement, useMemo } from "react";
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
import { applicationActionPlan } from "./applicationActionPlan";
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

/* A.1: the actions come from the projection, read by `applicationActionPlan`. What is left
   here is the two commands this screen sends and the bar it renders them in. */
export const ApplicationActions = ({ detail, onQueued }: ApplicationActionsProps) => {
  const queryClient = useQueryClient();
  /* App owns the live settings read. This subscription consumes that cache without
     opening one request per action panel; isolated renders retain the safe deterministic
     default until a shell-provided value exists. */
  const settingsQuery = useQuery({ ...settingsQueryOptions, enabled: false });
  const settings = settingsQuery.data?.settings;
  const provider = executionProvider(settings);
  const snapshotId = detail.active_job_snapshot_id;
  const plan = applicationActionPlan(detail);
  /* One key per snapshot: an answer that never arrived can be sent again without
     queueing a second analysis of the same posting. */
  const analyzeKey = useMemo(() => crypto.randomUUID(), [snapshotId]);
  /* One key per source pair, for the same reason: a resent generate for the same analysis
     and plan is the same command, and a different pair is a different one. */
  const draftKey = useMemo(
    () => crypto.randomUUID(),
    [plan.createDraft?.analysisId, plan.createDraft?.selectionPlanId],
  );

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
      if (plan.createDraft === null) {
        throw new Error("create_draft was offered without an active analysis and selection plan");
      }
      return startDraftGeneration(
        detail.application.id,
        plan.createDraft.analysisId,
        plan.createDraft.selectionPlanId,
        draftKey,
        { provider },
      );
    },
    onSuccess: followQueued,
  });

  const error = settingsQuery.error ?? analyze.error ?? draft.error;

  /* Keyed because the bar renders them from an array: with more than one secondary
     action, React needs each to be identifiable across renders. */
  const analyzeButton =
    plan.analyze === null ? null : (
      <Button
        disabled={settings === undefined || analyze.isPending}
        key="analyze"
        onClick={() => analyze.mutate()}
        variant={plan.analyze.emphasized ? "primary" : "secondary"}
      >
        {analyze.isPending
          ? "מפעיל ניתוח…"
          : plan.analyze.reanalysis
            ? "ניתוח מחדש של המשרה"
            : "ניתוח המשרה"}
      </Button>
    );

  const draftButton =
    plan.createDraft === null ? null : (
      <Button
        disabled={settings === undefined || draft.isPending}
        key="draft"
        onClick={() => draft.mutate()}
        variant={plan.createDraft.emphasized ? "primary" : "secondary"}
      >
        {draft.isPending ? "יוצר טיוטה…" : "יצירת טיוטה"}
      </Button>
    );

  const routeButton = (key: string, href: string, label: string, emphasized: boolean) => (
    <Link className={buttonClasses(emphasized ? "primary" : "secondary")} key={key} to={href}>
      {label}
    </Link>
  );
  const draftScreenButton =
    plan.draftScreen === null
      ? null
      : routeButton(
          "draft-screen",
          plan.draftScreen.href,
          plan.draftScreen.label,
          plan.draftScreen.emphasized,
        );
  const readyButton =
    plan.readyRevision === null
      ? null
      : routeButton(
          "ready",
          plan.readyRevision.href,
          "צפייה בגרסה המוכנה",
          plan.readyRevision.emphasized,
        );

  /* Workflow order, and the same order every visit: analyze, draft, the draft screen,
     ready. The bar used to be sorted by how far along each action was, which moved a
     button to the front of the row on the visit it became available - so the control
     under the pointer was not the one that had been there a moment earlier.

     One emphasized primary (A.1), which stays the projection's own `recommended_action`:
     the order below decides position, never emphasis. With nothing recommended, the
     furthest-along offered action leads, because that is the one the workflow is actually
     waiting on. */
  const inWorkflowOrder = [
    { emphasized: plan.analyze?.emphasized === true, node: analyzeButton },
    { emphasized: plan.createDraft?.emphasized === true, node: draftButton },
    { emphasized: plan.draftScreen?.emphasized === true, node: draftScreenButton },
    { emphasized: plan.readyRevision?.emphasized === true, node: readyButton },
  ].filter((entry): entry is { emphasized: boolean; node: ReactElement } => entry.node !== null);
  const emphasizedEntry =
    inWorkflowOrder.find((entry) => entry.emphasized) ??
    inWorkflowOrder[inWorkflowOrder.length - 1];
  const restButtons = inWorkflowOrder
    .filter((entry) => entry !== emphasizedEntry)
    .map((entry) => entry.node);

  return (
    <div className="flex flex-col gap-4">
      {error === null ? null : (
        <ErrorCallout
          error={error}
          fallbackDetail="לא ניתן להפעיל את הפעולה. מצב המועמדות לא השתנה ואפשר לנסות שוב."
          fallbackTitle="הפעולה לא בוצעה"
        />
      )}

      {plan.unbuiltRecommendation === null ? null : (
        <Callout
          title={`הפעולה המומלצת כעת היא ${actionLabel(plan.unbuiltRecommendation)}`}
          tone="neutral"
        >
          {plan.unbuiltRecommendation === "create_draft" && plan.draftWouldReplace
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
      {plan.analyze?.reanalysis === true && plan.draftWouldReplace ? (
        <p className="text-support leading-6 text-cv-text-muted">
          ניתוח מחדש יוצר ניתוח חדש ונפרד לאותו תצלום משרה. הטיוטה הפעילה נשמרת כפי שהיא, אך תסומן
          כלא מעודכנת מולו.
        </p>
      ) : null}

      {/* The sources are named, not resolved: the draft is built from the analysis and
          the plan the screen is showing, and neither is changed by building from it.

          The clause reassuring the reader that no active draft is being overwritten went
          with the stage that already says so - an offered `create_draft` requires
          `working_draft_state` to be `none`, which is the same fact. It returns above,
          where it stops being true. */}
      {plan.createDraft === null ? null : (
        <p className="text-support leading-6 text-cv-text-muted">
          הטיוטה נוצרת מהניתוח ומתוכנית הבחירה הפעילים של המועמדות. שניהם רשומות שאינן משתנות.
        </p>
      )}

      {inWorkflowOrder.length === 0 ? null : (
        <ActionBar
          /* The offered actions continue the next-step sentence above them rather than
             closing the page, so they start where that sentence starts. Whether there is
             one of them or several, they are the reader's way on from that line and belong
             beside it, not at the far edge of the card. */
          align="start"
          primary={emphasizedEntry.node}
          secondary={restButtons.length === 0 ? undefined : restButtons}
        />
      )}
    </div>
  );
};
