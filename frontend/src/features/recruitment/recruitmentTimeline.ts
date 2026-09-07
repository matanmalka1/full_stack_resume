import type { RecruitmentTimelineItem } from "@/api/contracts";
import { formatDate, formatDateTime } from "@/ui/formatDateTime";
import { recruitmentStatusLabel } from "./recruitmentStatus";

export const statusEventLabel = (event: RecruitmentTimelineItem): string =>
  `${formatDateTime(event.occurred_at)} · ${recruitmentStatusLabel(event.to_status ?? "saved")}`;

export const recruitmentEventDescription = (
  event: RecruitmentTimelineItem,
  byId: ReadonlyMap<string, RecruitmentTimelineItem>,
): string => {
  if (event.item_type === "submission") {
    return event.submission_type === "internal" ? "נרשמה הגשה של הגרסה המוכנה" : "נרשמה הגשה שבוצעה מחוץ למערכת";
  }
  if (event.item_type === "next_action") {
    return event.next_action == null
      ? "התזכורת לפעולה הבאה הוסרה"
      : `הפעולה הבאה נקבעה: ${event.next_action}${
          event.next_action_date == null ? "" : ` · ${formatDate(event.next_action_date)}`
        }`;
  }
  if (event.item_type === "status_correction") {
    const corrected = event.corrects_event_id == null ? undefined : byId.get(event.corrects_event_id);
    const target = recruitmentStatusLabel(event.to_status ?? "saved");
    return corrected === undefined
      ? `מצב הגיוס תוקן ל־${target}`
      : `האירוע „${statusEventLabel(corrected)}” תוקן ל־${target}`;
  }
  if (event.from_status == null) {
    return `המועמדות נפתחה במצב ${recruitmentStatusLabel(event.to_status ?? "saved")}`;
  }
  return `מצב הגיוס עבר מ־${recruitmentStatusLabel(event.from_status)} ל־${recruitmentStatusLabel(
    event.to_status ?? "saved",
  )}`;
};

const engineReasons: Record<string, string> = {
  "application created": "המועמדות נוצרה",
  "application closed": "המועמדות נסגרה",
  "submission recorded": "נרשמה הגשה",
};

export const recruitmentEventReason = (reason: string): string => engineReasons[reason] ?? reason;
