import type { ReactNode } from "react";

import type { Classification } from "@/api/analyses";
import type { ApplicationDetail } from "@/api/contracts";
import { surfaceClasses } from "@/ui/surface";
import { AnalysisHeader } from "./AnalysisHeader";
import { AnalysisNotes } from "./AnalysisNotes";
import { AnalysisOverview } from "./AnalysisOverview";
import { RequirementList } from "./RequirementList";
import { RoleSummary } from "./RoleSummary";

export const AnalysisPanel = ({
  classification,
  detail,
  footer,
}: {
  classification: Classification;
  detail: ApplicationDetail;
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
