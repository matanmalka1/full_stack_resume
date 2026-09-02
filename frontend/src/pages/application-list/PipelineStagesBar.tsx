import { Award, Bookmark, PhoneCall, Send, Users } from "lucide-react";

import type { RecruitmentStatus } from "../../api/contracts";
import { Card } from "../../ui/Card";
import { cx } from "../../ui/cx";

export const pipelineStages = [
  { id: "saved", label: "נשמר", statuses: ["saved"], icon: Bookmark, tone: "neutral" },
  { id: "applied", label: "הוגש", statuses: ["applied"], icon: Send, tone: "accent" },
  {
    id: "screening",
    label: "סינון טלפוני",
    statuses: ["recruiter_screen"],
    icon: PhoneCall,
    tone: "warning",
  },
  {
    id: "interviews",
    label: "ראיונות ומטלות",
    statuses: ["interview", "assignment"],
    icon: Users,
    tone: "success",
  },
  {
    id: "offer",
    label: "שלב סופי והצעה",
    statuses: ["final_stage", "offer", "accepted"],
    icon: Award,
    tone: "success",
  },
] as const satisfies readonly {
  id: string;
  label: string;
  statuses: readonly RecruitmentStatus[];
  icon: typeof Bookmark;
  tone: "neutral" | "accent" | "warning" | "success";
}[];

export type PipelineStageId = (typeof pipelineStages)[number]["id"];

const toneClasses: Record<(typeof pipelineStages)[number]["tone"], { active: string; count: string; icon: string }> = {
  neutral: {
    active: "border-cv-border-strong ring-cv-border/40",
    count: "bg-cv-surface-sunken text-cv-text-muted",
    icon: "bg-cv-surface-sunken text-cv-text-muted",
  },
  accent: {
    active: "border-cv-accent ring-cv-accent/20",
    count: "bg-cv-accent-soft text-cv-accent",
    icon: "bg-cv-accent-soft text-cv-accent",
  },
  warning: {
    active: "border-cv-warning ring-cv-warning/20",
    count: "bg-cv-warning-soft text-cv-warning",
    icon: "bg-cv-warning-soft text-cv-warning",
  },
  success: {
    active: "border-cv-success ring-cv-success/20",
    count: "bg-cv-success-soft text-cv-success",
    icon: "bg-cv-success-soft text-cv-success",
  },
};

export const selectedPipelineStage = (statuses: readonly RecruitmentStatus[] | undefined): PipelineStageId | null => {
  if (statuses == null || statuses.length === 0) {
    return null;
  }

  return (
    pipelineStages.find((stage) =>
      statuses.every((status) => (stage.statuses as readonly RecruitmentStatus[]).includes(status)),
    )?.id ?? null
  );
};

interface PipelineStagesBarProps {
  counts: Partial<Record<PipelineStageId, number | undefined>>;
  filterActive: boolean;
  onSelectStage: (stage: PipelineStageId | null) => void;
  selectedStage: PipelineStageId | null;
}

export const PipelineStagesBar = ({ counts, filterActive, onSelectStage, selectedStage }: PipelineStagesBarProps) => (
  <Card className="bg-cv-surface p-3.5 shadow-surface">
    <div className="mb-2 flex items-center justify-between gap-3 px-1">
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-support text-cv-text">
        <h2 className="font-bold">משפך שלבי הגיוס</h2>
        <span className="text-cv-text-muted">לחיצה על שלב מסננת את הרשימה</span>
      </div>
      {filterActive ? (
        <button
          className="text-support font-bold text-cv-accent hover:underline"
          onClick={() => onSelectStage(null)}
          type="button"
        >
          איפוס סינון שלב
        </button>
      ) : null}
    </div>

    <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-5">
      {pipelineStages.map((stage) => {
        const active = selectedStage === stage.id;
        const colors = toneClasses[stage.tone];
        const Icon = stage.icon;

        return (
          <button
            aria-pressed={active}
            className={cx(
              "flex items-center justify-between gap-2 rounded-control border p-2.5 text-right transition-all hover:border-cv-border-strong hover:bg-cv-surface",
              active ? cx("bg-cv-surface font-bold ring-2", colors.active) : "border-cv-border bg-cv-canvas/50",
            )}
            key={stage.id}
            onClick={() => onSelectStage(active ? null : stage.id)}
            type="button"
          >
            <span className="flex min-w-0 items-center gap-2">
              <span className={cx("rounded-control p-1.5", colors.icon)}>
                <Icon aria-hidden="true" className="size-3.5" />
              </span>
              <span className="truncate text-support font-semibold text-cv-text">{stage.label}</span>
            </span>
            <span className={cx("rounded-pill px-2 py-0.5 text-support font-black", colors.count)}>
              {counts[stage.id] ?? "—"}
            </span>
          </button>
        );
      })}
    </div>
  </Card>
);
