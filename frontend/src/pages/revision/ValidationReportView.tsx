import { CircleCheck, ShieldAlert, TriangleAlert } from "lucide-react";

import type { ValidationReport } from "../../api/contracts";
import { Callout } from "../../ui/Callout";

const blockerResolution = (code: string): string => {
  if (code === "unlinked-claim" || code === "pending-claim") {
    return "חזרו לעריכה וקשרו את הטענה לעובדה מאושרת, השלימו את מחזור אישור העובדה, או הסירו את הטענה; לאחר מכן הריצו אימות מחדש.";
  }
  if (code === "low-fit" || code === "classification-approval-required") {
    return "חזרו למסך המועמדות והשלימו את החלטת הסקירה הנדרשת לפני אימות מחדש.";
  }
  return "חזרו לעריכה, תקנו את הבעיה המתוארת והריצו אימות מחדש. האישור נשאר חסום עד לאימות שעובר.";
};

export const ValidationReportView = ({ report }: { report: ValidationReport }) => {
  const hard = report.issues.filter((issue) => issue.hard);
  const warnings = report.issues.filter((issue) => !issue.hard);
  const passedGroups = Object.values(report.groups).filter(Boolean).length;

  return (
    <div className="flex flex-col gap-4">
      <div className="grid gap-3 sm:grid-cols-3">
        <div className="rounded-surface border border-cv-success/25 bg-cv-success-soft p-4 shadow-surface">
          <CircleCheck aria-hidden="true" className="size-5 text-cv-success" />
          <p className="mt-3 text-heading-md font-bold text-cv-text">{passedGroups}</p>
          <p className="text-support font-medium text-cv-success">קבוצות שעברו</p>
        </div>
        <div className="rounded-surface border border-cv-blocker/25 bg-cv-blocker-soft p-4 shadow-surface">
          <ShieldAlert aria-hidden="true" className="size-5 text-cv-blocker" />
          <p className="mt-3 text-heading-md font-bold text-cv-text">{hard.length}</p>
          <p className="text-support font-medium text-cv-blocker">חסימות</p>
        </div>
        <div className="rounded-surface border border-cv-warning/25 bg-cv-warning-soft p-4 shadow-surface">
          <TriangleAlert aria-hidden="true" className="size-5 text-cv-warning" />
          <p className="mt-3 text-heading-md font-bold text-cv-text">{warnings.length}</p>
          <p className="text-support font-medium text-cv-warning">אזהרות</p>
        </div>
      </div>
      {hard.map((issue, index) => (
        <Callout key={`${issue.code}-${index}`} title="חסימת אימות" tone="blocker">
          <p dir="auto">{issue.message}</p>
          <p className="mt-2">{blockerResolution(issue.code)}</p>
        </Callout>
      ))}
      {warnings.map((issue, index) => (
        <Callout key={`${issue.code}-${index}`} title="אזהרת אימות לא חוסמת" tone="warning">
          <p dir="auto">{issue.message}</p>
        </Callout>
      ))}
      {report.issues.length === 0 ? (
        <Callout title="לא נמצאו חסימות או אזהרות" tone="success" />
      ) : null}
    </div>
  );
};
