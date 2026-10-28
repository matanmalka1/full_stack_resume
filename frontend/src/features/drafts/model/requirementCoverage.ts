import type { Requirement, RequirementImportance } from "@/api/analyses";
import { type DocumentOutline, outlineClaims } from "@/api/documents";

/* Where one requirement of the analysis stands in the draft on screen.

   - `in_document`: at least one of its supporting facts is linked by a line of the draft.
   - `not_in_document`: it lists supporting facts and the draft links none of them - the
     backend's `REQUIREMENT_NOT_IN_DOCUMENT` signal, read off the unsaved draft as well.
   - `no_facts`: the analysis found no fact supporting it, so no line could evidence it.

   One supporting fact linked is enough, exactly as the backend counts it; nothing here
   matches words or scores wording. */
export type RequirementDocumentState = "in_document" | "not_in_document" | "no_facts";

interface RequirementCoverageRow {
  requirement: Requirement;
  state: RequirementDocumentState;
  /* The same predicate the backend warns on: a mandatory requirement the analysis
     covered (matched or partial) whose supporting facts the draft no longer links. */
  warned: boolean;
}

export interface RequirementCoverageSummary {
  rows: RequirementCoverageRow[];
  inDocument: number;
  /* Requirements that list supporting facts at all; `inDocument` is out of this. */
  evidenced: number;
  warned: number;
}

const statePriority: Record<RequirementDocumentState, number> = {
  not_in_document: 0,
  no_facts: 1,
  in_document: 2,
};

const importancePriority: Record<RequirementImportance, number> = {
  mandatory: 0,
  preferred: 1,
  unknown: 2,
};

/* Every fact a line of the draft links, headline and contacts included - the backend's
   `dependent_fact_ids`. */
const linkedFactIds = (outline: DocumentOutline): Set<string> =>
  new Set(outlineClaims(outline).flatMap((claim) => claim.fact_ids));

const requirementDocumentState = (
  requirement: Requirement,
  linked: ReadonlySet<string>,
): RequirementDocumentState =>
  requirement.supportingFactIds.length === 0
    ? "no_facts"
    : requirement.supportingFactIds.some((factId) => linked.has(factId))
      ? "in_document"
      : "not_in_document";

export const requirementCoverage = (
  requirements: readonly Requirement[],
  outline: DocumentOutline,
): RequirementCoverageSummary => {
  const linked = linkedFactIds(outline);
  const rows = requirements.map((requirement) => {
    const state = requirementDocumentState(requirement, linked);
    return {
      requirement,
      state,
      warned:
        state === "not_in_document" &&
        requirement.importance === "mandatory" &&
        (requirement.coverage === "matched" || requirement.coverage === "partial"),
    };
  });
  /* What needs the reader first: dropped evidence, then gaps, then what is in the draft;
     within each, mandatory before preferred. `sort` is stable, so the analysis order holds
     inside a tie. */
  // oxlint-disable-next-line unicorn/no-array-sort
  const ordered = [...rows].sort(
    (left, right) =>
      statePriority[left.state] - statePriority[right.state] ||
      importancePriority[left.requirement.importance] - importancePriority[right.requirement.importance],
  );
  return {
    rows: ordered,
    inDocument: rows.filter((row) => row.state === "in_document").length,
    evidenced: rows.filter((row) => row.state !== "no_facts").length,
    warned: rows.filter((row) => row.warned).length,
  };
};
