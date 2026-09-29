import type { ApplicationListItem } from "@/api/contracts";
import { Skeleton } from "@/ui/Skeleton";
import { Tooltip } from "@/ui/Tooltip";
import { cx } from "@/ui/cx";
import { surfaceClasses } from "@/ui/surface";
import { useOpenRecord } from "../hooks/useOpenRecord";
import {
  applicationAttention,
  duplicatedApplicationIdentityIds,
  formatApplicationDate,
  formatRelativeUpdate,
  isNextActionOverdue,
} from "../model/applicationListPresentation";
import { ApplicationRecordActions } from "./ApplicationListItemActions";
import { ApplicationIdentity } from "./ApplicationIdentity";
import { ApplicationFitStatus, ApplicationProgress } from "./ApplicationListStatuses";
import { ApplicationCardNextAction, nextActionHeading } from "./ApplicationCardNextAction";

const cardGridClasses = "grid gap-4 md:grid-cols-2 xl:grid-cols-3";

interface ApplicationCardsViewProps {
  clearingApplicationId: string | null;
  items: readonly ApplicationListItem[];
  onClearNextAction: (item: ApplicationListItem) => void;
  onRequestClose: (item: ApplicationListItem) => void;
  onRequestDelete: (item: ApplicationListItem) => void;
  onRequestDetails: (item: ApplicationListItem) => void;
  onRequestUpdate: (item: ApplicationListItem) => void;
  /* The Application the reader just came back from: its card is ringed for a moment
     (styles.css, `cv-returned`) so the eye finds it, and nothing about its place changes. */
  returnedId: string | null;
}

/* The update time with both dates on the system tooltip. */
const UpdatedAt = ({ item }: { item: ApplicationListItem }) => (
  <Tooltip
    label={`עודכנה ב־${formatApplicationDate(item.updated_at)} · נפתחה ב־${formatApplicationDate(item.created_at)}`}
  >
    <time dateTime={item.updated_at}>{formatRelativeUpdate(item.updated_at)}</time>
  </Tooltip>
);

/* What a card's leading edge says before anything on it is read: a projected reason
   that blocks the work, or one that asks for it, or a reminder already past its date.
   The most severe wins. A closed Application asks for nothing. */
type CardUrgency = "blocker" | "warning";

const cardUrgency = (item: ApplicationListItem): CardUrgency | null => {
  if (item.is_closed) return null;
  const attention = applicationAttention(item);
  if (attention !== null) return attention.tone === "blocker" ? "blocker" : "warning";
  return isNextActionOverdue(item.next_action_date) && item.next_action != null ? "warning" : null;
};

const urgencyEdgeClasses: Record<CardUrgency, string> = {
  blocker: "border-s-4 border-s-cv-blocker",
  warning: "border-s-4 border-s-cv-warning",
};

/* One Application as a card, laid out after demo_re: who, how well it fits and the
   menu; the progress; what to do next; and a footer with when it last moved and the way
   into its recruitment record. The blocks are separated by space rather than each
   boxed, so a board of cards is not a grid of boxes inside boxes. Every block is a
   shared component, so the cards, the details dialog and the action hub cannot drift
   apart in what they say.

   The card itself takes focus and opens its details on Enter or Space, as a click on
   it does; its link icon stays the route straight to the work. */
