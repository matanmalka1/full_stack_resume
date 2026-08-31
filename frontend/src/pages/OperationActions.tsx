import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useMemo } from "react";

import type { Operation } from "../api/contracts";
import {
  cancelOperation,
  operationQueryKey,
  retryOperation,
} from "../api/operations";
import { ErrorCallout } from "../app/ErrorCallout";
import { Button } from "../ui/Button";

interface OperationActionsProps {
  /* Rendered beside a one-line summary of a run that already succeeded, where the row
     is the report and not the screen's main content. The controls drop the separator and
     the button chrome and read as links, so a settled run does not carry a call to action
     louder than the result it produced. */
  collapsed?: boolean;
  operation: Operation;
  /* Where a retry's new Operation goes. The host screen watches one Application's work,
     so it takes the id and keeps reporting in place.

     There is no second mode any more. These controls used to render on the Operation's
     own route as well, which needed a return link (a finished Operation was a dead end
     there) and a retry that navigated (nothing on that route was watching). Both existed
     because the screen holding the Operation did not hold the Application; every screen
     that shows an Operation now does. */
  onQueued: (operationId: string) => void;
}

export const OperationActions = ({
  collapsed = false,
  onQueued,
  operation,
}: OperationActionsProps) => {
  const queryClient = useQueryClient();
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
    onSuccess: ({ operation: queued }) => {
      queryClient.setQueryData(operationQueryKey(queued.id), queued);
      /* The host screen's watch takes the new run and the panel keeps reporting without
         the reader going anywhere. */
      onQueued(queued.id);
    },
  });

  const error = cancel.error ?? retry.error;
  const canCancel = operation.available_actions.includes("cancel");
  const canRetry = operation.available_actions.includes("retry");
  /* Retry on a run that succeeded re-runs work that has a result on record and
     supersedes it, so it is offered without being recommended: the loud control on the
     screen must never be the one that discards what the reader is looking at. The way on
     from a finished run is the host screen's own next action, which is on the page around
     this panel. */
  if (!canCancel && !canRetry && error === null) {
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

      <div className="flex flex-wrap gap-3">
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
            variant={operation.status === "succeeded" ? "secondary" : "primary"}
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
      </div>
    </div>
  );
};
