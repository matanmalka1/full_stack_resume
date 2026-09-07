import { describe, expect, it } from "vitest";

import type { SelectionPlanCandidate } from "@/api/contracts";
import { factGroups, factTotals, includableFactIds } from "./factGroups";

const candidate = (overrides: Partial<SelectionPlanCandidate> = {}): SelectionPlanCandidate => ({
  fact_id: "fact.a",
  outcome: "selected",
  reason: null,
  section: "Work Experience",
  text: "Led a B2B sales team",
  user_selectable: true,
  ...overrides,
});

const plan: SelectionPlanCandidate[] = [
  candidate({ fact_id: "role.title", outcome: "selected", text: "Team Leader", user_selectable: false }),
  candidate({ fact_id: "exp.selected" }),
  candidate({ fact_id: "exp.omitted", outcome: "omitted", reason: "below_section_budget" }),
  candidate({ fact_id: "exp.excluded", outcome: "omitted", reason: "excluded_by_user" }),
  candidate({ fact_id: "skill.pinned", outcome: "pinned", section: "Core Skills", text: "Priority ERP" }),
];

describe("the fact selection the screen shows", () => {
  /* The two overrides are independent decisions over a computed outcome. Inclusion is
     therefore derived from all three rather than stored, and an exclusion outranks a
     stale engine outcome. */
  it("reads inclusion from the overrides first and the recorded outcome second", () => {
    const totals = factTotals(plan, ["exp.omitted"], ["exp.selected"]);

    expect(totals).toEqual({ excluded: 2, included: 3, locked: 1, total: 5 });
  });

  it("groups by CV section in the order the plan listed them, with a live count per group", () => {
    const groups = factGroups(plan, [], [], "");

    expect(groups.map((group) => group.section)).toEqual(["Work Experience", "Core Skills"]);
    expect(groups[0]).toMatchObject({ included: 2, locked: 1, total: 4 });
    expect(groups[1]).toMatchObject({ included: 1, locked: 0, total: 1 });
  });

  it("filters across every group, on the fact text and on the section name", () => {
    expect(factGroups(plan, [], [], "priority").map((group) => group.section)).toEqual(["Core Skills"]);
    expect(factGroups(plan, [], [], "core skills")).toHaveLength(1);
    expect(factGroups(plan, [], [], "nothing here")).toHaveLength(0);
  });

  /* A bulk include may only name facts it would actually change, and never a structural
     component: excluding or pinning a heading is refused by the server. */
  it("offers a bulk include only for the selectable facts that are not already included", () => {
    const [experience] = factGroups(plan, [], [], "");
    if (experience === undefined) {
      throw new Error("the experience group was not produced");
    }

    expect(includableFactIds(experience, [], [])).toEqual(["exp.omitted", "exp.excluded"]);
    expect(includableFactIds(experience, ["exp.omitted"], [])).toEqual(["exp.excluded"]);
    expect(includableFactIds(experience, [], ["exp.selected"])).toEqual([
      "exp.selected",
      "exp.omitted",
      "exp.excluded",
    ]);
  });
});
