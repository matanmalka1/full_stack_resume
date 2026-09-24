import { type ReactNode, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import type { Operation } from "@/api/contracts";
import { isTerminalOperation } from "@/api/operations";
import { aiRegenerationAvailable } from "@/api/settings";
import { useSettings } from "@/api/useSettings";
import { routePaths } from "@/app/routePaths";
import { buttonClasses } from "@/ui/Button";
import { Callout } from "@/ui/Callout";
import { StatusBadge } from "@/ui/StatusBadge";
import { OperationActions } from "./OperationActions";
import { OperationExecutionDetails } from "./OperationExecutionDetails";
import { OperationPhaseSteps } from "./OperationPhaseSteps";
import {
  activeOutputLabels,
  failurePresentations,
  failureTones,
  joinHebrewList,
  failureReasonDetail,
  missingProviderPresentation,
  providerNowConfiguredPresentation,
  statusLabels,
  statusTones,
  terminalSummaries,
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

   One order for every status: what state the run is in, then - while it lives - which
   step it is on; when it has ended, what it came to or why it failed and what to do; then
   one row of actions; then the technical detail. A succeeded run's re-run is offered as
   the secondary action it always was, never louder than the result the page is showing. */
export const OperationReport = ({
  continuation,
  failureAction,
  onQueued,
  operation,
}: {
  /* What happens next by itself, when this run succeeding is not the end of the work.
     Supplied by the screen, because the screen is what knows a continuation is coming -
     the Operation record cannot say that its success will be followed. */
  continuation?: string | undefined;
  /* Recovery belongs to the workflow that owns the affected record, not to the generic
     Operation. The host supplies the exact safe action; the report places it in its one
     action row, beside the record's own retry. */
  failureAction?: ReactNode;
  /* Handed down to the retry inside: a re-queued Operation belongs to the same watch the
     host screen is already keeping, so it is reported here rather than followed. */
  onQueued: (operationId: string) => void;
  operation: Operation;
}) => {
  const showCancel = useCancelVisibility(operation);
  const terminal = isTerminalOperation(operation);
  const live = !terminal || continuation !== undefined;
  const progressLabel = operationProgressLabel(operation);
  const { settings } = useSettings();
  const providerUsable = settings !== undefined && aiRegenerationAvailable(settings);
  /* A run that needed a provider and had none: the server's own code, or - for a run
     recorded before that code existed - a refusal while Settings still show no usable
     provider. Settings is the fix while it is still true, and a retry would fail the same
     way; once a provider is usable, the run can simply be tried again. */
  const notConfigured = operation.failure_code === "PROVIDER_NOT_CONFIGURED";
  const missingProvider =
    settings !== undefined && !providerUsable && (notConfigured || operation.failure_code === "PROVIDER_REFUSED");
  const failure = missingProvider
    ? missingProviderPresentation(settings.provider_configured)
    : notConfigured && providerUsable
      ? providerNowConfiguredPresentation
      : operation.failure_code == null
        ? null
        : failurePresentations[operation.failure_code];
  const actionableDetail = failureReasonDetail(operation.failure_reason);
  const hasFailure = failure !== null || operation.safe_failure_detail != null;
  const produced = activeOutputLabels(operation);
  /* A finished run says what it came to in one line - unless it failed, where the reason
     below is that line and a second, vaguer one above it only delayed it. */
  const outcome =
    live || hasFailure
      ? null
      : produced.length > 0
        ? `הפעולה הושלמה ויצרה ${joinHebrewList(produced)}.`
        : (terminalSummaries[operation.status] ?? "הפעולה הסתיימה.");
  /* Settings for a missing provider replaces the retry that would fail the same way;
     otherwise the host's own recovery, if it has one. */
  const recovery = missingProvider ? (
    <Link className={buttonClasses("primary")} to={routePaths.settings}>
      פתיחת ההגדרות
    </Link>
  ) : (
    failureAction
  );

  return (
    <div className="flex flex-col gap-4">
      <div>
        <StatusBadge tone={continuation === undefined ? statusTones[operation.status] : "progress"}>
          {progressLabel}
        </StatusBadge>
      </div>

      {live ? (
        <div className="flex flex-col gap-2">
          {continuation === undefined ? (
            <OperationPhaseSteps phase={operation.phase} />
          ) : (
            <p className="text-support font-medium leading-6 text-cv-text">{continuation}</p>
          )}
          {/* A.3: the backend's safe progress line is English today, so it picks its own
              direction rather than inheriting the RTL shell. */}
          {operation.message === "" || continuation !== undefined ? null : (
            <p className="text-support leading-6 text-cv-text-muted" dir="auto">
              {operation.message}
            </p>
          )}
          <progress aria-label={`התקדמות: ${progressLabel}`} aria-valuetext={progressLabel} className="sr-only" />
        </div>
      ) : null}

      {outcome === null ? null : <p className="text-support leading-6 text-cv-text">{outcome}</p>}

      {/* The reason and what to do about it, straight under the status: on a failure they
          are the report. */}
      {!hasFailure ? null : (
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
            <p className={actionableDetail === null ? undefined : "mt-1"} dir="auto">
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

      {/* Cancel, retry, and any recovery, in the report's one action row. A continuation
          withdraws them: there is nothing to cancel on a run that succeeded, and re-running
          it would supersede the result that the work now starting is built on. */}
      {continuation === undefined ? (
        <OperationActions
          onQueued={onQueued}
          operation={operation}
          recovery={recovery}
          retryOffered={!missingProvider}
          showCancel={showCancel}
        />
      ) : null}

      {/* Technical detail last, after the status, the reason, and the way on. */}
      <OperationExecutionDetails operation={operation} />
    </div>
  );
};
