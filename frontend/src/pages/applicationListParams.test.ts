import { describe, expect, it } from "vitest";

import { PAGE_SIZE, paramsFromQuery, queryFromParams } from "./applicationListParams";

const read = (search: string) => queryFromParams(new URLSearchParams(search));

const write = (query: Parameters<typeof paramsFromQuery>[0]) =>
  paramsFromQuery(query).toString();

describe("queryFromParams", () => {
  /* An empty address bar is the board's opening question: live work, most recently
     updated first. */
  it("reads an empty address bar as the default board", () => {
    expect(read("")).toEqual({ activity: "open", sort: "updated", limit: PAGE_SIZE });
  });

  it("reads every field the toolbar can set", () => {
    expect(read("activity=closed&stage=ready&stage=approved&search=binat&sort=company")).toEqual({
      activity: "closed",
      sort: "company",
      limit: PAGE_SIZE,
      stages: ["ready", "approved"],
      search: "binat",
    });
  });

  /* The URL is user input. An arbitrary value in it must not become an arbitrary
     request, so anything outside the closed sets falls back to the default rather than
     being forwarded to the server. */
  it("falls back to the default for a value outside the closed sets", () => {
    const query = read("activity=archived&sort=whatever&stage=not_a_stage&stage=ready");

    expect(query.activity).toBe("open");
    expect(query.sort).toBe("updated");
    /* The unknown stage is dropped and the known one kept, rather than the whole
       filter being discarded because one entry was wrong. */
    expect(query.stages).toEqual(["ready"]);
  });

  it("keeps a page offset and rounds a hand-edited one down to a page boundary", () => {
    expect(read(`offset=${PAGE_SIZE}`).offset).toBe(PAGE_SIZE);
    /* An offset the pager could never have produced would leave its "previous" button
       one partial page from the start. */
    expect(read("offset=30").offset).toBe(PAGE_SIZE);
    expect(read("offset=10").offset).toBeUndefined();
  });

  it("ignores an offset that is not a whole number", () => {
    for (const search of ["offset=-25", "offset=abc", "offset=1e9", "offset=25.5"]) {
      expect(read(search).offset, search).toBeUndefined();
    }
  });
});

describe("paramsFromQuery", () => {
  /* Only what differs from the default is written, so an untouched board has a clean
     address bar and a shared link carries exactly the narrowing its sender applied. */
  it("writes nothing for the default board", () => {
    expect(write({ activity: "open", sort: "updated", limit: PAGE_SIZE })).toBe("");
  });

  it("writes each field the server takes, and repeats stage", () => {
    expect(
      write({
        activity: "all",
        stages: ["ready", "approved"],
        search: "binat",
        sort: "company",
        offset: PAGE_SIZE,
        limit: PAGE_SIZE,
      }),
    ).toBe(`activity=all&stage=ready&stage=approved&search=binat&sort=company&offset=${PAGE_SIZE}`);
  });

  /* The page size is this screen's layout decision rather than part of the question, and
     a user editing it in the URL would be setting a bound the screen has no control
     for. */
  it("never writes the page size", () => {
    expect(write({ limit: 200 })).toBe("");
  });

  it("round-trips a narrowed board", () => {
    const search = "activity=closed&stage=ready&search=binat&sort=stage&offset=50";

    expect(write(read(search))).toBe(search);
  });
});
