import type { ApplicationListItem } from "@/api/contracts";
import { Card } from "@/ui/Card";
import { cx } from "@/ui/cx";
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

/* A visual hint only: rows with the same company and role emphasize their dates so the
   reader can distinguish them. It does not represent domain duplicate detection. */
const duplicatedIdentities = (items: readonly ApplicationListItem[]): ReadonlySet<string> => {
  const byIdentity = new Map<string, string[]>();

  for (const item of items) {
    const key = `${item.company}\n${item.target_role}`;
    byIdentity.set(key, [...(byIdentity.get(key) ?? []), item.id]);
  }

  return new Set([...byIdentity.values()].filter((ids) => ids.length > 1).flat());
};

interface ApplicationListTableProps {
  items: readonly ApplicationListItem[];
  onRequestClose: (item: ApplicationListItem) => void;
  onRequestUpdate: (item: ApplicationListItem) => void;
}

export const ApplicationListTable = ({ items, onRequestClose, onRequestUpdate }: ApplicationListTableProps) => {
  const ambiguous = duplicatedIdentities(items);

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
  <Card aria-label="טוען את המועמדויות" className="overflow-hidden bg-cv-surface-raised shadow-surface" role="status">
    <div className="hidden h-10 border-b border-cv-border bg-cv-surface-muted lg:block" />
    <div className="divide-y divide-cv-border">
      {skeletonRows.map((key) => (
        <div
          className="grid min-h-32 animate-pulse grid-cols-[1fr_auto] gap-4 p-4 lg:grid-cols-[25%_15%_22%_24%_10%_3rem] lg:items-start lg:py-3"
          key={key}
        >
          <div className="flex gap-2">
            <span className="size-9 shrink-0 rounded-control bg-cv-surface-muted" />
            <span className="flex-1 space-y-2">
              <span className="block h-4 w-4/5 rounded-pill bg-cv-surface-muted" />
              <span className="block h-3 w-3/5 rounded-pill bg-cv-surface-muted" />
            </span>
          </div>
          <span className="size-9 rounded-control bg-cv-surface-muted lg:order-last" />
          <span className="col-span-2 h-4 w-24 rounded-pill bg-cv-surface-muted lg:col-span-1" />
          <span className="col-span-2 h-7 w-36 rounded-pill bg-cv-surface-muted lg:col-span-1" />
          <span className="col-span-2 h-4 w-2/3 rounded-pill bg-cv-surface-muted lg:col-span-1" />
          <span className="hidden h-4 w-16 rounded-pill bg-cv-surface-muted lg:block" />
        </div>
      ))}
    </div>
  </Card>
);
