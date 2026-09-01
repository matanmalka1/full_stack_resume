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
/* Widths sum to 100. The archive column is sized in rem rather than a percentage:
   it holds one icon button, and a percentage of a table this wide either starved it
   below its own padding or took space the text columns needed.

   The date column carries a fixed rem width instead of a percentage. A formatted date
   is the one cell whose content cannot grow, so giving it a share of the table only
   handed it space the wrapping text columns needed at narrow widths.

   Eight columns, not ten. Creation date sat beside last activity showing the same day
   for every row it did not distinguish, so it moved into the activity cell's tooltip,
   where it is still readable and no longer costs a column. */
const columns = [
  { key: "identity", label: "חברה ותפקיד", width: "w-[24%]" },
  /* The analysis verdict, beside the stage rather than inside it: how well the posting
     fits is what decides which of several ready rows is worth the next hour, and it is
     not derivable from how far the CV got. */
  { key: "fit", label: "התאמה", width: "w-[13%]" },
  { key: "preparation", label: "מצב קורות החיים", width: "w-[24%]" },
  { key: "recruitment", label: "שלב גיוס", width: "w-[11%]" },
  { key: "activity", label: "פעילות אחרונה", width: "w-28" },
  /* The two action columns are named for their owners. "הפעולה הבאה" beside "פעולה
     מומלצת" read as the same thing: one is the recruitment task the user typed, the
     other the workflow's derived next step. */
  { key: "next-action", label: "משימת גיוס", width: "w-[13%]" },
  { key: "recommendation", label: "המשך הכנה", width: "w-[15%]" },
  { key: "archive", label: "", width: "w-14" },
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
  /* Recruitment tasks are typed by hand, so most boards have none: a column of em dashes
     held an eighth of the table to say "nothing here" on every row. It appears with the
     first task on the page and leaves with the last. */
  const showNextAction = items.some((item) => item.next_action != null);
  const visibleColumns = columns.filter((column) => column.key !== "next-action" || showNextAction);

  return (
    /* The board is the one raised thing on this route: the page sits directly on the
       canvas, and the rows are a single sheet on top of it. That is also why the
       horizontal scroll lives on the sheet itself - the frame and the scrolling region
       are the same element, instead of a table breaking out of a card's padding. */
    <div className="overflow-x-auto rounded-surface border border-cv-border bg-cv-surface-raised shadow-surface">
      <table className="w-full min-w-[54rem] table-fixed border-collapse text-start">
        <thead>
          <tr className="border-b border-cv-border bg-cv-surface-muted">
            {visibleColumns.map(({ key, label, width }) => (
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
              showNextAction={showNextAction}
            />
          ))}
        </tbody>
      </table>
    </div>
  );
};
