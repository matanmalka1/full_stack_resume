import type { Classification } from "../../../api/analyses";
import type { ApplicationDetail } from "../../../api/contracts";
import { JobTextDisclosure } from "../JobTextDisclosure";
import { AnalysisHeader } from "./AnalysisHeader";
import { ApprovalReasonsSection } from "./ApprovalReasonsSection";
import { ClassificationSummary } from "./ClassificationSummary";
import { GapsSection } from "./GapsSection";
import { RationaleSection } from "./RationaleSection";
import { RequirementsSection } from "./RequirementsSection";

/* What the analysis concluded, on the Application screen rather than behind a route of
   its own: the analysis is the reasoning behind the stage this screen already reports,
   and a separate screen would ask the reader to leave the actions to read it.

   It reports the analysis and offers nothing. Overriding a classification stays the
   review screen's, which the projection opens through `available_actions` - a second
   place to change the same values would be the second workflow state machine A.1
   forbids.

   The panel itself only composes: the masthead, the four findings below it, and the
   source text disclosure each live in their own file under this folder, so a change to
   one - a new gap presentation, a reworded rationale note - never touches the others. */
export const AnalysisPanel = ({
  classification,
  detail,
}: {
  classification: Classification;
  detail: ApplicationDetail;
}) => (
  <section aria-labelledby="analysis-heading" className="rounded-surface border border-cv-border p-5">
    <AnalysisHeader classification={classification} />

    <div className="mt-4 flex flex-col gap-5">
      <ClassificationSummary classification={classification} />

      <ApprovalReasonsSection reasons={classification.approvalReasons} />

      <RationaleSection rationale={classification.rationale} />

      <RequirementsSection items={classification.mandatoryRequirements} title="דרישות חובה שזוהו" />

      <RequirementsSection
        items={classification.preferredRequirements}
        title="דרישות מועדפות שזוהו"
      />

      <RequirementsSection items={classification.keywords} title="מילות מפתח מהמשרה" />

      <GapsSection gaps={classification.gaps} />

      {/* The text the classification was drawn from, under the classification itself.
          Everything above is conclusion; without the posting on the same screen the
          only way to check a verdict against its source was to leave the screen the
          decision is taken on. Collapsed, because it is the source and not the
          finding. */}
      <JobTextDisclosure detail={detail} summary="הצגת נוסח המשרה שנותח" />
    </div>
  </section>
);
