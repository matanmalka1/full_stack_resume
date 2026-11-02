import type { ReactNode } from "react";

import type { Classification } from "@/api/analyses";
import type { ApplicationDetail } from "@/api/contracts";
import { surfaceClasses } from "@/ui/surface";
import { AnalysisHeader } from "./AnalysisHeader";
import { AnalysisNotes } from "./AnalysisNotes";
import { GapQuestionsSection } from "./gaps/GapQuestionsSection";
import { RequirementList } from "./RequirementList";
import { RoleSummary } from "./RoleSummary";

export const AnalysisPanel = ({
  classification,
  detail,
  footer,
  headerContent,
}: {
  classification: Classification;
  detail: ApplicationDetail;
  footer?: ReactNode;
  /* Controls about how the analysis was produced, shown under its heading. */
  headerContent?: ReactNode;
}) => (
  <section aria-labelledby="analysis-heading" className={surfaceClasses("bg-cv-surface p-5 max-lg:p-4")}>
    <AnalysisHeader record={detail.latest_analysis ?? null}>{headerContent}</AnalysisHeader>

    <div className="flex flex-col divide-y divide-cv-border [&>*]:py-5 [&>*:last-child]:pb-0">
      <RoleSummary summary={classification.summary} />

      {classification.requirements.length === 0 ? null : (
        <RequirementList detail={detail} gaps={classification.gaps} requirements={classification.requirements} />
      )}

      <GapQuestionsSection detail={detail} profile={classification.profile} />

      <AnalysisNotes
        issues={classification.issues}
        sourceCoverage={classification.sourceCoverage}
        unreadableRequirementCount={classification.unreadableRequirementCount}
      />

      {footer === undefined ? null : <div>{footer}</div>}
    </div>
  </section>
);
