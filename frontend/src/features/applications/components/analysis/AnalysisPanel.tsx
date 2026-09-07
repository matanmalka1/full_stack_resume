import type { Classification } from "@/api/analyses";
import type { ApplicationDetail } from "@/api/contracts";
import { Disclosure } from "@/ui/Disclosure";
import { surfaceClasses } from "@/ui/Surface";
import { JobTextDisclosure } from "../JobTextDisclosure";
import { AnalysisHeader } from "./AnalysisHeader";
import { ApprovalReasonsSection } from "./ApprovalReasonsSection";
import { ClassificationSummary } from "./ClassificationSummary";
import { GapsSection } from "./GapsSection";
import { RationaleSection } from "./RationaleSection";
import { RequirementCoverageSection, RequirementCoverageSummary } from "./RequirementCoverageSection";
import { RequirementsSection } from "./RequirementsSection";

/* What the analysis concluded, on the Application screen rather than behind a route of
   its own: the analysis is the reasoning behind the stage this screen already reports,
   and a separate screen would ask the reader to leave the actions to read it.

   It reports the analysis and decides nothing. The one control it carries - marking a
   hard gap as accepted - is submitted by the decision panel below, in that panel's single
   request; overriding a classification stays there too, which the projection opens
   through `available_actions`. A second place that *commits* the same values would be the
   second workflow state machine A.1 forbids.

   The panel itself only composes: the masthead, the four findings below it, and the
   source text disclosure each live in their own file under this folder, so a change to
   one - a new gap presentation, a reworded rationale note - never touches the others.

   Findings are laid out with the same `divide-y` rhythm JobDetailsPage uses for its own
   top-level sections, rather than one uniform `gap-5` column: a hairline and real
   padding between each finding read as distinct bands instead of an unbroken scroll of
   same-weight blocks. Each finding renders as its own `<section>` (or nothing at all
   when it has no content), which is what the divider selector below is keyed to. */
export const AnalysisPanel = ({
  classification,
  detail,
  showGaps,
}: {
  classification: Classification;
  detail: ApplicationDetail;
  /* False while the projection is asking for a gap decision. The gaps are then shown
     with their acceptance controls beside the decision they answer, and drawing them
     here as well would be the same finding in two places - one of them read-only and
     one of them a control, which is worse than either alone. */
  showGaps: boolean;
}) => (
  <section aria-labelledby="analysis-heading" className={surfaceClasses("bg-cv-surface p-5")}>
    <AnalysisHeader classification={classification} record={detail.latest_analysis ?? null} />

    <div className="flex flex-col divide-y divide-cv-border [&>section]:py-5 [&>section:last-child]:pb-0">
      <ClassificationSummary classification={classification} />

      {classification.requirements.length === 0 && classification.unreadableRequirementCount === 0 ? null : (
        <RequirementCoverageSummary
          requirements={classification.requirements}
          unreadableRequirementCount={classification.unreadableRequirementCount}
        />
      )}

      <ApprovalReasonsSection reasons={classification.approvalReasons} />

      {showGaps ? <GapsSection acceptance={null} gaps={classification.gaps} /> : null}

      <section>
        <Disclosure summary="פרטי הניתוח והמקור">
          <div className="flex flex-col divide-y divide-cv-border [&>section]:py-4 [&>section:first-child]:pt-1">
            <RationaleSection rationale={classification.rationale} />
            {/* The full requirement picture - matched requirements included - once the
                analysis carries one. An analysis stored before requirement coverage
                existed carries no `requirements` at all, and falls back to the plain
                mandatory/preferred term lists it always had. */}
            {classification.requirements.length > 0 || classification.unreadableRequirementCount > 0 ? (
              <RequirementCoverageSection
                requirements={classification.requirements}
                unreadableRequirementCount={classification.unreadableRequirementCount}
              />
            ) : (
              <>
                <RequirementsSection items={classification.mandatoryRequirements} title="דרישות חובה שזוהו" />
                <RequirementsSection items={classification.preferredRequirements} title="דרישות מועדפות שזוהו" />
              </>
            )}
            <RequirementsSection items={classification.keywords} title="מילות מפתח מהמשרה" />
            <section>
              <JobTextDisclosure detail={detail} summary="הצגת נוסח המשרה שנותח" />
            </section>
          </div>
        </Disclosure>
      </section>
    </div>
  </section>
);
