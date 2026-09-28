import type { ApplicationListItem } from "@/api/contracts";
import { fitLevelLabel } from "@/features/preparation";
import { Skeleton } from "@/ui/Skeleton";
import { Tooltip } from "@/ui/Tooltip";
import { surfaceClasses } from "@/ui/surface";
import { useOpenRecord } from "../hooks/useOpenRecord";
import {
  applicationAttention,
  duplicatedApplicationIdentityIds,
  formatApplicationDate,
  formatRelativeUpdate,
} from "../model/applicationListPresentation";
import { ApplicationRecordActions } from "./ApplicationListItemActions";
import { ApplicationIdentity } from "./ApplicationIdentity";
import { ApplicationProgress, fitScoreText } from "./ApplicationListStatuses";
import { ApplicationRowNextAction, nextActionHeading } from "./ApplicationRowNextAction";

const cardGridClasses = "grid gap-4 md:grid-cols-2 xl:grid-cols-3";

interface ApplicationCardsViewProps {
  clearingApplicationId: string | null;
  items: readonly ApplicationListItem[];
  onClearNextAction: (item: ApplicationListItem) => void;
  onRequestClose: (item: ApplicationListItem) => void;
  onRequestDelete: (item: ApplicationListItem) => void;
  onRequestDetails: (item: ApplicationListItem) => void;
  onRequestUpdate: (item: ApplicationListItem) => void;
}

/* The update time with both dates on the system tooltip. */
const UpdatedAt = ({ item }: { item: ApplicationListItem }) => (
  <Tooltip
    label={`עודכנה ב־${formatApplicationDate(item.updated_at)} · נפתחה ב־${formatApplicationDate(item.created_at)}`}
  >
    <time dateTime={item.updated_at}>{formatRelativeUpdate(item.updated_at)}</time>
  </Tooltip>
);

/* One Application as a card, laid out after demo_re: who and the menu, the progress
   block, what to do next, and a footer with when it last moved, how well it fits, and
   the way into its recruitment record. Every block is a shared component, so the cards,
   the details dialog and the action hub cannot drift apart in what they say. */
const ApplicationCard = ({
  ambiguous,
  clearing,
  item,
  onClearNextAction,
  onRequestClose,
  onRequestDelete,
  onRequestDetails,
  onRequestUpdate,
}: Omit<ApplicationCardsViewProps, "clearingApplicationId" | "items"> & {
  ambiguous: boolean;
  clearing: boolean;
  item: ApplicationListItem;
}) => {
  const open = useOpenRecord(() => onRequestDetails(item));
  const hasNext = nextActionHeading(item, applicationAttention(item) !== null) !== null;
  const score = fitScoreText(item);

  return (
    // The card opens its details on a click; its link icon and its menu stay the keyboard routes.
    // oxlint-disable-next-line jsx-a11y/click-events-have-key-events, jsx-a11y/no-noninteractive-element-interactions
    <article
      className={surfaceClasses(
        "group flex h-full min-w-0 cursor-pointer flex-col gap-4 bg-cv-surface-raised p-5 shadow-surface transition-all hover:border-cv-border-strong hover:shadow-floating",
      )}
      onClick={open.onClick}
    >
      <div className="flex items-start justify-between gap-3">
        <ApplicationIdentity ambiguous={ambiguous} item={item} variant="row" />
        <ApplicationRecordActions
          item={item}
          onRequestClose={onRequestClose}
          onRequestDelete={onRequestDelete}
          onRequestDetails={onRequestDetails}
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
  onRequestDetails,
  onRequestUpdate,
}: ApplicationCardsViewProps) => {
  /* Two Applications for the same company and role would otherwise read as one card
     drawn twice; each says there is another. */
  const ambiguous = duplicatedApplicationIdentityIds(items);

  /* Named, like the stages view's list, so the page's one grid of records is a region a
     reader can jump to rather than an anonymous run of articles after the action hub. */
  return (
    <section aria-label="כרטיסי מועמדויות" className={cardGridClasses}>
      {items.map((item) => (
        <ApplicationCard
          ambiguous={ambiguous.has(item.id)}
          clearing={clearingApplicationId === item.id}
          item={item}
          key={item.id}
          onClearNextAction={onClearNextAction}
          onRequestClose={onRequestClose}
          onRequestDelete={onRequestDelete}
          onRequestDetails={onRequestDetails}
          onRequestUpdate={onRequestUpdate}
        />
      ))}
    </section>
  );
};

const skeletonCards = ["skeleton-1", "skeleton-2", "skeleton-3", "skeleton-4", "skeleton-5", "skeleton-6"];

/* The first load reserves the card grid it will be replaced by, block for block: the
   identity and menu, the progress block, the next-action block, and the footer. Drawn
   with the `Skeleton` primitive so it sweeps like every other waiting region and keeps
   its `forced-colors` rule; radius comes from the primitive. */
export const ApplicationCardsSkeleton = () => (
  <output aria-label="טוען את המועמדויות" className={cardGridClasses}>
    {skeletonCards.map((key) => (
      <div className={surfaceClasses("flex min-h-72 flex-col gap-4 bg-cv-surface-raised p-5 shadow-surface")} key={key}>
        <div className="flex items-start justify-between gap-3">
          <span className="flex flex-1 gap-2">
            <Skeleton className="block size-9 shrink-0" />
            <span className="flex-1 space-y-2">
              <Skeleton className="block h-4 w-4/5" />
              <Skeleton className="block h-3 w-3/5" />
            </span>
          </span>
          <Skeleton className="block size-9 shrink-0" />
        </div>
        <Skeleton className="block h-16 w-full" />
        <Skeleton className="block h-14 w-full" />
        <div className="mt-auto flex items-center justify-between gap-3 border-t border-cv-border pt-3">
          <Skeleton className="block h-4 w-24" />
          <Skeleton className="block h-4 w-16" />
        </div>
      </div>
    ))}
  </output>
);
