import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";

import { type Requirement, selectionPlanQueryOptions } from "@/api/analyses";
import type { ApplicationDetail } from "@/api/contracts";
import { factsQueryOptions } from "@/api/facts";
import { candidateIncluded } from "../../model/factGroups";

/* Whether a fact cited as evidence will actually appear in the CV, by the saved selection.
   "unknown" when there is no plan yet, or the plan never considered the fact. */
export type EvidenceInclusion = "included" | "omitted" | "unknown";

export interface RequirementEvidence {
  error: unknown;
  inclusion: (factId: string) => EvidenceInclusion;
  label: (factId: string) => string;
  loading: boolean;
}

/* The two things a requirement's evidence needs beyond the analysis itself: the current
   wording of each cited fact, and whether the active selection carries it into the CV.

   The analysis names evidence by id, not by text - a fact's wording can change after the
   analysis was written - so the wording is read from the facts store, falling back to the
   plan's own rendering. The plan is the same query the fact selection below reads, so the
   two panels never disagree about what "in the CV" means. Both reads are defensive: an id
   nothing resolves is named as such rather than hidden. */
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
    if (plan === undefined || !Array.isArray(plan.candidates)) {
      return index;
    }
    const pinned = Array.isArray(plan.pinned_fact_ids) ? plan.pinned_fact_ids : [];
    const excluded = Array.isArray(plan.excluded_fact_ids) ? plan.excluded_fact_ids : [];
    for (const candidate of plan.candidates) {
      index.set(candidate.fact_id, {
        included: candidateIncluded(candidate, pinned, excluded),
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
