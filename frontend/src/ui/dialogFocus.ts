import type { KeyboardEvent } from "react";

/* showModal makes the background inert, but Tab can still leave the document for
   browser chrome. Wrap at the modal's boundaries and leave interior navigation native. */
export const wrapDialogFocus = (event: KeyboardEvent<HTMLDialogElement>): void => {
  if (event.key !== "Tab" || event.defaultPrevented) {
    return;
  }

  const dialog = event.currentTarget;
  const active = dialog.ownerDocument.activeElement;
  if (!dialog.open || active?.closest("dialog") !== dialog) {
    return;
  }

  const stops = Array.from(dialog.querySelectorAll<HTMLElement>("*"))
    .filter(
      (element) =>
        element.tabIndex >= 0 &&
        !element.matches(":disabled") &&
        element.closest("[inert], dialog") === dialog &&
        element.getClientRects().length > 0 &&
        getComputedStyle(element).visibility === "visible",
    )
    // ES2022 has no toSorted; this array is newly created and belongs only to this call.
    // oxlint-disable-next-line unicorn/no-array-sort
    .sort((left, right) => {
      const leftOrder = left.tabIndex || Number.POSITIVE_INFINITY;
      const rightOrder = right.tabIndex || Number.POSITIVE_INFINITY;
      return leftOrder === rightOrder ? 0 : leftOrder - rightOrder;
    });
  const first = stops[0];
  const last = stops.at(-1);

  if (first === undefined || last === undefined) {
    event.preventDefault();
    return;
  }

  if (event.shiftKey && (active === first || !stops.includes(active as HTMLElement))) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && active === last) {
    event.preventDefault();
    first.focus();
  }
};
