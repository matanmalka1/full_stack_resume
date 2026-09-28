import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";

import { type Requirement, selectionPlanQueryOptions } from "@/api/analyses";
import type { ApplicationDetail } from "@/api/contracts";
import { factsQueryOptions } from "@/api/facts";
import { candidateIncluded } from "../../model/factGroups";

export type EvidenceInclusion = "included" | "omitted" | "unknown";

export interface RequirementEvidence {
  error: unknown;
  inclusion: (factId: string) => EvidenceInclusion;
  label: (factId: string) => string;
  loading: boolean;
}

export const useRequirementEvidence = (
  detail: ApplicationDetail,
  requirements: readonly Requirement[],
): RequirementEvidence => {
  const cited = requirements.some(
    (requirement) => requirement.supportingFactIds.length > 0 || requirement.boundaryFactIds.length > 0,
  );
  const planId = detail.active_selection_plan_id ?? null;
  const factsQuery = useQuery({ ...factsQueryOptions(), enabled: cited });
  const planQuery = useQuery({ ...selectionPlanQueryOptions(planId ?? ""), enabled: cited && planId !== null });

  const meanings = useMemo(() => {
    const result = new Map<string, string>();
    for (const item of factsQuery.data?.items ?? []) {
      result.set(item.fact.fact_id, item.fact.meaning);
    }
    return result;
  }, [factsQuery.data]);

  const planIndex = useMemo(() => {
    const plan = planQuery.data;
    const index = new Map<string, { included: boolean; text: string | null }>();
    if (plan === undefined) {
      return index;
    }
    for (const candidate of plan.candidates) {
      index.set(candidate.fact_id, {
        included: candidateIncluded(candidate, plan.pinned_fact_ids, plan.excluded_fact_ids),
        text: candidate.text ?? null,
      });
    }
    return index;
  }, [planQuery.data]);

  return {
    error: factsQuery.error,
    inclusion: (factId) => {
      const entry = planIndex.get(factId);
      return entry === undefined ? "unknown" : entry.included ? "included" : "omitted";
    },
    label: (factId) =>
      meanings.get(factId) ?? planIndex.get(factId)?.text ?? `העובדה ${factId} אינה קיימת במאגר הנוכחי.`,
    loading: factsQuery.isLoading,
  };
};
