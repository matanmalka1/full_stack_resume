import type { FactDetail } from "../../api/contracts";
import { factStatusLabel } from "./factLabels";

interface FactEventHistoryProps {
  events: FactDetail["events"];
}

export const FactEventHistory = ({ events }: FactEventHistoryProps) => (
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
