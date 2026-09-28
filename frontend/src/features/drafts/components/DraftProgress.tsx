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

const stepDescriptions: Record<DraftStepId, string> = {
  review: "כל שורה צריכה עובדה מאושרת מאחוריה. שורה בלי ביסוס חוסמת אישור.",
  check: "בדיקה אוטומטית של המבנה, העובדות והמספרים מול המאגר.",
  approve: "האישור מפיק HTML ו־PDF סופיים. עריכה אחריו מחזירה את המסמך לטיוטה.",
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
   This is the same information as the three things the step is made of, in order, each
   with a sentence on what it asks. Every status is the projection's
   (`document_state`, `content_check`, `review_reasons`) or the outline's own claim types;
   nothing here decides whether a command is available. */
export const DraftProgress = ({ content, detail, dirty, draft, saveState }: DraftProgressProps) => {
  const steps = draftSteps(detail, content);

  return (
    <section aria-labelledby="draft-progress-heading" className="flex flex-col gap-4 border-b border-cv-hairline pb-5">
      <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
        <h2 className="text-body font-semibold text-cv-text" id="draft-progress-heading">
          התקדמות הטיוטה
        </h2>
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-support text-cv-text-muted">
          <DraftSaveState dirty={dirty} state={saveState} />
          <span>עודכנה {formatDateTime(draft.updated_at, "short")}</span>
        </div>
      </div>

      <ol className="grid gap-3 sm:grid-cols-3">
        {steps.map((step, index) => (
          <li
            aria-current={step.status === "current" ? "step" : undefined}
            className={cx(
              "flex gap-3 rounded-control border p-3",
              step.status === "current"
                ? "border-cv-accent/40 bg-cv-accent-soft"
                : step.status === "blocked"
                  ? "border-cv-blocker/30 bg-cv-blocker-soft"
                  : "border-cv-border bg-cv-surface",
            )}
            key={step.id}
          >
            <span
              aria-hidden="true"
              className={cx(
                "flex size-7 shrink-0 items-center justify-center rounded-pill text-support font-bold",
                step.status === "done"
                  ? "bg-cv-success-soft text-cv-success"
                  : step.status === "blocked"
                    ? "bg-cv-surface text-cv-blocker"
                    : step.status === "current"
                      ? "bg-cv-accent text-cv-on-accent"
                      : "bg-cv-surface-muted text-cv-text-muted",
              )}
            >
              {step.status === "done" ? (
                <Check className="size-icon-sm" />
              ) : step.status === "blocked" ? (
                <OctagonAlert className="size-icon-md" />
              ) : (
                index + 1
              )}
            </span>
            <div className="min-w-0">
              <p className="text-support font-semibold text-cv-text">{stepTitles[step.id]}</p>
              <p
                className={cx(
                  "text-support font-medium",
                  step.status === "blocked"
                    ? "text-cv-blocker"
                    : step.status === "done"
                      ? "text-cv-success"
                      : "text-cv-text-muted",
                )}
              >
                {stepStatus(step, detail, content)}
              </p>
              <p className="mt-1 text-caption leading-5 text-cv-text-muted">{stepDescriptions[step.id]}</p>
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
};
