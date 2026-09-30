import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";

import type { Requirement } from "@/api/analyses";
import type { ApplicationDetail } from "@/api/contracts";
import { documentQueryOptions } from "@/api/documents";
import { factsQueryOptions } from "@/api/facts";
import { candidateIncluded } from "../../model/factGroups";

type EvidenceInclusion = "included" | "omitted" | "unknown";

export interface RequirementEvidence {
  error: unknown;
  inclusion: (factId: string) => EvidenceInclusion;
  label: (factId: string) => string;
}

export const useRequirementEvidence = (
  detail: ApplicationDetail,
  requirements: readonly Requirement[],
): RequirementEvidence => {
  const cited = requirements.some(
    (requirement) => requirement.supportingFactIds.length > 0 || requirement.boundaryFactIds.length > 0,
  );
  /* Whether a cited fact is in the CV is the document's selection's answer. */
  const hasDocument = detail.document_id != null;
  const factsQuery = useQuery({ ...factsQueryOptions(), enabled: cited });
  const documentQuery = useQuery({
    ...documentQueryOptions(detail.application.id),
    enabled: cited && hasDocument,
  });

  const meanings = useMemo(() => {
    const result = new Map<string, string>();
    for (const item of factsQuery.data?.items ?? []) {
      result.set(item.fact.fact_id, item.fact.meaning);
    }
    return result;
  }, [factsQuery.data]);

  const planIndex = useMemo(() => {
    const selection = documentQuery.data?.document.selection;
    const index = new Map<string, { included: boolean; text: string | null }>();
    if (selection === undefined) {
      return index;
    }
    for (const candidate of selection.candidates) {
      index.set(candidate.fact_id, {
        included: candidateIncluded(candidate, selection.pinned_fact_ids, selection.excluded_fact_ids),
        text: candidate.text ?? null,
      });
    }
    return index;
  }, [documentQuery.data]);

  return {
    error: factsQuery.error,
    inclusion: (factId) => {
      const entry = planIndex.get(factId);
      return entry === undefined ? "unknown" : entry.included ? "included" : "omitted";
    },
    /* The evidence sits behind each row's disclosure, so loading is stated there, per fact,
       rather than as a banner over the whole list - and never as a missing fact. */
    label: (factId) =>
      meanings.get(factId) ??
      planIndex.get(factId)?.text ??
      (factsQuery.isLoading ? "טוען…" : `העובדה ${factId} אינה קיימת במאגר הנוכחי.`),
  };
};
