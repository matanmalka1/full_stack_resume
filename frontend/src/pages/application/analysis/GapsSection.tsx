import type { Classification } from "../../../api/analyses";
import { Checkbox } from "../../../ui/Checkbox";
import { StatusBadge } from "../../../ui/StatusBadge";
import { cx } from "../../../ui/cx";
import { gapSeverityLabels } from "../analysisLabels";
import { AnalysisSection } from "./AnalysisSection";

type Gap = Classification["gaps"][number];

/* Marking a hard gap as knowingly accepted. Offered only while the projection is asking
   for that decision, which is why it arrives as an object rather than as three loose
   props: absent means the section is the read-only finding it has always been.

   The mark is taken here, on the gap the reader is looking at, while the reason, the
   commit, and the refusal stay with the decision panel below - where every other decision
   on this screen is submitted, in the one request the server takes them in. */
export interface GapAcceptance {
  disabled: boolean;
  onToggle: (requirementId: string) => void;
  selected: readonly string[];
}

/* Absence of gaps is a finding, not an empty screen. Rendering nothing left the reader
   unable to tell "the analysis matched every requirement" from "the analysis never
   checked" - and the requirement lists elsewhere on this panel are derived from this same
   gap list (hard becomes mandatory, warning becomes preferred), so when it is empty all
   three sections say nothing about the candidate's coverage at once.

   Each gap reads as a line rather than a tile of its own: a severity-colored border does
   the same job a bordered, tinted card did, at a fraction of the chrome. The badge beside
   the requirement still names the severity in words for a reader who cannot rely on
   color alone (A.2). */
export const GapsSection = ({ acceptance, gaps }: { acceptance: GapAcceptance | null; gaps: Gap[] }) => {
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
        {gaps.map((gap) => {
          const heading = (
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-support font-medium text-cv-text" dir="auto">
                {gap.requirement}
              </span>
              <StatusBadge tone={gap.severity === "hard" ? "blocker" : "warning"}>
                {gapSeverityLabels[gap.severity]}
              </StatusBadge>
            </div>
          );
          const reason =
            gap.reason === "" ? null : (
              <p className="mt-1 text-support text-cv-text-muted" dir="auto">
                {gap.reason}
              </p>
            );
          /* Only a hard gap blocks, so only a hard gap is accepted - and only one that
             names a Requirement, since that id is the whole of what an acceptance
             records. A hard gap without one comes from an analysis written before
             requirement extraction; it is named as such rather than given a control that
             the server would refuse. */
          const acceptableId = gap.severity === "hard" ? gap.requirementId : null;

          return (
            <li
              className={cx(
                "border-s-2 ps-3",
                gap.severity === "hard" ? "border-cv-blocker/50" : "border-cv-warning/50",
              )}
              key={`${gap.severity}:${gap.requirement}`}
            >
              {acceptance !== null && acceptableId !== null ? (
                /* The label is the gap plus what marking it does, so the control reads as
                   a decision about this requirement rather than as a checkbox with the gap
                   printed beside it. The decision it takes is named on the control itself:
                   a bare gap label left the mark looking like "this gap is handled", which
                   is the opposite of what it records. Its negative padding pulls the
                   primitive's own inset back to the border, keeping the marked and unmarked
                   lines on one edge. */
                <Checkbox
                  checked={acceptance.selected.includes(acceptableId)}
                  className="-ms-3 -my-2.5"
                  disabled={acceptance.disabled}
                  hint={
                    <>
                      <span className="block">
                        סימון = המשך ביודעין עם הפער. הוא אינו מכסה את הדרישה ואינו מתיר טענה שאין לה עובדה.
                      </span>
                      {gap.reason === "" ? null : (
                        <span className="mt-1 block" dir="auto">
                          {gap.reason}
                        </span>
                      )}
                    </>
                  }
                  onChange={() => acceptance.onToggle(acceptableId)}
                >
                  {heading}
                </Checkbox>
              ) : (
                <>
                  {heading}
                  {reason}
                  {acceptance !== null && gap.severity === "hard" ? (
                    <p className="mt-1 text-support text-cv-text-muted" dir="auto">
                      הפער הזה נרשם בניתוח שנעשה לפני חילוץ הדרישות, ולכן אין דרישה מזוהה לקבל אותה. ניתוח מחדש של המשרה
                      יזהה את הדרישה ויאפשר להכריע עליה.
                    </p>
                  ) : null}
                </>
              )}
            </li>
          );
        })}
      </ul>
    </AnalysisSection>
  );
};
