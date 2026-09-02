import { Card } from "../../ui/Card";
import { cx } from "../../ui/cx";
import { type RecruitmentStageId, type RecruitmentStageTone, recruitmentStages } from "./recruitmentStages";

const toneClasses: Record<RecruitmentStageTone, { active: string; count: string; icon: string }> = {
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

interface PipelineStagesBarProps {
  counts: Partial<Record<RecruitmentStageId, number | undefined>>;
  filterActive: boolean;
  onSelectStage: (stage: RecruitmentStageId | null) => void;
  selectedStage: RecruitmentStageId | null;
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
      {recruitmentStages.map((stage) => {
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
