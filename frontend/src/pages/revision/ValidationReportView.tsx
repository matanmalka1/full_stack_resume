import { CircleCheck, ShieldAlert, TriangleAlert } from "lucide-react";

import type { ValidationReport } from "../../api/contracts";
import { Callout } from "../../ui/Callout";
import { StatusBadge } from "../../ui/StatusBadge";

const blockerResolution = (code: string): string => {
  if (code === "unlinked-claim" || code === "pending-claim") {
    return "חזרו לעריכה וקשרו את הטענה לעובדה מאושרת, השלימו את מחזור אישור העובדה, או הסירו את הטענה; לאחר מכן הריצו אימות מחדש.";
  }
  if (
    code === "low-fit" ||
    code === "classification-approval-required" ||
    code === "incomplete-analysis-not-accepted"
  ) {
    return "חזרו למסך המועמדות והשלימו את החלטת הסקירה הנדרשת לפני אימות מחדש.";
  }
  return "חזרו לעריכה, תקנו את הבעיה המתוארת והריצו אימות מחדש. האישור נשאר חסום עד לאימות שעובר.";
};

/* Three counts, on one line rather than in three cards.

   They were stat tiles the height of a paragraph each, stacked above the issues that
   actually say what to fix - so a report with one blocker opened with three large cards
   carrying three numbers, and the blocker itself was below the fold. The numbers are a
   summary of the list under them, not findings of their own: a chip is the right size for
   a summary. The icons stay, so the three counts are still separable without colour
   (A.2). */
export const ValidationReportView = ({ report }: { report: ValidationReport }) => {
  const hard = report.issues.filter((issue) => issue.hard);
  const warnings = report.issues.filter((issue) => !issue.hard);
  const passedGroups = Object.values(report.groups).filter(Boolean).length;

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap gap-2">
        <StatusBadge className="gap-1.5 px-2.5" icon={CircleCheck} tone="success">
          {passedGroups} קבוצות עברו
        </StatusBadge>
        <StatusBadge className="gap-1.5 px-2.5" icon={ShieldAlert} tone="blocker">
          {hard.length} חסימות
        </StatusBadge>
        <StatusBadge className="gap-1.5 px-2.5" icon={TriangleAlert} tone="warning">
          {warnings.length} אזהרות
        </StatusBadge>
      </div>

      {/* Blockers in full: each is a thing to go and fix, and its resolution line is the
          only text on the screen that says how. */}
      {hard.map((issue, index) => (
        <Callout key={`${issue.code}-${index}`} title="חסימת אימות" tone="blocker">
          <p dir="auto">{issue.message}</p>
          <p className="mt-2">{blockerResolution(issue.code)}</p>
        </Callout>
      ))}

      {/* Warnings block nothing, so they are folded away behind their own count rather
          than printing one full-width callout each above the approval control. A single
          warning is the common case and stays worth one line, so the fold opens for it
          too - closed, it is one row instead of one card. */}
      {warnings.length === 0 ? null : (
        <details className="rounded-control border border-cv-warning/25 bg-cv-warning-soft px-3 py-2">
          <summary className="cursor-pointer text-support font-semibold text-cv-warning">
            {warnings.length} אזהרות שאינן חוסמות אישור
          </summary>
          <ul className="mt-2 flex flex-col gap-1.5">
            {warnings.map((issue, index) => (
              <li className="text-support leading-6 text-cv-text" dir="auto" key={`${issue.code}-${index}`}>
                {issue.message}
              </li>
            ))}
          </ul>
        </details>
      )}

      {report.issues.length === 0 ? (
        <p className="text-support leading-6 text-cv-success">לא נמצאו חסימות או אזהרות.</p>
      ) : null}
    </div>
  );
};
