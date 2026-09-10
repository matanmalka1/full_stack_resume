import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { detail, json, operation, renderRoute, revision } from "@/test/fixtures";
import { RevisionPage } from "./RevisionPage";

afterEach(() => {
  vi.unstubAllGlobals();
  sessionStorage.clear();
});

describe("RevisionPage", () => {
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
    expect(screen.getByRole("heading", { name: "גרסה מוכנה למסירה" })).toBeInTheDocument();
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

  it("shows the revision decision record and preserves its server-suggested filename", async () => {
    const fetchMock = vi.fn((input: string | URL | Request) => {
      const url = String(input);
      if (url.includes("decision-markdown")) {
        return Promise.resolve(
          json(
            {
              application_id: "app-1",
              approved_revision_id: "revision-1",
              content: "# Why this revision\n\nSelected canonical facts.",
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

    expect(await screen.findByText(/# Why this revision/)).toBeInTheDocument();
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

    fireEvent.click(await screen.findByText("אפשרויות נוספות"));
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
                ? detail({ preparation_state: "ready", working_draft_state: "none" })
                : revision(),
            ),
          ),
    );
    vi.stubGlobal("fetch", fetchMock);
    renderRoute("/revisions/revision-1", "/revisions/:revisionId", <RevisionPage />);
    fireEvent.click(await screen.findByText("אפשרויות נוספות"));
    const newDraft = await screen.findByRole("button", { name: "יצירת טיוטה חדשה" });
    expect(screen.getByRole("link", { name: "חזרה ללוח המועמדויות" })).toHaveAttribute("href", "/");
    expect(screen.getByRole("link", { name: "חזרה לשלב ניתוח והתאמה" })).toHaveAttribute("href", "/applications/app-1");
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
