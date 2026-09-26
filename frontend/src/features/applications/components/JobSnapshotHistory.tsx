import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { jobSnapshotHistoryOptions } from "@/api/applications";
import type { JobSnapshotHistory as History } from "@/api/contracts";
import { Button } from "@/ui/Button";
import { Disclosure, DisclosureSummary } from "@/ui/Disclosure";
import { Select } from "@/ui/Select";
import { formatDateTime } from "@/utils/formatDateTime";
import { snapshotComparison } from "../model/snapshotComparison";

type Snapshot = History["items"][number];

const Comparison = ({ before, after }: { before: Snapshot; after: Snapshot }) => {
  const diff = useMemo(() => snapshotComparison(before.job_text ?? "", after.job_text ?? ""), [before, after]);
  const readable = before.job_text !== null && after.job_text !== null;
  return (
    <div className="mt-4 space-y-3">
      <p className="text-support text-cv-text-muted">
        האזור המסומן כולל את השינויים שבין תחילת וסוף הטקסט המשותף; ייתכן שיש בו גם טקסט שלא השתנה.
      </p>
      <p className="text-support">
        {before.source_url === after.source_url ? "כתובת המקור לא השתנתה." : "כתובת המקור השתנתה."}
      </p>
      {readable && before.job_text === after.job_text && <p className="text-support">נוסח המשרה זהה בדיוק.</p>}
      {!readable && <output className="block">תוכן שמור חסר; לא ניתן להשוות את הנוסחים.</output>}
      <div className="grid gap-4 lg:grid-cols-2">
        {(
          [
            { side: "before", snapshot: before },
            { side: "after", snapshot: after },
          ] as const
        ).map(({ side, snapshot }) => (
          <section key={side} className="min-w-0 rounded-control border border-cv-border p-3">
            <h4 className="text-support font-semibold">
              גרסה {snapshot.version_number} — {side === "before" ? "לפני (− מחיקות)" : "אחרי (+ תוספות)"}
            </h4>
            <p dir="ltr" className="my-2 break-all text-support">
              {snapshot.source_url ?? "ללא כתובת מקור"}
            </p>
            {snapshot.job_text === null ? (
              <p>נוסח המשרה אינו זמין.</p>
            ) : (
              <pre
                dir="auto"
                className="max-h-96 overflow-auto whitespace-break-spaces break-words font-sans text-support"
              >
                {readable ? (
                  <>
                    {diff.prefix}
                    <span
                      className={
                        side === "before" ? "bg-cv-blocker-soft text-cv-blocker" : "bg-cv-success-soft text-cv-success"
                      }
                    >
                      {side === "before" ? diff.removed : diff.added}
                    </span>
                    {diff.suffix}
                  </>
                ) : (
                  snapshot.job_text
                )}
              </pre>
            )}
          </section>
        ))}
      </div>
      {readable && (diff.removed !== "" || diff.added !== "") && (
        <Disclosure summary="הצגת רווחים ושבירות שורה באזור שהשתנה">
          <p>· = רווח, ⇥ = טאב, ↵ = ירידת שורה, ␍ = חזרת עגלה</p>
          {(
            [
              { kind: "removed", text: diff.removed },
              { kind: "added", text: diff.added },
            ] as const
          ).map(({ kind, text }) => (
            <div key={kind}>
              <p>{kind === "removed" ? "− מחיקות" : "+ תוספות"}</p>
              <pre dir="auto" className="max-h-48 overflow-auto whitespace-break-spaces break-words font-sans">
                {text.replace(/ /g, "·").replace(/\t/g, "⇥").replace(/\r/g, "␍").replace(/\n/g, "↵\n")}
              </pre>
            </div>
          ))}
        </Disclosure>
      )}
    </div>
  );
};

const HistorySelection = ({ history }: { history: History }) => {
  const [beforeId, setBeforeId] = useState(history.items.at(-2)?.id ?? history.items[0]?.id);
  const [afterId, setAfterId] = useState(history.items.at(-1)?.id);
  const before = history.items.find((item) => item.id === beforeId);
  const after = history.items.find((item) => item.id === afterId);
  if (history.items.length === 0) return <p>אין תצלומים שמורים.</p>;
  return (
    <>
      {history.items.length === 1 && <p className="text-support">קיים נוסח שמור אחד בלבד; אין גרסה קודמת להשוואה.</p>}
      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        {(["לפני", "אחרי"] as const).map((label, index) => (
          <label key={label} className="text-support">
            {label}
            <Select
              value={index === 0 ? beforeId : afterId}
              onChange={(event) => (index === 0 ? setBeforeId : setAfterId)(event.target.value)}
            >
              {history.items.map((item) => (
                <option key={item.id} value={item.id}>
                  גרסה {item.version_number} · {formatDateTime(item.captured_at, "short")}
                  {item.id === history.active_job_snapshot_id ? " · פעילה" : ""}
                </option>
              ))}
            </Select>
          </label>
        ))}
      </div>
      {before && after && <Comparison before={before} after={after} />}
    </>
  );
};

export const JobSnapshotHistory = ({
  applicationId,
  activeSnapshotId,
}: {
  applicationId: string;
  activeSnapshotId: string;
}) => {
  /* The history is read when it is asked for. Every posting it carries is a full job text,
     and fetching all of them behind a disclosure nobody opened spent that on every visit to
     the screen; it also put the panel's loading, error and empty states on a screen that
     was not showing the panel, where they compete with the states that screen does own. */
  const [open, setOpen] = useState(false);
  const history = useQuery({ ...jobSnapshotHistoryOptions(applicationId, activeSnapshotId), enabled: open });
  return (
    <details className="mt-4 border-t border-cv-border pt-4" onToggle={(event) => setOpen(event.currentTarget.open)}>
      <DisclosureSummary className="text-support font-semibold" open={open}>
        היסטוריית נוסחי משרה
      </DisclosureSummary>
      {open && (
        <>
          <p className="mt-2 text-support text-cv-text-muted">הצגת ההיסטוריה אינה משנה את נוסח המשרה הפעיל.</p>
          {history.isPending && <output className="block">טוען נוסחים שמורים…</output>}
          {history.isError && (
            <div role="alert">
              <p>לא ניתן לטעון את היסטוריית המשרה.</p>
              <Button variant="secondary" onClick={() => void history.refetch()}>
                ניסיון חוזר
              </Button>
            </div>
          )}
          {history.data && <HistorySelection key={activeSnapshotId} history={history.data} />}
        </>
      )}
    </details>
  );
};
