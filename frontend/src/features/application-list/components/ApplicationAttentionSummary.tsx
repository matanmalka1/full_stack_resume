import { useQuery } from "@tanstack/react-query";
import { BellOff, ChevronDown, ChevronLeft, CircleCheck, Sparkles } from "lucide-react";
import { Link } from "react-router-dom";

import { applicationListQueryOptions } from "@/api/applications";
import type { ApplicationListItem } from "@/api/contracts";
import { Button } from "@/ui/Button";
import { StatusBadge } from "@/ui/StatusBadge";
import { Tooltip } from "@/ui/Tooltip";
import { DuplicateIdentityHint } from "./ApplicationIdentity";
import { attentionHubItems, duplicatedApplicationIdentityIds } from "../model/applicationListPresentation";

interface ApplicationAttentionSummaryProps {
  /* Whether the board has any Application at all. An empty database already says so in
     its own empty state; a hub reporting "nothing waiting" above it would be noise. */
  boardHasApplications: boolean;
  clearingApplicationId: string | null;
  /* Whether the board below is already narrowed to the same preset. The offer to narrow
     it is then withdrawn rather than shown as a control that does nothing. */
  filterActive: boolean;
  onClearNextAction: (application: ApplicationListItem) => void;
  onOpenStatusDialog: (application: ApplicationListItem) => void;
  onShowAll: () => void;
}

