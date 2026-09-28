import type { AnalysisIssue } from "@/api/analyses";
import { Disclosure } from "@/ui/Disclosure";
import { analysisIssueLabel } from "../../model/analysisLabels";

export const AnalysisNotes = ({
  issues,
  unreadableRequirementCount,
}: {
  issues: AnalysisIssue[];
  unreadableRequirementCount: number;
}) => {
  const counts = issues.reduce((result, issue) => {
    result.set(issue.code, (result.get(issue.code) ?? 0) + 1);
    return result;
  }, new Map<string, number>());
  const total = counts.size + (unreadableRequirementCount > 0 ? 1 : 0);
  if (total === 0) {
    return null;
  }

  return (
    <section>
      <Disclosure summary={`הערות על אמינות הניתוח (${total})`}>
        <ul className="flex list-disc flex-col gap-1 ps-4">
          {unreadableRequirementCount === 0 ? null : (
            <li>
              {unreadableRequirementCount === 1
                ? "דרישה אחת לא הייתה תקינה ואינה מוצגת."
                : `${unreadableRequirementCount} דרישות לא היו תקינות ואינן מוצגות.`}
            </li>
          )}
          {[...counts].map(([code, count]) => (
            <li dir="auto" key={code}>
              {analysisIssueLabel(code)}
              {count > 1 ? ` (${count})` : null}
            </li>
          ))}
        </ul>
      </Disclosure>
    </section>
  );
};