const ApplicationCard = ({
  ambiguous,
  clearing,
  item,
  onClearNextAction,
  onRequestClose,
  onRequestDelete,
  onRequestDetails,
  onRequestUpdate,
  returned,
}: Omit<ApplicationCardsViewProps, "clearingApplicationId" | "items" | "returnedId"> & {
  ambiguous: boolean;
  clearing: boolean;
  item: ApplicationListItem;
  returned: boolean;
}) => {
  const open = useOpenRecord(() => onRequestDetails(item));
  const hasNext = nextActionHeading(item, applicationAttention(item) !== null) !== null;
  const urgency = cardUrgency(item);

  return (
    // oxlint-disable-next-line jsx-a11y/no-noninteractive-element-interactions
    <article
      aria-label={`${item.target_role} אצל ${item.company}`}
      className={surfaceClasses(
        cx(
          "group flex h-full min-w-0 cursor-pointer flex-col gap-4 p-5 transition-all hover:border-cv-border-strong focus-visible:border-cv-border-strong",
          /* A closed Application is history: it sits flat and quiet so the open work
             around it is what the eye lands on. Its text keeps full contrast. */
          item.is_closed
            ? "bg-cv-surface-muted"
            : "bg-cv-surface-raised shadow-surface hover:shadow-floating focus-visible:shadow-floating",
          urgency === null ? undefined : urgencyEdgeClasses[urgency],
          returned && "cv-returned",
        ),
      )}
      data-application-id={item.id}
      data-closed={item.is_closed ? true : undefined}
      data-urgency={urgency ?? undefined}
      onClick={open.onClick}
      onKeyDown={open.onKeyDown}
      /* Focusable so the keyboard opens the record the way a click does. It stays an
         article rather than a button: it holds links and buttons of its own. */
      // oxlint-disable-next-line jsx-a11y/no-noninteractive-tabindex
      tabIndex={0}
    >
      <div className="flex items-start justify-between gap-3">
        <ApplicationIdentity ambiguous={ambiguous} item={item} variant="card" />
        {/* Fit is read to decide whether to go on at all, so it sits beside who the
            Application is for rather than in the footer. Unanalysed, there is nothing
            to say yet and nothing is drawn. */}
        {item.fit_level == null ? null : (
          <span className="ms-auto shrink-0">
            <ApplicationFitStatus item={item} />
          </span>
        )}
        <ApplicationRecordActions
          item={item}
          onRequestClose={onRequestClose}
          onRequestDelete={onRequestDelete}
          onRequestDetails={onRequestDetails}
          onRequestUpdate={onRequestUpdate}
        />
      </div>

      <ApplicationProgress item={item} />

      {hasNext ? (
        <div>
          {/* Named for assistive tech only: drawn on every card it said nothing the
              action under it does not already say. */}
          <p className="sr-only">פעולה מומלצת הבאה</p>
          <ApplicationCardNextAction clearing={clearing} item={item} onClearNextAction={onClearNextAction} />
        </div>
      ) : (
        <p className="text-support text-cv-text-muted">אין פעולה מתוזמנת כעת</p>
      )}

      <div className="mt-auto flex items-center justify-between gap-3 border-t border-cv-border pt-3 text-support text-cv-text-muted">
        <UpdatedAt item={item} />
        <button
          className="shrink-0 font-semibold text-cv-accent hover:underline"
          onClick={() => onRequestUpdate(item)}
          type="button"
        >
          עדכון סטטוס ומשימות
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
  returnedId,
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
          returned={returnedId === item.id}
        />
      ))}
    </section>
  );
};

/* One row of the widest grid: enough to hold the layout, and a phone does not sweep
   through a column of placeholders that the first page may not fill. */
const skeletonCards = ["skeleton-1", "skeleton-2", "skeleton-3"];

/* The first load reserves the card grid it will be replaced by, block for block: the
   identity and menu, the progress block, the next-action block, and the footer. Drawn
   with the `Skeleton` primitive so it sweeps like every other waiting region and keeps
   its `forced-colors` rule; radius comes from the primitive. */
export const ApplicationCardsSkeleton = () => (
  <output aria-label="טוען את המועמדויות" className={cardGridClasses}>
    {skeletonCards.map((key) => (
      <div className={surfaceClasses("flex min-h-56 flex-col gap-4 bg-cv-surface-raised p-5 shadow-surface")} key={key}>
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
        <span className="space-y-2">
          <Skeleton className="block h-4 w-full" />
          <Skeleton className="block h-6 w-24" />
        </span>
        <span className="space-y-2">
          <Skeleton className="block h-3 w-32" />
          <Skeleton className="block h-4 w-3/4" />
        </span>
        <div className="mt-auto flex items-center justify-between gap-3 border-t border-cv-border pt-3">
          <Skeleton className="block h-4 w-24" />
          <Skeleton className="block h-4 w-16" />
        </div>
      </div>
    ))}
  </output>
);
