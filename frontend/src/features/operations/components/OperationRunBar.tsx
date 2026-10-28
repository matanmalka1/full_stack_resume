import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import type { Operation } from "@/api/contracts";
import { cancelOperation, operationQueryKey } from "@/api/operations";
import { boardPath, boardReturnState } from "@/navigation/boardReturn";
import { Button, buttonClasses } from "@/ui/Button";
import { CommitBar } from "@/ui/CommitBar";
import { ErrorCallout } from "@/ui/ErrorCallout";
import { useCancelReveal } from "../hooks/useCancelReveal";

/* Cancel is the record's own command, offered after the same delay the report waits, and
   only while the record says it can be cancelled. Shared by the phone's bar and the wide
   card, so the two places a run's whole screen offers it agree on when. */
const useRunCancel = (operation: Operation) => {
  const queryClient = useQueryClient();
  const revealed = useCancelReveal(operation);
  const cancel = useMutation({
    mutationFn: () => cancelOperation(operation.id),
    onSuccess: (cancelled) => {
      queryClient.setQueryData(operationQueryKey(cancelled.id), cancelled);
    },
  });
  return { cancel, canCancel: revealed && operation.available_actions.includes("cancel") };
};

const BoardLink = ({ operation }: { operation: Operation }) => (
  <Link className={buttonClasses("primary")} state={boardReturnState(operation.application_id)} to={boardPath()}>
    חזרה ללוח
  </Link>
);

const CancelError = ({ error }: { error: Error }) => (
  <ErrorCallout error={error} fallbackDetail="ההרצה ממשיכה. אפשר לנסות שוב." title="הפעולה לא בוטלה" />
);

/* The phone's bar under a run that is the step's whole screen: leave for the board - the
   run goes on without the reader - or stop it. Its failure is reported inside the bar,
   where the command was. */
export const OperationRunBar = ({ operation }: { operation: Operation }) => {
  const { cancel, canCancel } = useRunCancel(operation);

  return (
    <CommitBar
      primary={<BoardLink operation={operation} />}
      {...(cancel.error === null ? {} : { result: <CancelError error={cancel.error} /> })}
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

/* The same two ways on, at the foot of the wide screen's centred run card. A pinned bar
   at the viewport's bottom sat a screen's height away from a card centred in it, so on a
   wide screen they close the card itself, the way its design draws them. */
export const OperationRunActions = ({ operation }: { operation: Operation }) => {
  const { cancel, canCancel } = useRunCancel(operation);

  return (
    <div className="flex w-full flex-col items-center gap-3">
      {cancel.error === null ? null : <CancelError error={cancel.error} />}
      <div className="flex flex-wrap justify-center gap-3">
        {canCancel ? (
          <Button onClick={() => cancel.mutate()} pending={cancel.isPending} pendingLabel="מבטל…" variant="secondary">
            ביטול הפעולה
          </Button>
        ) : null}
        <BoardLink operation={operation} />
      </div>
    </div>
  );
};
