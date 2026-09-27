import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { detail, json, renderRoute, revision, revisionComparison } from "@/test/fixtures";
import { RevisionComparisonPage } from "./RevisionComparisonPage";

afterEach(() => {
  vi.unstubAllGlobals();
});

const revisions = [
  revision({ id: "revision-1", version_number: 1 }),
  revision({ id: "revision-2", version_number: 2, parent_revision_id: "revision-1" }),
  revision({ id: "revision-3", version_number: 3 }),
];

const stubApi = () => {
  const fetchMock = vi.fn((input: string | URL | Request) => {
    const url = String(input);
    if (url.includes("/comparison?")) {
      const base = new URL(url, "http://localhost").searchParams.get("base_revision_id");
      return Promise.resolve(
        json(
          revisionComparison({
            base_revision_id: base ?? "",
            base_version_number: base === "revision-1" ? 1 : 2,
            target_revision_id: "revision-3",
            target_version_number: 3,
            job_snapshot_changed: true,
            summary: { added: 1, removed: 1, reworded: 1, moved: 0, unchanged: 5 },
            sections: [
              {
                kind: "headline",
                name: "",
                status: "changed",
                unchanged_count: 0,
                changes: [
                  {
                    kind: "reworded",
                    style: "headline",
                    before_text: "Key Account Manager",
                    after_text: "Account Executive",
                    fact_ids: [],
                  },
                ],
              },
              {
                kind: "section",
                name: "Work Experience",
                status: "changed",
                unchanged_count: 5,
                changes: [
                  { kind: "added", style: "bullet", after_text: "Won complex tenders.", fact_ids: ["f-1"] },
                  { kind: "removed", style: "bullet", before_text: "Managed accounts.", fact_ids: ["f-2"] },
                ],
              },
              { kind: "section", name: "Languages", status: "unchanged", unchanged_count: 4, changes: [] },
            ],
          }),
        ),
      );
    }
    if (url.endsWith("/approved-revisions")) return Promise.resolve(json({ items: revisions }));
    if (url.includes("/applications/")) return Promise.resolve(json(detail()));
    return Promise.resolve(json(revision({ id: "revision-3", version_number: 3 })));
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
};

describe("RevisionComparisonPage", () => {
  it("summarises the change, explains its context and shows each line by section", async () => {
    stubApi();

    renderRoute(
      "/revisions/revision-3/compare?base=revision-2",
      "/revisions/:revisionId/compare",
      <RevisionComparisonPage />,
    );

    expect(await screen.findByRole("heading", { name: "השוואת גרסאות" })).toBeInTheDocument();
    expect(
      await screen.findByRole("heading", {
        name: "מגרסה 2 לגרסה 3: שורה אחת נוספה, שורה אחת הוסרה, שורה אחת נוסחה מחדש",
      }),
    ).toBeInTheDocument();
    expect(screen.getByText("נוסח מודעת המשרה עודכן בין הגרסאות")).toBeInTheDocument();

    const headline = screen.getByRole("heading", { name: "כותרת" }).closest("section");
    expect(within(headline!).getByText("Key Account Manager")).toBeInTheDocument();
    expect(within(headline!).getByText("Account Executive")).toBeInTheDocument();
    expect(within(headline!).getByText("נוסחה מחדש")).toBeInTheDocument();

    const work = screen.getByRole("heading", { name: "Work Experience" }).closest("section");
    expect(within(work!).getByText("Won complex tenders.")).toBeInTheDocument();
    expect(within(work!).getByText("Managed accounts.")).toHaveClass("line-through");
    expect(within(work!).getByText("ועוד 5 שורות ללא שינוי בסעיף הזה.")).toBeInTheDocument();
    /* An unchanged section is named once in the closing line, not drawn as an empty card. */
    expect(screen.queryByRole("heading", { name: "Languages" })).not.toBeInTheDocument();
    expect(screen.getByText(/ללא שינוי:/)).toHaveTextContent("Languages");
    expect(screen.getByRole("link", { name: "חזרה לגרסה 3" })).toHaveAttribute("href", "/revisions/revision-3");
  });

  it("compares against another version chosen in place", async () => {
    const fetchMock = stubApi();

    renderRoute(
      "/revisions/revision-3/compare?base=revision-2",
      "/revisions/:revisionId/compare",
      <RevisionComparisonPage />,
    );

    const base = await screen.findByLabelText("מגרסה (הישנה)");
    await waitFor(() => expect(within(base).getAllByRole("option")).toHaveLength(2));
    fireEvent.change(base, { target: { value: "revision-1" } });

    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some((call) =>
          String(call[0]).endsWith("/approved-revisions/revision-3/comparison?base_revision_id=revision-1"),
        ),
      ).toBe(true),
    );
    expect(await screen.findByRole("heading", { name: /^מגרסה 1 לגרסה 3/ })).toBeInTheDocument();
  });
});
