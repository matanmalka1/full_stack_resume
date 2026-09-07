import { BellOff, ChevronLeft, Sparkles } from "lucide-react";
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
