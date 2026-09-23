import { Info, Pencil } from "lucide-react";
import { Link } from "react-router-dom";

import type { ApplicationListItem } from "@/api/contracts";
import { buttonClasses } from "@/ui/Button";
import { Tooltip } from "@/ui/Tooltip";
import { cx } from "@/ui/cx";
import { useOpenRecord } from "../hooks/useOpenRecord";
import { applicationAttention } from "../model/applicationListPresentation";
import { closedStage, recruitmentStages } from "../model/recruitmentStages";
import { ApplicationIdentity } from "./ApplicationIdentity";
import { ApplicationNextAction } from "./ApplicationNextAction";
import { AttentionLink, nextActionHeading } from "./ApplicationRowNextAction";

interface ApplicationPipelineViewProps {
  items: readonly ApplicationListItem[];
  /* The server's count per recruitment status across every page of the current query,
     ignoring only the recruitment-stage filter itself, and the statuses that filter
     selects (none: no filter). Together they give each column its whole size. */
  recruitmentStatusCounts: Readonly<Record<string, number>>;
  recruitmentStatusFilter: readonly string[] | undefined;
  onRequestDetails: (item: ApplicationListItem) => void;
  onRequestUpdate: (item: ApplicationListItem) => void;
}

interface PipelineColumn {
  id: string;
  title: string;
  statuses: readonly string[];
  tone: "neutral" | "accent" | "warning" | "success";
}

/* Same stage grouping the filter bar uses, plus the closed applications the bar never
   shows a column for - the board covers the active stages and where work ends up. The
   columns stay recruitment stages: the CV's own progress is a separate axis and is not
   mixed into this one. */
const pipelineColumns: readonly PipelineColumn[] = [
  ...recruitmentStages.map((stage) => ({
    id: stage.id,
    title: stage.label,
    statuses: stage.statuses,
    tone: stage.tone,
  })),
  { id: closedStage.id, title: closedStage.label, statuses: closedStage.statuses, tone: closedStage.tone },
];

/* demo_re marks each column by a coloured top edge on one neutral lane rather than
   tinting the whole lane; the edge carries the stage's tone. */
const pipelineEdgeClasses: Record<PipelineColumn["tone"], string> = {
  neutral: "border-t-cv-border-strong",
  accent: "border-t-cv-accent",
  warning: "border-t-cv-warning",
  success: "border-t-cv-success",
};

/* The stage columns sort by recruitment, so a card that needs the reader would
   otherwise look like its neighbours. A mark beside the company says so at a glance;
   the words ride with it for anyone who cannot see the mark, and the reasons are the
   system tooltip. */
const AttentionMark = ({ item }: { item: ApplicationListItem }) => {
  const attention = applicationAttention(item);
  if (attention === null) return null;

  return (
    <Tooltip className="mt-1.5 shrink-0" label={attention.label} wrap>
      <span
        aria-hidden="true"
        className={cx("size-2 rounded-pill", attention.tone === "blocker" ? "bg-cv-blocker" : "bg-cv-warning")}
      />
      <span className="sr-only">דורש טיפול</span>
    </Tooltip>
  );
};

/* One Application in its stage, after demo_re: who, what is waiting on it, and a
   footer whose main control is the step to take - or, with none, the way into its
   recruitment record - beside a pencil for the stage itself. */
