/* The Operations feature's public surface.

   An Operation is durable work queued against one Application, and four screens report
   one: the Application hub, the preparation workflow inside it, the draft editor, and the
   revision. None of them owns the vocabulary or the panel, which is why neither lives in
   any of them any more - the panel and its Hebrew status/phase/failure maps were inside
   `features/applications` and reached by deep import from the other three.

   There is no Operation screen. Cancel and retry are the record's own actions and travel
   with the panel, so `OperationActions` is not exported: a caller that shows an Operation
   shows this panel. */
export { ActiveOperationPanel } from "./components/ActiveOperationPanel";
export { operationTypeLabels, statusLabels, statusTones } from "./model/operationLabels";
