import { approvalReasonLabel } from "../analysisLabels";
import { AnalysisSection } from "./AnalysisSection";

/* Why the classification is not settled. The projection's review reason says that a
   decision is needed and carries the action; this says what about the analysis made it
   necessary, which is the part a person needs in order to decide rather than merely to
   be told to. */
export const ApprovalReasonsSection = ({ reasons }: { reasons: string[] }) => {
  if (reasons.length === 0) {
    return null;
  }

  return (
    <AnalysisSection title="מה מחייב החלטה">
      <ul className="flex flex-col gap-1">
        {reasons.map((reason) => (
          <li className="text-support text-cv-text-muted" dir="auto" key={reason}>
            {approvalReasonLabel(reason)}
          </li>
        ))}
      </ul>
    </AnalysisSection>
  );
};
