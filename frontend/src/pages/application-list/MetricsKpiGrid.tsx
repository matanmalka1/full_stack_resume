import { AlertTriangle, ArrowUpLeft, Briefcase, CheckCircle2, FileCheck2 } from "lucide-react";

import type { ApplicationPreset } from "../../api/contracts";
import { cx } from "../../ui/cx";

type MetricSelection = ApplicationPreset | "all";

interface MetricsKpiGridProps {
  activeInterviewsCount: number | undefined;
  activePreset: MetricSelection;
  needsAttentionCount: number | undefined;
  onSelectPreset: (preset: MetricSelection) => void;
  readyCount: number | undefined;
  totalCount: number | undefined;
}

interface MetricCardProps {
  active: boolean;
  count: number | undefined;
  description: string;
  icon: typeof Briefcase;
  label: string;
  onSelect: () => void;
  tone: "accent" | "success" | "warning";
}

const toneClasses: Record<MetricCardProps["tone"], { active: string; count: string; icon: string; indicator: string }> =
  {
    accent: {
      active: "border-cv-accent ring-cv-accent/20",
      count: "text-cv-accent",
      icon: "bg-cv-accent-soft text-cv-accent",
      indicator: "bg-cv-accent",
    },
    success: {
      active: "border-cv-success ring-cv-success/20",
      count: "text-cv-success",
      icon: "bg-cv-success-soft text-cv-success",
      indicator: "bg-cv-success",
    },
    warning: {
      active: "border-cv-warning ring-cv-warning/20",
      count: "text-cv-warning",
      icon: "bg-cv-warning-soft text-cv-warning",
      indicator: "bg-cv-warning",
    },
  };

const MetricCard = ({ active, count, description, icon: Icon, label, onSelect, tone }: MetricCardProps) => {
  const colors = toneClasses[tone];

  return (
    <button
      aria-pressed={active}
      className={cx(
        "group relative rounded-surface border bg-cv-surface p-4 text-right shadow-surface transition-all hover:border-cv-border-strong hover:shadow-floating",
        active ? cx(colors.active, "ring-2") : "border-cv-border",
      )}
      onClick={onSelect}
      type="button"
    >
      <span className="mb-2 flex items-center justify-between gap-3 text-support font-semibold text-cv-text-muted">
        <span>{label}</span>
        <span className={cx("rounded-control p-1.5 transition-transform group-hover:scale-105", colors.icon)}>
          <Icon aria-hidden="true" className="size-4" />
        </span>
      </span>
      <span className="flex items-baseline justify-between gap-3">
        <span className={cx("text-heading-lg font-black", colors.count)}>{count ?? "—"}</span>
        <span className="inline-flex items-center gap-1 text-support font-semibold text-cv-accent">
          הצגה
          <ArrowUpLeft aria-hidden="true" className="size-3.5" />
        </span>
      </span>
      <span className="mt-1.5 block text-support text-cv-text-muted">{description}</span>
      <span
        aria-hidden="true"
        className={cx(
          "absolute inset-x-4 bottom-0 h-0.5 rounded-pill transition-colors",
          active ? colors.indicator : "bg-transparent group-hover:bg-cv-border",
        )}
      />
    </button>
  );
};

export const MetricsKpiGrid = ({
  activeInterviewsCount,
  activePreset,
  needsAttentionCount,
  onSelectPreset,
  readyCount,
  totalCount,
}: MetricsKpiGridProps) => (
  <div className="grid grid-cols-1 gap-3.5 sm:grid-cols-2 lg:grid-cols-4" aria-label="מדדי מועמדויות">
    <MetricCard
      active={activePreset === "all"}
      count={totalCount}
      description="כל המועמדויות במסגרת המסננים שנבחרו"
      icon={Briefcase}
      label="סך מועמדויות"
      onSelect={() => onSelectPreset("all")}
      tone="accent"
    />
    <MetricCard
      active={activePreset === "active_interviews"}
      count={activeInterviewsCount}
      description="שיחות מגייס, מטלות, ראיונות והצעות פעילות"
      icon={CheckCircle2}
      label="ראיונות פעילים"
      onSelect={() => onSelectPreset("active_interviews")}
      tone="success"
    />
    <MetricCard
      active={activePreset === "ready_to_send"}
      count={readyCount}
      description="גרסאות קורות חיים שמוכנות לשליחה"
      icon={FileCheck2}
      label="מסמכים מוכנים לשליחה"
      onSelect={() => onSelectPreset("ready_to_send")}
      tone="accent"
    />
    <MetricCard
      active={activePreset === "needs_attention"}
      count={needsAttentionCount}
      description="מועמדויות שממתינות להחלטה או פעולה"
      icon={AlertTriangle}
      label="דורש טיפול"
      onSelect={() => onSelectPreset("needs_attention")}
      tone="warning"
    />
  </div>
);
