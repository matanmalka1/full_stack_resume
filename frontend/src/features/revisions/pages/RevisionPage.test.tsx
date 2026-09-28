import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { detail, json, operation, renderRoute, revision, revisionComparison } from "@/test/fixtures";
import { RevisionPage } from "./RevisionPage";

afterEach(() => {
  vi.unstubAllGlobals();
  sessionStorage.clear();
});

describe("RevisionPage", () => {
  it("lists every immutable revision newest first, with what changed and a way to compare", async () => {
    const fetchMock = vi.fn((input: string | URL | Request) => {
      const url = String(input);
      if (url.includes("/comparison?")) {
        return Promise.resolve(
          json(
            revisionComparison({
              base_revision_id: "revision-1",
              target_revision_id: "revision-2",
              summary: { added: 2, removed: 1, reworded: 1, moved: 0, unchanged: 20 },
            }),
          ),
        );
      }
      if (url.endsWith("/approved-revisions")) {
        return Promise.resolve(
          json({
            items: [
              revision({ id: "revision-1", version_number: 1, approved_at: "2026-08-20T09:00:00Z" }),
              revision({
                id: "revision-2",
                version_number: 2,
                approved_at: "2026-08-25T09:00:00Z",
                parent_revision_id: "revision-1",
              }),
            ],
          }),
        );
      }
      return Promise.resolve(
        json(
          url.includes("applications")
            ? detail({
                active_working_draft_id: null,
                available_actions: ["create_draft"],
                preparation_state: "ready",
                latest_ready_revision_id: "revision-2",
                working_draft_state: "none",
              })
            : revision(),
        ),
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    renderRoute("/revisions/revision-1", "/revisions/:revisionId", <RevisionPage />);

    const history = await screen.findByRole("region", { name: "היסטוריית גרסאות" });
    /* Until the list arrives the history holds only the displayed revision, so wait for
       the full list rather than for the first entry. */
    await within(history).findByRole("heading", { name: "גרסה 2" });
    const entries = within(history).getAllByRole("listitem");
    /* Newest first; the displayed one is marked and is not offered as a link to itself. */
    expect(within(entries[0]!).getByRole("heading", { name: "גרסה 2" })).toBeInTheDocument();
    expect(within(entries[0]!).getByText("העדכנית")).toBeInTheDocument();
    expect(within(entries[0]!).getByText(/נפתחה מגרסה 1 ונערכה/)).toBeInTheDocument();
    expect(
      await within(entries[0]!).findByText("2 שורות נוספו · שורה אחת הוסרה · שורה אחת נוסחה מחדש"),
    ).toBeInTheDocument();
    expect(within(entries[0]!).getByRole("link", { name: "צפייה בגרסה 2" })).toHaveAttribute(
      "href",
      "/revisions/revision-2",
    );
    expect(within(entries[0]!).getByRole("link", { name: /השוואה לגרסה 1/ })).toHaveAttribute(
      "href",
      "/revisions/revision-2/compare?base=revision-1",
    );
    expect(entries[1]).toHaveAttribute("aria-current", "true");
    expect(within(entries[1]!).getByText(/הגרסה הראשונה שאושרה/)).toBeInTheDocument();
    expect(within(entries[1]!).queryByRole("link", { name: /צפייה/ })).not.toBeInTheDocument();
    expect(within(history).getByRole("button", { name: "יצירת טיוטה חדשה מגרסה 1" })).toBeInTheDocument();
    expect(
      fetchMock.mock.calls.some((call) =>
        String(call[0]).endsWith("/approved-revisions/revision-2/comparison?base_revision_id=revision-1"),
      ),
    ).toBe(true);
  });

  it("routes to the active draft instead of offering to create another one", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: string | URL | Request) =>
        Promise.resolve(
          json(
            String(input).includes("applications")
              ? detail({
                  active_working_draft_id: "draft-2",
                  newer_draft_in_progress: true,
                  working_draft_state: "editing",
                })
              : revision(),
          ),
        ),
      ),
    );

    renderRoute("/revisions/revision-1", "/revisions/:revisionId", <RevisionPage />);

    expect(await screen.findByRole("link", { name: "המשך עבודה על הטיוטה החדשה" })).toHaveAttribute(
      "href",
      "/applications/app-1/draft",
    );
    expect(screen.queryByRole("button", { name: /יצירת טיוטה חדשה/ })).not.toBeInTheDocument();
  });

  it("shows the route not-found frame without presenting a missing revision as completed", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          json(
            {
              type: "about:blank#not-found",
              title: "Not found",
              status: 404,
              code: "APPROVED_REVISION_NOT_FOUND",
              detail: "unknown approved revision: missing-revision",
            },
            404,
            { "Content-Type": "application/problem+json" },
          ),
        ),
      ),
    );

    renderRoute("/revisions/missing-revision", "/revisions/:revisionId", <RevisionPage />);

    expect(await screen.findByRole("heading", { name: "העמוד לא נמצא" })).toBeInTheDocument();
    expect(screen.getByText("404")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "חזרה ללוח המועמדויות" })).toHaveAttribute("href", "/");
    expect(screen.queryByRole("navigation", { name: "שלבי הכנת קורות החיים" })).not.toBeInTheDocument();
    expect(screen.queryByText(/הושלם 4 מתוך 4/)).not.toBeInTheDocument();
    expect(screen.queryByText(/unknown approved revision/)).not.toBeInTheDocument();
  });

  it("frames and downloads the exact Ready artifacts", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: string | URL | Request) =>
        Promise.resolve(
          json(
            String(input).includes("applications")
              ? detail({ preparation_state: "ready", latest_ready_revision_id: "revision-1" })
              : revision(),
          ),
        ),
      ),
    );
    renderRoute("/revisions/revision-1", "/revisions/:revisionId", <RevisionPage />);
    const frame = await screen.findByTitle("תצוגה מאושרת של קורות החיים");
    expect(await screen.findByRole("button", { name: "רישום הגשת הגרסה הזו" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "מוכן למסירה" })).toBeInTheDocument();
    expect(screen.getByRole("complementary", { name: "פרטי הגרסה והאימות" })).toBeInTheDocument();
    const technicalDetails = screen.getByText("פרטים טכניים וביקורת");
    expect(screen.getByText("draft-hash")).not.toBeVisible();
    fireEvent.click(technicalDetails);
    expect(screen.getByText("draft-hash")).toBeVisible();
    expect(frame).toHaveAttribute("sandbox", "");
    expect(frame).toHaveAttribute(
      "src",
      "/api/v1/approved-revisions/revision-1/preview?html_artifact_version_id=html-1",
    );
    expect(screen.getByRole("link", { name: "הורדת PDF" })).toHaveAttribute(
      "href",
      "/api/v1/approved-revisions/revision-1/recruiter-pdf?pdf_artifact_version_id=pdf-1",
    );
  });

  it("keeps an approved revision without qualified files visible in history", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: string | URL | Request) =>
        Promise.resolve(
          json(
            String(input).includes("applications")
              ? detail({
                  preparation_state: "approved",
                  active_working_draft_id: null,
                  latest_approved_revision_id: "revision-1",
                })
              : revision({
                  ready_qualified: false,
                  html_artifact_version_id: null,
                  pdf_artifact_version_id: null,
                }),
          ),
        ),
      ),
    );

    renderRoute("/revisions/revision-1", "/revisions/:revisionId", <RevisionPage />);

    expect(await screen.findByRole("heading", { name: "גרסה מאושרת" })).toBeInTheDocument();
    expect(screen.getByText("עדיין אין קובץ HTML לתצוגה")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "הורדת PDF" })).not.toBeInTheDocument();
  });

  it("shows the revision decision record and preserves its server-suggested filename", async () => {
    const fetchMock = vi.fn((input: string | URL | Request) => {
      const url = String(input);
      if (url.includes("/api/v1/facts")) {
        return Promise.resolve(
          json({
            items: [
              {
                fact: {
                  fact_id: "development.phdigital.cicd",
                  meaning: "Built CI/CD pipelines",
                  renderings: { en: "Built CI/CD pipelines with GitHub Actions" },
                  tags: [],
                  status: "canonical",
                  provenance: "user",
                  source: "development.json",
                  resume_style: "bullet",
                },
                recorded_status: "canonical",
              },
            ],
          }),
        );
      }
      if (url.includes("decision-markdown")) {
        return Promise.resolve(
          json(
            {
              application_id: "app-1",
              approved_revision_id: "revision-1",
              content: [
                "# CV Decision and Provenance",
                "",
                "## Decision",
                "",
                "Selected canonical facts.",
                "",
                "## Classification",
                "",
                "- Track: development",
                "- Language: en",
                "",
                "## Selected facts",
                "",
                "- `development.phdigital.cicd`",
                "- `retired.fact`",
                "",
                "## Overrides",
                "",
                "- User overrides: {}",
                "",
                "## Exact lineage",
                "",
                "- Job snapshot ID: `lineage-snapshot`",
                "",
              ].join("\n"),
              content_hash: "decision-hash",
            },
            200,
            { "Content-Disposition": 'attachment; filename="Acme-decision.md"' },
          ),
        );
      }
      return Promise.resolve(json(url.includes("applications") ? detail({ preparation_state: "ready" }) : revision()));
    });
    vi.stubGlobal("fetch", fetchMock);

    renderRoute("/revisions/revision-1", "/revisions/:revisionId", <RevisionPage />);

    /* Read for a person, not shown as raw Markdown: the decision leads, the classification
       is named in Hebrew, a fact id resolves to what the fact says under its source, an id
       the store no longer holds is named rather than hidden, and lineage stays as written. */
    expect(await screen.findByText("Selected canonical facts.")).toBeInTheDocument();
    expect(screen.queryByText(/^#/)).not.toBeInTheDocument();
    const overview = within(screen.getByRole("region", { name: "תקציר ההחלטה" }));
    expect(overview.getByText("פיתוח")).toBeInTheDocument();
    expect(overview.getByText("אנגלית")).toBeInTheDocument();
    expect(overview.getByText("2")).toBeInTheDocument();
    expect(overview.getByText("אין")).toBeInTheDocument();
    expect(await screen.findByText("Built CI/CD pipelines with GitHub Actions")).toBeInTheDocument();
    expect(screen.getByText("ניסיון בפיתוח · 1")).toBeInTheDocument();
    expect(screen.getByText("retired.fact")).toBeInTheDocument();
    expect(screen.queryByText("development.phdigital.cicd")).not.toBeInTheDocument();
    expect(screen.getByText("lineage-snapshot").tagName).toBe("CODE");
    expect(screen.getByRole("button", { name: "הורדת מסמך ההחלטה" })).toBeInTheDocument();
  });

  it("records submission against the exact displayed revision and PDF", async () => {
    const fetchMock = vi.fn((input: string | URL | Request, init?: RequestInit) => {
      const url = String(input);
      if (init?.method === "POST" && url.endsWith("/submissions")) {
        return Promise.resolve(
          json(
            {
              application_id: "app-1",
              submission_id: "submission-1",
              current_status: "applied",
              approved_revision_id: "revision-1",
              pdf_artifact_version_id: "pdf-1",
              warnings: [],
            },
            201,
          ),
        );
      }
      if (url.includes("decision-markdown")) {
        return Promise.resolve(
          json({
            application_id: "app-1",
            approved_revision_id: "revision-1",
            content: "# Decision",
            content_hash: "decision-hash",
          }),
        );
      }
      return Promise.resolve(json(url.includes("applications") ? detail({ preparation_state: "ready" }) : revision()));
    });
    vi.stubGlobal("fetch", fetchMock);
    renderRoute("/revisions/revision-1", "/revisions/:revisionId", <RevisionPage />);

    expect(screen.queryByRole("button", { name: "רישום הגשת הגרסה הזו" })).not.toBeInTheDocument();
    fireEvent.click(await screen.findByRole("link", { name: "הורדת PDF" }));
    fireEvent.click(await screen.findByRole("button", { name: "רישום הגשת הגרסה הזו" }));
    fireEvent.click(screen.getByRole("button", { name: "אישור ורישום ההגשה" }));

    await screen.findByText("ההגשה נרשמה");
    expect(screen.getByRole("link", { name: "סיום וחזרה ללוח" })).toHaveAttribute("href", "/");
    const request = fetchMock.mock.calls.find(
      (call) => call[1]?.method === "POST" && String(call[0]).endsWith("/submissions"),
    );
    expect(JSON.parse(String(request?.[1]?.body))).toMatchObject({
      approved_revision_id: "revision-1",
      pdf_artifact_version_id: "pdf-1",
      metadata: {},
    });
  });

  it("names a revision already on record as submitted and asks before recording a second one", async () => {
    const fetchMock = vi.fn((input: string | URL | Request) => {
      const url = String(input);
      if (url.includes("decision-markdown")) {
        return Promise.resolve(
          json({
            application_id: "app-1",
            approved_revision_id: "revision-1",
            content: "# Decision",
            content_hash: "decision-hash",
          }),
        );
      }
      return Promise.resolve(
        json(
          url.includes("applications")
            ? detail({
                preparation_state: "ready",
                recruitment_timeline: [
                  {
                    id: "event-1",
                    item_type: "submission",
                    submission_type: "internal",
                    approved_revision_id: "revision-1",
                    artifact_version_id: "pdf-1",
                    occurred_at: "2026-08-25T09:00:00Z",
                    actor_type: "user",
                    client: "web",
                    from_status: "saved",
                    to_status: "applied",
                    reason: "submission recorded",
                    metadata: {},
                  },
                ],
              })
            : revision(),
        ),
      );
    });
    vi.stubGlobal("fetch", fetchMock);
    renderRoute("/revisions/revision-1", "/revisions/:revisionId", <RevisionPage />);

    const revisionAside = await screen.findByRole("complementary", { name: "פרטי הגרסה והאימות" });
    fireEvent.click(await within(revisionAside).findByText("אפשרויות נוספות"));
    fireEvent.click(await screen.findByRole("button", { name: "רישום הגשה נוספת" }));
    expect(await screen.findByText("הגרסה הזו כבר נרשמה כמוגשת")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "אישור ורישום ההגשה" })).toBeDisabled();

    fireEvent.click(screen.getByLabelText("אני מבקש לרשום הגשה נוספת של אותה גרסה"));
    expect(screen.getByRole("button", { name: "אישור ורישום ההגשה" })).toBeEnabled();
  });

  it("labels the displayed Ready revision historical even when the latest Ready is current", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: string | URL | Request) =>
        Promise.resolve(
          json(
            String(input).includes("applications")
              ? detail({
                  preparation_state: "ready",
                  active_job_snapshot_id: "snapshot-2",
                  active_analysis_id: "analysis-2",
                  latest_ready_revision_id: "revision-2",
                  warnings: [
                    {
                      code: "READY_REVISION_FOR_OLDER_ANALYSIS",
                      message: "The latest Ready revision belongs to an older analysis.",
                      entity_references: { approved_revision_id: "revision-2" },
                    },
                  ],
                })
              : revision({ job_snapshot_id: "snapshot-1", job_analysis_id: "analysis-1" }),
          ),
        ),
      ),
    );
    renderRoute("/revisions/revision-1", "/revisions/:revisionId", <RevisionPage />);
    expect(await screen.findByText("הגרסה המוכנה שייכת לנוסח משרה ישן")).toBeInTheDocument();
    expect(screen.getByText(/תצלום משרה ישן יותר/)).toBeInTheDocument();
    expect(screen.getByText("הגרסה המוכנה שייכת לניתוח ישן")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "הורדת PDF" })).toBeInTheDocument();
  });

  it("creates a child draft from explicit active sources without a provider", async () => {
    const fetchMock = vi.fn((input: string | URL | Request, init?: RequestInit) =>
      init?.method === "POST"
        ? Promise.resolve(
            json({ ...operation(), id: "op-draft", operation_type: "create_draft" }, 202, {
              Location: "/api/v1/operations/op-draft",
            }),
          )
        : Promise.resolve(
            json(
              String(input).includes("applications")
                ? detail({
                    active_working_draft_id: null,
                    available_actions: ["create_draft"],
                    preparation_state: "ready",
                    working_draft_state: "none",
                  })
                : revision(),
            ),
          ),
    );
    vi.stubGlobal("fetch", fetchMock);
    renderRoute("/revisions/revision-1", "/revisions/:revisionId", <RevisionPage />);
    const newDraft = await screen.findByRole("button", { name: "יצירת טיוטה חדשה מגרסה 1" });
    expect(screen.getByRole("link", { name: "חזרה ללוח המועמדויות" })).toHaveAttribute("href", "/");
    expect(screen.getByRole("link", { name: "מעבר לשלב ניתוח והתאמה" })).toHaveAttribute("href", "/applications/app-1");
    expect(screen.getByRole("heading", { name: "מוכן למסירה" })).toBeInTheDocument();
    fireEvent.click(newDraft);
    await waitFor(() => expect(fetchMock.mock.calls.some((call) => call[1]?.method === "POST")).toBe(true));
    const request = fetchMock.mock.calls.find((call) => call[1]?.method === "POST");
    expect(JSON.parse(String(request?.[1]?.body))).toEqual({
      job_analysis_id: "analysis-1",
      selection_plan_id: "plan-1",
      parent_revision_id: "revision-1",
    });
  });
});
