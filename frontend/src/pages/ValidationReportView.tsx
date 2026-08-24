import type { ValidationReport } from "../api/contracts";
import { Callout } from "../ui/Callout";
import { LtrText } from "../ui/LtrText";
import { SummaryList } from "../ui/SummaryList";
import { TechnicalDetails } from "../ui/TechnicalDetails";

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

  return (
    <div className="flex flex-col gap-4">
      {hard.map((issue, index) => (
        <Callout key={`${issue.code}-${index}`} title="חסימת אימות" tone="blocker">
          <p dir="auto">{issue.message}</p>
          <p className="mt-2">{blockerResolution(issue.code)}</p>
          <TechnicalDetails className="mt-3">
            <LtrText>{`${issue.group} · ${issue.code}`}</LtrText>
          </TechnicalDetails>
        </Callout>
      ))}
      {warnings.map((issue, index) => (
        <Callout key={`${issue.code}-${index}`} title="אזהרת אימות לא חוסמת" tone="warning">
          <p dir="auto">{issue.message}</p>
          <TechnicalDetails className="mt-3">
            <LtrText>{`${issue.group} · ${issue.code}`}</LtrText>
          </TechnicalDetails>
        </Callout>
      ))}
      {report.issues.length === 0 ? (
        <Callout title="לא נמצאו חסימות או אזהרות" tone="success" />
      ) : null}
      <TechnicalDetails summary="ראיות האימות">
        <SummaryList
          items={[
            ...Object.entries(report.groups).map(([group, passed]) => ({
              term: group,
              value: passed ? "עבר" : "לא עבר",
              ltr: true,
            })),
            {
              term: "Evidence",
              value: <pre className="overflow-auto text-support">{JSON.stringify(report.evidence, null, 2)}</pre>,
            },
          ]}
        />
      </TechnicalDetails>
    </div>
  );
};
