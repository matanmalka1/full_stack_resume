import { ErrorCallout } from "@/ui/ErrorCallout";
import { Callout } from "@/ui/Callout";
import type { DocumentCheckState } from "../hooks/useDocumentCheck";
import { ValidationReportView } from "./ValidationReportView";

interface DraftValidationPanelProps {
  check: DocumentCheckState;
}

/* A.4 frame 5's result, as a panel of the editor rather than a screen of its own.

   It draws the stored content report and says whether it still describes the document
   (§5 `content_check`). An outdated report is kept on screen - the reader can still see
   what it found - but it is marked as outdated and authorizes nothing. */
export const DraftValidationPanel = ({ check }: DraftValidationPanelProps) => {
  const { contentCheck, error, report, stale } = check;

  return (
    <section aria-labelledby="validation-summary" className="flex flex-col gap-3 border-t border-cv-border pt-4">
      <h2 className="text-heading-sm font-bold text-cv-text" id="validation-summary">
        {contentCheck === "passed"
          ? "הקובץ עבר בדיקה"
          : contentCheck === "failed"
            ? "נדרשים תיקונים בקובץ"
            : "בדיקת הקובץ"}
      </h2>

      {stale ? (
        <Callout title="הטיוטה השתנתה מאז הבדיקה" tone="warning">
          יש לבדוק מחדש את הגרסה הנוכחית לפני הכנת ה־PDF.
        </Callout>
      ) : null}

      {contentCheck === "outdated" && report !== null ? (
        <Callout title="תוצאת הבדיקה אינה מעודכנת" tone="warning">
          הטיוטה, או עובדה שהיא נשענת עליה, השתנתה מאז הבדיקה. התוצאה למטה מתארת את המצב הקודם; יש לבדוק מחדש לפני
          האישור.
        </Callout>
      ) : null}

      {error === null || error === undefined ? null : (
        <ErrorCallout error={error} fallbackDetail="אפשר לנסות שוב." title="בדיקת הקובץ לא הושלמה" />
      )}

      {report === null ? (
        <p className="text-support leading-6 text-cv-text-muted">
          הבדיקה תופעל מכפתור הכנת ה־PDF ותוודא שהגרסה המוצגת מוכנה למסירה.
        </p>
      ) : (
        <div className={contentCheck === "outdated" ? "opacity-70" : undefined}>
          <ValidationReportView report={report} />
        </div>
      )}
    </section>
  );
};
