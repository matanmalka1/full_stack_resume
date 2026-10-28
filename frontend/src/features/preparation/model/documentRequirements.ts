import { type Requirement, classificationFromAnalysis } from "@/api/analyses";
import type { ApplicationDetail } from "@/api/contracts";

/* The requirements of the analysis the document is pinned to, or `null` when this client
   cannot read that analysis: the projection carries only the latest one, and once the
   document stands on an older analysis (`DOCUMENT_ON_OLDER_ANALYSIS`) the latest one's
   requirements are not the ones the backend compares the document with. Showing them
   anyway would mark coverage against the wrong posting. */
export const documentRequirements = (detail: ApplicationDetail): Requirement[] | null => {
  if (detail.document_analysis_id == null || detail.document_analysis_id !== detail.latest_analysis_id) {
    return null;
  }
  return classificationFromAnalysis(detail)?.requirements ?? null;
};
