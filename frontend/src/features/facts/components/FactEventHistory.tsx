import type { FactDetail } from "@/api/contracts";
import { factStatusLabel } from "../model/factLabels";

/* The fact's own trail, oldest first. Every line is an event that was written; nothing
   here is inferred, and no event is ever rewritten - which is why the first one reads as
   a creation rather than as a transition out of nothing. */
export const FactEventHistory = ({ events }: { events: FactDetail["events"] }) => (
  <ol className="flex flex-col gap-2">
    {events.map((event) => (
      <li className="border-s-2 border-cv-border ps-3 text-support text-cv-text-muted" key={event.id}>
        {event.from_status == null
          ? "נוצרה כממתינה"
          : `${factStatusLabel(event.from_status)} ← ${factStatusLabel(event.to_status)}`}
        {event.reason === "" ? "" : ` · ${event.reason}`}
      </li>
    ))}
  </ol>
);
