import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

import type { ApplicationListItem } from "@/api/contracts";
import { actionDestination, preparationResumeDestination } from "./actionDestinations";
import { actionDescription, actionLabel } from "./preparationLabels";

const item = (overrides: Partial<ApplicationListItem>): ApplicationListItem =>
  ({
    id: "app-1",
    preparation_state: "needs_analysis",
    recommended_action: null,
    ...overrides,
  }) as ApplicationListItem;

describe("preparationResumeDestination", () => {
  it("follows the action recommended by the server projection", () => {
    expect(
      preparationResumeDestination(item({ preparation_state: "draft_in_progress", recommended_action: "approve" })),
    ).toBe("/applications/app-1/draft");
  });

  it("reopens a document with content when no recommendation is present", () => {
    expect(preparationResumeDestination(item({ preparation_state: "draft_in_progress" }))).toBe(
      "/applications/app-1/draft",
    );
  });

  it("opens the Ready document for a completed flow", () => {
    expect(preparationResumeDestination(item({ id: "app / 1", preparation_state: "ready" }))).toBe(
      "/applications/app%20%2F%201/ready",
    );
  });

  it("falls back to analysis while the document has no content", () => {
    expect(preparationResumeDestination(item({ preparation_state: "ready_to_draft" }))).toBe("/applications/app-1");
  });
});

/* Derived guard over the backend's own action vocabulary.

   The projection reports `recommended_action` as a plain string, so there is no TypeScript
   union to be exhaustive over and a missing destination fails nowhere: the route table's
   honest default is "no screen yet", which is indistinguishable from a name nobody
   registered. The list is therefore read from the one place that defines it - the
   `PREPARATION_ACTIONS` tuple in the application layer - and every name must be classified,
   either by having a destination or by being named in UNBUILT with a reason.

   The tables are written for the single-document vocabulary of state-and-use-cases §9.
   That tuple is owned by the document-core lane, so in this lane's isolated tree it still
   carries the revision vocabulary; the guard is meant to run against the merged tree.

   UNBUILT is deliberately empty. Add an entry only with a reason, so forgetting to
   register a new action fails here instead of stranding the record that receives it. */
const UNBUILT: { action: string; reason: string }[] = [];

const preparationActions = (): string[] => {
  const source = readFileSync(resolve(process.cwd(), "../cv_engine/application/state.py"), "utf8");
  const tuple = /PREPARATION_ACTIONS = \(([^)]*)\)/.exec(source);

  if (tuple === null) {
    throw new Error("PREPARATION_ACTIONS not found in cv_engine/application/state.py");
  }

  return [...tuple[1].matchAll(/"([a-z_]+)"/g)].map((match) => match[1]);
};

describe("actionDestination covers the backend action vocabulary", () => {
  const actions = preparationActions();

  it("reads the tuple the projection is built from", () => {
    expect(actions).toContain("confirm_and_use_fact");
    expect(actions.length).toBeGreaterThan(10);
  });

  it.each(actions)("classifies %s as routed or explicitly unbuilt", (action) => {
    const unbuilt = UNBUILT.find((entry) => entry.action === action) ?? null;

    if (unbuilt !== null) {
      expect(actionDestination(action, "app-1")).toBeNull();
      expect(unbuilt.reason).not.toBe("");
      return;
    }

    expect(actionDestination(action, "app-1")).not.toBeNull();
  });

  /* The board row names the step it recommends and says in one line what it is. */
  it.each(actions)("names and describes %s", (action) => {
    expect(actionLabel(action)).not.toBe(action);
    expect(actionDescription(action)).not.toBeNull();
  });

  it("keeps the editor's own commands on the editor", () => {
    for (const action of [
      "edit",
      "confirm_and_use_fact",
      "regenerate_claim",
      "regenerate_section",
      "check",
      "approve",
      "render",
    ]) {
      expect(actionDestination(action, "app-1")).toBe("/applications/app-1/draft");
    }
  });

  it("keeps what is done with a Ready document on the ready step", () => {
    expect(actionDestination("submit", "app-1")).toBe("/applications/app-1/ready");
    expect(actionDestination("download_pdf", "app-1")).toBe("/applications/app-1/ready");
  });
});
