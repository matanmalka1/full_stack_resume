import { Callout } from "../../../ui/Callout";

/* A superseded analysis is not shown as if it were the one in force: the reader is told
   the analysis on record belongs to an older snapshot and that a new one is what the
   workflow is waiting on. The projection's stale and review reasons carry the action. */
export const SupersededAnalysisNote = () => (
  <Callout title="הניתוח שעל המסך אינו הניתוח הפעיל" tone="warning">
    הניתוח האחרון שנשמר נעשה מול תצלום משרה קודם, ולכן אינו מוצג כאן. ניתוח חדש מול התצלום הפעיל הוא מה שיציג את הסיווג
    העדכני.
  </Callout>
);
