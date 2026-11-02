import type { RecruitmentStatus } from "@/api/contracts";

/* The way an application climbs with the employer, as the hub's stage card draws it: five
   rungs, one segment each. The grouping is the board's
   (`application-list/model/recruitmentStages`) - an assignment is part of the interviews,
   a final stage part of the offer - so a card and the board's stage lanes never place
   one application on two different rungs.

   Each rung has two names: the full one a wide screen writes under every segment, and the
   short one a phone's bar has room for at its ends and in "הבא: …". */
const rungs = [
  { label: "טרם הוגש", short: "טרם הוגש", statuses: ["saved"] },
  { label: "הוגשה מועמדות", short: "הוגשה", statuses: ["applied"] },
  { label: "סינון טלפוני / HR", short: "סינון טלפוני", statuses: ["recruiter_screen"] },
  { label: "ראיונות ומטלות", short: "ראיונות", statuses: ["interview", "assignment"] },
  { label: "שלב סופי והצעה", short: "הצעה", statuses: ["final_stage", "offer", "accepted"] },
] as const satisfies readonly { label: string; short: string; statuses: readonly RecruitmentStatus[] }[];

export const recruitmentRungLabels: readonly string[] = rungs.map((rung) => rung.label);

export interface RecruitmentRung {
  /* The rung the status sits on, from 0; null once the process has closed - a rejection
     or a withdrawal leaves the ladder rather than reaching a rung of it. */
  index: number | null;
  /* The short name of the rung after the current one, when there is one to name. */
  next: string | null;
  first: string;
  last: string;
  total: number;
}

export const recruitmentRung = (status: string): RecruitmentRung => {
  const found = rungs.findIndex((rung) => (rung.statuses as readonly string[]).includes(status));
  const index = found === -1 ? null : found;
  return {
    index,
    next: index === null ? null : (rungs[index + 1]?.short ?? null),
    first: rungs[0].short,
    last: rungs[4].short,
    total: rungs.length,
  };
};

const localDateKey = (date: Date): string =>
  `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;

/* A next action's date is a calendar day, not an instant: it is late from the day after,
   read in the reader's own time zone, the way the board's cards read it. */
export const isNextActionLate = (value: string | null | undefined, today: Date = new Date()): boolean =>
  value != null && /^\d{4}-\d{2}-\d{2}$/.test(value) && value < localDateKey(today);
