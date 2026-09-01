import type { Classification } from "../../../api/analyses";
import { StatusBadge } from "../../../ui/StatusBadge";
import { fitDescriptions, fitIcons, fitLabels, fitTones } from "../analysisLabels";

/* Confidence is a 0..1 float in the document and a percentage to a reader.

   The sign is the Hebrew-side one and the whole value is written into the sentence rather
   than wrapped in an A.3 LTR island. An island is for a Latin run that must not be
   reordered - an id, a code, a filename. A percentage is a number in a Hebrew sentence,
   and isolating it pushed the run to the end of the line, so "58%" arrived on screen
   reading "%58". */
const confidenceText = (confidence: number): string => `${Math.round(confidence * 100)}%`;

/* The panel's masthead: what section this is, and the verdict that governs everything
   below it. The fit badge carries `fitIcons` - the same signal-strength mark the
   Application board already shows next to this same fit level - so the verdict reads as
   a point on a low/medium/high scale before the word beside it is even read (A.2: color
   is never the only signal, and here neither is the icon alone).

   Confidence qualifies the fit, so it is read with it rather than lower on the page: the
   two are reported independently - a classification may carry a confidence without a fit
   - so the badge and the number stay two elements that happen to sit together, not one
   that would drop the confidence in exactly that case. */
export const AnalysisHeader = ({ classification }: { classification: Classification }) => (
  <div className="border-b border-cv-border pb-4">
    <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-3">
      <h2 className="text-body font-semibold text-cv-text" id="analysis-heading">
        ניתוח המשרה
      </h2>

      {classification.fit === null && classification.confidence === null ? null : (
        <div className="flex flex-wrap items-center gap-2">
          {classification.fit === null ? null : (
            <StatusBadge icon={fitIcons[classification.fit]} tone={fitTones[classification.fit]}>
              {fitLabels[classification.fit]}
            </StatusBadge>
          )}
          {classification.confidence === null ? null : (
            <span className="text-support text-cv-text-muted">
              ברמת ביטחון {confidenceText(classification.confidence)}
            </span>
          )}
        </div>
      )}
    </div>

    {/* The badge names one of three levels; without the scale behind it "high" reads as
        praise rather than as a value, and the reader cannot tell what a different verdict
        would have meant for the same button. The sentence says what this level means for
        the workflow, which is the part that decides whether to press on. */}
    {classification.fit === null ? null : (
      <p className="mt-3 text-support leading-6 text-cv-text-muted" dir="auto">
        {fitDescriptions[classification.fit]}
      </p>
    )}
  </div>
);
