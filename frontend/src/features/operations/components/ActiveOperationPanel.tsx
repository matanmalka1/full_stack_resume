import { Check } from "lucide-react";
import { useEffect, useId, useState } from "react";

import type { Operation } from "@/api/contracts";
import { isTerminalOperation } from "@/api/operations";
import { Callout } from "@/ui/Callout";
import { Card } from "@/ui/Card";
import { LiveRegion } from "@/ui/LiveRegion";
import { LtrText } from "@/ui/LtrText";
import { StatusBadge } from "@/ui/StatusBadge";
import { OperationActions } from "./OperationActions";
import {
  activeOutputLabels,
  failurePresentations,
  failureTones,
  joinHebrewList,
  operationTypeLabels,
  statusLabels,
  statusTones,
} from "../model/operationLabels";
import { operationProgressLabel } from "../model/operationProgress";
import { WorkCardFrame } from "./WorkCard";

const reasoningEffortLabels: Record<NonNullable<Operation["reasoning_effort"]>, string> = {
  low: "נמוך",
  medium: "בינוני",
  high: "גבוה",
};

const CANCEL_REVEAL_DELAY_MS = 4_000;

const useCancelVisibility = (operation: Operation): boolean => {
  const [revealedOperationId, setRevealedOperationId] = useState<string | null>(null);

  useEffect(() => {
    if (operation.is_terminal) return;

    const timeout = window.setTimeout(() => setRevealedOperationId(operation.id), CANCEL_REVEAL_DELAY_MS);
    return () => window.clearTimeout(timeout);
  }, [operation.id, operation.is_terminal]);

  return operation.is_terminal || revealedOperationId === operation.id;
};

/* Work in progress, on the screen that queued it.

   Queueing an Operation used to navigate to a screen of its own, which made every action
   a round trip: the user left the Application, watched a progress line, and was handed a
   "חזרה למועמדות" link back to where they had started. Two of the workflow's steps were
   spent going somewhere and coming back, and the context they were deciding in - the
   analysis, the reasons, the stage - was not on the screen while they waited.

   The projection already carries `active_operation` in full and already polls while it is
   live, so nothing new is fetched to show this: the Application screen was holding the
   Operation all along and only linking to it.

   There is no Operation screen behind this panel any more. It used to link to one for
   "the full record", but that record was the type, the status, the phase, the message,
   the failure and its guidance - every one of which is here - plus timestamps and a
   column of identifiers, and the identifiers are no longer shown anywhere. A link
   promising more detail that leads to less is worse than no link. */
