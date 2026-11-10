import { screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ApplicationDetail } from "@/api/contracts";
import { HASH, cvDocument, detail, json, renderRoute } from "@/test/fixtures";
import { ReadyPage } from "./ReadyPage";

afterEach(() => {
  vi.unstubAllGlobals();
  sessionStorage.clear();
});

const readyDetail = (overrides: Partial<ApplicationDetail> = {}): ApplicationDetail =>
  detail({
    preparation_state: "ready",
    approved_at: "2026-08-25T08:00:00Z",
    available_actions: ["edit", "download_pdf"],
    recommended_action: "download_pdf",
    ...overrides,
  });

/* One answer per resource the screen reads. */
const stubReads = (projection: ApplicationDetail) => {
  const fetchMock = vi.fn((input: string | URL | Request) => {
    const url = String(input);
    if (url.endsWith("/document/decision-markdown")) {
      return Promise.resolve(json({ application_id: "app-1", document_id: "doc-1", markdown: "# Decision" }));
    }
    if (url.endsWith("/document/page-count")) {
      return Promise.resolve(json({ pages: 2, limit: 2 }));
    }
    if (url.endsWith("/document")) {
      return Promise.resolve(
        json(cvDocument({ preparation_state: projection.preparation_state, approved_at: projection.approved_at })),
      );
    }
    return Promise.resolve(json(projection));
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
};

const renderReady = () => renderRoute("/applications/app-1/ready", "/applications/:applicationId/ready", <ReadyPage />);

describe("ReadyPage", () => {
  it("offers the Ready document's PDF and the way back to editing it", async () => {
    stubReads(readyDetail());
    renderReady();

    expect(await screen.findByRole("heading", { name: "קורות החיים מוכנים" })).toBeInTheDocument();
    /* The page itself, framed from the document's own preview. */
    expect(await screen.findByTitle("קורות החיים המוכנים")).toHaveAttribute(
      "src",
      `/api/v1/applications/app-1/document/preview?v=${HASH}`,
    );
    /* Once, beside the step's own command. */
    const downloads = await screen.findAllByRole("link", { name: "הורדת PDF" });
    expect(downloads).toHaveLength(1);
    expect(downloads[0]).toHaveAttribute("href", `/api/v1/applications/app-1/document/pdf?v=${HASH}`);
    /* Editing a Ready document is allowed; it is the way back, not a new record. */
    expect(screen.getByRole("link", { name: "עריכת קורות החיים" })).toHaveAttribute(
      "href",
      "/applications/app-1/draft",
    );
    expect(screen.queryByText("פרטים טכניים")).not.toBeInTheDocument();
    expect(screen.queryByText("חתימת המסמך")).not.toBeInTheDocument();
    /* The step ends with the way back to the CV library, opened on this CV. */
    expect(screen.getByRole("link", { name: "סיום" })).toHaveAttribute("href", "/?application=app-1");
  });

  it("sends a document that changed since rendering back to the editor, offering no file", async () => {
    stubReads(readyDetail({ preparation_state: "draft_in_progress", available_actions: ["edit"] }));
    renderReady();

    expect(await screen.findByRole("heading", { name: "קורות החיים אינם מוכנים כרגע" })).toBeInTheDocument();
    expect(screen.getByText("המסמך השתנה מאז שהופק")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "מעבר לעורך הטיוטה" })).toHaveAttribute(
      "href",
      "/applications/app-1/draft",
    );
    expect(screen.queryByRole("link", { name: "הורדת PDF" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "סיום" })).not.toBeInTheDocument();
  });
});
