/* The Operations feature's public surface.

   An Operation is durable work queued against one Application, and three screens report
   one: the Application's preparation step, the draft editor, and the revision. None of
   them owns the vocabulary or the overlay, which is why neither lives in any of them.

   There is no Operation screen. Cancel and retry are the record's own actions and travel
   with the report inside the overlay, so neither `OperationActions` nor `OperationReport`
   is exported: a screen that shows an Operation shows this overlay, once. */
export { OperationOverlay, type PendingWork } from "./components/OperationOverlay";
/* Whether actions that change what a run replaces must wait - the same definition the
   overlay's session is built on, so a screen's lock and its overlay never disagree about
   when work is under way. */
export { isOperationLive } from "./model/operationLive";
/* Watching one Application's live work, on whichever screen queued it. It is
   Operation-shaped and every consumer of it already shows the overlay, so it sits with it
   rather than as root-level infrastructure. */
export { useWatchedOperation } from "./hooks/useWatchedOperation";
export { operationTypeLabels, statusLabels, statusTones } from "./model/operationLabels";
