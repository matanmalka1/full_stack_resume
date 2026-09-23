import { Clock3 } from "lucide-react";
import { useEffect, useState } from "react";

import type { Operation } from "@/api/contracts";
import { isTerminalOperation } from "@/api/operations";
import { Callout } from "@/ui/Callout";
import { StatusBadge } from "@/ui/StatusBadge";
import { OperationActions } from "./OperationActions";
import { OperationExecutionDetails } from "./OperationExecutionDetails";
import {
  actionableFailureDetail,
  activeOutputLabels,
  failurePresentations,
  failureTones,
  joinHebrewList,
  statusLabels,
  statusTones,
} from "../model/operationLabels";
import { operationProgressLabel } from "../model/operationProgress";

const CANCEL_REVEAL_DELAY_MS = 4_000;

/* Keyed by the Operation, and owned by a component the overlay keeps mounted while it is
   hidden: hiding the report and bringing it back does not restart the delay, so a run
   that has been going for a minute offers cancel the moment it is reopened. */
const useCancelVisibility = (operation: Operation): boolean => {
  const [revealedOperationId, setRevealedOperationId] = useState<string | null>(null);

  useEffect(() => {
    if (operation.is_terminal) return;

    const timeout = window.setTimeout(() => setRevealedOperationId(operation.id), CANCEL_REVEAL_DELAY_MS);
    return () => window.clearTimeout(timeout);
  }, [operation.id, operation.is_terminal]);

  return operation.is_terminal || revealedOperationId === operation.id;
};

/* Everything this client knows about one run: its status, its safe progress line, its
   execution metadata, its failure and the guidance for it, and the run's own actions.

   There is no Operation screen behind this. It used to link to one for "the full record",
   but that record was the type, the status, the phase, the message, the failure and its
   guidance - every one of which is here - plus timestamps and a column of identifiers. A
   link promising more detail that leads to less is worse than no link.

   The report has one shape for every status. A succeeded run used to collapse into a row
   in the page flow; it now lives behind the overlay's chip, reopened on request, so it is
   read in full or not at all - and its re-run is offered as the secondary action it
   already was, never louder than the result the page is showing. */
export const OperationReport = ({
  continuation,
  onQueued,
  operation,
}: {
  /* What happens next by itself, when this run succeeding is not the end of the work.
     Supplied by the screen, because the screen is what knows a continuation is coming -
     the Operation record cannot say that its success will be followed. */
  continuation?: string | undefined;
  /* Handed down to the retry inside: a re-queued Operation belongs to the same watch the
     host screen is already keeping, so it is reported here rather than followed. */
  onQueued: (operationId: string) => void;
  operation: Operation;
}) => {
  const showCancel = useCancelVisibility(operation);
  const terminal = isTerminalOperation(operation);
  const progressLabel = operationProgressLabel(operation);
  const failure = operation.failure_code == null ? null : failurePresentations[operation.failure_code];
  const actionableDetail = actionableFailureDetail(operation.failure_code, operation.safe_failure_detail);
  const produced = activeOutputLabels(operation);
  const summary =
    continuation ??
    (terminal
      ? produced.length === 0
        ? "הפעולה הסתיימה."
        : `הפעולה הושלמה ויצרה ${joinHebrewList(produced)}.`
      : "העמוד מתעדכן מעצמו עד לסיום הפעולה. אפשר לסגור את החלון - ההרצה תימשך.");

  return (
    <div className="flex flex-col gap-4">
      <div>
        <StatusBadge tone={continuation === undefined ? statusTones[operation.status] : "progress"}>
          {progressLabel}
        </StatusBadge>
      </div>

      <div className="rounded-control border border-cv-border bg-cv-surface-muted p-3.5 sm:p-4">
        <div className="flex items-start gap-3">
          <Clock3 aria-hidden="true" className="mt-0.5 size-icon-md shrink-0 text-cv-accent" />
          <div className="min-w-0 flex-1">
            <p className="text-support font-medium leading-6 text-cv-text" dir="auto">
              {summary}
            </p>

            {/* A.3: the backend's safe progress line is English today, so it picks its
                own direction rather than inheriting the RTL shell. The line's place is
                held by the stable status surface while live work has not reported one. */}
            <p className="mt-1 min-h-6 text-support leading-6 text-cv-text-muted" dir="auto">
              {operation.message === "" ? (terminal ? null : "ממתינים לעדכון מהפעולה…") : operation.message}
            </p>
          </div>
        </div>

        {terminal && continuation === undefined ? null : (
          <>
            <progress aria-label={`התקדמות: ${progressLabel}`} aria-valuetext={progressLabel} className="sr-only" />
            <div aria-hidden="true" className="mt-3 h-1.5 overflow-hidden rounded-pill bg-cv-border">
              <div className="cv-operation-progress h-full w-2/5 rounded-pill bg-cv-accent" />
            </div>
          </>
        )}
      </div>

      <OperationExecutionDetails operation={operation} />

      {failure === null && operation.safe_failure_detail == null ? null : (
        <Callout
          role="alert"
          title={failure?.title ?? statusLabels[operation.status]}
          tone={failureTones[operation.status] ?? "warning"}
        >
          {failure === null && operation.safe_failure_detail != null ? (
            <p dir="auto">{operation.safe_failure_detail}</p>
          ) : null}
          {actionableDetail === null ? null : (
            <p className="font-medium" dir="auto">
              {actionableDetail}
            </p>
          )}
          {failure === null ? null : (
            <p className={actionableDetail === null ? "mt-2" : "mt-1"} dir="auto">
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
          is shown. A continuation withdraws them: there is nothing to cancel on a run
          that succeeded, and re-running it would supersede the result that the work now
          starting is built on. */}
      {continuation === undefined ? (
        <OperationActions
          onQueued={onQueued}
          operation={operation}
          reserve={!terminal && operation.available_actions.includes("cancel")}
          showCancel={showCancel}
        />
      ) : null}
    </div>
  );
};
