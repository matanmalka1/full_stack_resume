import { Check } from "lucide-react";
import { Link } from "react-router-dom";

import type { ApplicationDetail, PreparationState } from "@/api/contracts";
import { routePaths } from "@/navigation/routePaths";
import { cx } from "@/ui/cx";

type RowState = "done" | "current" | "upcoming";

/* The five things preparing a CV comes down to, in the order they happen. They are finer
   than the four-stage spine: the draft stage holds both writing the draft and approving it,
   and a reader looking at one Application wants to know which of the two is waiting. */
const rows = [
  { key: "analysis", label: "ניתוח המשרה" },
  { key: "create", label: "יצירת טיוטה" },
  { key: "draft", label: "טיוטה בעבודה" },
  { key: "approve", label: "אישור ויצירת הקובץ" },
  { key: "ready", label: "קורות החיים מוכנים" },
] as const;

/* How many rows the projection's state has finished. Read off `preparation_state` only:
   the projection decides where the work stands, and this list draws that, nothing more. */
const doneCount: Record<PreparationState, number> = {
  needs_analysis: 0,
  ready_to_draft: 1,
  draft_in_progress: 2,
  approved: 3,
  ready: 5,
};

const markClasses: Record<RowState, string> = {
  done: "border-cv-accent bg-cv-accent text-cv-on-accent",
  current: "border-2 border-cv-accent bg-cv-surface",
  upcoming: "border-cv-border-strong bg-cv-surface",
};

/* From the large breakpoint the rows stand abreast as five tiles, as the desktop
   Application screen draws them: a done step on a muted fill, the open one on a bordered
   surface, what is ahead in a dashed outline - shape as well as tone, so the three states
   survive greyscale. */
const tileClasses: Record<RowState, string> = {
  done: "lg:border-transparent lg:bg-cv-surface-muted",
  current: "lg:border-cv-accent lg:bg-cv-surface",
  upcoming: "lg:border-dashed lg:border-cv-border-strong",
};

const stateWords: Record<RowState, string> = {
  done: "הושלם",
  current: "השלב הנוכחי",
  upcoming: "בהמשך",
};

/* The Application screen's account of its CV: five rows, each done, current or ahead, and
   the way into the editor where the open row is worked on there.

   A row links only where there is something at the other end: the editor once the
   document has content. The analysis and the draft's creation happen on the Application
   screen itself, so they are not links from it. */
export const PreparationChecklist = ({ detail }: { detail: ApplicationDetail }) => {
  const done = doneCount[detail.preparation_state];
  const position = Math.min(done + 1, rows.length);
  const editor = routePaths.draft(detail.application.id);
  const hasContent = done >= 2 && detail.document_id != null;

  return (
    <section
      aria-labelledby="preparation-checklist-heading"
      className="rounded-surface border border-cv-border bg-cv-surface p-card-padding shadow-surface"
    >
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-body font-bold text-cv-text" id="preparation-checklist-heading">
          הכנת קורות החיים
        </h2>
        <span className="rounded-pill bg-cv-surface-muted px-2 text-caption font-bold text-cv-text tabular-nums">
          <span className="sr-only">שלב </span>
          <span dir="ltr">{`${position}/${rows.length}`}</span>
        </span>
      </div>
      <ol className="mt-3 flex flex-col gap-1 lg:mt-4 lg:grid lg:grid-cols-5 lg:gap-2">
        {rows.map((row, index) => {
          const state: RowState = index < done ? "done" : index === done ? "current" : "upcoming";
          const editorRow = row.key === "draft" || row.key === "approve";
          const href = editorRow && hasContent ? editor : null;

          return (
            <li
              aria-current={state === "current" ? "step" : undefined}
              className={cx(
                "flex min-h-11 items-center gap-3 rounded-control px-2",
                state === "current" && "bg-cv-surface-muted",
                "lg:flex-col lg:items-start lg:gap-2 lg:border lg:p-3",
                tileClasses[state],
              )}
              key={row.key}
            >
              <span
                aria-hidden="true"
                className={cx(
                  "flex size-6 shrink-0 items-center justify-center rounded-pill border",
                  markClasses[state],
                )}
              >
                {state === "done" ? <Check className="size-icon-sm [stroke-width:var(--stroke-icon-strong)]" /> : null}
                {state === "current" ? <span className="size-2.5 rounded-pill bg-cv-accent" /> : null}
              </span>
              <span
                className={cx(
                  "min-w-0 flex-1 text-support lg:flex-none",
                  state === "current"
                    ? "font-bold text-cv-text"
                    : state === "done"
                      ? "text-cv-text"
                      : "text-cv-text-muted",
                )}
              >
                {row.label}
                <span className="sr-only">{`, ${stateWords[state]}`}</span>
              </span>
              {state === "current" && href !== null ? (
                <Link
                  aria-label={`עריכה: ${row.label}`}
                  className="inline-flex min-h-11 items-center px-1 text-support font-bold text-cv-text underline underline-offset-4"
                  to={href}
                >
                  עריכה
                </Link>
              ) : null}
            </li>
          );
        })}
      </ol>
    </section>
  );
};
