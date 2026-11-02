import type { ReactNode } from "react";

import type { Operation } from "@/api/contracts";
import { ErrorCallout } from "@/ui/ErrorCallout";
import { Button } from "@/ui/Button";
import { useOperationCommands } from "../hooks/useOperationCommands";

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
  /* The recovery that is not the record's own - Settings for a missing provider, or the
     host's way back for the record the run failed to produce. It shares this row with
     retry, so every report ends in the same one place, whatever offered the way on. There
     is no reserved empty row any more: an empty footer under a divider read as a control
     that failed to load. */
  recovery?: ReactNode;
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
  recovery,
  retryOffered = true,
  showCancel = true,
}: OperationActionsProps) => {
  const { cancel, error, retry } = useOperationCommands(operation, onQueued);
  const canCancel = showCancel && operation.available_actions.includes("cancel");
  const canRetry = retryOffered && operation.available_actions.includes("retry");
  /* Retry on a run that succeeded re-runs work that has a result on record and
     supersedes it, so it is offered without being recommended: the loud control on the
     screen must never be the one that discards what the reader is looking at. The way on
     from a finished run is the host screen's own next action, which is on the page around
     this overlay. */
  if (!canCancel && !canRetry && error === null && recovery == null) return null;

  return (
    <div className="mt-2 flex flex-col gap-4 border-t border-cv-border pt-5">
      {error === null ? null : (
        <ErrorCallout error={error} fallbackDetail="המצב הקיים נשמר. אפשר לנסות שוב." title="הפעולה לא בוצעה" />
      )}

      {/* On a phone the row is the report's foot: its commands share the width evenly,
          each one a full thumb's target, as the bottom bars of the steps around it do. */}
      <div className="flex flex-wrap gap-3 max-lg:flex-nowrap max-lg:[&>*]:min-h-11 max-lg:[&>*]:flex-1">
        {recovery}
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
