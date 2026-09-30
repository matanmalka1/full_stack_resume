import type { Requirement, RequirementCoverage, RequirementImportance } from "@/api/analyses";

const importanceOrder: readonly RequirementImportance[] = ["mandatory", "preferred", "unknown"];

const coveragePriority: Record<RequirementCoverage, number> = {
  unsupported: 0,
  partial: 1,
  unknown: 2,
  matched: 3,
};

export const needsAttention = (requirement: Requirement): boolean => requirement.coverage !== "matched";

interface RequirementGroup {
  importance: RequirementImportance;
  /* Matched and total count the whole group, whatever the filter shows. */
  matched: number;
  requirements: Requirement[];
  total: number;
}

export type RequirementFilter = "all" | "attention" | "matched";

const passes = (requirement: Requirement, filter: RequirementFilter): boolean =>
  filter === "all" || (filter === "attention" ? needsAttention(requirement) : !needsAttention(requirement));

export const requirementGroups = (
  requirements: readonly Requirement[],
  filter: RequirementFilter = "all",
): RequirementGroup[] =>
  importanceOrder.flatMap((importance) => {
    const all = requirements.filter((requirement) => requirement.importance === importance);
    if (all.length === 0) {
      return [];
    }
    // oxlint-disable-next-line unicorn/no-array-sort
    const ordered = [...all].sort((left, right) => coveragePriority[left.coverage] - coveragePriority[right.coverage]);
    return [
      {
        importance,
        matched: all.filter((requirement) => !needsAttention(requirement)).length,
        requirements: ordered.filter((requirement) => passes(requirement, filter)),
        total: all.length,
      },
    ];
  });

export const requirementsByFact = (requirements: readonly Requirement[]): Map<string, Requirement[]> => {
  const index = new Map<string, Requirement[]>();
  for (const requirement of requirements) {
    for (const factId of requirement.supportingFactIds) {
      index.set(factId, [...(index.get(factId) ?? []), requirement]);
    }
  }
  return index;
};
