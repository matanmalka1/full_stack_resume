import { useQuery } from "@tanstack/react-query";
import { Bell, CalendarDays, ChevronLeft, Clock, FileCheck2, TriangleAlert, type LucideIcon } from "lucide-react";
import { useId, useState } from "react";
import { Link } from "react-router-dom";

import { applicationListQueryOptions } from "@/api/applications";
import { StatusBadge } from "@/ui/StatusBadge";
import { cx } from "@/ui/cx";
import { BOARD_LIMIT } from "../model/applicationListParams";
import { attentionHubItems, type HubItem } from "../model/applicationListPresentation";

/* How many rows the panel draws before "all": two on a phone, where it sits above the
   cards and must not push them off the first screen; three beside them on a wide screen. */
const PHONE_ROWS = 2;
const WIDE_ROWS = 3;

const rowIcons: Record<HubItem["type"], LucideIcon> = {
  overdue: Clock,
  due_today: Clock,
  attention: TriangleAlert,
  due_this_week: CalendarDays,
  ready: FileCheck2,
};

const HubRow = ({ hidden, item }: { hidden: string | undefined; item: HubItem }) => {
  const Icon = rowIcons[item.type];
  const urgent = item.type === "overdue";

  return (
    <li className={cx("border-t border-cv-hairline first:border-t-0", hidden)}>
      <Link
        className="flex min-h-14 items-center gap-3 px-3.5 py-3 text-cv-text transition-colors hover:bg-cv-surface-muted"
        to={item.to}
      >
        {/* The row's kind as a mark, on a phone only - the design's wide panel is text. */}
        <span
          aria-hidden="true"
          className={cx(
            "flex size-9 shrink-0 items-center justify-center rounded-control-sm lg:hidden",
            urgent ? "bg-cv-text text-cv-surface" : "bg-cv-surface-muted text-cv-text",
          )}
        >
          <Icon className="size-icon-md" />
        </span>
        <span className="min-w-0 flex-1">
          <span className="block truncate text-label font-bold">
            <bdi>{item.title}</bdi>
          </span>
          <span className="block truncate text-support text-cv-text-muted">
            <span dir="auto">{item.application.company}</span> · <span dir="auto">{item.application.target_role}</span>
          </span>
        </span>
        <StatusBadge icon={false} className="px-2.25 py-0.75" tone="progress" variant={urgent ? "solid" : "soft"}>
          {item.label}
        </StatusBadge>
      </Link>
    </li>
  );
};

/* The board's one dark block: what waits on the reader across the open board, each row
   the way to where it is done. It reads the whole open board itself - the same question
   the unnarrowed board asks, so the two share one cached answer - because a slice chosen
   below must not hide what is waiting from the panel that exists to say so.

   It says nothing when nothing waits: the design has no "all clear" state, and an empty
   panel would only push the cards down. */
export const ApplicationAttentionSummary = () => {
  const headingId = useId();
  const [expanded, setExpanded] = useState(false);
  const hubQuery = useQuery(applicationListQueryOptions({ activity: "open", sort: "updated", limit: BOARD_LIMIT }));
  const items = attentionHubItems(hubQuery.data?.items ?? []);

  if (items.length === 0) {
    return null;
  }

  /* Rows past the phone's two fold away below the large breakpoint, rows past three at
     every width, until the reader asks for all of them. */
  const hiddenClasses = (index: number): string | undefined =>
    expanded ? undefined : index >= WIDE_ROWS ? "hidden" : index >= PHONE_ROWS ? "max-lg:hidden" : undefined;

  /* One "all" for both widths: on a wide screen it is drawn only when there is more than
     its three rows. */
  const toggle =
    items.length > PHONE_ROWS ? (
      <button
        aria-expanded={expanded}
        className={cx(
          "inline-flex min-h-8 items-center gap-0.5 text-support font-medium",
          items.length > WIDE_ROWS ? undefined : "lg:hidden",
        )}
        onClick={() => setExpanded((value) => !value)}
        type="button"
      >
        {expanded ? "פחות" : `הכל (${items.length})`}
        <ChevronLeft aria-hidden="true" className={cx("size-icon-sm transition-transform", expanded && "-rotate-90")} />
      </button>
    ) : null;

  return (
    <section
      aria-labelledby={headingId}
      className="rounded-fab bg-cv-accent p-1 text-cv-on-accent shadow-fab lg:w-75 lg:shrink-0"
    >
      <div className="flex items-center justify-between gap-3 px-3 pt-2 pb-2.5">
        <h2 className="flex items-center gap-2 text-body font-bold" id={headingId}>
          <Bell aria-hidden="true" className="size-icon-md" />
          מוקד פעולות
        </h2>
        <span className="flex items-center gap-3">
          <span className="text-support opacity-85 max-lg:hidden">{items.length} ממתינות</span>
          {toggle}
        </span>
      </div>
      <ul className="m-0 list-none overflow-hidden rounded-control-lg bg-cv-surface p-0">
        {items.map((item, index) => (
          <HubRow hidden={hiddenClasses(index)} item={item} key={item.application.id} />
        ))}
      </ul>
    </section>
  );
};
