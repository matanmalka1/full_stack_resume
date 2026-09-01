import { useMemo } from "react";

import type { RecruitmentTimelineItem } from "../../api/contracts";
import { formatDate, formatDateTime } from "../../ui/formatDateTime";
import { recruitmentStatusLabel } from "../application/applicationLabels";

export const statusEventLabel = (event: RecruitmentTimelineItem): string =>
  `${formatDateTime(event.occurred_at)} · ${recruitmentStatusLabel(event.to_status ?? "saved")}`;

const descriptionFor = (event: RecruitmentTimelineItem, byId: ReadonlyMap<string, RecruitmentTimelineItem>): string => {
  if (event.item_type === "submission") {
    return event.submission_type === "internal" ? "נרשמה הגשה של הגרסה המוכנה" : "נרשמה הגשה שבוצעה מחוץ למערכת";
  }
  if (event.item_type === "next_action") {
    return event.next_action == null
      ? "התזכורת לפעולה הבאה הוסרה"
      : `הפעולה הבאה נקבעה: ${event.next_action}${
          event.next_action_date == null ? "" : ` · ${formatDate(event.next_action_date)}`
        }`;
  }
  if (event.item_type === "status_correction") {
    const corrected = event.corrects_event_id == null ? undefined : byId.get(event.corrects_event_id);
    const target = recruitmentStatusLabel(event.to_status ?? "saved");
    return corrected === undefined
      ? `מצב הגיוס תוקן ל־${target}`
      : `האירוע „${statusEventLabel(corrected)}” תוקן ל־${target}`;
  }
  return `מצב הגיוס עבר מ־${recruitmentStatusLabel(
    event.from_status ?? "saved",
  )} ל־${recruitmentStatusLabel(event.to_status ?? "saved")}`;
};

const reasonFor = (reason: string): string => (reason === "application created" ? "המועמדות נוצרה" : reason);

export const RecruitmentTimeline = ({ items }: { items: RecruitmentTimelineItem[] }) => {
  const byId = useMemo(() => new Map(items.map((event) => [event.id, event])), [items]);

  if (items.length === 0) return <p className="mt-3 text-support text-cv-text-muted">עדיין אין אירועים.</p>;

  return (
    <ol className="mt-4 flex flex-col gap-3">
      {[...items].reverse().map((event) => (
        <li className="border-s-2 border-cv-border ps-4" key={event.id}>
          <p className="font-medium text-cv-text" dir="auto">
            {descriptionFor(event, byId)}
          </p>
          <p className="text-support text-cv-text-muted">
            {formatDateTime(event.occurred_at)}
            {event.actor_type === "user" ? " · אתה" : ""}
          </p>
          {event.reason === "" ? null : (
            <p className="mt-1 text-support text-cv-text-muted" dir="auto">
              {reasonFor(event.reason)}
            </p>
          )}
        </li>
      ))}
    </ol>
  );
};
