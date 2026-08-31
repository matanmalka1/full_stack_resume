import { afterEach, describe, expect, it, vi } from "vitest";

import {
  correctRecruitmentStatus,
  recordExternalSubmission,
  setNextAction,
  transitionRecruitmentStatus,
} from "./tracking";

const json = (value: unknown, status = 200) =>
  new Response(JSON.stringify(value), {
    status,
    headers: { "Content-Type": "application/json" },
  });

afterEach(() => vi.unstubAllGlobals());

describe("recruitment tracking transport", () => {
  it("sends a direct transition selected from the server projection", async () => {
    const fetchMock = vi.fn().mockResolvedValue(json({ application_id: "app-1" }));
    vi.stubGlobal("fetch", fetchMock);

    await transitionRecruitmentStatus("app-1", {
      target_status: "withdrawn",
      reason: "role changed",
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/applications/app-1/status",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ target_status: "withdrawn", reason: "role changed" }),
      }),
    );
  });

  it("keeps a correction append-only and clears the whole next-action value", async () => {
    const fetchMock = vi.fn().mockImplementation(() =>
      Promise.resolve(json({ application_id: "app-1" }, 201)),
    );
    vi.stubGlobal("fetch", fetchMock);

    await correctRecruitmentStatus("app-1", {
      target_status: "interview",
      corrects_event_id: "event-1",
      reason: "wrong application",
    });
    await setNextAction("app-1", { next_action: null, next_action_date: null });

    expect(JSON.parse(String(fetchMock.mock.calls[0]?.[1]?.body))).toEqual({
      target_status: "interview",
      corrects_event_id: "event-1",
      reason: "wrong application",
    });
    expect(JSON.parse(String(fetchMock.mock.calls[1]?.[1]?.body))).toEqual({
      next_action: null,
      next_action_date: null,
    });
  });

  it("records an external submission without inventing immutable artifact IDs", async () => {
    const fetchMock = vi.fn().mockResolvedValue(json({ application_id: "app-1" }, 201));
    vi.stubGlobal("fetch", fetchMock);

    await recordExternalSubmission("app-1", {
      submitted_at: "2026-08-30T09:00:00Z",
      artifact_version_id: null,
      metadata: { note: "email" },
    });

    expect(JSON.parse(String(fetchMock.mock.calls[0]?.[1]?.body))).toEqual({
      submitted_at: "2026-08-30T09:00:00Z",
      artifact_version_id: null,
      metadata: { note: "email" },
    });
  });
});
