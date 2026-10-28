import { classificationFromAnalysis } from "@/api/analyses";
import type { ApplicationDetail } from "@/api/contracts";

/* How far the posting's requirements are answered, read for the draft step from the
   analysis the projection already carries. */
export interface DraftFit {
  matched: number;
  total: number;
  /* The requirements the facts do not fully answer, demanded ones first. */
  gaps: { requirementId: string; requirement: string; severity: "hard" | "warning" }[];
}

/* `null` whenever the analysis is not the current posting's (see
   `classificationFromAnalysis`) or names no requirement: a ratio over nothing, or over a
   posting the Application no longer holds, would be a number about something else.

   `matched` counts only fully met requirements. A partial one is not a match, and it is
   named among the gaps instead, as the analysis step names it. */
export const draftFit = (detail: ApplicationDetail): DraftFit | null => {
  const classification = classificationFromAnalysis(detail);
  if (classification === null || classification.requirements.length === 0) return null;
  return {
    matched: classification.requirements.filter((requirement) => requirement.coverage === "matched").length,
    total: classification.requirements.length,
    gaps: [
      ...classification.gaps.filter((gap) => gap.severity === "hard"),
      ...classification.gaps.filter((gap) => gap.severity !== "hard"),
    ].map(({ requirementId, requirement, severity }) => ({ requirementId, requirement, severity })),
  };
};
