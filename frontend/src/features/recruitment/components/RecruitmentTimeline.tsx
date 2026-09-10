import { Activity, CalendarClock, RefreshCcw, Send, type LucideIcon } from "lucide-react";
import { useMemo } from "react";
import { useState } from "react";

import type { RecruitmentTimelineItem } from "@/api/contracts";
import { Button } from "@/ui/Button";
import { cx } from "@/ui/cx";
import { formatDateTime } from "@/utils/formatDateTime";
import { recruitmentStatusIcon, recruitmentStatusTone } from "../model/recruitmentStatus";
import { recruitmentEventDescription, recruitmentEventReason } from "../model/recruitmentTimeline";

const markerFor = (event: RecruitmentTimelineItem): { classes: string; icon: LucideIcon } => {
  if (event.item_type === "submission") {
    return { classes: "border-cv-success/30 bg-cv-success-soft text-cv-success", icon: Send };
  }
  if (event.item_type === "next_action") {
    return { classes: "border-cv-accent/30 bg-cv-accent-soft text-cv-accent", icon: CalendarClock };
  }
  if (event.item_type === "status_correction") {
    return { classes: "border-cv-warning/30 bg-cv-warning-soft text-cv-warning", icon: RefreshCcw };
  }

  const tone = recruitmentStatusTone(event.to_status ?? "saved");
  const classes = {
    blocker: "border-cv-blocker/30 bg-cv-blocker-soft text-cv-blocker",
    info: "border-cv-info/30 bg-cv-info-soft text-cv-info",
    neutral: "border-cv-border bg-cv-surface text-cv-text-muted",
    progress: "border-cv-accent/30 bg-cv-accent-soft text-cv-accent",
    success: "border-cv-success/30 bg-cv-success-soft text-cv-success",
    warning: "border-cv-warning/30 bg-cv-warning-soft text-cv-warning",
  }[tone];

  return { classes, icon: event.to_status == null ? Activity : recruitmentStatusIcon(event.to_status) };
};

const initialTimelineItems = 5;

export const RecruitmentTimeline = ({ items }: { items: RecruitmentTimelineItem[] }) => {
  const byId = useMemo(() => new Map(items.map((event) => [event.id, event])), [items]);
  const [expanded, setExpanded] = useState(false);

  if (items.length === 0) return <p className="mt-3 text-support text-cv-text-muted">עדיין אין אירועים.</p>;

  // The spread protects props from mutation; the runtime target is ES2022.
  // oxlint-disable-next-line unicorn/no-array-reverse
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
                  "relative z-(--cv-z-content-raised) inline-flex size-8 items-center justify-center rounded-full border",
                  marker.classes,
                )}
              >
                <Icon className="size-icon-md" />
              </span>
              <div className="min-w-0 pt-0.5">
                <p className="font-medium text-cv-text" dir="auto">
                  {recruitmentEventDescription(event, byId)}
                </p>
                <p className="text-support text-cv-text-muted">
                  {formatDateTime(event.occurred_at)}
                  {event.actor_type === "user" ? " · אתה" : ""}
                </p>
                {event.reason === "" ? null : (
                  <p className="mt-1 text-support text-cv-text-muted" dir="auto">
                    {recruitmentEventReason(event.reason)}
                  </p>
                )}
              </div>
            </li>
          );
        })}
      </ol>
      {items.length <= initialTimelineItems ? null : (
        <Button className="mt-4" onClick={() => setExpanded((value) => !value)} size="flush" variant="ghost">
          {expanded ? "הצגת פחות אירועים" : `הצגת כל ההיסטוריה (${items.length})`}
        </Button>
      )}
    </>
  );
};
