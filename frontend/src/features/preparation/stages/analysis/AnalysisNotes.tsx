import type { AnalysisIssue } from "@/api/analyses";
import { Disclosure } from "@/ui/Disclosure";
import { analysisIssueLabel, confidenceText } from "../../model/analysisLabels";

export const AnalysisNotes = ({
  issues,
  sourceCoverage,
  unreadableRequirementCount,
}: {
  issues: AnalysisIssue[];
  sourceCoverage: number | null;
  unreadableRequirementCount: number;
}) => {
  const counts = issues.reduce((result, issue) => {
    result.set(issue.code, (result.get(issue.code) ?? 0) + 1);
    return result;
  }, new Map<string, number>());
  /* Source anchoring is a reliability note only when some requirement was not found in the
     posting's wording; full anchoring has nothing to report. */
  const unanchored = sourceCoverage !== null && sourceCoverage < 1;
  const total = counts.size + (unreadableRequirementCount > 0 ? 1 : 0) + (unanchored ? 1 : 0);
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
          {unanchored ? <li>רק {confidenceText(sourceCoverage)} מהדרישות אותרו בנוסח המודעה.</li> : null}
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
