import type { ApplicationListItem } from "../../api/contracts";
import { cx } from "../../ui/cx";
import { ApplicationListRow } from "./ApplicationListRow";

const ARCHIVE_COLUMN = "";

const columns = [
  "חברה ותפקיד",
  "נוצר",
  "מצב קורות החיים",
  "שלב גיוס",
  "פעילות אחרונה",
  "הפעולה הבאה",
  "אזהרות",
  "פעולה מומלצת",
  ARCHIVE_COLUMN,
];

const columnWidths: Record<string, string> = {
  "חברה ותפקיד": "w-[19%]",
  נוצר: "w-[8%]",
  "מצב קורות החיים": "w-[18%]",
  "שלב גיוס": "w-[11%]",
  "פעילות אחרונה": "w-[9%]",
  "הפעולה הבאה": "w-[11%]",
  אזהרות: "w-[7%]",
  "פעולה מומלצת": "w-[16%]",
  [ARCHIVE_COLUMN]: "w-[4%]",
};

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
    <div className="-mx-5 mt-4 overflow-x-auto border-y border-cv-border bg-cv-surface-raised sm:-mx-8">
      <table className="w-full min-w-[64rem] table-fixed border-collapse text-start">
        <thead>
          <tr className="border-b border-cv-border bg-cv-surface-muted">
            {columns.map((column) => (
              <th
                className={cx(
                  "px-4 py-3 text-start text-support font-semibold text-cv-text-muted",
                  columnWidths[column],
                )}
                key={column}
                scope="col"
              >
                {column}
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
