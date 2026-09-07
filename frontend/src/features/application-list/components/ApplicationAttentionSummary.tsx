import { BellOff, ChevronLeft, Sparkles } from "lucide-react";
import { Link } from "react-router-dom";

import type { ApplicationListItem } from "@/api/contracts";
import { routePaths } from "@/app/routePaths";
import { Button } from "@/ui/Button";
import { StatusBadge } from "@/ui/StatusBadge";
import type { StatusTone } from "@/ui/status";
import {
  applicationAttention,
  formatApplicationDate,
  isDueToday,
  isNextActionOverdue,
} from "../model/applicationListPresentation";

type HubItemType = "attention" | "due_today" | "overdue" | "ready";

interface HubItem {
  actionLabel: string;
  actionTo: string | null;
  application: ApplicationListItem;
  label: string;
  subtitle: string;
  title: string;
  tone: StatusTone;
  type: HubItemType;
}

interface ApplicationAttentionSummaryProps {
  clearingApplicationId: string | null;
  items: readonly ApplicationListItem[];
  onClearNextAction: (application: ApplicationListItem) => void;
  onOpenStatusDialog: (application: ApplicationListItem) => void;
}

/* This is a priority summary of the current server-projected page, not a second list
   filter. Attention comes from the projection's reason collections, Ready comes from
   its active ready revision, and the date comparison is only a local presentation of a
   stored reminder. One card per Application prevents a single row from occupying the
   entire hub when it happens to satisfy several conditions. */
const hubItems = (items: readonly ApplicationListItem[], today: Date = new Date()): HubItem[] => {
  const due: HubItem[] = [];
  const attention: HubItem[] = [];
  const ready: HubItem[] = [];

  for (const application of items) {
    if (application.is_closed) {
      continue;
    }

    const applicationHref = routePaths.application(application.id);
    if (
      application.next_action != null &&
      application.next_action_date != null &&
      (isNextActionOverdue(application.next_action_date, today) || isDueToday(application.next_action_date, today))
    ) {
      const overdue = isNextActionOverdue(application.next_action_date, today);
      due.push({
        actionLabel: overdue ? "עדכון סטטוס ומשימה" : "פתיחת המועמדות",
        actionTo: overdue ? null : applicationHref,
        application,
        label: overdue ? "באיחור" : "להיום",
        subtitle: `${formatApplicationDate(application.next_action_date)} · ${application.target_role}`,
        title: application.next_action,
        tone: overdue ? "blocker" : "progress",
        type: overdue ? "overdue" : "due_today",
      });
      continue;
    }

    const projectedAttention = applicationAttention(application);
    if (projectedAttention != null) {
      attention.push({
        actionLabel: "פתיחת מסך ההכנה",
        actionTo: routePaths.preparation(application.id),
        application,
        label: "דורש טיפול",
        subtitle: application.target_role,
        title: projectedAttention.label,
        tone: projectedAttention.tone,
        type: "attention",
      });
      continue;
    }

    if (application.latest_ready_revision_id != null) {
      ready.push({
        actionLabel: "פתיחת הגרסה המוכנה",
        actionTo: routePaths.revision(application.latest_ready_revision_id),
        application,
        label: "מוכן לשליחה",
        subtitle: application.target_role,
        title: "קורות החיים מוכנים להורדה ולהגשה",
        tone: "success",
        type: "ready",
      });
    }
  }

  due.sort((left, right) =>
    (left.application.next_action_date ?? "").localeCompare(right.application.next_action_date ?? ""),
  );
  return [...due, ...attention, ...ready].slice(0, 3);
};

export const ApplicationAttentionSummary = ({
  clearingApplicationId,
  items,
  onClearNextAction,
  onOpenStatusDialog,
}: ApplicationAttentionSummaryProps) => {
  const displayItems = hubItems(items);

  if (displayItems.length === 0) {
    return null;
  }

  return (
    <section
      aria-labelledby="urgent-action-heading"
      className="rounded-surface border border-cv-warning/30 bg-gradient-to-l from-cv-warning-soft/70 via-cv-surface to-cv-accent-soft/40 p-2.5 shadow-surface sm:p-3"
    >
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2 border-b border-cv-warning/25 pb-1.5">
        <div className="flex items-center gap-1.5">
          <span className="flex size-6 shrink-0 items-center justify-center rounded-control bg-cv-warning text-cv-on-accent">
            <Sparkles aria-hidden="true" className="size-3" />
          </span>
          <div>
            <h2 className="font-extrabold text-cv-text" id="urgent-action-heading">
              מוקד פעולות
            </h2>
            <p className="text-support text-cv-text-muted">
              {displayItems.length} פעולות בעדיפות מתוך המועמדויות המוצגות
            </p>
          </div>
        </div>
        <StatusBadge className="px-2 py-0.5" tone="warning">
          לטיפול קרוב
        </StatusBadge>
      </div>

      <div className="grid gap-2 md:grid-cols-3">
        {displayItems.map((item) => (
          <article
            className="flex min-h-32 flex-col justify-between rounded-control border border-cv-border bg-cv-surface p-2.5 shadow-surface transition-colors hover:border-cv-border-strong"
            key={`${item.application.id}-${item.type}`}
          >
            <div>
              <div className="mb-1 flex items-start justify-between gap-2">
                <StatusBadge className="px-2 py-0.5" tone={item.tone}>
                  {item.label}
                </StatusBadge>
                <span className="truncate text-support font-semibold text-cv-text-muted" dir="auto">
                  {item.application.company}
                </span>
              </div>
              <h3 className="line-clamp-1 text-support font-bold text-cv-text" dir="auto">
                {item.title}
              </h3>
              <p className="mt-0.5 line-clamp-1 text-support leading-5 text-cv-text-muted" dir="auto">
                {item.subtitle}
              </p>
            </div>

            <div className="mt-1.5 flex flex-wrap items-center justify-between gap-1.5 border-t border-cv-border pt-1.5">
              {item.type === "overdue" || item.type === "due_today" ? (
                <Button
                  className="min-h-8 px-1.5 text-cv-text-muted hover:text-cv-success"
                  disabled={clearingApplicationId !== null}
                  onClick={() => onClearNextAction(item.application)}
                  pending={clearingApplicationId === item.application.id}
                  pendingLabel="מסיר…"
                  title="הסרת התזכורת, ללא רישום השלמה"
                  variant="ghost"
                >
                  <BellOff aria-hidden="true" className="size-3.5" />
                  הסרת תזכורת
                </Button>
              ) : (
                <span />
              )}

              {item.actionTo == null ? (
                <Button
                  className="min-h-8 gap-1 px-2.5"
                  onClick={() => onOpenStatusDialog(item.application)}
                  variant="secondary"
                >
                  {item.actionLabel}
                  <ChevronLeft aria-hidden="true" className="size-3.5" />
                </Button>
              ) : (
                <Link
                  className="inline-flex min-h-8 items-center gap-1 rounded-control bg-cv-accent-soft px-2.5 text-support font-semibold text-cv-accent transition-colors hover:bg-cv-accent hover:text-cv-on-accent"
                  to={item.actionTo}
                >
                  {item.actionLabel}
                  <ChevronLeft aria-hidden="true" className="size-3.5" />
                </Link>
              )}
            </div>
          </article>
        ))}
      </div>
    </section>
  );
};
