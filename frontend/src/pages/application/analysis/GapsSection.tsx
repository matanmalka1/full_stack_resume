import type { Classification } from "../../../api/analyses";
import { StatusBadge } from "../../../ui/StatusBadge";
import { cx } from "../../../ui/cx";
import { gapSeverityLabels } from "../analysisLabels";
import { AnalysisSection } from "./AnalysisSection";

type Gap = Classification["gaps"][number];

/* Absence of gaps is a finding, not an empty screen. Rendering nothing left the reader
   unable to tell "the analysis matched every requirement" from "the analysis never
   checked" - and the requirement lists elsewhere on this panel are derived from this same
   gap list (hard becomes mandatory, warning becomes preferred), so when it is empty all
   three sections say nothing about the candidate's coverage at once.

   Each gap reads as a line rather than a tile of its own: a severity-colored border does
   the same job a bordered, tinted card did, at a fraction of the chrome. The badge beside
   the requirement still names the severity in words for a reader who cannot rely on
   color alone (A.2). */
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

  return (
    <AnalysisSection title="פערים מול העובדות">
      <ul className="flex flex-col gap-3">
        {gaps.map((gap) => (
          <li
            className={cx("border-s-2 ps-3", gap.severity === "hard" ? "border-cv-blocker/50" : "border-cv-warning/50")}
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
              <p className="mt-1 text-support text-cv-text-muted" dir="auto">
                {gap.reason}
              </p>
            )}
          </li>
        ))}
      </ul>
    </AnalysisSection>
  );
};
