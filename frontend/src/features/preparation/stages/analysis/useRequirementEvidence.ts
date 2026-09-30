import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";

import type { Requirement } from "@/api/analyses";
import type { ApplicationDetail } from "@/api/contracts";
import { documentQueryOptions } from "@/api/documents";
import { factsQueryOptions } from "@/api/facts";

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
  /* Whether a cited fact is in the CV is the drafted content's answer; before a draft
     nothing is decided yet. */
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

  const used = useMemo(() => {
    const document = documentQuery.data?.document;
    if (document?.content == null) {
      return null;
    }
    return new Map((document.facts ?? []).map((fact) => [fact.fact_id, fact.text ?? null]));
  }, [documentQuery.data]);

  return {
    error: factsQuery.error,
    inclusion: (factId) => (used === null ? "unknown" : used.has(factId) ? "included" : "omitted"),
    /* The evidence sits behind each row's disclosure, so loading is stated there, per fact,
       rather than as a banner over the whole list - and never as a missing fact. */
    label: (factId) =>
      meanings.get(factId) ??
      used?.get(factId) ??
      (factsQuery.isLoading ? "טוען…" : `העובדה ${factId} אינה קיימת במאגר הנוכחי.`),
  };
};