export const ApplicationAttentionSummary = ({
  boardHasApplications,
  clearingApplicationId,
  filterActive,
  onClearNextAction,
  onOpenStatusDialog,
  onShowAll,
}: ApplicationAttentionSummaryProps) => {
  const attentionQuery = useQuery(applicationListQueryOptions({ preset: "needs_attention", limit: 3 }));
  const sourceItems = attentionQuery.data?.items ?? [];
  const displayItems = attentionHubItems(sourceItems);
  const ambiguous = duplicatedApplicationIdentityIds(sourceItems);
  /* The hub reads at most three; the server's match count is the whole preset, so the
     badge says how much is waiting even when only the first three are drawn. */
  const waitingCount = Math.max(attentionQuery.data?.matched ?? 0, displayItems.length);

  if (displayItems.length === 0) {
    /* Only a successful read may say nothing is waiting. While loading, or after a
       failure, the hub stays silent rather than claim a state it has not seen. */
    if (!attentionQuery.isSuccess || !boardHasApplications) {
      return null;
    }

    return (
      <section
        aria-labelledby="urgent-action-heading"
        className="flex items-center gap-2 rounded-surface border border-cv-border bg-cv-surface px-3 py-2.5"
      >
        <CircleCheck aria-hidden="true" className="size-icon-md shrink-0 text-cv-success" />
        <h2 className="text-support font-bold text-cv-text" id="urgent-action-heading">
          מוקד פעולות
        </h2>
        <p className="truncate text-support text-cv-text-muted">אין פעולות ממתינות.</p>
      </section>
    );
  }

  /* Below the large breakpoint the hub is the board's one dark block: an accent frame
     whose heading sits on the accent and whose rows sit on a light card inside it, so
     what is waiting is the first thing a phone's reader sees under the slices. */
  return (
    <section
      aria-labelledby="urgent-action-heading"
      className="rounded-surface border border-cv-border bg-cv-surface max-lg:border-cv-accent max-lg:bg-cv-accent max-lg:p-1 max-lg:shadow-floating"
    >
      <details className="group/attention" open>
        <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-3 py-2.5 lg:hover:bg-cv-surface-muted">
          <span className="flex min-w-0 items-baseline gap-2">
            <Sparkles
              aria-hidden="true"
              className="size-icon-md shrink-0 self-center text-cv-warning max-lg:text-cv-on-accent"
            />
            <h2 className="text-support font-bold text-cv-text max-lg:text-cv-on-accent" id="urgent-action-heading">
              מוקד פעולות
            </h2>
            <span className="shrink-0 self-center rounded-pill bg-cv-accent px-2 text-support font-bold text-cv-on-accent tabular-nums max-lg:bg-cv-on-accent max-lg:text-cv-accent">
              {waitingCount}
              <span className="sr-only"> ממתינות</span>
            </span>
            <span className="truncate text-support text-cv-text-muted max-lg:text-cv-on-accent">
              {waitingCount > displayItems.length
                ? `${displayItems.length} הראשונות מוצגות`
                : displayItems.length === 1
                  ? "פעולה אחת בעדיפות"
                  : `${displayItems.length} פעולות בעדיפות`}
            </span>
          </span>
          <ChevronDown
            aria-hidden="true"
            className="size-icon-md shrink-0 text-cv-text-muted transition-transform group-open/attention:rotate-180 max-lg:text-cv-on-accent"
          />
        </summary>

        {/* The first column is a fixed width rather than `auto`: each row is its own
            grid, so a badge-width column let every title start at a different x and the
            three rows read as unrelated blocks. */}
        <div className="divide-y divide-cv-border border-t border-cv-border max-lg:overflow-hidden max-lg:rounded-control max-lg:border-t-0 max-lg:bg-cv-surface">
          {displayItems.map((item) => (
            <article
              className="grid gap-x-3 gap-y-2 px-3 py-2.5 transition-colors hover:bg-cv-surface-muted sm:grid-cols-[9rem_minmax(0,1fr)_auto] sm:items-center"
              key={`${item.application.id}-${item.type}`}
            >
              <StatusBadge className="w-fit px-2 py-0.5 whitespace-nowrap" tone={item.tone}>
                {item.label}
              </StatusBadge>
              {/* One combined line, not a single-script identity field like `CompanyMark`
                  or `ApplicationSummary` carry - `dir="auto"` per line is wrong here: a
                  Latin company name (most of them) flips just the subtitle to LTR while
                  the Hebrew title above stays RTL, splitting the row into two halves with
                  a gap between them. Both lines follow the page's own direction instead. */}
              <div className="min-w-0" dir="rtl">
                <h3 className="truncate text-support font-bold text-cv-text">{item.title}</h3>
                <p className="truncate text-support text-cv-text-muted">
                  {item.application.company} · {item.subtitle}
                </p>
                {ambiguous.has(item.application.id) ? (
                  <DuplicateIdentityHint createdAt={item.application.created_at} />
                ) : null}
              </div>
              <div className="flex flex-wrap items-center gap-1.5 sm:justify-end">
                {item.type === "overdue" || item.type === "due_today" ? (
                  <Tooltip label="הסרת התזכורת, ללא רישום השלמה">
                    <Button
                      className="text-cv-text-muted hover:text-cv-success"
                      disabled={clearingApplicationId === item.application.id}
                      onClick={() => onClearNextAction(item.application)}
                      pending={clearingApplicationId === item.application.id}
                      pendingLabel="מסיר…"
                      size="compact"
                      variant="ghost"
                    >
                      <BellOff aria-hidden="true" className="size-icon-sm" />
                      הסרת תזכורת
                    </Button>
                  </Tooltip>
                ) : null}

                {item.actionTo == null ? (
                  <Button
                    className="gap-1"
                    onClick={() => onOpenStatusDialog(item.application)}
                    size="compact"
                    variant="secondary"
                  >
                    {item.actionLabel}
                    <ChevronLeft aria-hidden="true" className="size-icon-sm" />
                  </Button>
                ) : (
                  <Link
                    className="inline-flex min-h-8 items-center gap-1 rounded-control bg-cv-accent-soft px-2.5 text-support font-semibold text-cv-accent transition-colors hover:bg-cv-accent hover:text-cv-on-accent"
                    to={item.actionTo}
                  >
                    {item.actionLabel}
                    <ChevronLeft aria-hidden="true" className="size-icon-sm" />
                  </Link>
                )}
              </div>
            </article>
          ))}
        </div>
        {filterActive ? null : (
          <div className="flex justify-end border-t border-cv-border px-3 py-2 max-lg:border-t-0 max-lg:px-2 max-lg:py-1">
            <Button
              className="gap-1 max-lg:text-cv-on-accent max-lg:hover:bg-transparent max-lg:hover:underline"
              onClick={onShowAll}
              size="compact"
              variant="ghost"
            >
              הצגת כל הדורשות טיפול בלוח
              <ChevronLeft aria-hidden="true" className="size-icon-sm" />
            </Button>
          </div>
        )}
      </details>
    </section>
  );
};
