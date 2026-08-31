import { Link } from "react-router-dom";

import type { Operation } from "../api/contracts";
import { isTerminalOperation } from "../api/operations";
import { Callout } from "../ui/Callout";
import { LiveRegion } from "../ui/LiveRegion";
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

/* Work in progress, on the screen that queued it.

   Queueing an Operation used to navigate to a screen of its own, which made every action
   a round trip: the user left the Application, watched a progress line, and was handed a
   "חזרה למועמדות" link back to where they had started. Two of the workflow's steps were
   spent going somewhere and coming back, and the context they were deciding in - the
   analysis, the reasons, the stage - was not on the screen while they waited.

   The projection already carries `active_operation` in full and already polls while it is
   live, so nothing new is fetched to show this: the Application screen was holding the
   Operation all along and only linking to it.

   `/operations/:id` stays a route. It is where a direct link, a bookmark, or a reload of
   a queued operation lands, and it lays out the whole record; this panel is the same
   Operation reported in place, which is why both read from one vocabulary module. */
export const ActiveOperationPanel = ({
  onQueued,
  operation,
}: {
  /* Handed down to the retry inside: a re-queued Operation belongs to the same watch the
     host screen is already keeping, so it is reported here rather than followed. */
  onQueued?: (operationId: string) => void;
  operation: Operation;
}) => {
  const terminal = isTerminalOperation(operation);
  const failure =
    operation.failure_code == null ? null : failurePresentations[operation.failure_code];
  const produced = activeOutputLabels(operation);

  return (
    <section
      aria-labelledby="active-operation-heading"
      className="rounded-surface border border-cv-border p-5"
    >
      <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-3">
        <h2 className="text-body font-semibold text-cv-text" id="active-operation-heading">
          {operationTypeLabels[operation.operation_type]}
        </h2>
        <div className="flex flex-wrap items-center gap-3">
          <StatusBadge tone={statusTones[operation.status]}>
            {statusLabels[operation.status]}
          </StatusBadge>
          {/* At a terminal status the phase collapses onto the status word - `succeeded`
              and `completed` are both "הושלמה" - so it is dropped rather than said twice. */}
          {terminal ? null : (
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
            {operation.safe_failure_detail == null ? null : (
              <p dir="auto">{operation.safe_failure_detail}</p>
            )}
            {failure === null ? null : (
              <p className="mt-2" dir="auto">
                {failure.guidance}
              </p>
            )}
          </Callout>
        )}

        {operation.cancellation_requested_at != null && !operation.is_terminal ? (
          <Callout title="בקשת הביטול התקבלה" tone="neutral">
            הביטול של פעולה שכבר התחילה הוא מיטבי. גם אם העבודה החיצונית תסתיים, התוצאה שלה
            לא תופעל; המצב כאן ימשיך להתעדכן עד שיירשם המצב הסופי.
          </Callout>
        ) : null}

        {/* Cancel and retry, which are the Operation's own actions and belong wherever it
            is shown. The panel passes no return link: this is the screen the user is
            already on. */}
        <OperationActions inline onQueued={onQueued} operation={operation} />

        <p className="text-support text-cv-text-muted">
          <Link
            className="underline underline-offset-4 hover:text-cv-text"
            to={`/operations/${encodeURIComponent(operation.id)}`}
          >
            פרטי הפעולה המלאים
          </Link>
        </p>
      </div>
    </section>
  );
};
