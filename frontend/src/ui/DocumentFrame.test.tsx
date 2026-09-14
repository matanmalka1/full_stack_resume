import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { DocumentFrame } from "./DocumentFrame";

type ResizeCallback = ConstructorParameters<typeof ResizeObserver>[0];
let resizeCallback: ResizeCallback | undefined;

class ResizeObserverMock {
  constructor(callback: ResizeCallback) {
    resizeCallback = callback;
  }
  disconnect = vi.fn();
  observe = vi.fn();
  unobserve = vi.fn();
}

const reportWidth = (width: number) => {
  act(() => resizeCallback?.([{ contentRect: { width } } as ResizeObserverEntry], {} as ResizeObserver));
};

describe("DocumentFrame", () => {
  afterEach(() => {
    resizeCallback = undefined;
    vi.unstubAllGlobals();
  });

  it("fits to the available width and follows later resizes", () => {
    vi.stubGlobal("ResizeObserver", ResizeObserverMock);
    render(<DocumentFrame src="/preview" title="מסמך לבדיקה" />);

    reportWidth(397);
    expect(screen.getByText("50%")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "התאמה לרוחב" })).toHaveAttribute("aria-pressed", "true");

    reportWidth(635.2);
    expect(screen.getByText("80%")).toBeInTheDocument();
  });

  it("offers fixed, incremental, and keyboard-accessible scrolling controls", () => {
    vi.stubGlobal("ResizeObserver", ResizeObserverMock);
    render(<DocumentFrame src="/preview" title="מסמך לבדיקה" />);

    fireEvent.click(screen.getByRole("button", { name: "100%" }));
    fireEvent.click(screen.getByRole("button", { name: "הגדלת המסמך" }));
    expect(screen.getByText("110%")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "התאמה לרוחב" })).toHaveAttribute("aria-pressed", "false");

    const viewport = screen.getByRole("region", { name: "מסמך קורות החיים — ניתן לגלול" });
    expect(viewport).toHaveAttribute("tabindex", "0");
    expect(viewport).toHaveAttribute("dir", "ltr");
    expect(screen.getByTitle("מסמך לבדיקה")).toHaveStyle({ height: "1123px", width: "794px" });
  });
});
