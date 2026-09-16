import type { AnalysisIssue } from "@/api/analyses";
import { analysisIssueLabel } from "../../model/analysisLabels";
import { AnalysisSection } from "./AnalysisSection";

/* Where the engine narrowed the provider's reading, and why. This is what answers "why does
   the analysis claim less than the posting seems to ask for": a citation dropped, a
   coverage lowered, a quote the stored posting does not carry. It explains and gates
   nothing.

   Repeated codes are collapsed with a count, because one line per occurrence would bury the
   one issue that matters under several of the same kind. */
export const IssuesSection = ({ issues }: { issues: AnalysisIssue[] }) => {
  if (issues.length === 0) {
    return null;
  }
  const counts = issues.reduce((result, issue) => {
    result.set(issue.code, (result.get(issue.code) ?? 0) + 1);
    return result;
  }, new Map<string, number>());

  return (
    <AnalysisSection title="איפה הקריאה צומצמה">
      <ul className="flex flex-col gap-1">
        {[...counts].map(([code, count]) => (
          <li className="text-support text-cv-text-muted" dir="auto" key={code}>
            {analysisIssueLabel(code)}
            {count > 1 ? ` (${count})` : null}
          </li>
        ))}
      </ul>
    </AnalysisSection>
  );
};