const PipelineCard = ({
  item,
  onRequestDetails,
  onRequestUpdate,
}: {
  item: ApplicationListItem;
  onRequestDetails: (item: ApplicationListItem) => void;
  onRequestUpdate: (item: ApplicationListItem) => void;
}) => {
  const open = useOpenRecord(() => onRequestDetails(item));
  const attention = applicationAttention(item);
  const head = nextActionHeading(item, attention !== null);

  return (
    // The card opens its details on a click like the row does; its company link stays the keyboard route.
    // oxlint-disable-next-line jsx-a11y/click-events-have-key-events, jsx-a11y/no-noninteractive-element-interactions
    <article
      className="group flex cursor-pointer flex-col gap-2.5 rounded-control border border-cv-border bg-cv-surface p-3.5 shadow-surface transition-all hover:border-cv-border-strong"
      onClick={open.onClick}
    >
      <ApplicationIdentity afterCompany={<AttentionMark item={item} />} item={item} variant="pipeline" />

      {attention === null ? null : (
        <div
          className={cx(
            "rounded-control border px-2 py-1.5",
            attention.tone === "blocker"
              ? "border-cv-blocker/30 bg-cv-blocker-soft"
              : "border-cv-warning/30 bg-cv-warning-soft",
          )}
        >
          <AttentionLink attention={attention} className="leading-tight" item={item} />
        </div>
      )}

      <ApplicationNextAction item={item} />

      <div className="flex items-center justify-between gap-2 border-t border-cv-border pt-2">
        {head?.command == null ? (
          <button
            className="text-support font-medium text-cv-accent hover:underline"
            onClick={() => onRequestUpdate(item)}
            type="button"
          >
            עדכון סטטוס
          </button>
        ) : (
          <Link
            aria-label={`${head.title} · ${item.company}`}
            className={buttonClasses(
              head.command.strong ? "primary" : "secondary",
              "min-w-0 flex-1 truncate",
              "compact",
            )}
            to={head.command.to}
          >
            <span className="truncate">{head.title}</span>
          </Link>
        )}
        {/* The card body opens the details on a click; this is the same for the keyboard. */}
        <Tooltip label="פרטי משרה">
          <button
            aria-label={`פרטי המשרה של ${item.company}`}
            className="inline-flex size-8 shrink-0 items-center justify-center rounded-control text-cv-text-muted transition-colors hover:bg-cv-surface-muted hover:text-cv-text"
            onClick={() => onRequestDetails(item)}
            type="button"
          >
            <Info aria-hidden="true" className="size-icon-sm" />
          </button>
        </Tooltip>
        <Tooltip label="עדכון שלב הגיוס">
          <button
            aria-label={`עדכון שלב הגיוס של ${item.company}`}
            className="inline-flex size-8 shrink-0 items-center justify-center rounded-control text-cv-text-muted transition-colors hover:bg-cv-surface-muted hover:text-cv-text"
            onClick={() => onRequestUpdate(item)}
            type="button"
          >
            <Pencil aria-hidden="true" className="size-icon-sm" />
          </button>
        </Tooltip>
      </div>
    </article>
  );
};

export const ApplicationPipelineView = ({
  items,
  recruitmentStatusCounts,
  recruitmentStatusFilter,
  onRequestDetails,
  onRequestUpdate,
}: ApplicationPipelineViewProps) => {
  /* A column holds only this page's Applications, but the board is paged. Its size is
     therefore the server's count over every page - limited to the statuses the stage
     filter lets through, since the others cannot be on any page - and never less than
     what this page actually holds. */
  const columnTotal = (column: PipelineColumn, onPage: number): number =>
    Math.max(
      onPage,
      column.statuses
        .filter((status) => recruitmentStatusFilter === undefined || recruitmentStatusFilter.includes(status))
        .reduce((sum, status) => sum + (recruitmentStatusCounts[status] ?? 0), 0),
    );

  const knownStatuses = new Set(pipelineColumns.flatMap((column) => column.statuses));
  const unknownStatuses = [...new Set(items.map((item) => item.recruitment_status))].filter(
    (status) => !knownStatuses.has(status),
  );
  /* The closed column appears once there is anything closed on any page, not just this one. */
  const populatedOrActiveColumns = pipelineColumns.filter(
    (column) => column.id !== "closed" || columnTotal(column, 0) > 0,
  );
  const columns: readonly PipelineColumn[] =
    unknownStatuses.length === 0
      ? populatedOrActiveColumns
      : [...populatedOrActiveColumns, { id: "other", title: "שלב אחר", statuses: unknownStatuses, tone: "neutral" }];

  return (
    <ul aria-label="מועמדויות לפי שלב גיוס" className="flex items-start gap-3.5 overflow-x-auto pt-1 pb-4">
      {columns.map((column) => {
        const stageItems = items.filter((item) => column.statuses.includes(item.recruitment_status));
        const total = columnTotal(column, stageItems.length);

        return (
          <li
            className={cx(
              "flex max-h-[75vh] w-72 shrink-0 flex-col rounded-surface border border-t-[3px] border-cv-border bg-cv-surface-muted p-3",
              pipelineEdgeClasses[column.tone],
            )}
            key={column.id}
          >
            <div className="mb-3 flex items-center justify-between gap-3 px-1">
              <h2 className="text-support font-bold text-cv-text">{column.title}</h2>
              <span className="rounded-pill border border-cv-border bg-cv-surface px-2 py-0.5 text-support font-bold text-cv-text-muted tabular-nums shadow-surface">
                {total === stageItems.length ? stageItems.length : `${stageItems.length} מתוך ${total}`}
              </span>
            </div>
            <div className="flex flex-1 flex-col gap-2.5 overflow-y-auto">
              {stageItems.length === 0 ? (
                <p className="rounded-control border border-dashed border-cv-border py-8 text-center text-support text-cv-text-muted">
                  אין מועמדויות בשלב זה
                </p>
              ) : (
                stageItems.map((item) => (
                  <PipelineCard
                    item={item}
                    key={item.id}
                    onRequestDetails={onRequestDetails}
                    onRequestUpdate={onRequestUpdate}
                  />
                ))
              )}
            </div>
          </li>
        );
      })}
    </ul>
  );
};
