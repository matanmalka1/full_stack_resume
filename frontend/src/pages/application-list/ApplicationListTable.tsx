import type { ApplicationListItem } from "../../api/contracts";
import { cx } from "../../ui/cx";
import { ApplicationListRow } from "./ApplicationListRow";

const ARCHIVE_COLUMN = "";

const columns = [
  { label: "חברה ותפקיד", width: "w-[19%]" },
  { label: "נוצר", width: "w-[8%]" },
  { label: "מצב קורות החיים", width: "w-[17%]" },
  { label: "שלב גיוס", width: "w-[11%]" },
  { label: "פעילות אחרונה", width: "w-[9%]" },
  { label: "הפעולה הבאה", width: "w-[11%]" },
  { label: "אזהרות", width: "w-[9%]" },
  { label: "פעולה מומלצת", width: "w-[15%]" },
  { label: "", width: "w-[4%]" },
] as const;

/* A visual hint only: rows with the same company and role emphasize their dates so the
   reader can distinguish them. It does not represent domain duplicate detection. */
const duplicatedIdentities = (
  items: readonly ApplicationListItem[],
): ReadonlySet<string> => {
  const byIdentity = new Map<string, string[]>();

  for (const item of items) {
    const key = `${item.company}\n${item.target_role}`;
    byIdentity.set(key, [...(byIdentity.get(key) ?? []), item.id]);
  }

  return new Set(
    [...byIdentity.values()].filter((ids) => ids.length > 1).flat(),
  );
};

interface ApplicationListTableProps {
  items: readonly ApplicationListItem[];
  onRequestClose: (item: ApplicationListItem) => void;
}

export const ApplicationListTable = ({
  items,
  onRequestClose,
}: ApplicationListTableProps) => {
  const ambiguous = duplicatedIdentities(items);

  return (
    <div className="-mx-5 mt-4 overflow-x-auto border-y border-cv-border bg-cv-surface-raised sm:-mx-8">
      <table className="w-full min-w-[64rem] table-fixed border-collapse text-start">
        <thead>
          <tr className="border-b border-cv-border bg-cv-surface-muted">
            {columns.map(({ label, width }, index) => (
              <th
                className={cx(
                  "px-4 py-3 text-start text-support font-semibold text-cv-text-muted",
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
