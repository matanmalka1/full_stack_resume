import type { ApplicationListItem } from "../../api/contracts";
import { cx } from "../../ui/cx";
import { ApplicationIdentity, ApplicationNextAction, ApplicationPreparationBadge } from "./ApplicationListParts";
import { ApplicationFitStatus, ApplicationRecruitmentStatus } from "./ApplicationListStatuses";
import { closedStage, recruitmentStages } from "./recruitmentStages";

interface ApplicationPipelineViewProps {
  items: readonly ApplicationListItem[];
  onRequestUpdate: (item: ApplicationListItem) => void;
}

interface PipelineColumn {
  id: string;
  title: string;
  statuses: readonly string[];
  tone: "neutral" | "accent" | "warning" | "success";
}

/* Same stage grouping the filter bar uses, plus the closed applications the bar never
   shows a column for - the board covers the active stages and where work ends up. */
const pipelineColumns: readonly PipelineColumn[] = [
  ...recruitmentStages.map((stage) => ({
    id: stage.id,
    title: stage.label,
    statuses: stage.statuses,
    tone: stage.tone,
  })),
  { id: closedStage.id, title: closedStage.label, statuses: closedStage.statuses, tone: closedStage.tone },
];

const pipelineToneClasses: Record<PipelineColumn["tone"], string> = {
  neutral: "border-cv-border bg-cv-surface-muted",
  accent: "border-cv-accent/30 bg-cv-accent-soft/40",
  warning: "border-cv-warning/30 bg-cv-warning-soft/40",
  success: "border-cv-success/30 bg-cv-success-soft/40",
};

const PipelineCard = ({
  item,
  onRequestUpdate,
}: {
  item: ApplicationListItem;
  onRequestUpdate: (item: ApplicationListItem) => void;
}) => (
  <article className="group flex flex-col gap-2.5 rounded-control border border-cv-border bg-cv-surface p-3 shadow-surface transition-all hover:border-cv-border-strong hover:shadow-floating">
    <div>
      <ApplicationIdentity
        afterCompany={<ApplicationFitStatus item={item} variant="pipeline" />}
        item={item}
        variant="pipeline"
      />
      <ApplicationPreparationBadge item={item} variant="pipeline" />
      <ApplicationNextAction item={item} variant="pipeline" />
    </div>
    <div className="flex items-center justify-between gap-2 border-t border-cv-border pt-2 text-support">
      <button
        className="font-semibold text-cv-text-muted hover:text-cv-text hover:underline"
        onClick={() => onRequestUpdate(item)}
        type="button"
      >
        פרטים ומשימה
      </button>
      <ApplicationRecruitmentStatus item={item} variant="pipeline" />
    </div>
  </article>
);

export const ApplicationPipelineView = ({ items, onRequestUpdate }: ApplicationPipelineViewProps) => {
  const knownStatuses = new Set(pipelineColumns.flatMap((column) => column.statuses));
  const unknownStatuses = [...new Set(items.map((item) => item.recruitment_status))].filter(
    (status) => !knownStatuses.has(status),
  );
  const populatedOrActiveColumns = pipelineColumns.filter(
    (column) => column.id !== "closed" || items.some((item) => column.statuses.includes(item.recruitment_status)),
  );
  const columns: readonly PipelineColumn[] =
    unknownStatuses.length === 0
      ? populatedOrActiveColumns
      : [...populatedOrActiveColumns, { id: "other", title: "שלב אחר", statuses: unknownStatuses, tone: "neutral" }];

  return (
    <div
      aria-label="מועמדויות לפי שלב גיוס"
      className="grid grid-cols-1 items-start gap-4 md:grid-cols-2 xl:grid-cols-4"
      role="list"
    >
      {columns.map((column) => {
        const stageItems = items.filter((item) => column.statuses.includes(item.recruitment_status));

        return (
          <section
            className={cx(
              "flex min-h-96 flex-col rounded-surface border p-3 shadow-surface",
              pipelineToneClasses[column.tone],
            )}
            key={column.id}
            role="listitem"
          >
            <div className="mb-2 flex items-center justify-between gap-3 border-b border-cv-border px-1 pb-2.5">
              <h2 className="text-support font-extrabold text-cv-text">{column.title}</h2>
              <span className="rounded-pill border border-cv-border bg-cv-surface px-2 py-0.5 text-support font-bold text-cv-text">
                {stageItems.length}
              </span>
            </div>
            {stageItems.length === 0 ? (
              <div className="flex h-28 items-center justify-center rounded-control border border-dashed border-cv-border bg-cv-surface/40 px-3 text-center text-support text-cv-text-muted">
                אין מועמדויות בשלב זה
              </div>
            ) : (
              <div className="flex flex-col gap-3">
                {stageItems.map((item) => (
                  <PipelineCard item={item} key={item.id} onRequestUpdate={onRequestUpdate} />
                ))}
              </div>
            )}
          </section>
        );
      })}
    </div>
  );
};
