import { Check, OctagonAlert } from "lucide-react";

import type { ApplicationDetail } from "@/api/contracts";
import { formatDateTime } from "@/utils/formatDateTime";
import { cx } from "@/ui/cx";
import { contentCheckLabels } from "@/features/preparation";
import type { AutosaveState } from "../hooks/useDraftAutosave";
import { type ContentSummary, type DraftStep, type DraftStepId, draftSteps } from "../model/draftOverview";
import type { EditableDocument } from "../model/drafts.types";
import { DraftSaveState } from "./DraftSaveState";

interface DraftProgressProps {
  content: ContentSummary;
  detail: ApplicationDetail;
  dirty: boolean;
  draft: EditableDocument;
  saveState: AutosaveState;
}

const stepTitles: Record<DraftStepId, string> = {
  review: "ביסוס התוכן",
  check: "בדיקת הקובץ",
  approve: "אישור והפקת PDF",
};

/* What the step in front of the reader asks of them - said once, for that step only,
   rather than a paragraph under each of three boxes. */
const stepGuidance: Record<DraftStepId, string> = {
  review: "כל שורה צריכה עובדה מאושרת מאחוריה. יש לטפל בשורות שמסומנות למטה לפני הבדיקה.",
  check: "התוכן מבוסס. הכפתור בתחתית בודק את המבנה, העובדות והמספרים של הגרסה המוצגת.",
  approve: "הבדיקה עברה. האישור מפיק HTML ו־PDF סופיים; עריכה אחריו מחזירה את המסמך לטיוטה.",
};

const plural = (count: number, one: string, many: string) => (count === 1 ? one : `${count} ${many}`);

const stepStatus = (step: DraftStep, detail: ApplicationDetail, content: ContentSummary): string => {
  if (step.id === "review") {
    const parts = [
      content.unsupportedClaims.length === 0
        ? undefined
        : plural(content.unsupportedClaims.length, "שורה אחת ללא ביסוס", "שורות ללא ביסוס"),
      detail.review_reasons.length === 0
        ? undefined
        : plural(detail.review_reasons.length, "החלטה אחת פתוחה", "החלטות פתוחות"),
    ].filter((part): part is string => part !== undefined);
    return parts.length === 0 ? "כל השורות נשענות על עובדות" : parts.join(" · ");
  }
  if (step.id === "check") {
    return detail.content_check === "none" ? "עוד לא הורצה" : contentCheckLabels[detail.content_check];
  }
  return detail.document_state === "ready"
    ? "הקבצים הופקו"
    : detail.document_state === "approved"
      ? "אושר, הקבצים עוד לא הופקו"
      : "ממתין לאישור";
};

/* Where the reader stands inside the draft step, and whether their work is saved.

   The screen used to open with a row of status chips - a hash, a document state, a check
   state - which named values without saying what they were values of or what came next.
   This is the three things the step is made of, in order, with the one that is waiting
   on the reader marked and explained. Every status is the projection's
   (`document_state`, `content_check`, `review_reasons`) or the outline's own claim types;
   nothing here decides whether a command is available. */
export const DraftProgress = ({ content, detail, dirty, draft, saveState }: DraftProgressProps) => {
  const steps = draftSteps(detail, content);
  const focus = steps.find((step) => step.status === "blocked" || step.status === "current");

  return (
    <section
      aria-labelledby="draft-progress-heading"
      className="flex flex-col gap-3 border border-cv-border bg-cv-surface p-card-padding"
    >
      <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1">
        <h2 className="text-body font-semibold text-cv-text" id="draft-progress-heading">
          התקדמות הטיוטה
        </h2>
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-caption text-cv-text-muted">
          <DraftSaveState dirty={dirty} state={saveState} />
          <span>עודכנה {formatDateTime(draft.updated_at, "short")}</span>
        </div>
      </div>

      <ol className="flex flex-col gap-2 sm:flex-row sm:items-start sm:gap-0">
        {steps.map((step, index) => (
          <li
            aria-current={step === focus ? "step" : undefined}
            className="flex min-w-0 flex-1 items-start gap-2.5 sm:after:mx-3 sm:after:mt-3.5 sm:after:h-px sm:after:min-w-6 sm:after:flex-1 sm:after:bg-cv-border sm:last:after:hidden"
            key={step.id}
          >
            <span
              aria-hidden="true"
              className={cx(
                "flex size-7 shrink-0 items-center justify-center rounded-pill border text-support font-bold",
                step.status === "done"
                  ? "border-cv-success/40 bg-cv-success-soft text-cv-success"
                  : step.status === "blocked"
                    ? "border-cv-blocker bg-cv-blocker-soft text-cv-blocker"
                    : step.status === "current"
                      ? "border-cv-accent bg-cv-accent text-cv-on-accent"
                      : "border-cv-border bg-cv-surface text-cv-text-muted",
              )}
            >
              {step.status === "done" ? (
                <Check className="size-icon-sm" />
              ) : step.status === "blocked" ? (
                <OctagonAlert className="size-icon-sm" />
              ) : (
                index + 1
              )}
            </span>
            <div className="min-w-0 shrink-0">
              <p
                className={cx(
                  "text-support font-semibold",
                  step.status === "upcoming" ? "text-cv-text-muted" : "text-cv-text",
                )}
              >
                {stepTitles[step.id]}
              </p>
              <p
                className={cx(
                  "text-caption font-medium",
                  step.status === "blocked"
                    ? "text-cv-blocker"
                    : step.status === "done"
                      ? "text-cv-success"
                      : "text-cv-text-muted",
                )}
              >
                {stepStatus(step, detail, content)}
              </p>
            </div>
          </li>
        ))}
      </ol>

      {focus === undefined ? null : (
        <p
          className={cx(
            "rounded-control px-3 py-2 text-support leading-6",
            focus.status === "blocked" ? "bg-cv-blocker-soft text-cv-text" : "bg-cv-surface-muted text-cv-text",
          )}
        >
          <span className="font-semibold">מה עכשיו: </span>
          {stepGuidance[focus.id]}
        </p>
      )}
    </section>
  );
};
