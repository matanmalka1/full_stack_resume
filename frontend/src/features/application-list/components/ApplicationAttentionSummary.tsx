import { BellOff, ChevronDown, ChevronLeft, Sparkles } from "lucide-react";
import { Link } from "react-router-dom";

import type { ApplicationListItem } from "@/api/contracts";
import { Button } from "@/ui/Button";
import { StatusBadge } from "@/ui/StatusBadge";
import { attentionHubItems } from "../model/applicationListPresentation";

interface ApplicationAttentionSummaryProps {
  clearingApplicationId: string | null;
  items: readonly ApplicationListItem[];
  onClearNextAction: (application: ApplicationListItem) => void;
  onOpenStatusDialog: (application: ApplicationListItem) => void;
}

export const ApplicationAttentionSummary = ({
  clearingApplicationId,
  items,
  onClearNextAction,
  onOpenStatusDialog,
}: ApplicationAttentionSummaryProps) => {
  const displayItems = attentionHubItems(items);

  if (displayItems.length === 0) {
    return null;
  }

  return (
    <section aria-labelledby="urgent-action-heading" className="rounded-surface border border-cv-border bg-cv-surface">
      <details className="group/attention" open>
        <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-3 py-2.5 hover:bg-cv-surface-muted">
          <span className="flex min-w-0 items-baseline gap-2">
            <Sparkles aria-hidden="true" className="size-4 shrink-0 self-center text-cv-warning" />
            <h2 className="text-support font-bold text-cv-text" id="urgent-action-heading">
              מוקד פעולות
            </h2>
            <span className="truncate text-support text-cv-text-muted">
              {displayItems.length === 1 ? "פעולה אחת בעדיפות" : `${displayItems.length} פעולות בעדיפות`}
            </span>
          </span>
          <ChevronDown
            aria-hidden="true"
            className="size-4 shrink-0 text-cv-text-muted transition-transform group-open/attention:rotate-180"
          />
        </summary>

        {/* The first column is a fixed width rather than `auto`: each row is its own
            grid, so a badge-width column let every title start at a different x and the
            three rows read as unrelated blocks. */}
        <div className="divide-y divide-cv-border border-t border-cv-border">
          {displayItems.map((item) => (
            <article
              className="grid gap-x-3 gap-y-2 px-3 py-2.5 transition-colors hover:bg-cv-surface-muted sm:grid-cols-[9rem_minmax(0,1fr)_auto] sm:items-center"
              key={`${item.application.id}-${item.type}`}
            >
              <StatusBadge className="w-fit px-2 py-0.5 whitespace-nowrap" tone={item.tone}>
                {item.label}
              </StatusBadge>
              <div className="min-w-0">
                <h3 className="truncate text-support font-bold text-cv-text" dir="auto">
                  {item.title}
                </h3>
                <p className="truncate text-support text-cv-text-muted" dir="auto">
                  {item.application.company} · {item.subtitle}
                </p>
              </div>
              <div className="flex flex-wrap items-center gap-1.5 sm:justify-end">
                {item.type === "overdue" || item.type === "due_today" ? (
                  <Button
                    className="text-cv-text-muted hover:text-cv-success"
                    disabled={clearingApplicationId !== null}
                    onClick={() => onClearNextAction(item.application)}
                    pending={clearingApplicationId === item.application.id}
                    pendingLabel="מסיר…"
                    size="compact"
                    title="הסרת התזכורת, ללא רישום השלמה"
                    variant="ghost"
                  >
                    <BellOff aria-hidden="true" className="size-3.5" />
                    הסרת תזכורת
                  </Button>
                ) : null}

                {item.actionTo == null ? (
                  <Button
                    className="gap-1"
                    onClick={() => onOpenStatusDialog(item.application)}
                    size="compact"
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
      </details>
    </section>
  );
};
