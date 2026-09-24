import type { Operation } from "@/api/contracts";
import { cx } from "@/ui/cx";
import { Disclosure } from "@/ui/Disclosure";
import { LtrText } from "@/ui/LtrText";
import { formatDateTime } from "@/utils/formatDateTime";
import { formatUsd } from "@/utils/formatUsd";

const effortLabels: Record<NonNullable<Operation["reasoning_effort"]>, string> = {
  low: "נמוך",
  medium: "בינוני",
  high: "גבוה",
};

const duration = (start: string, end: string | number): string | null => {
  const milliseconds = (typeof end === "number" ? end : Date.parse(end)) - Date.parse(start);
  if (!Number.isFinite(milliseconds) || milliseconds < 0) return null;
  const seconds = Math.floor(milliseconds / 1000);
  return seconds < 60 ? `${seconds} שניות` : `${Math.floor(seconds / 60)} דקות ו־${seconds % 60} שניות`;
};

type Row = [string, string | number | null | undefined];

const useRowGroups = (operation: Operation): [string, Row[]][] => {
  const waiting = operation.started_at == null ? null : duration(operation.created_at, operation.started_at);
  // The host polls live Operations. A terminal run without a finish time has no known duration.
  const end = operation.finished_at ?? (operation.is_terminal ? null : Date.now());
  const elapsed = operation.started_at == null || end == null ? null : duration(operation.started_at, end);

  return [
    [
      "תזמון",
      [
        ["נוצרה", formatDateTime(operation.created_at, "short")],
        ["התחילה", operation.started_at == null ? null : formatDateTime(operation.started_at, "short")],
        ["הסתיימה", operation.finished_at == null ? null : formatDateTime(operation.finished_at, "short")],
        ["המתנה בתור", waiting],
        [operation.is_terminal ? "משך הריצה" : "זמן שחלף", elapsed],
        [
          "ביטול התבקש",
          operation.cancellation_requested_at == null
            ? null
            : formatDateTime(operation.cancellation_requested_at, "short"),
        ],
      ],
    ],
    [
      "הרצה",
      [
        ["ספק", operation.provider],
        ["מודל", operation.model],
        ["מאמץ חשיבה", operation.reasoning_effort == null ? null : effortLabels[operation.reasoning_effort]],
        ["הרצה", operation.retry_of_operation_id == null ? null : "ניסיון חוזר"],
      ],
    ],
    [
      "עלות וטוקנים",
      [
        ["עלות", operation.cost_usd == null ? null : formatUsd(operation.cost_usd)],
        ["טוקני קלט", operation.input_tokens],
        ["קלט מהמטמון", operation.cached_input_tokens],
        ["טוקני פלט", operation.output_tokens],
        ["סך הטוקנים", operation.total_tokens],
      ],
    ],
  ];
};

export const OperationExecutionDetails = ({ operation }: { operation: Operation }) => {
  const groups = useRowGroups(operation)
    .map(([heading, rows]): [string, Row[]] => [heading, rows.filter(([, value]) => value != null)])
    .filter(([, rows]) => rows.length > 0);

  return (
    <Disclosure className="mt-2" summary="פרטי ביצוע">
      <div className="flex flex-col gap-4 sm:flex-row sm:flex-wrap sm:gap-x-8">
        {groups.map(([heading, rows], index) => (
          <div
            className={cx(
              "min-w-40 flex-1",
              index > 0 && "border-t border-cv-border pt-3 sm:border-t-0 sm:border-s sm:ps-8 sm:pt-0",
            )}
            key={heading}
          >
            <p className="mb-1.5 text-support font-semibold text-cv-text">{heading}</p>
            <dl className="grid grid-cols-[auto_1fr] items-baseline gap-x-3 gap-y-1">
              {rows.map(([label, value]) => (
                <div className="contents" key={label}>
                  <dt className="text-support text-cv-text-muted">{label}</dt>
                  <dd className="min-w-0 break-words text-support text-cv-text">
                    {typeof value === "number" ? (
                      <LtrText className="tabular-nums">{value.toLocaleString("he-IL")}</LtrText>
                    ) : (
                      <span dir="auto">{value}</span>
                    )}
                  </dd>
                </div>
              ))}
            </dl>
          </div>
        ))}
      </div>
    </Disclosure>
  );
};
