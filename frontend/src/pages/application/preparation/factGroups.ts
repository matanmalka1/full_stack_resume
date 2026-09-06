import type { SelectionPlanCandidate } from "../../../api/contracts";

/* Whether a candidate is on its way into the CV, as the screen currently stands.

   Three things decide it, in this order: an exclusion the reader placed, a pin the reader
   placed, and - where the reader placed neither - the outcome the engine recorded. The
   two overrides are independent decisions laid over a computed outcome, which is why this
   is a derivation rather than a stored flag: nothing here is sent to the server, and the
   pinned/excluded lists remain exactly what the plan is rebuilt from. */
export const candidateIncluded = (
  candidate: SelectionPlanCandidate,
  pinned: readonly string[],
  excluded: readonly string[],
): boolean => {
  if (excluded.includes(candidate.fact_id)) {
    return false;
  }
  if (pinned.includes(candidate.fact_id)) {
    return true;
  }
  return candidate.outcome !== "omitted";
};

/* A structural component of the document - a role heading, a date line - rather than a
   claim. The plan ranked it like anything else, but excluding it would delete a heading,
   so the server refuses the attempt and the row carries no override controls at all. */
export const candidateLocked = (candidate: SelectionPlanCandidate): boolean => !candidate.user_selectable;

export interface FactGroup {
  included: number;
  items: SelectionPlanCandidate[];
  locked: number;
  section: string;
  total: number;
}

export interface FactTotals {
  excluded: number;
  included: number;
  locked: number;
  total: number;
}

const matches = (candidate: SelectionPlanCandidate, needle: string): boolean =>
  needle === "" ||
  (candidate.text ?? "").toLowerCase().includes(needle) ||
  candidate.section.toLowerCase().includes(needle);

/* The plan's candidates as the CV reads them: one group per section, in the order the
   plan listed them, so the reader recognises the document rather than a flat list of 27
   sentences. The section string is the Profile's own English section name; it is not
   translated here, since the set is open and a guessed Hebrew name would be a fact this
   screen invented. */
export const factGroups = (
  candidates: readonly SelectionPlanCandidate[],
  pinned: readonly string[],
  excluded: readonly string[],
  query: string,
): FactGroup[] => {
  const needle = query.trim().toLowerCase();
  const groups = new Map<string, FactGroup>();

  for (const candidate of candidates) {
    if (!matches(candidate, needle)) {
      continue;
    }
    const group = groups.get(candidate.section) ?? {
      included: 0,
      items: [],
      locked: 0,
      section: candidate.section,
      total: 0,
    };
    group.items.push(candidate);
    group.total += 1;
    if (candidateIncluded(candidate, pinned, excluded)) {
      group.included += 1;
    }
    if (candidateLocked(candidate)) {
      group.locked += 1;
    }
    groups.set(candidate.section, group);
  }

  return [...groups.values()];
};

export const factTotals = (
  candidates: readonly SelectionPlanCandidate[],
  pinned: readonly string[],
  excluded: readonly string[],
): FactTotals => {
  const included = candidates.filter((candidate) => candidateIncluded(candidate, pinned, excluded)).length;

  return {
    excluded: candidates.length - included,
    included,
    locked: candidates.filter(candidateLocked).length,
    total: candidates.length,
  };
};

/* Which facts of a group a "כלול הכל" would actually change: the selectable ones that are
   not on their way in as things stand. A group with none is offered no bulk action, since
   pressing it would send the same plan back. */
export const includableFactIds = (group: FactGroup, pinned: readonly string[], excluded: readonly string[]): string[] =>
  group.items
    .filter(
      (candidate) =>
        !candidateLocked(candidate) && candidate.text != null && !candidateIncluded(candidate, pinned, excluded),
    )
    .map((candidate) => candidate.fact_id);