export const ActiveOperationPanel = ({
  continuation,
  onQueued,
  operation,
}: {
  /* What happens next by itself, when this run succeeding is not the end of the work.

     A run that finished collapses to a single line, which is right when the workflow is
     then waiting on the reader. It is wrong when the screen is already starting the next
     run or leaving for the next step: the panel shrank to announce "done" and grew back a
     tick later for the continuation, so the one moment the reader was told to look at was
     a state the flow had passed through rather than one it stopped in.

     Supplied by the screen, because the screen is what knows a continuation is coming -
     the Operation record cannot say that its success will be followed. Its presence keeps
     the full frame and its words say what is starting; absent, a finished run settles. */
  continuation?: string;
  /* Handed down to the retry inside: a re-queued Operation belongs to the same watch the
     host screen is already keeping, so it is reported here rather than followed. Required,
     because every screen that shows an Operation holds such a watch - a panel with
     nowhere to report a retry would queue work that nothing then follows. */
  onQueued: (operationId: string) => void;
  operation: Operation;
}) => {
  /* The collapsed row's own, for the same reason `WorkCardFrame` mints one: a settled run
     can share a screen with the next step's card. */
  const settledHeadingId = useId();
  const showCancel = useCancelVisibility(operation);
  const terminal = isTerminalOperation(operation);
  const progressLabel = operationProgressLabel(operation);
  const failure = operation.failure_code == null ? null : failurePresentations[operation.failure_code];
  const produced = activeOutputLabels(operation);
  const aiExecution = operation.provider === "openai" && operation.model != null;
  const executionDetail = aiExecution ? (
    <span className="text-support text-cv-text-muted">
      <LtrText>{operation.model}</LtrText>
      {operation.reasoning_effort == null ? null : <> · מאמץ {reasoningEffortLabels[operation.reasoning_effort]}</>}
      {operation.cost_usd == null ? null : (
        <>
          {" "}
          · עלות <LtrText>${operation.cost_usd}</LtrText>
        </>
      )}
    </span>
  ) : null;

  /* A run that succeeded has nothing left to watch. Reported at full panel weight it
     took the top of the screen - heading, badge, progress sentence, actions, link - to
     say that finished work had finished, and pushed the thing it produced below the
     fold. Failure keeps the full panel: there the status, the safe detail, and the way
     on are the screen's most important content.

     Nothing left to watch is exactly what a continuation contradicts, so a screen that
     names one holds the frame open until the run it is starting arrives to fill it. */
  const settled = terminal && operation.status === "succeeded" && failure === null && continuation === undefined;

  if (settled) {
    return (
      /* One settled fact, so it is set as one line rather than as five. The full panel
         earns a heading, a badge, a sentence and two controls because each is doing
         separate work while the run is live; collapsed, the same five treatments in a
         single 40px row read as five competing things to look at. Everything here is
         muted body text on one baseline, and the only marks that survive are the
         status word, which carries the outcome, and the two controls. */
      <Card
        aria-labelledby={settledHeadingId}
        className="cv-settle-in flex flex-wrap items-center gap-x-3 gap-y-2 bg-cv-surface-muted px-4 py-2.5 text-support text-cv-text-muted"
      >
        <Check aria-hidden="true" className="size-icon-md shrink-0 text-cv-success" />
        <h2 className="font-medium text-cv-text" id={settledHeadingId}>
          הרצת {operationTypeLabels[operation.operation_type]}
        </h2>
        <p dir="auto">
          {produced.length === 0
            ? statusLabels[operation.status]
            : `${statusLabels[operation.status]} · יצרה ${joinHebrewList(produced)}`}
        </p>
        {executionDetail}

        {/* A.5: the row a watched run collapses into is the moment worth announcing, so
            the live region survives the change of shape. Without it the panel went quiet
            exactly as it reached the status the reader was waiting for. */}
        <LiveRegion>{statusLabels[operation.status]}</LiveRegion>
        <div className="ms-auto flex flex-wrap items-center gap-x-3 gap-y-2">
          {/* Retry stays reachable - it is the Operation's own action - but at the weight
              of a link rather than a button, because re-running work that succeeded
              supersedes the result the screen is showing. */}
          <OperationActions collapsed onQueued={onQueued} operation={operation} />
        </div>
      </Card>
    );
  }

  return (
    <WorkCardFrame
      badge={<StatusBadge tone={statusTones[operation.status]}>{progressLabel}</StatusBadge>}
      /* The run, not its subject. `operationTypeLabels` names the work ("ניתוח המשרה"),
         which is also what the panel reporting the resulting analysis calls itself - two
         adjacent regions carrying one accessible name, which reads as a duplicated section
         rather than as a run and its conclusion. Naming the event here keeps the noun for
         the panel that owns the result. */
      heading={<>הרצת {operationTypeLabels[operation.operation_type]}</>}
    >
      {/* A.5: announce the same single progress sentence shown in the badge, so an
          identical poll tick re-renders without speaking. */}
      <LiveRegion>{continuation ?? progressLabel}</LiveRegion>

      {executionDetail}
      <p className="text-support leading-6 text-cv-text-muted" dir="auto">
        {continuation ??
          (terminal
            ? produced.length === 0
              ? "הפעולה הסתיימה."
              : `הפעולה הושלמה ויצרה ${joinHebrewList(produced)}.`
            : "העמוד מתעדכן מעצמו עד לסיום הפעולה.")}
      </p>

      {/* A.3: the backend's safe progress line is English today, so it picks its own
          direction rather than inheriting the RTL shell.

          Its place is held open while the run is live rather than mounted when the first
          message arrives: the line appears partway through a run, and a paragraph
          appearing between two poll ticks pushed everything below it down mid-read. */}
      {operation.message !== "" ? (
        <p className="text-body leading-7" dir="auto">
          {operation.message}
        </p>
      ) : terminal ? null : (
        <div aria-hidden="true" className="h-7" />
      )}

      {failure === null && operation.safe_failure_detail == null ? null : (
        <Callout
          role="alert"
          title={failure?.title ?? statusLabels[operation.status]}
          tone={failureTones[operation.status] ?? "warning"}
        >
          {failure === null && operation.safe_failure_detail != null ? (
            <p dir="auto">{operation.safe_failure_detail}</p>
          ) : null}
          {failure === null ? null : (
            <p className="mt-2" dir="auto">
              {failure.guidance}
            </p>
          )}
        </Callout>
      )}

      {operation.cancellation_requested_at != null && !operation.is_terminal ? (
        <Callout title="בקשת הביטול התקבלה" tone="info">
          הביטול של פעולה שכבר התחילה הוא מיטבי. גם אם העבודה החיצונית תסתיים, התוצאה שלה לא תופעל; המצב כאן ימשיך
          להתעדכן עד שיירשם המצב הסופי.
        </Callout>
      ) : null}

      {/* Cancel and retry, which are the Operation's own actions and belong wherever it
          is shown. The panel passes no return link: this is the screen the user is
          already on.

          A continuation withdraws them: there is nothing to cancel on a run that
          succeeded, and re-running it would supersede the result that the work now
          starting is built on. */}
      {continuation === undefined ? (
        <OperationActions
          onQueued={onQueued}
          operation={operation}
          reserve={!terminal && operation.available_actions.includes("cancel")}
          showCancel={showCancel}
        />
      ) : null}
    </WorkCardFrame>
  );
};
