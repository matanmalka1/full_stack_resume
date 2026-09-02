import type { ApplicationListItem } from "../../api/contracts";
import { Card } from "../../ui/Card";
import { cx } from "../../ui/cx";
import { ApplicationListRow } from "./ApplicationListRow";

/* Recruitment and preparation remain adjacent but independent: the former says where
   the employer process stands, the latter what the CV still needs. The final column
   gathers links and commands so the row has one predictable action edge. */
const columns = [
  { key: "identity", label: "חברה ותפקיד", width: "w-[24%]" },
  { key: "recruitment", label: "שלב גיוס", width: "w-[12%]" },
  { key: "preparation", label: "מצב קו״ח", width: "w-[21%]" },
  { key: "fit", label: "התאמה", width: "w-[12%]" },
  { key: "next-action", label: "צעד הבא ויעד", width: "w-[15%]" },
  { key: "activity", label: "פעילות אחרונה", width: "w-28" },
  { key: "actions", label: "פעולות מהירות", width: "w-[16%]" },
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
    /* The board is the one raised thing on this route: the page sits directly on the
       canvas, and the rows are a single sheet on top of it. That is also why the
       horizontal scroll lives on the sheet itself - the frame and the scrolling region
       are the same element, instead of a table breaking out of a card's padding. */
    <Card className="overflow-x-auto bg-cv-surface-raised shadow-surface">
      <table className="w-full min-w-[64rem] table-fixed border-collapse text-start">
        <thead>
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
        <tbody>
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
