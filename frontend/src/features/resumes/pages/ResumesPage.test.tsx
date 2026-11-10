import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ApplicationListItem, ApplicationListResponse } from "@/api/contracts";
import { json } from "@/test/fixtures";
import { ResumesPage } from "./ResumesPage";

const readyItem = (id: string, company: string, overrides: Partial<ApplicationListItem> = {}): ApplicationListItem =>
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
    ...overrides,
  }) as ApplicationListItem;

const draftItem = (id: string, company: string, overrides: Partial<ApplicationListItem> = {}): ApplicationListItem =>
  readyItem(id, company, {
    preparation_state: "draft_in_progress",
    document_hash: null,
    available_actions: ["patch_draft"],
    recommended_action: "patch_draft",
    ...overrides,
  });

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
      <MemoryRouter initialEntries={["/"]}>
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
  it("lists CVs in preparation and Ready ones, and previews the newest Ready one", async () => {
    const fetchMock = renderPage([draftItem("app-0", "Draftco"), readyItem("app-1", "Acme"), readyItem("app-2", "Binat")]);

    expect(await screen.findByRole("button", { name: /Acme/ })).toBeInTheDocument();
    const requested = new URL(String(fetchMock.mock.calls[0]?.[0]), "http://localhost");
    expect(requested.searchParams.getAll("stage")).toEqual([]);
    expect(screen.getByRole("region", { name: "בהכנה" })).toHaveTextContent("Draftco");
    expect(screen.getByRole("region", { name: "מוכנים" })).toHaveTextContent("Acme");
    expect(screen.getByTitle("קורות החיים: Acme · Backend Engineer")).toBeInTheDocument();
  });

  it("shows where a CV in preparation stands and the way on to its step", async () => {
    const reason = {
      code: "PENDING_FACT_REQUIRES_RESOLUTION",
      message: "m",
      entity_references: {},
      allowed_resolution_actions: [],
    };
    renderPage([draftItem("app-0", "Draftco", { review_reasons: [reason] }), readyItem("app-1", "Acme")]);

    fireEvent.click(await screen.findByRole("button", { name: /Draftco/ }));

    expect(screen.getByRole("link", { name: "המשך הכנה" })).toHaveAttribute("href", "/applications/app-0/draft");
    expect(screen.getByText("טיוטה בעבודה")).toBeInTheDocument();
    expect(screen.getAllByText("דורש טיפול").length).toBeGreaterThan(0);
    expect(screen.queryByRole("link", { name: "הורדת PDF" })).not.toBeInTheDocument();
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

  it("pages the list by twenty rows and keeps each section's full count", async () => {
    const items = Array.from({ length: 25 }, (_, index) => readyItem(`app-${index}`, `Company ${index}`));
    renderPage(items);

    const firstPage = await screen.findByRole("region", { name: "מוכנים" });
    expect(firstPage).toHaveTextContent("מוכנים (25)");
    expect(within(firstPage).getByText("Company 19")).toBeInTheDocument();
    expect(within(firstPage).queryByText("Company 20")).not.toBeInTheDocument();
    expect(screen.getByText("עמוד 1 מתוך 2")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "הקודם" })).toBeDisabled();

    fireEvent.click(screen.getByRole("button", { name: "הבא" }));

    const secondPage = screen.getByRole("region", { name: "מוכנים" });
    expect(secondPage).toHaveTextContent("מוכנים (25)");
    expect(within(secondPage).getByText("Company 24")).toBeInTheDocument();
    expect(within(secondPage).queryByText("Company 0")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "הבא" })).toBeDisabled();
  });

  it("offers the first job when there is no CV at all", async () => {
    renderPage([]);

    expect(await screen.findByText("עוד אין קורות חיים")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /קליטת משרה ראשונה/ })).toHaveAttribute("href", "/applications/new");
  });
});
