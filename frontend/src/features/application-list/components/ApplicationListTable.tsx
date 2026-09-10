import type { ApplicationListItem } from "@/api/contracts";
import { Card } from "@/ui/Card";
import { Skeleton } from "@/ui/Skeleton";
import { cx } from "@/ui/cx";
import { duplicatedApplicationIdentityIds } from "../model/applicationListPresentation";
import { ApplicationListRow } from "./ApplicationListRow";

/* Recruitment and preparation remain adjacent but independent: the former says where
   the employer process stands, the latter what the CV still needs. The final column
   gathers links and commands so the row has one predictable action edge. */
const columns = [
  { key: "identity", label: "משרה", width: "w-[25%]" },
  { key: "recruitment", label: "סטטוס", width: "w-[15%]" },
  { key: "preparation", label: "הכנת קורות חיים", width: "w-[22%]" },
  { key: "next-action", label: "המשך טיפול", width: "w-[24%]" },
  { key: "activity", label: "עודכן", width: "w-[10%]" },
  { key: "actions", label: "פעולות", width: "w-12" },
] as const;

interface ApplicationListTableProps {
  items: readonly ApplicationListItem[];
  onRequestClose: (item: ApplicationListItem) => void;
  onRequestUpdate: (item: ApplicationListItem) => void;
}

export const ApplicationListTable = ({ items, onRequestClose, onRequestUpdate }: ApplicationListTableProps) => {
  const ambiguous = duplicatedApplicationIdentityIds(items);

  return (
    /* One semantic table becomes stacked rows below the tablet breakpoint. Keeping one
       tree avoids duplicating controls and status announcements for assistive tech. */
    <Card className="overflow-visible bg-cv-surface-raised shadow-surface">
      <table className="block w-full border-collapse text-start lg:table lg:table-fixed">
        <thead className="hidden lg:table-header-group">
          <tr className="border-b border-cv-border bg-cv-surface-muted">
            {columns.map(({ key, label, width }) => (
              <th
                className={cx(
                  "px-2.5 py-2.5 text-start text-support font-semibold text-cv-text-muted first:ps-4 last:pe-4",
                  width,
                )}
                key={key}
                scope="col"
              >
                {label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="block divide-y divide-cv-border lg:table-row-group lg:divide-y-0">
          {items.map((item) => (
            <ApplicationListRow
              ambiguous={ambiguous.has(item.id)}
              item={item}
              key={item.id}
              onRequestClose={onRequestClose}
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
  <Card aria-label="טוען את המועמדויות" className="overflow-hidden bg-cv-surface-raised shadow-surface" role="status">
    <div className="hidden h-10 border-b border-cv-border bg-cv-surface-muted lg:block" />
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
          className="grid min-h-32 grid-cols-[minmax(0,1fr)_auto] gap-4 p-4 lg:grid-cols-[25%_15%_22%_24%_10%_3rem] lg:items-start lg:py-3"
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
          <Skeleton className="col-span-2 block h-4 w-24 lg:col-span-1" />
          <Skeleton className="col-span-2 block h-7 w-36 lg:col-span-1" />
          <Skeleton className="col-span-2 block h-4 w-2/3 lg:col-span-1" />
          <Skeleton className="hidden h-4 w-16 lg:block" />
        </div>
      ))}
    </div>
  </Card>
);
