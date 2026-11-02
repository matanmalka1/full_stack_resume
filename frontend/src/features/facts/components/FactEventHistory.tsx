import { useEffect } from "react";

import type { FactDetail } from "@/api/contracts";
import { cx } from "@/ui/cx";
import { DateTime } from "@/ui/DateTime";
import { factStatusLabel } from "../model/factLabels";

/* The fact's own trail, oldest first: a dot, what happened, and when. Every line is an
   event that was written; nothing here is inferred, and no event is ever rewritten -
   which is why the first one reads as a creation rather than as a transition out of
   nothing. A reason recorded with the event follows on the same line. */
export const FactEventHistory = ({
  events,
  selectedEventId,
}: {
  events: FactDetail["events"];
  selectedEventId?: string | null;
}) => {
  useEffect(() => {
    if (selectedEventId === undefined || selectedEventId === null) return;
    document.getElementById(`fact-event-${selectedEventId}`)?.scrollIntoView?.({ block: "center" });
  }, [selectedEventId]);

  return (
    <ol className="flex flex-col gap-3">
      {events.map((event) => {
        const selected = event.id === selectedEventId;
        return (
          <li
            aria-current={selected ? "location" : undefined}
            className={cx(
              "flex scroll-mt-6 items-start gap-2.5",
              selected && "-mx-2 rounded-item bg-cv-accent-soft px-2 py-1",
            )}
            id={`fact-event-${event.id}`}
            key={event.id}
          >
            <span aria-hidden="true" className="mt-1.75 size-2.5 shrink-0 rounded-pill bg-cv-accent" />
            <span className="min-w-0 flex-1 text-label">
              {(event.from_status == null
                ? "נוצרה כממתינה"
                : `${factStatusLabel(event.from_status)} ← ${factStatusLabel(event.to_status)}`) +
                (event.reason === "" ? "" : ` · ${event.reason}`)}
            </span>
            <span className="shrink-0 pt-0.5 text-caption text-cv-text-muted">
              <DateTime format="date" value={event.created_at} />
            </span>
          </li>
        );
      })}
    </ol>
  );
};
