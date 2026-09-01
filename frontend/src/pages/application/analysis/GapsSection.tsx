import type { Classification } from "../../../api/analyses";
import { StatusBadge } from "../../../ui/StatusBadge";
import { gapSeverityLabels } from "../analysisLabels";
import { AnalysisSection } from "./AnalysisSection";

type Gap = Classification["gaps"][number];

const countBySeverity = (gaps: Gap[], severity: Gap["severity"]): number =>
  gaps.filter((gap) => gap.severity === severity).length;

/* Absence of gaps is a finding, not an empty screen. Rendering nothing left the reader
   unable to tell "the analysis matched every requirement" from "the analysis never
   checked" - and the requirement lists elsewhere on this panel are derived from this same
   gap list (hard becomes mandatory, warning becomes preferred), so when it is empty all
   three sections say nothing about the candidate's coverage at once.

   When there are gaps, a count by severity sits above the list: the list itself keeps the
   analysis's own order, but a reader deciding whether to press on wants "how many are
   blocking" before "which ones", and the counts answer that without reordering the list
   under them. */
export const GapsSection = ({ gaps }: { gaps: Gap[] }) => {
  if (gaps.length === 0) {
    return (
      <AnalysisSection title="פערים מול העובדות">
        <p className="text-support leading-6 text-cv-text-muted" dir="auto">
          הניתוח לא מצא דרישה שאין לה כיסוי בעובדות המועמד. לכן גם רשימות דרישות החובה והדרישות המועדפות ריקות — הן
          נגזרות מאותם פערים.
        </p>
      </AnalysisSection>
    );
  }

  const hardCount = countBySeverity(gaps, "hard");
  const warningCount = countBySeverity(gaps, "warning");

  return (
    <AnalysisSection title="פערים מול העובדות">
      <div className="mb-3 flex flex-wrap gap-2">
        {hardCount === 0 ? null : (
          <StatusBadge tone="blocker">{`${gapSeverityLabels.hard} · ${hardCount}`}</StatusBadge>
        )}
        {warningCount === 0 ? null : (
          <StatusBadge tone="warning">{`${gapSeverityLabels.warning} · ${warningCount}`}</StatusBadge>
        )}
      </div>

      <ul className="flex flex-col gap-3">
        {gaps.map((gap) => (
          <li
            className="rounded-surface border border-cv-border bg-cv-surface-muted p-3"
            key={`${gap.severity}:${gap.requirement}`}
          >
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-support font-medium text-cv-text" dir="auto">
                {gap.requirement}
              </span>
              <StatusBadge tone={gap.severity === "hard" ? "blocker" : "warning"}>
                {gapSeverityLabels[gap.severity]}
              </StatusBadge>
            </div>
            {gap.reason === "" ? null : (
              <p className="mt-2 text-support text-cv-text-muted" dir="auto">
                {gap.reason}
              </p>
            )}
          </li>
        ))}
      </ul>
    </AnalysisSection>
  );
};
