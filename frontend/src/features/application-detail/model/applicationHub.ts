import type { ApplicationDetail, PreparationState } from "@/api/contracts";
import { preparationResumeDestinationFromDetail } from "@/features/preparation";
import { routePaths } from "@/navigation/routePaths";

/* The statuses that end the process with the employer. Together with a terminal outcome
   they are the server's own rule for a closed application (`application_is_closed`), so
   the hub says "סגורה" exactly where the board's list item says `is_closed`. */
const closedStatuses: ReadonlySet<string> = new Set(["rejected", "withdrawn", "closed"]);

export const isApplicationClosed = (detail: Pick<ApplicationDetail, "recruitment_status" | "terminal_outcome">) =>
  detail.terminal_outcome != null || closedStatuses.has(detail.recruitment_status);

/* When the application was last sent, read off its recruitment history: the newest
   submission recorded, internal or external. Null while nothing was sent. */
export const lastSubmittedAt = (detail: ApplicationDetail): string | null =>
  detail.recruitment_timeline
    .filter((item) => item.item_type === "submission")
    .reduce<string | null>(
      (latest, item) => (latest === null || item.occurred_at > latest ? item.occurred_at : latest),
      null,
    );

export type PreparationRowKey = "analysis" | "create" | "draft" | "approve" | "ready";
export type PreparationRowState = "done" | "current" | "upcoming";

/* The five things preparing a CV comes down to, in the order they happen. They are finer
   than the four-stage spine: the draft stage holds both writing the draft and approving it,
   and a reader looking at one Application wants to know which of the two is waiting. */
const rows: readonly { key: PreparationRowKey; label: string }[] = [
  { key: "analysis", label: "ניתוח המשרה" },
  { key: "create", label: "יצירת טיוטה" },
  { key: "draft", label: "טיוטה בעבודה" },
  { key: "approve", label: "אישור ויצירת הקובץ" },
  { key: "ready", label: "קורות החיים מוכנים" },
];

/* How many rows the projection's state has finished. Read off `preparation_state` only:
   the projection decides where the work stands, and the hub draws that, nothing more. */
const doneCount: Record<PreparationState, number> = {
  needs_analysis: 0,
  ready_to_draft: 1,
  draft_in_progress: 2,
  approved: 3,
  ready: 5,
};

export interface PreparationRow {
  /* Where the row's work is done, when there is something there to open. */
  href: string | null;
  key: PreparationRowKey;
  label: string;
  state: PreparationRowState;
}

export interface PreparationProgress {
  rows: PreparationRow[];
  /* The row the work stands on, from 1 - all five once the CV is ready. */
  position: number;
  total: number;
}

/* The hub's account of its CV: each row done, current or ahead, and the screen it is
   worked on where that screen has something to show. The analysis and the draft's
   creation are the analysis step's; writing and approving the draft are the editor's,
   once the document has content; the finished CV is the ready step's. */
export const preparationProgress = (detail: ApplicationDetail): PreparationProgress => {
  const applicationId = detail.application.id;
  const done = doneCount[detail.preparation_state];
  const hasContent = done >= 2 && detail.document_id != null;
  const hrefFor = (key: PreparationRowKey): string | null => {
    if (key === "analysis" || key === "create") return routePaths.analysis(applicationId);
    if (key === "ready") return detail.preparation_state === "ready" ? routePaths.ready(applicationId) : null;
    return hasContent ? routePaths.draft(applicationId) : null;
  };

  return {
    position: Math.min(done + 1, rows.length),
    rows: rows.map((row, index) => {
      const state: PreparationRowState = index < done ? "done" : index === done ? "current" : "upcoming";
      return { ...row, href: state === "upcoming" ? null : hrefFor(row.key), state };
    }),
    total: rows.length,
  };
};

/* The hub's one command forward: the screen the work is waiting on, worded by what the
   reader will do there. The destination is preparation's own resume answer. */
export const continuation = (detail: ApplicationDetail): { label: string; to: string } => {
  const applicationId = detail.application.id;
  const to = preparationResumeDestinationFromDetail(applicationId, detail);

  if (to === routePaths.ready(applicationId)) return { label: "פתיחת קורות החיים המוכנים", to };
  if (to === routePaths.draft(applicationId)) {
    return { label: detail.preparation_state === "approved" ? "המשך ליצירת הקובץ" : "המשך לעריכת הטיוטה", to };
  }
  return {
    label: detail.preparation_state === "needs_analysis" ? "המשך לניתוח המשרה" : "המשך ליצירת טיוטה",
    to,
  };
};
