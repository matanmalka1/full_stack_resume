import { AlertTriangle, Briefcase, CheckCircle2, FileCheck2 } from "lucide-react";

import type { ApplicationPreset } from "@/api/contracts";
import { cx } from "@/ui/cx";

type MetricSelection = ApplicationPreset | "all";

interface ApplicationStatusSummaryProps {
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

const MetricCard = ({ active, count, icon: Icon, label, onSelect, tone }: MetricCardProps) => {
  const colors = toneClasses[tone];

  return (
    <button
      aria-pressed={active}
      className={cx(
        "group relative flex min-h-14 items-center gap-3 rounded-control border bg-cv-surface px-3 py-2 text-right transition-colors hover:border-cv-border-strong hover:bg-cv-surface-muted",
        active ? cx(colors.active, "ring-1") : "border-cv-border",
      )}
      onClick={onSelect}
      type="button"
    >
      <span className={cx("rounded-control p-1.5", colors.icon)}>
        <Icon aria-hidden="true" className="size-4" />
      </span>
      <span className="min-w-0 flex-1">
        <span className="block truncate text-support font-semibold text-cv-text-muted">{label}</span>
        <span className={cx("block text-heading-sm font-black", colors.count)}>{count ?? "—"}</span>
      </span>
      <span
        aria-hidden="true"
        className={cx(
          "absolute inset-x-3 bottom-0 h-0.5 rounded-pill transition-colors",
          active ? colors.indicator : "bg-transparent group-hover:bg-cv-border",
        )}
      />
    </button>
  );
};

export const ApplicationStatusSummary = ({
  activeInterviewsCount,
  activePreset,
  needsAttentionCount,
  onSelectPreset,
  readyCount,
  totalCount,
}: ApplicationStatusSummaryProps) => (
  <div aria-label="סינון מהיר לפי מצב" className="grid grid-cols-2 gap-2 lg:grid-cols-4" role="group">
    <MetricCard
      active={activePreset === "all"}
      count={totalCount}
      icon={Briefcase}
      label="סך מועמדויות"
      onSelect={() => onSelectPreset("all")}
      tone="accent"
    />
    <MetricCard
      active={activePreset === "active_interviews"}
      count={activeInterviewsCount}
      icon={CheckCircle2}
      label="ראיונות פעילים"
      onSelect={() => onSelectPreset("active_interviews")}
      tone="success"
    />
    <MetricCard
      active={activePreset === "ready_to_send"}
      count={readyCount}
      icon={FileCheck2}
      label="מסמכים מוכנים לשליחה"
      onSelect={() => onSelectPreset("ready_to_send")}
      tone="accent"
    />
    <MetricCard
      active={activePreset === "needs_attention"}
      count={needsAttentionCount}
      icon={AlertTriangle}
      label="דורש טיפול"
      onSelect={() => onSelectPreset("needs_attention")}
      tone="warning"
    />
  </div>
);
