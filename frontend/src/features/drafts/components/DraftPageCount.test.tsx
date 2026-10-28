import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { json } from "@/test/fixtures";
import { DraftPageCount, PAGE_COUNT_SETTLE_MS } from "./DraftPageCount";

const count = (pages: number | null, maximum: number | null, hash: string) => ({
  application_id: "app-1",
  document_id: "doc-1",
  document_hash: hash,
  template: null,
  pages,
  maximum,
});

const renderCount = (documentHash: string) => {
  const client = new QueryClient({ defaultOptions: { queries: { gcTime: 0 } } });
  const view = render(
    <QueryClientProvider client={client}>
      <DraftPageCount applicationId="app-1" documentHash={documentHash} />
    </QueryClientProvider>,
  );
  return {
    ...view,
    rerenderWith: (hash: string) =>
      view.rerender(
        <QueryClientProvider client={client}>
          <DraftPageCount applicationId="app-1" documentHash={hash} />
        </QueryClientProvider>,
      ),
  };
};

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("DraftPageCount", () => {
  it("shows the pages against the limit and warns when over it", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(json(count(2, 1, "h1")))),
    );
    renderCount("h1");

    expect(await screen.findByText("2 עמודים מתוך 1 המותרים, חורג ממגבלת העמודים")).toBeInTheDocument();
    expect(screen.getByTestId("draft-page-count")).toHaveClass("text-cv-warning");
  });

  it("is quiet within the limit and shows nothing when the server could not measure", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(json(count(1, 2, "h1")))),
    );
    const { unmount } = renderCount("h1");
    expect(await screen.findByText("1 עמודים מתוך 2 המותרים")).toBeInTheDocument();
    expect(screen.getByTestId("draft-page-count")).not.toHaveClass("text-cv-warning");
    unmount();

    const unmeasured = vi.fn(() => Promise.resolve(json(count(null, 1, "h2"))));
    vi.stubGlobal("fetch", unmeasured);
    renderCount("h2");
    await waitFor(() => expect(unmeasured).toHaveBeenCalledTimes(1));
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 0));
    });
    expect(screen.queryByTestId("draft-page-count")).not.toBeInTheDocument();
  });

  it("counts a new saved version only once the saves settle", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      void input;
      return Promise.resolve(json(count(fetchMock.mock.calls.length, 1, "h")));
    });
    vi.stubGlobal("fetch", fetchMock);
    const { rerenderWith } = renderCount("h1");
    expect(await screen.findByText("1 עמודים מתוך 1 המותרים")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(String(fetchMock.mock.calls[0]?.[0])).toBe("/api/v1/applications/app-1/document/page-count");

    // Three saves in quick succession: the last count stays, and nothing is measured.
    rerenderWith("h2");
    act(() => void vi.advanceTimersByTime(PAGE_COUNT_SETTLE_MS / 2));
    rerenderWith("h3");
    act(() => void vi.advanceTimersByTime(PAGE_COUNT_SETTLE_MS / 2));
    rerenderWith("h4");
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(screen.getByTestId("draft-page-count")).toHaveClass("opacity-60");

    // Once the last one settles, it alone is counted.
    act(() => void vi.advanceTimersByTime(PAGE_COUNT_SETTLE_MS));
    expect(await screen.findByText("2 עמודים מתוך 1 המותרים, חורג ממגבלת העמודים")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});
