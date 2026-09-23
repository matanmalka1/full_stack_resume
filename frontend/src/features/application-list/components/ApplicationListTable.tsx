import type { ApplicationListItem } from "@/api/contracts";
import { Card } from "@/ui/Card";
import { Skeleton } from "@/ui/Skeleton";
import { cx } from "@/ui/cx";
import { duplicatedApplicationIdentityIds } from "../model/applicationListPresentation";
import { ApplicationListRow } from "./ApplicationListRow";

/* Six columns, laid out after demo_re: who, how far, what next, how well it fits, when
   it last moved, and the menu. Preparation and recruitment share the progress column
   but stay two separate lines - one says what the CV still needs, the other where the
   employer process stands - so neither reads as a step of the other. The final column
   gathers commands so the row has one predictable action edge. */
const columns = [
  { key: "identity", label: "חברה ותפקיד", width: "w-[24%]" },
  { key: "progress", label: "התקדמות הכנה וגיוס", width: "w-[22%]" },
  { key: "next-action", label: "פעולה מומלצת הבאה", width: "w-[30%]" },
  { key: "fit", label: "ציון התאמה", width: "w-[9%]", center: true },
  { key: "activity", label: "עדכון אחרון", width: "w-[11%]" },
  /* The column holds one icon-sized menu trigger. Its name stays for assistive tech but is
     not drawn: at the trigger's width a visible label was clipped by the table edge. */
  { key: "actions", label: "פעולות", width: "w-12", visuallyHidden: true },
] as const;

interface ApplicationListTableProps {
  clearingApplicationId: string | null;
  items: readonly ApplicationListItem[];
  onClearNextAction: (item: ApplicationListItem) => void;
  onRequestClose: (item: ApplicationListItem) => void;
  onRequestDelete: (item: ApplicationListItem) => void;
  onRequestUpdate: (item: ApplicationListItem) => void;
}

export const ApplicationListTable = ({
  clearingApplicationId,
  items,
  onClearNextAction,
  onRequestClose,
  onRequestDelete,
  onRequestUpdate,
}: ApplicationListTableProps) => {
  const ambiguous = duplicatedApplicationIdentityIds(items);

  return (
    /* One semantic table becomes stacked rows below the tablet breakpoint. Keeping one
       tree avoids duplicating controls and status announcements for assistive tech. */
    /* Rounded and lifted like demo_re's table rather than the flat default Card. The
       card cannot clip its corners - the row menus open over its edge - so the header
       rounds its own two corner cells instead, and its light fill stays inside. */
    <Card className="overflow-visible rounded-surface bg-cv-surface-raised shadow-surface">
      <table className="block w-full border-collapse text-start lg:table lg:table-fixed">
        <thead className="hidden lg:table-header-group">
          <tr className="border-b border-cv-border">
            {columns.map(({ key, label, width, ...column }) => (
              <th
                className={cx(
                  "bg-cv-canvas px-4 py-3 text-support font-semibold text-cv-text-muted first:rounded-ss-surface last:rounded-se-surface",
                  "center" in column ? "text-center" : "text-start",
                  width,
                )}
                key={key}
                scope="col"
              >
                {"visuallyHidden" in column ? <span className="sr-only">{label}</span> : label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="block divide-y divide-cv-border lg:table-row-group lg:divide-y-0">
          {items.map((item) => (
            <ApplicationListRow
              ambiguous={ambiguous.has(item.id)}
              clearing={clearingApplicationId === item.id}
              item={item}
              key={item.id}
              onClearNextAction={onClearNextAction}
              onRequestClose={onRequestClose}
              onRequestDelete={onRequestDelete}
              onRequestUpdate={onRequestUpdate}
            />
          ))}
        </tbody>
      </table>
    </Card>
  );
};

const skeletonRows = ["skeleton-1", "skeleton-2", "skeleton-3", "skeleton-4"];

export const ApplicationListTableSkeleton = () => (
  // role="status" is a Card prop, not a DOM role; Card already renders an <output> for it.
  // oxlint-disable-next-line jsx-a11y/prefer-tag-over-role
  <Card
    aria-label="טוען את המועמדויות"
    className="overflow-hidden rounded-surface bg-cv-surface-raised shadow-surface"
    role="status"
  >
    <div className="hidden h-11 border-b border-cv-border bg-cv-canvas lg:block" />
    {/* Drawn with the `Skeleton` primitive rather than by hand. The hand-rolled version
        pulsed - `animate-pulse` on the whole row - while every other waiting region in
        the product sweeps, so the one screen a reader opens first was also the one that
        waited differently. It also missed what the primitive carries: the
        `forced-colors` rule is keyed to `.cv-skeleton`, so in Windows high contrast these
        bars had their background replaced by the system and vanished, leaving a blank
        pulsing card. Radius comes from the primitive; a `rounded-pill` passed here would
        collide with its own `rounded-surface` and `cx` resolves no conflicts. */}
    <div className="divide-y divide-cv-border">
      {skeletonRows.map((key) => (
        <div
          className="grid min-h-32 grid-cols-[minmax(0,1fr)_auto] gap-4 p-4 lg:grid-cols-[24%_22%_30%_9%_11%_3rem] lg:items-start lg:py-3"
          key={key}
        >
          <div className="flex gap-2">
            <Skeleton className="block size-9 shrink-0" />
            <span className="flex-1 space-y-2">
              <Skeleton className="block h-4 w-4/5" />
              <Skeleton className="block h-3 w-3/5" />
            </span>
          </div>
          <Skeleton className="block size-9 lg:order-last" />
          <Skeleton className="col-span-2 block h-7 w-36 lg:col-span-1" />
          <Skeleton className="col-span-2 block h-4 w-2/3 lg:col-span-1" />
          <Skeleton className="col-span-2 block h-4 w-20 lg:col-span-1" />
          <Skeleton className="hidden h-4 w-16 lg:block" />
        </div>
      ))}
    </div>
  </Card>
);
