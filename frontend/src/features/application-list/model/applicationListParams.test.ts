import { describe, expect, it } from "vitest";

import { PAGE_SIZE, paramsFromQuery, queryFromParams } from "./applicationListParams";

describe("application list URL parameters", () => {
  it("reads every supported filter and rounds an offset down to a page boundary", () => {
    const params = new URLSearchParams([
      ["activity", "closed"],
      ["stage", "needs_review"],
      ["stage", "not-a-stage"],
      ["stage", "ready"],
      ["recruitment_status", "interview"],
      ["recruitment_status", "not-a-status"],
      ["preset", "needs_attention"],
      ["search", "platform engineer"],
      ["sort", "company"],
      ["offset", "51"],
    ]);

    expect(queryFromParams(params)).toEqual({
      activity: "closed",
      stages: ["needs_review", "ready"],
      recruitmentStatuses: ["interview"],
      preset: "needs_attention",
      search: "platform engineer",
      sort: "company",
      limit: PAGE_SIZE,
      offset: 50,
    });
  });

  it.each(["-1", "3abc", "1e9", "1.5", "9007199254740992"])(
    "rejects an offset the pager could not have produced: %s",
    (offset) => {
      expect(queryFromParams(new URLSearchParams({ offset }))).toEqual({
        activity: "open",
        sort: "updated",
        limit: PAGE_SIZE,
      });
    },
  );

  it("falls back from unknown closed-set values without forwarding them", () => {
    expect(
      queryFromParams(
        new URLSearchParams({
          activity: "deleted",
          preset: "everything",
          recruitment_status: "waiting_forever",
          sort: "random",
          stage: "invented",
        }),
      ),
    ).toEqual({
      activity: "open",
      sort: "updated",
      limit: PAGE_SIZE,
    });
  });

  it("writes only non-default state and preserves repeated filters", () => {
    const params = paramsFromQuery({
      activity: "closed",
      stages: ["needs_review", "ready"],
      recruitmentStatuses: ["interview", "offer"],
      preset: "active_interviews",
      search: "Acme & Sons",
      sort: "created",
      limit: 100,
      offset: 50,
    });

    expect(params.get("activity")).toBe("closed");
    expect(params.getAll("stage")).toEqual(["needs_review", "ready"]);
    expect(params.getAll("recruitment_status")).toEqual(["interview", "offer"]);
    expect(params.get("preset")).toBe("active_interviews");
    expect(params.get("search")).toBe("Acme & Sons");
    expect(params.get("sort")).toBe("created");
    expect(params.get("offset")).toBe("50");
    expect(params.has("limit")).toBe(false);

    expect(
      paramsFromQuery({
        activity: "open",
        search: "",
        sort: "updated",
        limit: PAGE_SIZE,
        offset: 0,
      }).toString(),
    ).toBe("");
  });
});
