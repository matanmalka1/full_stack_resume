import { act, renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { DraftClaim, Operation } from "@/api/contracts";
import { cvDocument } from "@/test/records";
import type { EditableDocument } from "../model/drafts.types";
import { useRegenerationDiff } from "./useRegenerationDiff";

const line = (claim_id: string, text: string): DraftClaim => ({
  claim_id,
  claim_type: "reviewed",
  fact_ids: ["f1"],
  style: "bullet",
  text,
});

const draftWith = (hash: string, text: string) =>
  cvDocument({
    document_hash: hash,
    outline: {
      headline: { ...line("h", "Engineer"), claim_type: "headline", style: "headline" },
      contacts: [],
      sections: [{ name: "Experience", claims: [line("a", text)] }],
    },
  }) as EditableDocument;

const run = (id: string, status: Operation["status"]) =>
  ({ id, operation_type: "regenerate_claim", status, is_terminal: status !== "running" }) as Operation;

describe("useRegenerationDiff", () => {
  it("shows the change once the bound run succeeded and the new draft was read", () => {
    const { result, rerender } = renderHook(
      ({ draft, operation }: { draft: EditableDocument; operation: Operation | undefined }) =>
        useRegenerationDiff({ draft, operation }),
      { initialProps: { draft: draftWith("h1", "old"), operation: undefined as Operation | undefined } },
    );
    act(() => result.current.capture({ kind: "claim", claimId: "a" }));
    act(() => result.current.bind("op-1"));
    rerender({ draft: draftWith("h1", "old"), operation: run("op-1", "running") });
    expect(result.current.changes).toEqual([]);
    /* Succeeded, but the document read is a poll behind: nothing to compare yet. */
    rerender({ draft: draftWith("h1", "old"), operation: run("op-1", "succeeded") });
    expect(result.current.changes).toEqual([]);
    rerender({ draft: draftWith("h2", "new"), operation: run("op-1", "succeeded") });
    expect(result.current.changes.map((change) => [change.before.text, change.after.text])).toEqual([["old", "new"]]);
    /* Later edits do not move the frozen "after". */
    rerender({ draft: draftWith("h3", "typed"), operation: run("op-1", "succeeded") });
    expect(result.current.changes[0]?.after.text).toBe("new");
  });

  it("drops the snapshot when the run failed", () => {
    const { result, rerender } = renderHook(
      ({ draft, operation }: { draft: EditableDocument; operation: Operation | undefined }) =>
        useRegenerationDiff({ draft, operation }),
      { initialProps: { draft: draftWith("h1", "old"), operation: undefined as Operation | undefined } },
    );
    act(() => result.current.capture({ kind: "claim", claimId: "a" }));
    act(() => result.current.bind("op-1"));
    rerender({ draft: draftWith("h1", "old"), operation: run("op-1", "failed") });
    rerender({ draft: draftWith("h2", "new"), operation: run("op-2", "succeeded") });
    expect(result.current.changes).toEqual([]);
  });

  it("ignores a run it did not capture", () => {
    const { result, rerender } = renderHook(
      ({ draft, operation }: { draft: EditableDocument; operation: Operation | undefined }) =>
        useRegenerationDiff({ draft, operation }),
      { initialProps: { draft: draftWith("h1", "old"), operation: undefined as Operation | undefined } },
    );
    act(() => result.current.bind("op-1"));
    rerender({ draft: draftWith("h2", "new"), operation: run("op-1", "succeeded") });
    expect(result.current.changes).toEqual([]);
  });
});
