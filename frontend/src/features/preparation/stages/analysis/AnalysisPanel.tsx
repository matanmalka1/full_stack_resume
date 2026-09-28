import type { ReactNode } from "react";

import type { Classification } from "@/api/analyses";
import type { ApplicationDetail } from "@/api/contracts";
import { surfaceClasses } from "@/ui/surface";
import { AnalysisHeader } from "./AnalysisHeader";
import { AnalysisNotes } from "./AnalysisNotes";
import { AnalysisOverview } from "./AnalysisOverview";
import { RequirementList } from "./RequirementList";
import { RoleSummary } from "./RoleSummary";

/* What the analysis concluded, read in the order a candidate checks it:

   1. what the role is (the analysis' own summary and the posting's keywords),
   2. how the approved facts cover it, split by mandatory and preferred asks,
   3. each requirement, with the facts that answer it and whether the CV carries them,
   4. folded at the foot, where the engine narrowed the reading.

   It reports the analysis and decides nothing. The classification it was built from -
   track, profile, emphasis, language - is not restated here: the matching configuration
   beside this panel shows those values as the controls that change them, and a second,
   read-only copy was one of the things that made the step read as cluttered. The fit
   verdict is the step banner's, for the same reason. */
export const AnalysisPanel = ({
  classification,
  detail,
  footer,
}: {
  classification: Classification;
  detail: ApplicationDetail;
  /* A last band inside the panel, for a control that acts on the analysis itself -
     re-running it. */
  footer?: ReactNode;
}) => (
  <section aria-labelledby="analysis-heading" className={surfaceClasses("bg-cv-surface p-5")}>
    <AnalysisHeader record={detail.latest_analysis ?? null} />

    <div className="flex flex-col divide-y divide-cv-border [&>*]:py-5 [&>*:last-child]:pb-0">
      <RoleSummary keywords={classification.keywords} summary={classification.summary} />

      <AnalysisOverview classification={classification} />

      {classification.requirements.length === 0 ? null : (
        <RequirementList detail={detail} gaps={classification.gaps} requirements={classification.requirements} />
      )}

      <AnalysisNotes
        issues={classification.issues}
        unreadableRequirementCount={classification.unreadableRequirementCount}
      />

      {footer === undefined ? null : <div>{footer}</div>}
    </div>
  </section>
);
