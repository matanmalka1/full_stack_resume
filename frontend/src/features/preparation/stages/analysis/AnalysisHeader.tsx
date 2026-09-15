import type { Classification } from "@/api/analyses";
import type { JobAnalysisRecord } from "@/api/contracts";
import { LtrText } from "@/ui/LtrText";
import { StatusBadge } from "@/ui/StatusBadge";
import { formatDateTime } from "@/utils/formatDateTime";
import { fitLabels, fitTones } from "../../model/analysisLabels";

/* Which run produced this analysis, and when - the record's own provenance rather than
   anything the analysis document itself claims about itself. Every analysis is an AI run
   now, so the model id is what distinguishes one from another and is always shown. */
const Provenance = ({ record }: { record: JobAnalysisRecord | null }) =>
  record === null ? null : (
    <p className="mt-1 text-support text-cv-text-muted" dir="auto">
      נותח על ידי AI (<LtrText>{record.model}</LtrText>) · {formatDateTime(record.created_at)}
      {record.version_number <= 1 ? null : ` · ניתוח מס' ${record.version_number}`}
    </p>
  );

/* The panel's masthead: what section this is, and the verdict that governs everything
   below it. The fit badge keeps the tone's own icon rather than a fit-specific one - a
   signal-strength mark next to a badge that already states the level in words repeated
   the same fact twice without adding anything a reader could act on.

   Confidence qualifies the fit, so it is read with it rather than lower on the page: the
   two are reported independently - a classification may carry a confidence without a fit
   - so the badge and the number stay two elements that happen to sit together, not one
   that would drop the confidence in exactly that case. */
export const AnalysisHeader = ({
  classification,
  record,
}: {
  classification: Classification;
  record: JobAnalysisRecord | null;
}) => (
  <div className="border-b border-cv-border pb-4">
    <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-3">
      <h2 className="text-body font-semibold text-cv-text" id="analysis-heading">
        ניתוח המשרה
      </h2>

      {/* Confidence is read with the classification tiles below, not here: the two are
          reported independently by the analysis, but a number repeated beside the fit
          badge and again in its own tile a few lines down is one figure shown twice. */}
      {classification.fit === null ? null : (
        <StatusBadge tone={fitTones[classification.fit]}>{fitLabels[classification.fit]}</StatusBadge>
      )}
    </div>

    {/* What the level means for the workflow is said once, in the status banner at the
        top of the screen. It stood here as well, and a third time in the decision panel's
        preamble - three copies of one sentence, each far enough from the others that a
        reader met it as new information every time. */}
    <Provenance record={record} />
  </div>
);
