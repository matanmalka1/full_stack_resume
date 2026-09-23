import type { ApplicationListItem } from "@/api/contracts";
import { fitLevelLabel, preparationResumeDestination } from "@/features/preparation";
import { Tooltip } from "@/ui/Tooltip";
import { surfaceClasses } from "@/ui/surface";
import { useOpenRecord } from "../hooks/useOpenRecord";
import { applicationAttention } from "../model/applicationListPresentation";
import { ApplicationRecordActions } from "./ApplicationListItemActions";
import { ApplicationIdentity } from "./ApplicationIdentity";
import { UpdatedAt } from "./ApplicationListRow";
import { ApplicationProgress, fitScoreText } from "./ApplicationListStatuses";
import { ApplicationRowNextAction, nextActionHeading } from "./ApplicationRowNextAction";

interface ApplicationCardsViewProps {
  clearingApplicationId: string | null;
  items: readonly ApplicationListItem[];
  onClearNextAction: (item: ApplicationListItem) => void;
  onRequestClose: (item: ApplicationListItem) => void;
  onRequestDelete: (item: ApplicationListItem) => void;
  onRequestUpdate: (item: ApplicationListItem) => void;
}

/* One Application as a card, laid out after demo_re: who and the menu, the progress
   block, what to do next, and a footer with when it last moved, how well it fits, and
   the way into its recruitment record. Every block is the table row's own component, so
   the two views cannot drift apart in what they say. */
const ApplicationCard = ({
  clearing,
  item,
  onClearNextAction,
  onRequestClose,
  onRequestDelete,
  onRequestUpdate,
}: Omit<ApplicationCardsViewProps, "clearingApplicationId" | "items"> & {
  clearing: boolean;
  item: ApplicationListItem;
}) => {
  const open = useOpenRecord(preparationResumeDestination(item));
  const hasNext = nextActionHeading(item, applicationAttention(item) !== null) !== null;
  const score = fitScoreText(item);

  return (
    // The card opens on a click like the row does; its link icon stays the keyboard route.
    // oxlint-disable-next-line jsx-a11y/click-events-have-key-events, jsx-a11y/no-noninteractive-element-interactions
    <article
      className={surfaceClasses(
        "group flex h-full min-w-0 cursor-pointer flex-col gap-4 bg-cv-surface-raised p-5 shadow-surface transition-all hover:border-cv-border-strong hover:shadow-floating",
      )}
      onClick={open.onClick}
    >
      <div className="flex items-start justify-between gap-3">
        <ApplicationIdentity item={item} variant="row" />
        <ApplicationRecordActions
          item={item}
          onRequestClose={onRequestClose}
          onRequestDelete={onRequestDelete}
          onRequestUpdate={onRequestUpdate}
        />
      </div>

      <div className="rounded-control border border-cv-border bg-cv-canvas p-3">
        <ApplicationProgress item={item} />
      </div>

      {hasNext ? (
        <div className="rounded-control border border-cv-border bg-cv-surface p-3">
          <p className="mb-1 text-support font-semibold text-cv-text-muted">פעולה מומלצת הבאה</p>
          <ApplicationRowNextAction clearing={clearing} item={item} onClearNextAction={onClearNextAction} />
        </div>
      ) : (
        <p className="rounded-control border border-dashed border-cv-border p-3 text-center text-support text-cv-text-muted">
          אין פעולה מתוזמנת כעת
        </p>
      )}

      <div className="mt-auto flex items-center justify-between gap-3 border-t border-cv-border pt-3 text-support text-cv-text-muted">
        <span className="flex min-w-0 items-center gap-2">
          <UpdatedAt item={item} />
          {item.fit_level == null ? null : (
            <>
              <span aria-hidden="true">·</span>
              <Tooltip align="center" label={fitLevelLabel(item.fit_level)}>
                <span className="font-semibold text-cv-text tabular-nums">
                  {score === null ? fitLevelLabel(item.fit_level) : `${score} התאמה`}
                </span>
              </Tooltip>
            </>
          )}
        </span>
        <button
          className="shrink-0 font-semibold text-cv-accent hover:underline"
          onClick={() => onRequestUpdate(item)}
          type="button"
        >
          ניהול גיוס
        </button>
      </div>
    </article>
  );
};

export const ApplicationCardsView = ({
  clearingApplicationId,
  items,
  onClearNextAction,
  onRequestClose,
  onRequestDelete,
  onRequestUpdate,
}: ApplicationCardsViewProps) => (
  <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
    {items.map((item) => (
      <ApplicationCard
        clearing={clearingApplicationId === item.id}
        item={item}
        key={item.id}
        onClearNextAction={onClearNextAction}
        onRequestClose={onRequestClose}
        onRequestDelete={onRequestDelete}
        onRequestUpdate={onRequestUpdate}
      />
    ))}
  </div>
);
