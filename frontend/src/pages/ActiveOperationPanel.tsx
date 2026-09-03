import { Check } from "lucide-react";

import type { Operation } from "../api/contracts";
import { isTerminalOperation } from "../api/operations";
import { Callout } from "../ui/Callout";
import { Card } from "../ui/Card";
import { LiveRegion } from "../ui/LiveRegion";
import { LtrText } from "../ui/LtrText";
import { StatusBadge } from "../ui/StatusBadge";
import { OperationActions } from "./OperationActions";
import {
  activeOutputLabels,
  failurePresentations,
  failureTones,
  joinHebrewList,
  operationTypeLabels,
  phaseLabels,
  statusLabels,
  statusTones,
} from "./operationLabels";

const reasoningEffortLabels: Record<NonNullable<Operation["reasoning_effort"]>, string> = {
  low: "נמוך",
  medium: "בינוני",
  high: "גבוה",
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
  onQueued,
  operation,
}: {
  /* Handed down to the retry inside: a re-queued Operation belongs to the same watch the
     host screen is already keeping, so it is reported here rather than followed. Required,
     because every screen that shows an Operation holds such a watch - a panel with
     nowhere to report a retry would queue work that nothing then follows. */
  onQueued: (operationId: string) => void;
  operation: Operation;
}) => {
  const terminal = isTerminalOperation(operation);
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
     on are the screen's most important content. */
  const settled = terminal && operation.status === "succeeded" && failure === null;

  if (settled) {
    return (
      /* One settled fact, so it is set as one line rather than as five. The full panel
         earns a heading, a badge, a sentence and two controls because each is doing
         separate work while the run is live; collapsed, the same five treatments in a
         single 40px row read as five competing things to look at. Everything here is
         muted body text on one baseline, and the only marks that survive are the
         status word, which carries the outcome, and the two controls. */
      <Card
        aria-labelledby="active-operation-heading"
        className="flex flex-wrap items-center gap-x-3 gap-y-2 bg-cv-surface-muted px-4 py-2.5 text-support text-cv-text-muted"
      >
        <Check aria-hidden="true" className="size-4 shrink-0 text-cv-success" />
        <h2 className="font-medium text-cv-text" id="active-operation-heading">
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
    <Card aria-labelledby="active-operation-heading" className="p-5">
      <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-3">
        {/* The run, not its subject. `operationTypeLabels` names the work ("ניתוח
            המשרה"), which is also what the panel reporting the resulting analysis calls
            itself - two adjacent regions carrying one accessible name, which reads as a
            duplicated section rather than as a run and its conclusion. Naming the event
            here keeps the noun for the panel that owns the result. */}
        <h2 className="text-body font-semibold text-cv-text" id="active-operation-heading">
          הרצת {operationTypeLabels[operation.operation_type]}
        </h2>
        <div className="flex flex-wrap items-center gap-3">
          <StatusBadge tone={statusTones[operation.status]}>{statusLabels[operation.status]}</StatusBadge>
          {/* The phase is the progress axis and earns its place only when it says
              something the status has not. The two share vocabulary at both ends -
              `queued`/`queued` are both "ממתינה בתור", `succeeded`/`completed` both
              "הושלמה" - so the test is whether the words differ, not whether the run has
              finished. Keyed on `terminal` alone, a queued run printed one word twice. */}
          {phaseLabels[operation.phase] === statusLabels[operation.status] ? null : (
            <span className="text-support text-cv-text-muted">{phaseLabels[operation.phase]}</span>
          )}
        </div>
      </div>

      {/* A.5: the announcement is the status and phase themselves, so an identical poll
          tick re-renders without speaking. */}
      <LiveRegion>
        {phaseLabels[operation.phase] === statusLabels[operation.status]
          ? statusLabels[operation.status]
          : `${statusLabels[operation.status]}. ${phaseLabels[operation.phase]}.`}
      </LiveRegion>

      <div className="mt-4 flex flex-col gap-4">
        {executionDetail}
        <p className="text-support leading-6 text-cv-text-muted" dir="auto">
          {terminal
            ? produced.length === 0
              ? "הפעולה הסתיימה."
              : `הפעולה הושלמה ויצרה ${joinHebrewList(produced)}.`
            : "העמוד מתעדכן מעצמו עד לסיום הפעולה."}
        </p>

        {/* A.3: the backend's safe progress line is English today, so it picks its own
            direction rather than inheriting the RTL shell. */}
        {operation.message === "" ? null : (
          <p className="text-body leading-7" dir="auto">
            {operation.message}
          </p>
        )}

        {failure === null && operation.safe_failure_detail == null ? null : (
          <Callout
            role="alert"
            title={failure?.title ?? statusLabels[operation.status]}
            tone={failureTones[operation.status] ?? "warning"}
          >
            {operation.safe_failure_detail == null ? null : <p dir="auto">{operation.safe_failure_detail}</p>}
            {failure === null ? null : (
              <p className="mt-2" dir="auto">
                {failure.guidance}
              </p>
            )}
          </Callout>
        )}

        {operation.cancellation_requested_at != null && !operation.is_terminal ? (
          <Callout title="בקשת הביטול התקבלה" tone="neutral">
            הביטול של פעולה שכבר התחילה הוא מיטבי. גם אם העבודה החיצונית תסתיים, התוצאה שלה לא תופעל; המצב כאן ימשיך
            להתעדכן עד שיירשם המצב הסופי.
          </Callout>
        ) : null}

        {/* Cancel and retry, which are the Operation's own actions and belong wherever it
            is shown. The panel passes no return link: this is the screen the user is
            already on. */}
        <OperationActions onQueued={onQueued} operation={operation} />
      </div>
    </Card>
  );
};
