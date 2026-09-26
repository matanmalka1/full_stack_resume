import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { json, renderRoute } from "@/test/fixtures";

import { GlobalSearch } from "./GlobalSearch";

afterEach(() => {
  vi.unstubAllGlobals();
});

const openPalette = async () => {
  /* A fresh Response per call: a body is readable once, and the deferred search can ask
     more than once. */
  vi.stubGlobal(
    "fetch",
    vi.fn(() => Promise.resolve(json({ items: [], total: 0, limit: 8, offset: 0 }))),
  );
  renderRoute("/", "/", <GlobalSearch />);
  fireEvent.click(screen.getByRole("button", { name: "מעבר מהיר למועמדות" }));
  const field = await screen.findByRole("combobox");
  return { dialog: field.closest("dialog") as HTMLDialogElement, field };
};

describe("GlobalSearch", () => {
  it("opens the palette with focus in its field", async () => {
    const { dialog, field } = await openPalette();

    expect(field).toHaveFocus();
    expect(dialog.open).toBe(true);
  });

  /* Closing a modal dialog by removing it from the document leaves focus on the body.
     The element has to stay and be closed through `close()`, which is what hands focus
     back to whatever opened the palette. The browser suite asserts where focus lands;
     here the point is that the element is still there to hand it back. */
  it("closes the palette through the element rather than by unmounting it", async () => {
    const { dialog } = await openPalette();

    fireEvent.click(dialog);

    await waitFor(() => {
      expect(dialog.open).toBe(false);
    });
    expect(dialog.isConnected).toBe(true);
  });
});
