import type { ApplicationListItem } from "@/api/contracts";
import { preparationStateLabels } from "@/features/preparation";
import { StatusBadge } from "@/ui/StatusBadge";
import { cx } from "@/ui/cx";
import { applicationAttention } from "../model/applicationListPresentation";
import { type RecruitmentStage, recruitmentStages } from "../model/recruitmentStages";

interface ApplicationPipelineViewProps {
  items: readonly ApplicationListItem[];
  /* The server's count per recruitment status across the open board. The board draws it
     whole, so this agrees with the column; it is read anyway so a column can never claim
     fewer than the server holds. */
  recruitmentStatusCounts: Readonly<Record<string, number>>;
  onRequestDetails: (item: ApplicationListItem) => void;
  returnedId: string | null;
}

/* One Application in its stage: the role, the employer, and where its CV stands, with a
   "needs attention" chip beside the role when the projection holds a reason. The whole card
   is one button that opens the Application's details sheet, where the way into the work
   is. */
const PipelineCard = ({
  item,
  onRequestDetails,
  returned,
}: {
  item: ApplicationListItem;
  onRequestDetails: (item: ApplicationListItem) => void;
  returned: boolean;
}) => {
  const attention = applicationAttention(item);

  return (
    <li>
      <button
        className={cx(
          "flex w-full flex-col items-stretch gap-2 rounded-control-lg border border-cv-hairline bg-cv-surface px-3.5 py-3 text-start text-cv-text shadow-surface transition-colors hover:border-cv-border-strong lg:gap-1.5 lg:rounded-control lg:border-transparent lg:p-3",
          returned && "cv-returned",
        )}
        data-application-id={item.id}
        onClick={() => onRequestDetails(item)}
        type="button"
      >
        <span className="flex items-start justify-between gap-2">
          <span className="min-w-0 text-body font-bold lg:text-label">
            <bdi>{item.target_role}</bdi>
          </span>
          {attention === null ? null : (
            <StatusBadge icon={false} className="px-2 py-0.5" tone="progress" variant="solid">
              <span title={attention.label}>דורש טיפול</span>
            </StatusBadge>
          )}
        </span>
        <span className="text-support text-cv-text-muted lg:text-caption">
          <bdi>{item.company}</bdi>
        </span>
        <span className="text-caption text-cv-text-muted">
          הכנת קו״ח: {preparationStateLabels[item.preparation_state]}
        </span>
      </button>
    </li>
  );
};

/* The open board by recruitment stage, one column per stage in the order a process moves.

   From the large breakpoint the columns are grey lanes side by side, each holding white
   cards; five of them fit a laptop's content width and a narrower one scrolls them
   sideways. On a phone each lane is a heading over bare cards, most of the screen wide, in
   a strip that scrolls sideways and snaps lane by lane - the next lane peeks in at the edge
   to say there is more. An empty stage says so in a dashed frame rather than vanishing, so
   the five stages are always the same five places. */
export const ApplicationPipelineView = ({
  items,
  recruitmentStatusCounts,
  onRequestDetails,
  returnedId,
}: ApplicationPipelineViewProps) => {
  const columnTotal = (stage: RecruitmentStage, onPage: number): number =>
    Math.max(
      onPage,
      stage.statuses.reduce((sum, status) => sum + (recruitmentStatusCounts[status] ?? 0), 0),
    );

  return (
    <ul
      aria-label="שלבי הגיוס"
      className="m-0 flex list-none items-stretch gap-3 overflow-x-auto p-0 pb-2 max-lg:-mx-4 max-lg:snap-x max-lg:snap-mandatory max-lg:scroll-px-4 max-lg:px-4 sm:max-lg:-mx-6 sm:max-lg:scroll-px-6 sm:max-lg:px-6 lg:grid lg:grid-cols-[repeat(5,minmax(13.75rem,1fr))] lg:gap-3.5"
    >
      {recruitmentStages.map((stage) => {
        const stageItems = items.filter((item) =>
          (stage.statuses as readonly string[]).includes(item.recruitment_status),
        );
        const total = columnTotal(stage, stageItems.length);
        const Icon = stage.icon;
        const headingId = `pipeline-stage-${stage.id}`;

        return (
          <li
            aria-labelledby={headingId}
            className="relative flex w-75 max-w-[80vw] shrink-0 snap-start flex-col gap-2.5 lg:min-h-130 lg:w-auto lg:max-w-none lg:rounded-surface lg:bg-cv-surface-muted lg:p-3"
            key={stage.id}
          >
            <h2
              className="flex items-center gap-2 text-body font-extrabold text-cv-text lg:px-1 lg:py-0.5 lg:text-label"
              id={headingId}
            >
              <span
                aria-hidden="true"
                className="flex size-7.5 shrink-0 items-center justify-center rounded-item border border-cv-border bg-cv-surface lg:hidden"
              >
                <Icon className="size-icon-md" />
              </span>
              <span className="min-w-0 flex-1">{stage.label}</span>
              <span className="text-support font-bold text-cv-text-muted tabular-nums">
                <span className="sr-only">, </span>
                {total}
              </span>
            </h2>
            {stageItems.length === 0 ? (
              <p className="rounded-control-lg border border-dashed border-cv-border-soft px-3.5 py-4.5 text-center text-support text-cv-text-muted lg:rounded-control lg:border-cv-border-strong">
                אין מועמדויות בשלב הזה
              </p>
            ) : (
              <ul className="m-0 flex list-none flex-col gap-2.5 p-0">
                {stageItems.map((item) => (
                  <PipelineCard
                    item={item}
                    key={item.id}
                    onRequestDetails={onRequestDetails}
                    returned={returnedId === item.id}
                  />
                ))}
              </ul>
            )}
          </li>
        );
      })}
    </ul>
  );
};
