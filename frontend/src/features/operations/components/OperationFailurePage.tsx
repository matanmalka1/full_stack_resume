import { ShieldCheck } from "lucide-react";
import { type ReactNode, useEffect } from "react";
import { Link } from "react-router-dom";

import type { Operation } from "@/api/contracts";
import { routePaths } from "@/navigation/routePaths";
import { Button, buttonClasses } from "@/ui/Button";
import { reportError } from "@/ui/reportError";
import type { FailureSummary } from "../model/failureSummary";
import { OperationActions } from "./OperationActions";
import { OperationExecutionDetails } from "./OperationExecutionDetails";
import { OperationPhaseSteps } from "./OperationPhaseSteps";

/* A run that ended without a result, as a page of its own - a phone's sheet, a wide
   screen's centred card: what happened, that
   nothing the reader had was lost, where the run stopped, and the two ways on - back to
   the application, or the run again.

   The wide report says the same in a callout over a row of actions; on a phone the
   failure is the whole of what the reader came to see, so it gets the page the design
   draws. The words are the catalogue's, as in the report: the server's own sentence is
   never shown. The sheet's title carries the headline and its icon the warning mark; this
   is the body under them. */
export const OperationFailurePage = ({
  failureAction,
  onClose,
  onQueued,
  operation,
  summary,
}: {
  /* The host's recovery for the record the run failed to produce, as the report offers
     it - beside the way back, in the one action row. */
  failureAction?: ReactNode;
  onClose: () => void;
  onQueued: (operationId: string) => void;
  operation: Operation;
  summary: FailureSummary;
}) => {
  /* The run stopped in the queue if it never started, otherwise while executing. */
  const failedStep = operation.started_at == null ? 0 : 1;
  /* A failure this client has no wording for: the server's detail is English and meant
     for diagnosis, so it goes to the console, as the report sends it, while the reader
     gets the safe general line. */
  const unreportedDetail = operation.failure_code == null ? (operation.safe_failure_detail ?? null) : null;
  useEffect(() => {
    if (unreportedDetail !== null) {
      reportError("operation_failure", { failure_code: operation.failure_code, detail: unreportedDetail });
    }
  }, [operation.failure_code, unreportedDetail]);

  return (
    <div className="flex flex-col gap-5">
      {/* Announced as it appears, the way the report's failure callout was: the page
          opens by itself on an outcome, and this is the outcome. */}
      <section
        aria-labelledby="operation-failure-what"
        role="alert"
        className="rounded-surface border border-cv-border bg-cv-surface p-4"
      >
        <h3 className="mb-2 text-support font-bold text-cv-text" id="operation-failure-what">
          מה קרה
        </h3>
        {summary.sentences.map((sentence) => (
          <p className="text-body leading-7 text-cv-text" dir="auto" key={sentence}>
            {sentence}
          </p>
        ))}
        <p className="mt-3 flex items-center gap-2 border-t border-cv-border pt-3 text-support text-cv-text-muted">
          <ShieldCheck aria-hidden="true" className="size-icon-md shrink-0" />
          המצב שהיה פעיל לפני הפעולה נשמר.
        </p>
      </section>

      <div className="flex flex-col gap-2">
        <p aria-hidden="true" className="text-support font-bold text-cv-text">
          שלבי ההרצה
        </p>
        <div className="rounded-surface border border-cv-border bg-cv-surface px-4 py-3 text-support">
          <OperationPhaseSteps failedStep={failedStep} phase={operation.phase} />
        </div>
      </div>

      <OperationExecutionDetails operation={operation} />

      {/* The way back and the run again, in the report's one action row: back to the
          application first, then the retry - or Settings, when a retry would fail the
          same way for want of a provider. */}
      <OperationActions
        onQueued={onQueued}
        operation={operation}
        recovery={
          <>
            <Button onClick={onClose} variant="secondary">
              חזרה למועמדות
            </Button>
            {summary.missingProvider ? (
              <Link className={buttonClasses("primary")} to={routePaths.settings}>
                פתיחת ההגדרות
              </Link>
            ) : (
              failureAction
            )}
          </>
        }
        retryOffered={!summary.missingProvider}
        showCancel={false}
      />
    </div>
  );
};
