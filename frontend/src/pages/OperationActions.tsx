import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useMemo } from "react";
import { Link, useNavigate } from "react-router-dom";

import { ApiProblem } from "../api/client";
import type { Operation } from "../api/contracts";
import {
  cancelOperation,
  operationQueryKey,
  retryOperation,
} from "../api/operations";
import { Button, buttonClasses } from "../ui/Button";
import { Callout } from "../ui/Callout";
import { LtrText } from "../ui/LtrText";
import { TechnicalDetails } from "../ui/TechnicalDetails";

interface OperationActionsProps {
  operation: Operation;
}

const mutationMessage = (error: unknown): string =>
  error instanceof ApiProblem
    ? error.problem.detail
    : "לא ניתן להשלים את הפעולה. המצב הבטוח האחרון נשמר ואפשר לנסות שוב.";

export const OperationActions = ({ operation }: OperationActionsProps) => {
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
      void navigate(operationPath);
    },
  });

  const error = cancel.error ?? retry.error;
  const canCancel = operation.available_actions.includes("cancel");
  const canRetry = operation.available_actions.includes("retry");
  /* A finished Operation used to be a dead end: it reported that the work was over and
     offered nowhere to go. The way on is not this screen's to invent - which action
     follows depends on the application projection (A.1) - so it hands the user back to
     the screen that owns that projection and lets it say what comes next. */
  const returnPath = `/applications/${encodeURIComponent(operation.application_id)}`;

  if (!canCancel && !canRetry && !operation.is_terminal && error === null) {
    return null;
  }

  return (
    <div className="mt-8 flex flex-col gap-4 border-t border-cv-border pt-6">
      {error === null ? null : (
        <Callout role="alert" title="הפעולה לא בוצעה" tone="blocker">
          {mutationMessage(error)}
          {error instanceof ApiProblem ? (
            <TechnicalDetails className="mt-3">
              <LtrText>{error.problem.code}</LtrText>
            </TechnicalDetails>
          ) : null}
        </Callout>
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
          >
            {retry.isPending ? "יוצר ניסיון חדש…" : "ניסיון חוזר"}
          </Button>
        ) : null}
        {operation.is_terminal ? (
          <Link className={buttonClasses(canRetry ? "secondary" : "primary")} to={returnPath}>
            חזרה למועמדות
          </Link>
        ) : null}
      </div>
    </div>
  );
};
