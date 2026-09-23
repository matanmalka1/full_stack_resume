import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { settingsQueryKey } from "@/api/settings";
import { settings } from "@/test/fixtures";
import { AppLayout } from "./AppLayout";
import { useDisplaySettingsPreview } from "./DisplaySettingsPreview";

const PreviewControl = () => {
  const setPreview = useDisplaySettingsPreview();
  return (
    <button
      onClick={() => setPreview({ ui_density: "compact", ui_text_size: "large", ui_theme: "system" })}
      type="button"
    >
      תצוגה מקדימה
    </button>
  );
};

describe("AppLayout display settings", () => {
  it("applies an unsaved display preview to the layout without changing persisted settings", () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    client.setQueryData(settingsQueryKey, { settings: settings(), etag: '"settings-1"' });

    const { container } = render(
      <QueryClientProvider client={client}>
        <MemoryRouter initialEntries={["/"]}>
          <Routes>
            <Route element={<AppLayout />}>
              <Route element={<PreviewControl />} index />
            </Route>
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    );

    const layout = container.firstElementChild;
    expect(layout).toHaveAttribute("data-density", "comfortable");
    expect(layout).toHaveAttribute("data-text-size", "normal");

    fireEvent.click(screen.getByRole("button", { name: "תצוגה מקדימה" }));

    expect(layout).toHaveAttribute("data-density", "compact");
    expect(layout).toHaveAttribute("data-text-size", "large");
    expect(
      client.getQueryData<{ settings: ReturnType<typeof settings> }>(settingsQueryKey)?.settings.ui_text_size,
    ).toBe("normal");
  });
});

afterEach(() => {
  localStorage.clear();
  document.documentElement.removeAttribute("data-theme");
  vi.restoreAllMocks();
});
it("applies the server theme even when local storage is blocked", () => {
  vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
    throw new Error("blocked");
  });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } });
  client.setQueryData(settingsQueryKey, { settings: settings({ ui_theme: "dark" }), etag: '"settings-1"' });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <Routes>
          <Route element={<AppLayout />}>
            <Route index element={<p>content</p>} />
          </Route>
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
  expect(document.documentElement).toHaveAttribute("data-theme", "dark");
});

describe("AppLayout sidebar collapse", () => {
  const stubViewport = (wide: boolean) =>
    vi.stubGlobal("matchMedia", (query: string) => ({
      matches: query === "(min-width: 64rem)" && wide,
      addEventListener: () => undefined,
      removeEventListener: () => undefined,
    }));

  const renderLayout = () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } });
    client.setQueryData(settingsQueryKey, { settings: settings(), etag: '"settings-1"' });
    return render(
      <QueryClientProvider client={client}>
        <MemoryRouter>
          <Routes>
            <Route element={<AppLayout />}>
              <Route index element={<p>content</p>} />
            </Route>
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    );
  };

  afterEach(() => vi.unstubAllGlobals());

  it("folds the wide sidebar to its rail, keeps every destination named, and remembers the choice", () => {
    stubViewport(true);
    const { container, unmount } = renderLayout();
    const layout = container.firstElementChild;

    const collapse = screen.getByRole("button", { name: "כיווץ סרגל הניווט" });
    expect(collapse).toHaveAttribute("aria-expanded", "true");
    expect(collapse).toHaveAttribute("aria-controls", "app-sidebar");
    collapse.focus();
    fireEvent.click(collapse);

    expect(layout).toHaveAttribute("data-sidebar", "collapsed");
    const expand = screen.getByRole("button", { name: "הרחבת סרגל הניווט" });
    expect(expand).toHaveAttribute("aria-expanded", "false");
    // The same element, not a remount: the reader who pressed it keeps focus.
    expect(expand).toBe(collapse);
    expect(expand).toHaveFocus();
    for (const name of ["לוח המועמדויות", "מאגר העובדות", "הגדרות", "קליטת משרה חדשה"]) {
      expect(screen.getByRole("link", { name })).toBeInTheDocument();
    }
    expect(screen.queryByText("קורות חיים")).not.toBeInTheDocument();
    expect(localStorage.getItem("cv-sidebar-collapsed")).toBe("true");

    unmount();
    const remounted = renderLayout();
    expect(remounted.container.firstElementChild).toHaveAttribute("data-sidebar", "collapsed");
  });

  it("keeps the narrow masthead expanded whatever a wide window saved", () => {
    localStorage.setItem("cv-sidebar-collapsed", "true");
    stubViewport(false);
    const { container } = renderLayout();

    expect(container.firstElementChild).toHaveAttribute("data-sidebar", "expanded");
    expect(screen.getByText("קורות חיים")).toBeInTheDocument();
  });

  it("still collapses for the visit when local storage is blocked", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    stubViewport(true);
    const { container } = renderLayout();

    fireEvent.click(screen.getByRole("button", { name: "כיווץ סרגל הניווט" }));

    expect(container.firstElementChild).toHaveAttribute("data-sidebar", "collapsed");
  });
});
