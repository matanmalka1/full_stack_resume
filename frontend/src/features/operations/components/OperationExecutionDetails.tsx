import type { Operation } from "@/api/contracts";
import { Disclosure } from "@/ui/Disclosure";
import { LtrText } from "@/ui/LtrText";
import { formatDateTime } from "@/utils/formatDateTime";

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

/** Uses only reported metadata; missing usage is not zero usage. */
export const OperationExecutionDetails = ({ operation }: { operation: Operation }) => {
  const waiting = operation.started_at == null ? null : duration(operation.created_at, operation.started_at);
  // The host polls live Operations. A terminal run without a finish time has no known duration.
  const end = operation.finished_at ?? (operation.is_terminal ? null : Date.now());
  const elapsed = operation.started_at == null || end == null ? null : duration(operation.started_at, end);
  const rows: [string, string | number | null | undefined][] = [
    ["נוצרה", formatDateTime(operation.created_at, "short")],
    ["התחילה", operation.started_at == null ? null : formatDateTime(operation.started_at, "short")],
    ["הסתיימה", operation.finished_at == null ? null : formatDateTime(operation.finished_at, "short")],
    ["המתנה בתור", waiting],
    [operation.is_terminal ? "משך הריצה" : "זמן שחלף", elapsed],
    ["ספק", operation.provider],
    ["מודל", operation.model],
    ["מאמץ חשיבה", operation.reasoning_effort == null ? null : effortLabels[operation.reasoning_effort]],
    ["עלות", operation.cost_usd == null ? null : `$${operation.cost_usd}`],
    ["טוקני קלט", operation.input_tokens],
    ["קלט מהמטמון", operation.cached_input_tokens],
    ["טוקני פלט", operation.output_tokens],
    ["סך הטוקנים", operation.total_tokens],
    ["הרצה", operation.retry_of_operation_id == null ? null : "ניסיון חוזר"],
    [
      "ביטול התבקש",
      operation.cancellation_requested_at == null ? null : formatDateTime(operation.cancellation_requested_at, "short"),
    ],
  ];

  return (
    <Disclosure className="mt-2" summary="פרטי ביצוע">
      <dl className="grid gap-x-6 gap-y-1 sm:grid-cols-2">
        {rows
          .filter(([, value]) => value != null)
          .map(([label, value]) => (
            <div className="flex min-w-0 flex-wrap gap-x-2" key={label}>
              <dt>{label}</dt>
              <dd className="min-w-0 break-words text-cv-text">
                {typeof value === "number" ? (
                  <LtrText>{value.toLocaleString("he-IL")}</LtrText>
                ) : (
                  <span dir="auto">{value}</span>
                )}
              </dd>
            </div>
          ))}
      </dl>
    </Disclosure>
  );
};
