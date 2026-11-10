import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ApplicationListItem, ApplicationListResponse } from "@/api/contracts";
import { json } from "@/test/fixtures";
import { ResumesPage } from "./ResumesPage";

const readyItem = (id: string, company: string): ApplicationListItem =>
  ({
    id,
    company,
    target_role: "Backend Engineer",
    notes: "",
    created_at: "2026-08-24T07:00:00Z",
    updated_at: "2026-08-24T07:00:00Z",
    preparation_state: "ready",
    content_check: "passed",
    review_reasons: [],
    warnings: [],
    job_text_hash: "c".repeat(64),
    document_hash: `${id.at(-1)}`.repeat(64),
    available_actions: ["download_pdf"],
    blocked_actions: [],
    recommended_action: "download_pdf",
  }) as ApplicationListItem;

const listBody = (items: ApplicationListItem[]): ApplicationListResponse => ({
  items,
  matched: items.length,
  total: items.length,
  offset: 0,
  preset_counts: {},
  stage_counts: {},
});

const renderPage = (items: ApplicationListItem[]) => {
  const fetchMock = vi.fn(async (_url: unknown) => json(listBody(items)));
  vi.stubGlobal("fetch", fetchMock);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/resumes"]}>
        <ResumesPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return fetchMock;
};

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("ResumesPage", () => {
  it("asks the server for Ready CVs only and previews the first one", async () => {
    const fetchMock = renderPage([readyItem("app-1", "Acme"), readyItem("app-2", "Binat")]);

    expect(await screen.findByRole("button", { name: /Acme/ })).toBeInTheDocument();
    const requested = new URL(String(fetchMock.mock.calls[0]?.[0]), "http://localhost");
    expect(requested.searchParams.getAll("stage")).toEqual(["ready"]);
    expect(screen.getByTitle("קורות החיים: Acme · Backend Engineer")).toBeInTheDocument();
  });

  it("switches the preview to the chosen CV", async () => {
    renderPage([readyItem("app-1", "Acme"), readyItem("app-2", "Binat")]);

    fireEvent.click(await screen.findByRole("button", { name: /Binat/ }));

    expect(await screen.findByTitle("קורות החיים: Binat · Backend Engineer")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "הורדת PDF" })).toHaveAttribute(
      "href",
      expect.stringContaining("/applications/app-2/document/pdf"),
    );
  });

  it("narrows the list by employer or role and previews the first match", async () => {
    renderPage([readyItem("app-1", "Acme"), readyItem("app-2", "Binat")]);

    const field = await screen.findByRole("searchbox", { name: "חיפוש קורות חיים" });
    fireEvent.change(field, { target: { value: "binat" } });

    expect(screen.queryByRole("button", { name: /Acme/ })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Binat/ })).toBeInTheDocument();
    expect(screen.getByTitle("קורות החיים: Binat · Backend Engineer")).toBeInTheDocument();

    fireEvent.change(field, { target: { value: "nothing" } });
    expect(screen.getByText("לא נמצאו קורות חיים שתואמים לחיפוש.")).toBeInTheDocument();
  });

  it("says so when no CV is Ready yet", async () => {
    renderPage([]);

    expect(await screen.findByText("עדיין אין קורות חיים מוכנים.")).toBeInTheDocument();
  });
});
