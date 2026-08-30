import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

import "@testing-library/jest-dom/vitest";

/* Testing Library only auto-cleans when Vitest globals are on. They are off here, so
   the teardown is explicit rather than absent. */
afterEach(cleanup);

/* jsdom implements <dialog> as an element but not its modal methods, so a component that
   calls `showModal` throws where a browser would open the dialog. The shim is the
   smallest thing that makes the element behave as the DOM specifies for these tests: the
   `open` attribute reflects the state, and closing fires the `close` event that React
   components listen for. It lives here rather than in one test file because every dialog
   in this app is opened the same way. */
if (typeof HTMLDialogElement !== "undefined") {
  const open = (dialog: HTMLDialogElement) => {
    dialog.open = true;
  };

  HTMLDialogElement.prototype.showModal ??= function showModal(this: HTMLDialogElement) {
    open(this);
  };
  HTMLDialogElement.prototype.show ??= function show(this: HTMLDialogElement) {
    open(this);
  };
  HTMLDialogElement.prototype.close ??= function close(this: HTMLDialogElement) {
    this.open = false;
    this.dispatchEvent(new Event("close"));
  };
}
