import type { Requirement, RequirementCoverage, RequirementImportance } from "@/api/analyses";

/* The analysis' requirements as the reader weighs them: by how much the employer insists
   on each one first, and by how well the approved facts answer it second.

   Grouping by importance rather than by coverage is what lets the page answer the
   question a candidate actually asks - "do I meet what they demand?" - in one glance per
   group. Within a group the requirements that need attention still lead. */

const importanceOrder: readonly RequirementImportance[] = ["mandatory", "preferred", "unknown"];

/* `unknown` sits between `partial` and `matched`: it is not evidence of a shortfall the
   way `unsupported`/`partial` are, but it is also not a settled `matched`. */
const coveragePriority: Record<RequirementCoverage, number> = {
  unsupported: 0,
  partial: 1,
  unknown: 2,
  matched: 3,
};

export const needsAttention = (requirement: Requirement): boolean => requirement.coverage !== "matched";

interface RequirementGroup {
  importance: RequirementImportance;
  matched: number;
  requirements: Requirement[];
  total: number;
}

export type RequirementFilter = "all" | "attention" | "matched";

const passes = (requirement: Requirement, filter: RequirementFilter): boolean =>
  filter === "all" || (filter === "attention" ? needsAttention(requirement) : !needsAttention(requirement));

/* Counts describe the whole group, not the filtered view: "2 מתוך 5 מכוסות" stays true
   while the reader narrows the list to the three that are not. */
export const requirementGroups = (
  requirements: readonly Requirement[],
  filter: RequirementFilter = "all",
): RequirementGroup[] =>
  importanceOrder.flatMap((importance) => {
    const all = requirements.filter((requirement) => requirement.importance === importance);
    if (all.length === 0) {
      return [];
    }
    // The spread already protects the input from mutation; ES2022 does not expose toSorted.
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

export const coverageCounts = (requirements: readonly Requirement[]): Record<RequirementCoverage, number> =>
  requirements.reduce(
    (result, requirement) => {
      result[requirement.coverage] += 1;
      return result;
    },
    { matched: 0, partial: 0, unsupported: 0, unknown: 0 } satisfies Record<RequirementCoverage, number>,
  );

/* Which requirements each fact is cited as evidence for. Read by the fact selection so a
   fact can say *which* demand it answers, not only that it answers one. Boundary facts are
   left out: they cap a requirement's coverage and are never support for it. */
export const requirementsByFact = (requirements: readonly Requirement[]): Map<string, Requirement[]> => {
  const index = new Map<string, Requirement[]>();
  for (const requirement of requirements) {
    for (const factId of requirement.supportingFactIds) {
      index.set(factId, [...(index.get(factId) ?? []), requirement]);
    }
  }
  return index;
};
