import type { Operation } from "@/api/contracts";
import { isTerminalOperation } from "@/api/operations";

interface OperationLiveness {
  /* See `useWatchedOperation`. */
  awaitingRecord: boolean;
  /* The screen's own continuation line, present while it is starting the next run or
     leaving for the next step after this one succeeded. */
  continuation?: string | undefined;
  operation: Operation | undefined;
  /* Work this screen asked for before any Operation record exists to report it. */
  pending: boolean;
  settled: boolean;
}

/* Work is starting or under way: something was asked for, a record is on its way, a run
   is queued or running, or the screen is moving straight on to the next run. This is the
   only signal that starts an overlay session - a record that was already finished when
   the screen read it is history, not work the reader is waiting on. */
export const isOperationStarting = ({ awaitingRecord, continuation, operation, pending }: OperationLiveness) =>
  pending ||
  awaitingRecord ||
  (operation !== undefined && !isTerminalOperation(operation)) ||
  continuation !== undefined;

/* Whether actions that change what the run replaces must wait. Wider than "starting" by
   the tail between a success and the refreshed read of what it produced: the output is
   already written, but the screen still holds the reads from before it, and a command
   sent from them - an edit carrying the previous draft version - is refused as a
   conflict. That tail ends as soon as the refresh the watch starts has landed, including
   on a reload that arrives at a finished run, so it never holds a screen for long. */
export const isOperationLive = (liveness: OperationLiveness) =>
  isOperationStarting(liveness) || (liveness.operation?.status === "succeeded" && !liveness.settled);
