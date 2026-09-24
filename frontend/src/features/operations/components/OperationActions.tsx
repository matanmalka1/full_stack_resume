import { useMutation, useQueryClient } from "@tanstack/react-query";

import type { Operation } from "@/api/contracts";
import { cancelOperation, operationQueryKey, retryOperation } from "@/api/operations";
import { ErrorCallout } from "@/ui/ErrorCallout";
import { Button } from "@/ui/Button";

interface OperationActionsProps {
  operation: Operation;
  /* Where a retry's new Operation goes. The host screen watches one Application's work,
     so it takes the id and keeps reporting in place.

     There is no second mode any more. These controls used to render on the Operation's
     own route as well, which needed a return link (a finished Operation was a dead end
     there) and a retry that navigated (nothing on that route was watching). Both existed
     because the screen holding the Operation did not hold the Application; every screen
     that shows an Operation now does. */
  onQueued: (operationId: string) => void;
  /* Hold this row's height while `showCancel` is still withholding a control that is
     coming. The delayed reveal keeps a destructive button off short runs, but a button
     arriving into a row that was not there displaced the card mid-run - which is the same
     jump the reveal was added to avoid, four seconds later. The space is kept from the
     start and only the control fades in. */
  reserve?: boolean;
  /* False when the host knows a retry cannot succeed - no AI provider for a refused AI
     run - and offers the fix in its place rather than a button that fails the same way. */
  retryOffered?: boolean;
  /* Short Operations should not flash a destructive control that cannot realistically be
     used. The host reveals it after its own "taking longer" threshold; a terminal action
     surface can leave this at the default. */
  showCancel?: boolean;
}

export const OperationActions = ({
  onQueued,
  operation,
  reserve = false,
  retryOffered = true,
  showCancel = true,
}: OperationActionsProps) => {
  const queryClient = useQueryClient();
  /* One key per original Operation: an uncertain response can be retried safely, while
     navigating to the newly queued Operation rotates the key for its own future retry.
     Derived rather than cached, since a discarded useMemo would mint a new key on the
     same Operation and send a second one to the server. */
  const retryKey = `retry:${operation.id}`;

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
      /* The host screen's watch takes the new run and the overlay keeps reporting without
         the reader going anywhere. */
      onQueued(queued.id);
    },
  });

  const error = cancel.error ?? retry.error;
  const canCancel = showCancel && operation.available_actions.includes("cancel");
  const canRetry = retryOffered && operation.available_actions.includes("retry");
  /* Retry on a run that succeeded re-runs work that has a result on record and
     supersedes it, so it is offered without being recommended: the loud control on the
     screen must never be the one that discards what the reader is looking at. The way on
     from a finished run is the host screen's own next action, which is on the page around
     this overlay. */
  if (!canCancel && !canRetry && error === null) {
    /* The row's own chrome around a slot the height of the button that is coming, so the
       reveal fills a space that was already there rather than making one. */
    return reserve ? (
      <div aria-hidden="true" className="mt-2 flex flex-col gap-4 border-t border-cv-border pt-5">
        <div className="h-11" />
      </div>
    ) : null;
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
            className="cv-settle-in"
            disabled={retry.isPending}
            onClick={() => cancel.mutate()}
            pending={cancel.isPending}
            pendingLabel="מבטל…"
            variant="destructive"
          >
            ביטול הפעולה
          </Button>
        ) : null}
        {canRetry ? (
          <Button
            disabled={cancel.isPending}
            onClick={() => retry.mutate()}
            pending={retry.isPending}
            pendingLabel="יוצר ניסיון חדש…"
            variant={operation.status === "succeeded" ? "secondary" : "primary"}
          >
            {/* On a run that failed, a retry is plainly another attempt at work that
                produced nothing. On one that succeeded it re-runs work that has a
                result on record and supersedes it, so the button says so rather than
                leaving "ניסיון חוזר" to imply a repeat of nothing. */}
            {operation.status === "succeeded" ? "הרצה מחדש" : "ניסיון חוזר"}
          </Button>
        ) : null}
      </div>
    </div>
  );
};
