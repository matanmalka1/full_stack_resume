import type { Classification } from "@/api/analyses";
import { StatusBadge } from "@/ui/StatusBadge";
import { cx } from "@/ui/cx";
import { gapSeverityLabels } from "../../model/analysisLabels";
import { AnalysisSection } from "./AnalysisSection";

type Gap = Classification["gaps"][number];

/* What the posting asks for that the candidate's facts do not fully answer. A finding to
   read, not a decision to take: a hard gap marks a demanded requirement the facts do not
   support, and the user may still draft, approve and apply. There used to be a control
   here for "proceeding knowingly" past each hard gap; there is nothing to proceed past now,
   so the section only reports.

   Absence of gaps is a finding too, not an empty screen: rendering nothing left the reader
   unable to tell "the analysis matched every requirement" from "the analysis never
   checked".

   Each gap reads as a line rather than a tile of its own: a severity-colored border does
   the same job a bordered, tinted card did, at a fraction of the chrome. The badge beside
   the requirement still names the severity in words for a reader who cannot rely on color
   alone (A.2). */
export const GapsSection = ({ gaps }: { gaps: Gap[] }) => {
  if (gaps.length === 0) {
    return (
      <AnalysisSection title="פערים מול העובדות">
        <p className="text-support leading-6 text-cv-text-muted" dir="auto">
          הניתוח לא מצא דרישה שאין לה כיסוי בעובדות המועמד.
        </p>
      </AnalysisSection>
    );
  }

  return (
    <AnalysisSection title="פערים מול העובדות">
      <ul className="flex flex-col gap-3">
        {gaps.map((gap) => (
          <li
            className={cx("border-s-2 ps-3", gap.severity === "hard" ? "border-cv-warning/60" : "border-cv-border")}
            key={gap.requirementId}
          >
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-support font-medium text-cv-text" dir="auto">
                {gap.requirement}
              </span>
              {/* Warning, not blocker: a hard gap is serious and stops nothing. The blocker
                  tone is reserved for what the reader cannot act their way past. */}
              <StatusBadge tone={gap.severity === "hard" ? "warning" : "neutral"}>
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
