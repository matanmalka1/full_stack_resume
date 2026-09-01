import type { ApplicationListItem } from "../../api/contracts";
import { cx } from "../../ui/cx";
import { ApplicationListRow } from "./ApplicationListRow";

const ARCHIVE_COLUMN = "";

/* Widths sum to 100. The archive column is sized in rem rather than a percentage:
   it holds one icon button, and a percentage of a table this wide either starved it
   below its own padding or took space the text columns needed.

   The two date columns carry a fixed rem width instead of a percentage. A formatted
   date is the one cell whose content cannot grow, so giving it a share of the table
   only handed it space the wrapping text columns needed at narrow widths. */
const columns = [
  { label: "חברה ותפקיד", width: "w-[20%]" },
  { label: "נוצר", width: "w-24" },
  { label: "מצב קורות החיים", width: "w-[17%]" },
  { label: "שלב גיוס", width: "w-[12%]" },
  { label: "פעילות אחרונה", width: "w-28" },
  { label: "הפעולה הבאה", width: "w-[13%]" },
  { label: "דורש טיפול", width: "w-[15%]" },
  { label: "פעולה מומלצת", width: "w-[15%]" },
  { label: "", width: "w-16" },
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
}

export const ApplicationListTable = ({ items, onRequestClose }: ApplicationListTableProps) => {
  const ambiguous = duplicatedIdentities(items);

  return (
    /* The negative margin must equal the Card's own padding (p-4 sm:p-6) so the table's
       rules meet the card edge instead of overhanging it. */
    <div className="-mx-4 mt-3 overflow-x-auto border-y border-cv-border bg-cv-surface-raised sm:-mx-6">
      <table className="w-full min-w-[52rem] table-fixed border-collapse text-start">
        <thead>
          <tr className="border-b border-cv-border bg-cv-surface-muted">
            {columns.map(({ label, width }, index) => (
              <th
                className={cx(
                  "px-2.5 py-2.5 text-start text-support font-semibold text-cv-text-muted first:ps-4 last:pe-4",
                  width,
                )}
                key={`${label}-${index}`}
                scope="col"
              >
                {label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <ApplicationListRow
              ambiguous={ambiguous.has(item.id)}
              item={item}
              key={item.id}
              onRequestClose={onRequestClose}
            />
          ))}
        </tbody>
      </table>
    </div>
  );
};
