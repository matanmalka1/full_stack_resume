import type { RecruitmentStatus } from "@/api/contracts";

/* The way an application climbs with the employer, as the detail screen's stage card
   draws it: five rungs, one segment each. The grouping is the board's
   (`application-list/model/recruitmentStages`) - an assignment is part of the interviews,
   a final stage part of the offer - so a card and the board's stage lanes never place
   one application on two different rungs. The names are the short ones a segmented bar's
   end labels have room for; `name` is the rung's full one, which a wide screen writes
   under each segment of its own. */
const rungs = [
  { label: "טרם הוגש", name: "טרם הוגש", statuses: ["saved"] },
  { label: "הוגשה", name: "הוגשה מועמדות", statuses: ["applied"] },
  { label: "סינון טלפוני", name: "סינון טלפוני / HR", statuses: ["recruiter_screen"] },
  { label: "ראיונות", name: "ראיונות ומטלות", statuses: ["interview", "assignment"] },
  { label: "הצעה", name: "שלב סופי והצעה", statuses: ["final_stage", "offer", "accepted"] },
] as const satisfies readonly { label: string; name: string; statuses: readonly RecruitmentStatus[] }[];

export interface RecruitmentRung {
  /* The rung the status sits on, from 0; null once the process has closed - a rejection
     or a withdrawal leaves the ladder rather than reaching a rung of it. */
  index: number | null;
  /* The rung after the current one, when there is one to name. */
  next: string | null;
  first: string;
  last: string;
  /* Every rung's full name, in order. */
  names: readonly string[];
  total: number;
}

export const recruitmentRung = (status: string): RecruitmentRung => {
  const found = rungs.findIndex((rung) => (rung.statuses as readonly string[]).includes(status));
  const index = found === -1 ? null : found;
  return {
    index,
    next: index === null ? null : (rungs[index + 1]?.label ?? null),
    first: rungs[0].label,
    last: rungs[4].label,
    names: rungs.map((rung) => rung.name),
    total: rungs.length,
  };
};

const localDateKey = (date: Date): string =>
  `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;

/* A next action's date is a calendar day, not an instant: it is late from the day after,
   read in the reader's own time zone, the way the board's cards read it. */
export const isNextActionLate = (value: string | null | undefined, today: Date = new Date()): boolean =>
  value != null && /^\d{4}-\d{2}-\d{2}$/.test(value) && value < localDateKey(today);
