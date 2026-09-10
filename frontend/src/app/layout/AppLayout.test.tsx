import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { settingsQueryKey } from "@/api/settings";
import { settings } from "@/test/fixtures";
import { AppLayout } from "./AppLayout";
import { useDisplaySettingsPreview } from "./DisplaySettingsPreview";

const PreviewControl = () => {
  const setPreview = useDisplaySettingsPreview();
  return (
    <button onClick={() => setPreview({ ui_density: "compact", ui_text_size: "large" })} type="button">
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
