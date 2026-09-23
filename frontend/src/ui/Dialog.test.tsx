import { act, fireEvent, render, screen } from "@testing-library/react";
import { useRef, useState } from "react";
import { describe, expect, it, vi } from "vitest";

import { Dialog } from "./Dialog";

/* jsdom does not translate an Escape key press on a modal dialog into the element's
   cancel behavior, so the cancel event stands in for the key. What the component owns is
   the decision the event carries - whether the cancel is allowed to proceed - and that is
   what these assertions read. The key itself is covered by the browser suite. */
const escape = (dialog: HTMLElement): Event => {
  const cancel = new Event("cancel", { bubbles: false, cancelable: true });
  fireEvent(dialog, cancel);
  return cancel;
};

const dialogOf = (title: string): HTMLDialogElement =>
  screen.getByRole("heading", { name: title }).closest("dialog") as HTMLDialogElement;

describe("Dialog", () => {
  it("opens with focus on its heading and offers an explicit close", () => {
    render(
      <Dialog description="תיאור קצר" headingId="heading" onClose={vi.fn()} open title="כותרת">
        תוכן
      </Dialog>,
    );

    expect(screen.getByRole("heading", { name: "כותרת" })).toHaveFocus();
    expect(screen.getByRole("button", { name: "סגירה" })).toBeInTheDocument();
    /* The line under the title describes the dialog as a whole. */
    expect(dialogOf("כותרת")).toHaveAccessibleDescription("תיאור קצר");
  });

  it("refuses Escape and hides the close control when cancelling would decide an outcome", () => {
    const onClose = vi.fn();
    render(
      <Dialog dismissible={false} headingId="heading" onClose={onClose} open title="כותרת">
        תוכן
      </Dialog>,
    );

    const cancel = escape(dialogOf("כותרת"));

    expect(cancel.defaultPrevented).toBe(true);
    expect(onClose).not.toHaveBeenCalled();
    expect(screen.queryByRole("button", { name: "סגירה" })).not.toBeInTheDocument();
  });

  it("lets Escape cancel a dialog that decides nothing", () => {
    render(
      <Dialog headingId="heading" onClose={vi.fn()} open title="כותרת">
        תוכן
      </Dialog>,
    );

    expect(escape(dialogOf("כותרת")).defaultPrevented).toBe(false);
  });

  it("closes on a backdrop click while nothing has been typed", () => {
    const onClose = vi.fn();
    render(
      <Dialog headingId="heading" onClose={onClose} open title="כותרת">
        <input aria-label="הערה" />
      </Dialog>,
    );

    fireEvent.click(dialogOf("כותרת"));

    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("keeps typed content when the backdrop is clicked by accident", () => {
    const onClose = vi.fn();
    render(
      <Dialog headingId="heading" onClose={onClose} open title="כותרת">
        <input aria-label="הערה" />
      </Dialog>,
    );

    const field = screen.getByRole("textbox", { name: "הערה" });
    fireEvent.change(field, { target: { value: "טיוטה" } });
    fireEvent.click(dialogOf("כותרת"));

    expect(onClose).not.toHaveBeenCalled();
    expect(field).toHaveValue("טיוטה");

    /* The deliberate route out is still open, and it is the one allowed to discard. */
    fireEvent.click(screen.getByRole("button", { name: "סגירה" }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("does not treat a value the form wrote on open as something the user typed", () => {
    const onClose = vi.fn();
    render(
      <Dialog headingId="heading" onClose={onClose} open title="כותרת">
        <input aria-label="הערה" defaultValue="ערך קיים" />
      </Dialog>,
    );

    fireEvent.click(dialogOf("כותרת"));

    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("returns focus to a named control after Escape and after the close button", () => {
    const Host = () => {
      const [open, setOpen] = useState(true);
      const reopen = useRef<HTMLButtonElement>(null);
      return (
        <>
          <button onClick={() => setOpen(true)} ref={reopen} type="button">
            פתיחה
          </button>
          <Dialog headingId="heading" onClose={() => setOpen(false)} open={open} restoreFocusTo={reopen} title="כותרת">
            תוכן
          </Dialog>
        </>
      );
    };
    render(<Host />);

    const dialog = dialogOf("כותרת");
    /* A browser closes a cancelled modal itself; the shim's close stands in for it. */
    escape(dialog);
    act(() => dialog.close());
    expect(screen.getByRole("button", { name: "פתיחה" })).toHaveFocus();

    fireEvent.click(screen.getByRole("button", { name: "פתיחה" }));
    expect(screen.getByRole("heading", { name: "כותרת" })).toHaveFocus();
    fireEvent.click(screen.getByRole("button", { name: "סגירה" }));
    expect(screen.getByRole("button", { name: "פתיחה" })).toHaveFocus();
  });

  it("keeps the owning dialog open when a dialog inside it closes", () => {
    const onOuterClose = vi.fn();

    const Nested = () => {
      const [innerOpen, setInnerOpen] = useState(true);
      return (
        <Dialog headingId="outer" onClose={onOuterClose} open title="חיצוני">
          <Dialog headingId="inner" onClose={() => setInnerOpen(false)} open={innerOpen} title="פנימי">
            תוכן
          </Dialog>
        </Dialog>
      );
    };
    render(<Nested />);

    const outer = dialogOf("חיצוני");
    const inner = dialogOf("פנימי");
    expect(outer.open).toBe(true);
    expect(inner.open).toBe(true);

    fireEvent.click(screen.getAllByRole("button", { name: "סגירה" })[1] as HTMLElement);

    expect(inner.open).toBe(false);
    expect(outer.open).toBe(true);
    expect(onOuterClose).not.toHaveBeenCalled();
  });
});
