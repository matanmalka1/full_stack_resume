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
import { cx } from "../ui/cx";
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
     follows depends on the application projection (A.1) - so it hands the user back to
     the screen that owns that projection and lets it say what comes next. */
  const returnPath = `/applications/${encodeURIComponent(operation.application_id)}`;

  if (!canCancel && !canRetry && !operation.is_terminal && error === null) {
    return null;
  }

  return (
    <div className="mt-2 flex flex-col gap-4 border-t border-cv-border pt-5">
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
            {retry.isPending ? "יוצר ניסיון חדש…" : "ניסיון חוזר"}
          </Button>
        ) : null}
        {operation.is_terminal ? (
          <Link
            className={buttonClasses(canRetry && !returnRecommended ? "secondary" : "primary")}
            to={returnPath}
          >
            חזרה למועמדות
          </Link>
        ) : null}
      </div>
    </div>
  );
};
