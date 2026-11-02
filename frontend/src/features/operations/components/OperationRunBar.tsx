import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import type { Operation } from "@/api/contracts";
import { cancelOperation, operationQueryKey } from "@/api/operations";
import { boardPath, boardReturnState } from "@/navigation/boardReturn";
import { Button, buttonClasses } from "@/ui/Button";
import { CommitBar } from "@/ui/CommitBar";
import { ErrorCallout } from "@/ui/ErrorCallout";
import { useCancelReveal } from "../hooks/useCancelReveal";

/* The phone's bar under a run that is the step's whole screen: leave for the board - the
   run goes on without the reader - or stop it.

   Cancel is the record's own command, offered after the same delay the report waits, and
   only while the record says it can be cancelled. Its failure is reported inside the bar,
   where the command was. */
export const OperationRunBar = ({ operation }: { operation: Operation }) => {
  const queryClient = useQueryClient();
  const revealed = useCancelReveal(operation);
  const cancel = useMutation({
    mutationFn: () => cancelOperation(operation.id),
    onSuccess: (cancelled) => {
      queryClient.setQueryData(operationQueryKey(cancelled.id), cancelled);
    },
  });
  const canCancel = revealed && operation.available_actions.includes("cancel");

  return (
    <CommitBar
      primary={
        <Link className={buttonClasses("primary")} state={boardReturnState(operation.application_id)} to={boardPath()}>
          חזרה ללוח
        </Link>
      }
      {...(cancel.error === null
        ? {}
        : {
            result: (
              <ErrorCallout
                error={cancel.error}
                fallbackDetail="ההרצה ממשיכה. אפשר לנסות שוב."
                title="הפעולה לא בוטלה"
              />
            ),
          })}
      {...(canCancel
        ? {
            secondary: (
              <Button
                onClick={() => cancel.mutate()}
                pending={cancel.isPending}
                pendingLabel="מבטל…"
                variant="secondary"
              >
                ביטול הפעולה
              </Button>
            ),
          }
        : {})}
    />
  );
};
