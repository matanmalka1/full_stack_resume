import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useMemo } from "react";
import { Link, useNavigate } from "react-router-dom";

import type { Operation } from "../api/contracts";
import {
  cancelOperation,
  operationQueryKey,
  retryOperation,
} from "../api/operations";
import { ErrorCallout } from "../app/ErrorCallout";
import { Button, buttonClasses } from "../ui/Button";
import { cx } from "../ui/cx";

interface OperationActionsProps {
  /* Rendered inside a screen that already holds this Application rather than on the
     Operation's own route. Two things differ.

     The return link: on the Operation screen a finished Operation is a dead end without
     it, since the way on depends on the application projection that screen does not hold.
     Inline, that projection is the page around the panel - a link back to the screen the
     reader is already looking at is not an exit.

     And retry: inline it re-queues into the watch the host screen is already keeping, so
     the panel simply starts reporting the new run. On the Operation route there is no
     such watch, so retry navigates to the Operation it queued. */
  inline?: boolean;
  /* Rendered beside a one-line summary of a run that already succeeded, where the row
     is the report and not the screen's main content. The controls drop the separator and
     the button chrome and read as links, so a settled run does not carry a call to action
     louder than the result it produced. */
  collapsed?: boolean;
  operation: Operation;
  /* Where a retry's new Operation goes when the panel is inline. The host screen watches
     one Application's work, so it takes the id and keeps reporting in place. */
  onQueued?: (operationId: string) => void;
  /* Where the return link leads, when the caller knows somewhere better than the
     Application screen.

     The Application screen is the safe answer and stays the default: it owns the
     projection, so it can always say what comes next. But a caller that already holds
     that projection can name the screen the projection's own recommended action lives on,
     which saves the reader a hop through a screen whose only job was to point at it.

     It is not a rule invented here about which Operation leads where - that would be the
     second workflow state machine A.1 forbids. The caller derives it from
     `recommended_action` through `actionDestination`, the same table the Application
     screen and the board already link through. */
  returnPath?: string;
  /* What the return link is called. It defaults to the Application, and a caller that
     supplies a destination supplies its name too: a link that says "back to the
     application" and leads to the draft editor is a worse exit than no name at all. */
  returnLabel?: string;
}

export const OperationActions = ({
  collapsed = false,
  inline = false,
  onQueued,
  operation,
  returnLabel,
  returnPath,
}: OperationActionsProps) => {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  /* One key per original Operation: an uncertain response can be retried safely, while
     navigating to the newly queued Operation rotates the key for its own future retry. */
  const retryKey = useMemo(() => crypto.randomUUID(), [operation.id]);

  const cancel = useMutation({
    mutationFn: () => cancelOperation(operation.id),
    onSuccess: (cancelled) => {
      queryClient.setQueryData(operationQueryKey(cancelled.id), cancelled);
    },
  });
  const retry = useMutation({
    mutationFn: () => retryOperation(operation.id, retryKey),
    onSuccess: ({ operation: queued, operationPath }) => {
      queryClient.setQueryData(operationQueryKey(queued.id), queued);
      /* Inline, the host screen's watch takes the new run and the panel keeps reporting
         without the reader going anywhere. On the Operation route there is nothing
         watching, so the retry is followed to the Operation it queued. */
      if (onQueued === undefined) {
        void navigate(operationPath);
      } else {
        onQueued(queued.id);
      }
    },
  });

  const error = cancel.error ?? retry.error;
  const canCancel = operation.available_actions.includes("cancel");
  const canRetry = operation.available_actions.includes("retry");
  /* Which of the two ways out is the emphasized one.

     SOURCE_CHANGED says the frozen command no longer describes the active context. Retry
     remains visible because the backend permits it, but the application projection is the
     safe primary route to actions over the current source.

     Success is the other case, and it was the one this rule originally missed: the
     emphasis logic was written for a failed Operation, where retry is plainly the way on,
     and applied unchanged to a succeeded one. That put the loudest control on the screen
     on re-running work that had just worked - for `analyze_job`, a second analysis that
     supersedes the active one and marks any existing draft stale - while the actual next
     step sat beside it as the quiet button. Retry stays offered wherever the backend
     offers it; on success it is no longer the recommendation. */
  const returnRecommended =
    operation.failure_code === "SOURCE_CHANGED" || operation.status === "succeeded";
  /* A finished Operation used to be a dead end: it reported that the work was over and
     offered nowhere to go. The way on is not this screen's to invent - which action
     follows depends on the application projection (A.1) - so without a caller-supplied
     destination it hands the user back to the screen that owns that projection and lets
     it say what comes next. */
  const destination =
    returnPath ?? `/applications/${encodeURIComponent(operation.application_id)}`;

  const showReturn = operation.is_terminal && !inline;

  if (!canCancel && !canRetry && error === null && !showReturn) {
    return null;
  }

  if (collapsed) {
    if (!canRetry && error === null) {
      return null;
    }

    return (
      <>
        {error === null ? null : (
          <ErrorCallout
            error={error}
            fallbackDetail="לא ניתן להשלים את הפעולה. המצב הבטוח האחרון נשמר ואפשר לנסות שוב."
            fallbackTitle="הפעולה לא בוצעה"
          />
        )}
        {canRetry ? (
          <button
            className="rounded-control underline underline-offset-4 hover:text-cv-text disabled:no-underline disabled:opacity-60"
            disabled={retry.isPending}
            onClick={() => retry.mutate()}
            type="button"
          >
            {retry.isPending ? "יוצר ניסיון חדש…" : "הרצה מחדש"}
          </button>
        ) : null}
      </>
    );
  }

  return (
    <div className="mt-2 flex flex-col gap-4 border-t border-cv-border pt-5">
      {error === null ? null : (
        <ErrorCallout
          error={error}
          fallbackDetail="לא ניתן להשלים את הפעולה. המצב הבטוח האחרון נשמר ואפשר לנסות שוב."
          fallbackTitle="הפעולה לא בוצעה"
        />
      )}

      {/* Reading order follows emphasis: the recommended way out leads the row. With
          retry recommended that is retry, and where returning is recommended - a changed
          source, or a run that succeeded - the return link leads instead, so the loud
          button and the first button are never two different controls. */}
      <div className={cx("flex flex-wrap gap-3", returnRecommended && "flex-row-reverse justify-end")}>
        {canCancel ? (
          <Button
            disabled={cancel.isPending || retry.isPending}
            onClick={() => cancel.mutate()}
            variant="destructive"
          >
            {cancel.isPending ? "מבטל…" : "ביטול הפעולה"}
          </Button>
        ) : null}
        {canRetry ? (
          <Button
            disabled={cancel.isPending || retry.isPending}
            onClick={() => retry.mutate()}
            variant={returnRecommended ? "secondary" : "primary"}
          >
            {retry.isPending
              ? "יוצר ניסיון חדש…"
              : /* On a run that failed, a retry is plainly another attempt at work that
                   produced nothing. On one that succeeded it re-runs work that has a
                   result on record and supersedes it, so the button says so rather than
                   leaving "ניסיון חוזר" to imply a repeat of nothing. */
                operation.status === "succeeded"
                ? "הרצה מחדש"
                : "ניסיון חוזר"}
          </Button>
        ) : null}
        {showReturn ? (
          <Link
            className={buttonClasses(canRetry && !returnRecommended ? "secondary" : "primary")}
            to={destination}
          >
            {returnLabel ?? "חזרה למועמדות"}
          </Link>
        ) : null}
      </div>
    </div>
  );
};
