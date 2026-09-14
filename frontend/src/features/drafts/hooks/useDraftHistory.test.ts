import { act, renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { DraftClaim, WorkingDraft } from "@/api/contracts";
import { draft as draftFixture } from "@/test/fixtures";
import { useDraftHistory } from "./useDraftHistory";

const claim = (id: string, text = id): DraftClaim => ({
  claim_id: id,
  claim_type: "canonical",
  fact_ids: [`fact-${id}`],
  style: "bullet",
  text,
});

const workingDraft = (): WorkingDraft =>
  draftFixture({
    outline: {
      headline: claim("headline", "Engineer"),
      contacts: [],
      sections: [
        { name: "experience", claims: [claim("a"), claim("b")] },
        { name: "skills", claims: [claim("c")] },
      ],
    },
  });

const setup = () => {
  const queueClaimOrder = vi.fn();
  const queueEdit = vi.fn();
  const queueSectionOrder = vi.fn();
  const draft = workingDraft();
  const hook = renderHook(() => useDraftHistory({ draft, queueClaimOrder, queueEdit, queueSectionOrder }));
  return { ...hook, draft, queueClaimOrder, queueEdit, queueSectionOrder };
};

describe("useDraftHistory", () => {
  it("undoes and redoes a move by replacing the pending absolute order", () => {
    const { result, queueClaimOrder } = setup();

    act(() => result.current.moveClaim("experience", 0, 1));
    expect(result.current.visibleDraft?.outline.sections[0]?.claims.map((item) => item.claim_id)).toEqual(["b", "a"]);

    act(() => result.current.undo());
    expect(queueClaimOrder).toHaveBeenLastCalledWith("experience", ["a", "b"]);
    expect(result.current.canRedo).toBe(true);

    act(() => result.current.redo());
    expect(queueClaimOrder).toHaveBeenLastCalledWith("experience", ["b", "a"]);
  });

  it("groups consecutive typing and clears redo after a new edit", () => {
    const { result, draft, queueEdit } = setup();
    const first = draft.outline.sections[0]?.claims[0];
    if (first === undefined) throw new Error("fixture must include a first claim");

    act(() => {
      result.current.edit(first, "first");
      result.current.edit(first, "second");
    });
    act(() => result.current.undo());
    expect(queueEdit).toHaveBeenLastCalledWith(expect.objectContaining({ claim_id: "a" }), "a");
    act(() => result.current.edit(first, "new branch"));
    expect(result.current.canRedo).toBe(false);
  });
});
