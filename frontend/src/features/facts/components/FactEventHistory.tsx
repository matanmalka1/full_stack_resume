import { useEffect } from "react";

import type { FactDetail } from "@/api/contracts";
import { factStatusLabel } from "../model/factLabels";

/* The fact's own trail, oldest first. Every line is an event that was written; nothing
   here is inferred, and no event is ever rewritten - which is why the first one reads as
   a creation rather than as a transition out of nothing. */
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
    <ol className="flex flex-col gap-2">
      {events.map((event) => (
        <li
          aria-current={event.id === selectedEventId ? "location" : undefined}
          className={
            event.id === selectedEventId
              ? "scroll-mt-6 rounded-control border-s-2 border-cv-accent bg-cv-accent-soft ps-3 text-support text-cv-text"
              : "scroll-mt-6 border-s-2 border-cv-border ps-3 text-support text-cv-text-muted"
          }
          id={`fact-event-${event.id}`}
          key={event.id}
        >
          {event.from_status == null
            ? "נוצרה כממתינה"
            : `${factStatusLabel(event.from_status)} ← ${factStatusLabel(event.to_status)}`}
          {event.reason === "" ? "" : ` · ${event.reason}`}
        </li>
      ))}
    </ol>
  );
};
