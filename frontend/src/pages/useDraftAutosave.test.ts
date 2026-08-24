import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ClaimPatch } from "../api/contracts";
import { useDraftAutosave } from "./useDraftAutosave";

const patch = (claimId: string, text: string): ClaimPatch => ({
  claim_id: claimId,
  fact_ids: ["f-1"],
  text,
});

const updateResponse = (editVersion: number, pending: string[] = []): Response =>
  new Response(
    JSON.stringify({
      application_id: "app-1",
      working_draft_id: "wd-1",
      edit_version: editVersion,
      content_hash: `hash-${editVersion}`,
      selection_plan_id: "sp-1",
      pending_claim_ids: pending,
    }),
    {
      status: 200,
      headers: { "Content-Type": "application/json", ETag: `"${editVersion}-hash-${editVersion}"` },
    },
  );

const conflictResponse = (): Response =>
  new Response(
    JSON.stringify({
      type: "about:blank#state_conflict",
      title: "Conflict",
      status: 409,
      code: "STATE_CONFLICT",
      detail: "working draft wd-1 has content hash hash-9, not hash-4",
    }),
    { status: 409, headers: { "Content-Type": "application/problem+json" } },
  );

const deferred = () => {
  let resolve: (response: Response) => void = () => {};
  const promise = new Promise<Response>((settle) => {
    resolve = settle;
  });
  return { promise, resolve };
};

const setup = (onSaved = vi.fn()) =>
  renderHook(() => useDraftAutosave({ etag: '"4-hash-4"', onSaved, workingDraftId: "wd-1" }));

const bodyOf = (call: unknown[] | undefined) =>
  JSON.parse(String((call?.[1] as RequestInit)?.body));

const headerOf = (call: unknown[] | undefined, name: string) =>
  ((call?.[1] as RequestInit)?.headers as Headers).get(name);

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe("useDraftAutosave", () => {
  it("saves one coalesced patch on blur rather than one request per keystroke", async () => {
    const fetchMock = vi.fn().mockResolvedValue(updateResponse(5));
    vi.stubGlobal("fetch", fetchMock);
    const { result } = setup();

    act(() => {
      result.current.queueEdit(patch("c-1", "first"));
      result.current.queueEdit(patch("c-1", "second"));
      result.current.queueEdit(patch("c-2", "other"));
      result.current.flush();
    });

    await waitFor(() => expect(result.current.status).toBe("saved"));
    expect(fetchMock).toHaveBeenCalledTimes(1);
    /* The latest text per claim, once: the buffer is the user's intent, not a log. */
    expect(bodyOf(fetchMock.mock.calls[0])).toEqual({
      claim_edits: [patch("c-1", "second"), patch("c-2", "other")],
      claim_removals: [],
    });
    expect(headerOf(fetchMock.mock.calls[0], "If-Match")).toBe('"4-hash-4"');
  });

  it("never opens a second save while one is in flight, and sends the next against the returned token", async () => {
    const first = deferred();
    const fetchMock = vi
      .fn()
      .mockReturnValueOnce(first.promise)
      .mockResolvedValueOnce(updateResponse(6));
    vi.stubGlobal("fetch", fetchMock);
    const { result } = setup();

    act(() => {
      result.current.queueEdit(patch("c-1", "first"));
      result.current.flush();
    });
    await waitFor(() => expect(result.current.status).toBe("saving"));

    /* Typed while the first request is open. A second request here is what lets an older
       response install an older ETag over a newer one. */
    act(() => {
      result.current.queueEdit(patch("c-1", "while saving"));
      result.current.flush();
    });
    expect(fetchMock).toHaveBeenCalledTimes(1);

    await act(async () => {
      first.resolve(updateResponse(5));
    });

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    expect(bodyOf(fetchMock.mock.calls[1])).toEqual({
      claim_edits: [patch("c-1", "while saving")],
      claim_removals: [],
    });
    /* The token is the one the first response returned, not the one this edit was made
       against. */
    expect(headerOf(fetchMock.mock.calls[1], "If-Match")).toBe('"5-hash-5"');
  });

  it("stops the queue on a conflict and keeps the user's text for the choice", async () => {
    const fetchMock = vi.fn().mockResolvedValue(conflictResponse());
    vi.stubGlobal("fetch", fetchMock);
    const { result } = setup();

    act(() => {
      result.current.queueEdit(patch("c-1", "mine"));
      result.current.flush();
    });

    await waitFor(() => expect(result.current.status).toBe("conflict"));
    expect(result.current.pending).toEqual([patch("c-1", "mine")]);
    expect(result.current.message).toContain("hash-9");

    /* Nothing is resent while the dialog is open: a retry would be an answer the user
       has not given. */
    act(() => {
      result.current.flush();
    });
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("discards the local text only when the user chooses the current version", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(conflictResponse()));
    const { result } = setup();

    act(() => {
      result.current.queueEdit(patch("c-1", "mine"));
      result.current.flush();
    });
    await waitFor(() => expect(result.current.status).toBe("conflict"));

    act(() => {
      result.current.discardLocal();
    });

    expect(result.current.status).toBe("idle");
    expect(result.current.pending).toEqual([]);
  });

  it("keeps the text after an ordinary failure so the next save still carries it", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response("", { status: 503 }))
      .mockResolvedValueOnce(updateResponse(5));
    vi.stubGlobal("fetch", fetchMock);
    const { result } = setup();

    act(() => {
      result.current.queueEdit(patch("c-1", "mine"));
      result.current.flush();
    });
    await waitFor(() => expect(result.current.status).toBe("failed"));
    expect(result.current.pending).toEqual([patch("c-1", "mine")]);

    /* Not retried on its own - A.4's failure state is shown, and the next edit or blur
       carries the same text. */
    expect(fetchMock).toHaveBeenCalledTimes(1);
    act(() => {
      result.current.flush();
    });
    await waitFor(() => expect(result.current.status).toBe("saved"));
    expect(bodyOf(fetchMock.mock.calls[1])).toEqual({
      claim_edits: [patch("c-1", "mine")],
      claim_removals: [],
    });
  });

  it("sends a removal as part of the same patch and drops a queued edit for that claim", async () => {
    const fetchMock = vi.fn().mockResolvedValue(updateResponse(5));
    vi.stubGlobal("fetch", fetchMock);
    const { result } = setup();

    act(() => {
      result.current.queueEdit(patch("c-1", "typed then removed"));
      result.current.queueRemoval("c-1");
      result.current.flush();
    });

    await waitFor(() => expect(result.current.status).toBe("saved"));
    /* The server refuses a patch that both edits and removes one claim, so the buffer
       resolves the contradiction before it is ever sent. */
    expect(bodyOf(fetchMock.mock.calls[0])).toEqual({
      claim_edits: [],
      claim_removals: ["c-1"],
    });
  });
});
