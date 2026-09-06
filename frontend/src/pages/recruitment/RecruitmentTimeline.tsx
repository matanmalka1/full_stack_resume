import { Activity, CalendarClock, RefreshCcw, Send, type LucideIcon } from "lucide-react";
import { useMemo } from "react";
import { useState } from "react";

import type { RecruitmentTimelineItem } from "../../api/contracts";
import { Button } from "../../ui/Button";
import { cx } from "../../ui/cx";
import { formatDate, formatDateTime } from "../../ui/formatDateTime";
import { recruitmentStatusIcon, recruitmentStatusLabel, recruitmentStatusTone } from "../application/applicationLabels";

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
  /* A first event carries no `from_status`, because there was no status before it. The
     null was read as "saved" and printed as a transition from a status the record never
     held - "מצב הגיוס עבר מ־נשמר ל־נשמר" on every Application the moment it was created.
     An absent origin is now named as the opening it is. */
  if (event.from_status == null) {
    return `המועמדות נפתחה במצב ${recruitmentStatusLabel(event.to_status ?? "saved")}`;
  }
  return `מצב הגיוס עבר מ־${recruitmentStatusLabel(
    event.from_status,
  )} ל־${recruitmentStatusLabel(event.to_status ?? "saved")}`;
};

/* The reasons the engine writes into the immutable event, in Hebrew. The records keep the
   exact English sentence they were written with; this is presentation over them, and a
   reason with no entry is shown exactly as recorded rather than guessed at. */
const engineReasons: Record<string, string> = {
  "application created": "המועמדות נוצרה",
  "application closed": "המועמדות נסגרה",
  "submission recorded": "נרשמה הגשה",
};

const reasonFor = (reason: string): string => engineReasons[reason] ?? reason;

const markerFor = (event: RecruitmentTimelineItem): { classes: string; icon: LucideIcon } => {
  if (event.item_type === "submission") {
    return { classes: "border-cv-success/30 bg-cv-success/10 text-cv-success", icon: Send };
  }
  if (event.item_type === "next_action") {
    return { classes: "border-cv-accent/30 bg-cv-accent-soft text-cv-accent", icon: CalendarClock };
  }
  if (event.item_type === "status_correction") {
    return { classes: "border-cv-warning/30 bg-cv-warning/10 text-cv-warning", icon: RefreshCcw };
  }

  const tone = recruitmentStatusTone(event.to_status ?? "saved");
  const classes = {
    blocker: "border-cv-blocker/30 bg-cv-blocker/10 text-cv-blocker",
    neutral: "border-cv-border bg-cv-surface text-cv-text-muted",
    progress: "border-cv-accent/30 bg-cv-accent-soft text-cv-accent",
    success: "border-cv-success/30 bg-cv-success/10 text-cv-success",
    warning: "border-cv-warning/30 bg-cv-warning/10 text-cv-warning",
  }[tone];

  return { classes, icon: event.to_status == null ? Activity : recruitmentStatusIcon(event.to_status) };
};

const initialTimelineItems = 5;

export const RecruitmentTimeline = ({ items }: { items: RecruitmentTimelineItem[] }) => {
  const byId = useMemo(() => new Map(items.map((event) => [event.id, event])), [items]);
  const [expanded, setExpanded] = useState(false);

  if (items.length === 0) return <p className="mt-3 text-support text-cv-text-muted">עדיין אין אירועים.</p>;

  const newestFirst = [...items].reverse();
  const visibleItems = expanded ? newestFirst : newestFirst.slice(0, initialTimelineItems);

  return (
    <>
      <ol className="mt-4 flex flex-col">
        {visibleItems.map((event, index) => {
          const marker = markerFor(event);
          const Icon = marker.icon;

          return (
            <li className="relative grid grid-cols-[2rem_minmax(0,1fr)] gap-3 pb-5 last:pb-0" key={event.id}>
              {index === visibleItems.length - 1 ? null : (
                <span aria-hidden="true" className="absolute bottom-0 start-[0.9375rem] top-8 w-px bg-cv-border" />
              )}
              <span
                aria-hidden="true"
                className={cx(
                  "relative z-10 inline-flex size-8 items-center justify-center rounded-full border",
                  marker.classes,
                )}
              >
                <Icon className="size-4" />
              </span>
              <div className="min-w-0 pt-0.5">
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
              </div>
            </li>
          );
        })}
      </ol>
      {items.length <= initialTimelineItems ? null : (
        <Button className="mt-4 px-0" onClick={() => setExpanded((value) => !value)} variant="ghost">
          {expanded ? "הצגת פחות אירועים" : `הצגת כל ההיסטוריה (${items.length})`}
        </Button>
      )}
    </>
  );
};
