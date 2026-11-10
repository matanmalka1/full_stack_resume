import { describe, expect, it } from "vitest";

import { BOARD_LIMIT, paramsFromQuery, queryFromParams } from "./applicationListParams";

describe("application list URL parameters", () => {
  it("reads the slice and the order, and always asks for the board in one page", () => {
    const params = new URLSearchParams([
      ["preset", "needs_attention"],
      ["sort", "company"],
    ]);

    expect(queryFromParams(params)).toEqual({
      preset: "needs_attention",
      sort: "company",
      limit: BOARD_LIMIT,
    });
  });

  /* The board no longer has a search box, stage menus or a pager. An old link that still
     carries their parameters opens the plain board rather than a narrowing nothing on
     screen can show or undo. */
  it("ignores the parameters of the removed filter panel and pager", () => {
    expect(
      queryFromParams(
        new URLSearchParams({
          activity: "closed",
          offset: "48",
          recruitment_status: "interview",
          search: "Acme",
          stage: "ready",
        }),
      ),
    ).toEqual({ sort: "updated", limit: BOARD_LIMIT });
  });

  it("falls back from unknown closed-set values without forwarding them", () => {
    expect(queryFromParams(new URLSearchParams({ preset: "everything", sort: "random" }))).toEqual({
      sort: "updated",
      limit: BOARD_LIMIT,
    });
  });

  it("writes only non-default state", () => {
    const params = paramsFromQuery({ preset: "ready_to_send", sort: "created", limit: 200 });

    expect(params.toString()).toBe("preset=ready_to_send&sort=created");
    expect(paramsFromQuery({ sort: "updated", limit: BOARD_LIMIT }).toString()).toBe("");
  });
});
